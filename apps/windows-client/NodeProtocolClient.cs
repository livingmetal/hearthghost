using System.Buffers.Binary;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;

namespace HearthGhost.WindowsClient;

internal sealed class NodeProtocolClient : IAsyncDisposable
{
    private const string ContractVersion = "1.0";
    private const int MaxFrameBytes = 16 * 1024;
    private const int MaxTextLength = 4_000;
    private const int MaxResponseTextLength = 8_000;
    private static readonly TimeSpan ConnectTimeout = TimeSpan.FromSeconds(5);
    private static readonly TimeSpan ExchangeTimeout = TimeSpan.FromSeconds(20);

    private readonly WindowsClientOptions options;
    private readonly SemaphoreSlim gate = new(1, 1);
    private TcpClient? tcpClient;
    private SslStream? sslStream;
    private string? nodeSessionId;
    private string? conversationSessionId;
    private long nextSequence;

    internal NodeProtocolClient(WindowsClientOptions options)
    {
        this.options = options;
    }

    internal async Task<NodeConnectResult> ConnectAsync(CancellationToken cancellationToken = default)
    {
        await gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await DisconnectNoLockAsync().ConfigureAwait(false);
            X509Certificate2 nodeCertificate = LoadNodeCertificate();
            X509Certificate2 authorityCertificate = LoadAuthorityCertificate();
            EnsurePrivateKeyIsNonExportable(nodeCertificate);

            TcpClient candidateTcp = new();
            using CancellationTokenSource connectCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            connectCts.CancelAfter(ConnectTimeout);
            try
            {
                await candidateTcp.ConnectAsync(options.CoreHost, options.CorePort, connectCts.Token).ConfigureAwait(false);
                SslStream candidateTls = new(
                    candidateTcp.GetStream(),
                    leaveInnerStreamOpen: false,
                    (_, certificate, _, errors) => ValidateServerCertificate(certificate, errors, authorityCertificate));

                SslClientAuthenticationOptions authentication = new()
                {
                    TargetHost = options.CoreHost,
                    ClientCertificates = new X509CertificateCollection { nodeCertificate },
                    EnabledSslProtocols = SslProtocols.Tls13,
                    ApplicationProtocols = [new SslApplicationProtocol(WindowsClientOptions.Alpn)],
                    CertificateRevocationCheckMode = X509RevocationMode.NoCheck,
                    AllowRenegotiation = false,
                };
                await candidateTls.AuthenticateAsClientAsync(authentication, connectCts.Token).ConfigureAwait(false);
                if (!candidateTls.IsEncrypted
                    || !candidateTls.IsSigned
                    || !candidateTls.IsMutuallyAuthenticated
                    || candidateTls.SslProtocol != SslProtocols.Tls13
                    || candidateTls.NegotiatedApplicationProtocol != new SslApplicationProtocol(WindowsClientOptions.Alpn))
                {
                    candidateTls.Dispose();
                    candidateTcp.Dispose();
                    throw new WindowsNodeException("tls_profile_not_negotiated");
                }

                tcpClient = candidateTcp;
                sslStream = candidateTls;
                NodeWireResult opened = await GatewayExchangeNoLockAsync(
                    new Dictionary<string, object?>
                    {
                        ["contract_version"] = ContractVersion,
                        ["message_type"] = "session.open",
                        ["request_id"] = Guid.NewGuid().ToString(),
                        ["node_id"] = options.NodeId,
                    },
                    cancellationToken).ConfigureAwait(false);
                if (!opened.Accepted || opened.SessionId is null)
                {
                    throw new WindowsNodeException(opened.ReasonCode);
                }
                nodeSessionId = opened.SessionId;
                nextSequence = 1;

                NodeWireResult capability = await GatewayExchangeNoLockAsync(
                    new Dictionary<string, object?>
                    {
                        ["contract_version"] = ContractVersion,
                        ["message_type"] = "capability.request",
                        ["request_id"] = Guid.NewGuid().ToString(),
                        ["session_id"] = nodeSessionId,
                        ["sequence"] = ConsumeSequence(),
                        ["capability"] = "conversation.text",
                    },
                    cancellationToken).ConfigureAwait(false);

                string trust;
                string[] grants;
                if (capability.Accepted)
                {
                    trust = "trusted";
                    grants = ["conversation.text"];
                }
                else if (capability.ReasonCode == "node_not_trusted")
                {
                    trust = "untrusted";
                    grants = [];
                }
                else if (capability.ReasonCode is "capability_not_granted" or "capability_not_advertised")
                {
                    trust = "trusted";
                    grants = [];
                }
                else
                {
                    throw new WindowsNodeException(capability.ReasonCode);
                }
                return new NodeConnectResult(true, options.NodeId, nodeSessionId, trust, grants);
            }
            catch
            {
                candidateTcp.Dispose();
                await DisconnectNoLockAsync().ConfigureAwait(false);
                throw;
            }
        }
        finally
        {
            gate.Release();
        }
    }

    internal async Task<ConversationBridgeResult> OpenConversationAsync(
        string requestedNodeSessionId,
        CancellationToken cancellationToken = default)
    {
        await gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            RequireConnected();
            if (!string.Equals(nodeSessionId, requestedNodeSessionId, StringComparison.Ordinal))
            {
                throw new WindowsNodeException("node_session_mismatch");
            }
            JsonElement result = await ConversationExchangeNoLockAsync(
                new Dictionary<string, object?>
                {
                    ["contract_version"] = ContractVersion,
                    ["message_type"] = "conversation.open",
                    ["request_id"] = Guid.NewGuid().ToString(),
                    ["node_session_id"] = nodeSessionId,
                    ["sequence"] = ConsumeSequence(),
                },
                cancellationToken).ConfigureAwait(false);
            conversationSessionId = RequiredString(result, "conversation_session_id", 128);
            return ParseConversationResult(result, requireResponseText: false);
        }
        finally
        {
            gate.Release();
        }
    }

    internal async Task<ConversationBridgeResult> SendTextAsync(
        string requestedConversationSessionId,
        string text,
        CancellationToken cancellationToken = default)
    {
        await gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            RequireConversation(requestedConversationSessionId);
            string normalized = text.Trim();
            if (normalized.Length is < 1 or > MaxTextLength || normalized.Contains('\0'))
            {
                throw new WindowsNodeException("text_input_invalid");
            }
            JsonElement result = await ConversationExchangeNoLockAsync(
                new Dictionary<string, object?>
                {
                    ["contract_version"] = ContractVersion,
                    ["message_type"] = "conversation.text",
                    ["request_id"] = Guid.NewGuid().ToString(),
                    ["node_session_id"] = nodeSessionId,
                    ["sequence"] = ConsumeSequence(),
                    ["conversation_session_id"] = conversationSessionId,
                    ["text"] = normalized,
                },
                cancellationToken).ConfigureAwait(false);
            return ParseConversationResult(result, requireResponseText: true);
        }
        finally
        {
            gate.Release();
        }
    }

    internal async Task<ConversationBridgeResult> CloseConversationAsync(
        string requestedConversationSessionId,
        CancellationToken cancellationToken = default)
    {
        await gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            RequireConversation(requestedConversationSessionId);
            JsonElement result = await ConversationExchangeNoLockAsync(
                new Dictionary<string, object?>
                {
                    ["contract_version"] = ContractVersion,
                    ["message_type"] = "conversation.close",
                    ["request_id"] = Guid.NewGuid().ToString(),
                    ["node_session_id"] = nodeSessionId,
                    ["sequence"] = ConsumeSequence(),
                    ["conversation_session_id"] = conversationSessionId,
                },
                cancellationToken).ConfigureAwait(false);
            ConversationBridgeResult parsed = ParseConversationResult(result, requireResponseText: false);
            conversationSessionId = null;
            return parsed;
        }
        finally
        {
            gate.Release();
        }
    }

    internal async Task DisconnectAsync(CancellationToken cancellationToken = default)
    {
        await gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await DisconnectNoLockAsync().ConfigureAwait(false);
        }
        finally
        {
            gate.Release();
        }
    }

    private async Task DisconnectNoLockAsync()
    {
        if (sslStream is not null && nodeSessionId is not null)
        {
            try
            {
                using CancellationTokenSource cts = new(ExchangeTimeout);
                await GatewayExchangeNoLockAsync(
                    new Dictionary<string, object?>
                    {
                        ["contract_version"] = ContractVersion,
                        ["message_type"] = "session.close",
                        ["request_id"] = Guid.NewGuid().ToString(),
                        ["session_id"] = nodeSessionId,
                    },
                    cts.Token).ConfigureAwait(false);
            }
            catch
            {
                // Transport close is authoritative. No retry or downgrade.
            }
        }
        sslStream?.Dispose();
        tcpClient?.Dispose();
        sslStream = null;
        tcpClient = null;
        nodeSessionId = null;
        conversationSessionId = null;
        nextSequence = 0;
    }

    private async Task<NodeWireResult> GatewayExchangeNoLockAsync(
        Dictionary<string, object?> request,
        CancellationToken cancellationToken)
    {
        string requestId = (string)request["request_id"]!;
        JsonElement result = await ExchangeNoLockAsync(request, cancellationToken).ConfigureAwait(false);
        RequireCommonResult(result, requestId, "node.result");
        return new NodeWireResult(
            RequiredString(result, "outcome", 16) == "accepted",
            RequiredString(result, "reason_code", 128),
            OptionalString(result, "session_id", 128));
    }

    private async Task<JsonElement> ConversationExchangeNoLockAsync(
        Dictionary<string, object?> request,
        CancellationToken cancellationToken)
    {
        string requestId = (string)request["request_id"]!;
        JsonElement result = await ExchangeNoLockAsync(request, cancellationToken).ConfigureAwait(false);
        RequireCommonResult(result, requestId, "conversation.result");
        if (RequiredString(result, "outcome", 16) != "accepted")
        {
            throw new WindowsNodeException(RequiredString(result, "reason_code", 128));
        }
        return result;
    }

    private async Task<JsonElement> ExchangeNoLockAsync(
        Dictionary<string, object?> request,
        CancellationToken cancellationToken)
    {
        RequireConnectedStream();
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(request);
        if (payload.Length is < 2 or > MaxFrameBytes)
        {
            throw new WindowsNodeException("outbound_frame_invalid");
        }
        byte[] header = new byte[4];
        BinaryPrimitives.WriteInt32BigEndian(header, payload.Length);
        using CancellationTokenSource cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cts.CancelAfter(ExchangeTimeout);
        await sslStream!.WriteAsync(header, cts.Token).ConfigureAwait(false);
        await sslStream.WriteAsync(payload, cts.Token).ConfigureAwait(false);
        await sslStream.FlushAsync(cts.Token).ConfigureAwait(false);
        await sslStream.ReadExactlyAsync(header, cts.Token).ConfigureAwait(false);
        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        if (length is < 2 or > MaxFrameBytes)
        {
            throw new WindowsNodeException("inbound_frame_invalid");
        }
        byte[] response = new byte[length];
        await sslStream.ReadExactlyAsync(response, cts.Token).ConfigureAwait(false);
        using JsonDocument document = JsonDocument.Parse(response, new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 16,
        });
        if (document.RootElement.ValueKind != JsonValueKind.Object)
        {
            throw new WindowsNodeException("protocol_result_invalid");
        }
        return document.RootElement.Clone();
    }

    private ConversationBridgeResult ParseConversationResult(JsonElement result, bool requireResponseText)
    {
        string returnedNodeSession = RequiredString(result, "node_session_id", 128);
        if (!string.Equals(returnedNodeSession, nodeSessionId, StringComparison.Ordinal))
        {
            throw new WindowsNodeException("conversation_node_session_mismatch");
        }
        string returnedConversation = RequiredString(result, "conversation_session_id", 128);
        if (conversationSessionId is not null
            && !string.Equals(returnedConversation, conversationSessionId, StringComparison.Ordinal))
        {
            throw new WindowsNodeException("conversation_session_mismatch");
        }
        JsonElement profile = RequiredObject(result, "character_profile");
        if (profile.EnumerateObject().Select(property => property.Name).ToArray() is not ["name"])
        {
            throw new WindowsNodeException("character_profile_invalid");
        }
        _ = RequiredString(profile, "name", 80);
        JsonElement events = RequiredArray(result, "events", 8);
        string? responseText = requireResponseText
            ? RequiredString(result, "response_text", MaxResponseTextLength)
            : OptionalString(result, "response_text", MaxResponseTextLength);
        return new ConversationBridgeResult(
            returnedNodeSession,
            returnedConversation,
            responseText,
            profile.Clone(),
            events.EnumerateArray().Select(item => item.Clone()).ToArray());
    }

    private X509Certificate2 LoadNodeCertificate()
    {
        X509Certificate2 certificate = FindCertificate(StoreName.My, options.NodeCertificateThumbprint);
        if (!certificate.HasPrivateKey)
        {
            certificate.Dispose();
            throw new WindowsNodeException("node_certificate_private_key_missing");
        }
        return certificate;
    }

    private X509Certificate2 LoadAuthorityCertificate()
    {
        return FindCertificate(StoreName.Root, options.AuthorityCertificateThumbprint);
    }

    private static X509Certificate2 FindCertificate(StoreName storeName, string thumbprint)
    {
        using X509Store store = new(storeName, StoreLocation.CurrentUser);
        store.Open(OpenFlags.ReadOnly | OpenFlags.OpenExistingOnly);
        X509Certificate2Collection matches = store.Certificates.Find(
            X509FindType.FindByThumbprint,
            thumbprint,
            validOnly: false);
        if (matches.Count != 1)
        {
            throw new WindowsNodeException("certificate_store_identity_ambiguous_or_missing");
        }
        return new X509Certificate2(matches[0]);
    }

    private static void EnsurePrivateKeyIsNonExportable(X509Certificate2 certificate)
    {
        using RSA? rsa = certificate.GetRSAPrivateKey();
        if (rsa is RSACng rsaCng)
        {
            EnsureCngKeyNonExportable(rsaCng.Key);
            return;
        }
        using ECDsa? ecdsa = certificate.GetECDsaPrivateKey();
        if (ecdsa is ECDsaCng ecdsaCng)
        {
            EnsureCngKeyNonExportable(ecdsaCng.Key);
            return;
        }
        throw new WindowsNodeException("node_private_key_provider_not_nonexportable_cng");
    }

    private static void EnsureCngKeyNonExportable(CngKey key)
    {
        CngExportPolicies forbidden = CngExportPolicies.AllowExport
            | CngExportPolicies.AllowPlaintextExport
            | CngExportPolicies.AllowArchiving
            | CngExportPolicies.AllowPlaintextArchiving;
        if ((key.ExportPolicy & forbidden) != 0)
        {
            throw new WindowsNodeException("node_private_key_exportable");
        }
    }

    private static bool ValidateServerCertificate(
        X509Certificate? certificate,
        SslPolicyErrors errors,
        X509Certificate2 authority)
    {
        if (certificate is null
            || (errors & (SslPolicyErrors.RemoteCertificateNameMismatch | SslPolicyErrors.RemoteCertificateNotAvailable)) != 0)
        {
            return false;
        }
        using X509Certificate2 leaf = new(certificate);
        using X509Chain chain = new();
        chain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
        chain.ChainPolicy.CustomTrustStore.Add(authority);
        chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
        chain.ChainPolicy.VerificationFlags = X509VerificationFlags.NoFlag;
        return chain.Build(leaf)
            && chain.ChainElements.Count >= 2
            && string.Equals(
                chain.ChainElements[^1].Certificate.Thumbprint,
                authority.Thumbprint,
                StringComparison.OrdinalIgnoreCase);
    }

    private static void RequireCommonResult(JsonElement result, string requestId, string messageType)
    {
        if (RequiredString(result, "contract_version", 16) != ContractVersion
            || RequiredString(result, "message_type", 64) != messageType
            || RequiredString(result, "request_id", 64) != requestId)
        {
            throw new WindowsNodeException("protocol_result_identity_mismatch");
        }
        string outcome = RequiredString(result, "outcome", 16);
        if (outcome is not ("accepted" or "denied"))
        {
            throw new WindowsNodeException("protocol_result_outcome_invalid");
        }
        _ = RequiredString(result, "reason_code", 128);
    }

    private void RequireConnected()
    {
        RequireConnectedStream();
        if (nodeSessionId is null)
        {
            throw new WindowsNodeException("node_session_missing");
        }
    }

    private void RequireConversation(string requestedConversationSessionId)
    {
        RequireConnected();
        if (conversationSessionId is null
            || !string.Equals(conversationSessionId, requestedConversationSessionId, StringComparison.Ordinal))
        {
            throw new WindowsNodeException("conversation_session_mismatch");
        }
    }

    private void RequireConnectedStream()
    {
        if (sslStream is null || tcpClient is null || !tcpClient.Connected)
        {
            throw new WindowsNodeException("node_transport_disconnected");
        }
    }

    private long ConsumeSequence()
    {
        if (nextSequence is < 1 or >= int.MaxValue)
        {
            throw new WindowsNodeException("node_sequence_exhausted");
        }
        return nextSequence++;
    }

    private static JsonElement RequiredObject(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.Object)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return value;
    }

    private static JsonElement RequiredArray(JsonElement parent, string name, int maxItems)
    {
        if (!parent.TryGetProperty(name, out JsonElement value)
            || value.ValueKind != JsonValueKind.Array
            || value.GetArrayLength() > maxItems)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return value;
    }

    private static string RequiredString(JsonElement parent, string name, int maxLength)
    {
        string? value = OptionalString(parent, name, maxLength);
        if (value is null)
        {
            throw new WindowsNodeException($"{name}_missing");
        }
        return value;
    }

    private static string? OptionalString(JsonElement parent, string name, int maxLength)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }
        if (value.ValueKind != JsonValueKind.String)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        string? text = value.GetString();
        if (string.IsNullOrWhiteSpace(text)
            || text.Length > maxLength
            || text != text.Trim()
            || text.Contains('\0'))
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return text;
    }

    public async ValueTask DisposeAsync()
    {
        await DisconnectAsync().ConfigureAwait(false);
        gate.Dispose();
    }

    private sealed record NodeWireResult(bool Accepted, string ReasonCode, string? SessionId);
}

internal sealed record NodeConnectResult(
    bool Authenticated,
    string NodeId,
    string TechnicalSessionId,
    string Trust,
    string[] GrantedCapabilities);

internal sealed record ConversationBridgeResult(
    string NodeSessionId,
    string ConversationSessionId,
    string? ResponseText,
    JsonElement CharacterProfile,
    JsonElement[] Events);

internal sealed class WindowsNodeException : Exception
{
    internal WindowsNodeException(string reasonCode)
        : base(reasonCode)
    {
    }
}
