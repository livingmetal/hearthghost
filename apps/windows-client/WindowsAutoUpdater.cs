using System.Buffers.Binary;
using System.Diagnostics;
using System.IO;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;

namespace HearthGhost.WindowsClient;

internal static class WindowsAutoUpdater
{
    private const string ApplyArgument = "--apply-update";
    private const string ReleaseFile = ".hearthghost-release";

    internal static async Task<bool> TryStartUpdateAsync(WindowsClientOptions options)
    {
        if (!options.IdentityConfigured || Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_DISABLE_UPDATE") == "1")
        {
            return false;
        }
        try
        {
            string currentRelease = ReadCurrentRelease();
            string updatesRoot = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "HearthGhost",
                "updates");
            string staging = Path.Combine(updatesRoot, "staging");
            if (Directory.Exists(staging))
            {
                Directory.Delete(staging, recursive: true);
            }
            await using UpdateProtocolClient client = new(options);
            UpdateDownloadResult result = await client.DownloadAsync(currentRelease, staging).ConfigureAwait(true);
            RecordStatus(result.ReasonCode);
            if (!result.Downloaded || result.ReleaseId is null)
            {
                return false;
            }
            string updater = Path.Combine(staging, "HearthGhost.WindowsClient.exe");
            if (!File.Exists(updater))
            {
                Directory.Delete(staging, recursive: true);
                return false;
            }
            ProcessStartInfo start = new(updater)
            {
                UseShellExecute = false,
                WorkingDirectory = staging,
            };
            start.ArgumentList.Add(ApplyArgument);
            start.ArgumentList.Add(Environment.ProcessId.ToString(System.Globalization.CultureInfo.InvariantCulture));
            start.ArgumentList.Add(staging);
            start.ArgumentList.Add(Path.TrimEndingDirectorySeparator(AppContext.BaseDirectory));
            start.ArgumentList.Add(result.ReleaseId);
            _ = Process.Start(start) ?? throw new InvalidOperationException("update helper did not start");
            return true;
        }
        catch (Exception error)
        {
            // A failed or unauthorized update is never applied. The last verified
            // installed client remains usable and can retry on the next launch.
            RecordStatus(error is WindowsNodeException ? error.Message : error.GetType().Name);
            return false;
        }
    }

    internal static async Task<bool> HandleHelperModeAsync(string[] arguments)
    {
        if (arguments.Length == 0 || arguments[0] != ApplyArgument)
        {
            return false;
        }
        if (arguments.Length != 5
            || !int.TryParse(arguments[1], out int processId)
            || processId <= 0
            || !IsReleaseId(arguments[4]))
        {
            throw new InvalidOperationException("update helper arguments are invalid");
        }
        string localAppData = Path.GetFullPath(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData));
        string source = Path.GetFullPath(arguments[2]);
        string target = Path.GetFullPath(arguments[3]);
        string expectedSourceRoot = Path.Combine(localAppData, "HearthGhost", "updates") + Path.DirectorySeparatorChar;
        string expectedTarget = Path.Combine(localAppData, "Programs", "HearthGhost");
        if (!source.StartsWith(expectedSourceRoot, StringComparison.OrdinalIgnoreCase)
            || !string.Equals(target, expectedTarget, StringComparison.OrdinalIgnoreCase)
            || File.ReadAllText(Path.Combine(source, ReleaseFile)).Trim() != arguments[4])
        {
            throw new InvalidOperationException("update helper paths are invalid");
        }

        try
        {
            using Process prior = Process.GetProcessById(processId);
            using CancellationTokenSource timeout = new(TimeSpan.FromSeconds(60));
            await prior.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
        }
        catch (ArgumentException)
        {
            // The prior process already exited between launch and lookup.
        }

        string incoming = target + ".incoming";
        string previous = target + ".previous";
        if (Directory.Exists(incoming))
        {
            Directory.Delete(incoming, recursive: true);
        }
        CopyDirectory(source, incoming);
        if (Directory.Exists(previous))
        {
            Directory.Delete(previous, recursive: true);
        }
        Directory.Move(target, previous);
        try
        {
            Directory.Move(incoming, target);
        }
        catch
        {
            Directory.Move(previous, target);
            throw;
        }
        _ = Process.Start(new ProcessStartInfo(Path.Combine(target, "HearthGhost.WindowsClient.exe"))
        {
            UseShellExecute = false,
            WorkingDirectory = target,
        });
        return true;
    }

    private static string ReadCurrentRelease()
    {
        string path = Path.Combine(AppContext.BaseDirectory, ReleaseFile);
        if (!File.Exists(path))
        {
            return "unversioned";
        }
        string value = File.ReadAllText(path).Trim();
        return IsReleaseId(value) ? value : "unversioned";
    }

    private static bool IsReleaseId(string value) =>
        value.Length == 40 && value.All(character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static void RecordStatus(string reasonCode)
    {
        try
        {
            string root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "HearthGhost");
            Directory.CreateDirectory(root);
            string bounded = reasonCode.Length is >= 1 and <= 128
                && reasonCode.All(character => character is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_' or '.')
                ? reasonCode
                : "update_failure_unclassified";
            File.WriteAllText(
                Path.Combine(root, "update-status.txt"),
                $"{DateTimeOffset.UtcNow:O} {bounded}{Environment.NewLine}");
        }
        catch
        {
            // Update diagnostics must never block the installed client.
        }
    }

    private static void CopyDirectory(string source, string destination)
    {
        Directory.CreateDirectory(destination);
        foreach (string directory in Directory.EnumerateDirectories(source, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(Path.Combine(destination, Path.GetRelativePath(source, directory)));
        }
        foreach (string file in Directory.EnumerateFiles(source, "*", SearchOption.AllDirectories))
        {
            string relative = Path.GetRelativePath(source, file);
            string target = Path.GetFullPath(Path.Combine(destination, relative));
            if (!target.StartsWith(Path.GetFullPath(destination) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("update payload path escaped destination");
            }
            File.Copy(file, target, overwrite: false);
        }
    }
}

internal sealed class UpdateProtocolClient : IAsyncDisposable
{
    private const string ContractVersion = "1.0";
    private const int MaxFrameBytes = 16 * 1024;
    private const int MaxFiles = 128;
    private const long MaxFileBytes = 128L * 1024 * 1024;
    private const long MaxBundleBytes = 256L * 1024 * 1024;
    private readonly WindowsClientOptions options;
    private TcpClient? tcp;
    private SslStream? tls;
    private X509Certificate2? nodeCertificate;
    private X509Certificate2? authorityCertificate;
    private string? sessionId;
    private long sequence;

    internal UpdateProtocolClient(WindowsClientOptions options) => this.options = options;

    internal async Task<UpdateDownloadResult> DownloadAsync(string currentRelease, string staging)
    {
        using CancellationTokenSource timeout = new(TimeSpan.FromMinutes(10));
        using (CancellationTokenSource connectTimeout = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token))
        {
            connectTimeout.CancelAfter(TimeSpan.FromSeconds(5));
            await ConnectAsync(connectTimeout.Token).ConfigureAwait(false);
        }
        string capabilityRequestId = Guid.NewGuid().ToString();
        JsonElement capability = await ExchangeAsync(new()
        {
            ["contract_version"] = ContractVersion,
            ["message_type"] = "capability.request",
            ["request_id"] = capabilityRequestId,
            ["session_id"] = sessionId,
            ["sequence"] = sequence++,
            ["capability"] = "client.update",
        }, timeout.Token).ConfigureAwait(false);
        RequireGatewayResult(capability, capabilityRequestId);
        if (RequiredString(capability, "outcome", 16) != "accepted")
        {
            return new(false, null, RequiredString(capability, "reason_code", 128));
        }

        string checkId = Guid.NewGuid().ToString();
        JsonElement manifest = await ExchangeAsync(new()
        {
            ["contract_version"] = ContractVersion,
            ["message_type"] = "client.update.check",
            ["request_id"] = checkId,
            ["node_session_id"] = sessionId,
            ["sequence"] = sequence++,
            ["platform"] = "win-x64",
            ["current_release_id"] = currentRelease,
        }, timeout.Token).ConfigureAwait(false);
        RequireResult(manifest, checkId, sessionId!);
        if (RequiredString(manifest, "outcome", 16) != "accepted" || !RequiredBoolean(manifest, "available"))
        {
            return new(false, null, RequiredString(manifest, "reason_code", 128));
        }
        string releaseId = RequiredHex(manifest, "release_id", 40);
        JsonElement fileArray = RequiredArray(manifest, "files", MaxFiles);
        UpdateFile[] files = fileArray.EnumerateArray().Select(ParseFile).ToArray();
        if (files.Length == 0 || files.Sum(item => item.Size) > MaxBundleBytes)
        {
            throw new WindowsNodeException("update_manifest_invalid");
        }
        string root = Path.GetFullPath(staging);
        Directory.CreateDirectory(root);
        foreach (UpdateFile file in files)
        {
            string destination = Path.GetFullPath(Path.Combine(root, file.Path.Replace('/', Path.DirectorySeparatorChar)));
            if (!destination.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            {
                throw new WindowsNodeException("update_path_invalid");
            }
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            string requestId = Guid.NewGuid().ToString();
            await WriteFrameAsync(new()
            {
                ["contract_version"] = ContractVersion,
                ["message_type"] = "client.update.file",
                ["request_id"] = requestId,
                ["node_session_id"] = sessionId,
                ["sequence"] = sequence++,
                ["release_id"] = releaseId,
                ["path"] = file.Path,
            }, timeout.Token).ConfigureAwait(false);
            JsonElement header = await ReadFrameAsync(timeout.Token).ConfigureAwait(false);
            RequireResult(header, requestId, sessionId!);
            if (RequiredString(header, "outcome", 16) != "accepted"
                || RequiredHex(header, "release_id", 40) != releaseId
                || RequiredString(header, "path", 240) != file.Path
                || RequiredInt64(header, "size", MaxFileBytes) != file.Size
                || RequiredHex(header, "sha256", 64) != file.Sha256)
            {
                throw new WindowsNodeException("update_file_header_invalid");
            }
            await DownloadFileAsync(destination, file, timeout.Token).ConfigureAwait(false);
        }
        return new(true, releaseId, "update_downloaded");
    }

    private async Task ConnectAsync(CancellationToken cancellationToken)
    {
        X509Certificate2 node = FindCertificate(StoreName.My, options.NodeCertificateThumbprint);
        X509Certificate2 authority = FindCertificate(StoreName.CertificateAuthority, options.AuthorityCertificateThumbprint);
        nodeCertificate = node;
        authorityCertificate = authority;
        EnsureNonExportable(node);
        tcp = new TcpClient();
        await tcp.ConnectAsync(options.CoreHost, options.CorePort, cancellationToken).ConfigureAwait(false);
        tls = new SslStream(tcp.GetStream(), false, (_, certificate, _, errors) => ValidateServer(certificate, errors, authority));
        await tls.AuthenticateAsClientAsync(new SslClientAuthenticationOptions
        {
            TargetHost = options.CoreHost,
            ClientCertificates = new X509CertificateCollection { node },
            EnabledSslProtocols = SslProtocols.Tls13,
            ApplicationProtocols = [new SslApplicationProtocol(WindowsClientOptions.Alpn)],
            CertificateRevocationCheckMode = X509RevocationMode.NoCheck,
            AllowRenegotiation = false,
        }, cancellationToken).ConfigureAwait(false);
        if (!tls.IsEncrypted
            || !tls.IsSigned
            || !tls.IsMutuallyAuthenticated
            || tls.SslProtocol != SslProtocols.Tls13
            || tls.NegotiatedApplicationProtocol != new SslApplicationProtocol(WindowsClientOptions.Alpn))
        {
            throw new WindowsNodeException("update_tls_profile_invalid");
        }
        string requestId = Guid.NewGuid().ToString();
        JsonElement opened = await ExchangeAsync(new()
        {
            ["contract_version"] = ContractVersion,
            ["message_type"] = "session.open",
            ["request_id"] = requestId,
            ["node_id"] = options.NodeId,
        }, cancellationToken).ConfigureAwait(false);
        RequireGatewayResult(opened, requestId);
        if (RequiredString(opened, "outcome", 16) != "accepted")
        {
            throw new WindowsNodeException("update_session_denied");
        }
        sessionId = RequiredString(opened, "session_id", 128);
        sequence = 1;
    }

    private async Task<JsonElement> ExchangeAsync(Dictionary<string, object?> request, CancellationToken cancellationToken)
    {
        await WriteFrameAsync(request, cancellationToken).ConfigureAwait(false);
        return await ReadFrameAsync(cancellationToken).ConfigureAwait(false);
    }

    private async Task WriteFrameAsync(Dictionary<string, object?> request, CancellationToken cancellationToken)
    {
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(request);
        if (payload.Length is < 2 or > MaxFrameBytes || tls is null)
        {
            throw new WindowsNodeException("update_outbound_frame_invalid");
        }
        byte[] header = new byte[4];
        BinaryPrimitives.WriteInt32BigEndian(header, payload.Length);
        try
        {
            await tls.WriteAsync(header, cancellationToken).ConfigureAwait(false);
            await tls.WriteAsync(payload, cancellationToken).ConfigureAwait(false);
            await tls.FlushAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (IOException)
        {
            throw new WindowsNodeException("update_frame_write_io");
        }
    }

    private async Task<JsonElement> ReadFrameAsync(CancellationToken cancellationToken)
    {
        if (tls is null)
        {
            throw new WindowsNodeException("update_transport_missing");
        }
        byte[] header = new byte[4];
        try
        {
            await tls.ReadExactlyAsync(header, cancellationToken).ConfigureAwait(false);
        }
        catch (IOException)
        {
            throw new WindowsNodeException("update_frame_read_io");
        }
        int length = BinaryPrimitives.ReadInt32BigEndian(header);
        if (length is < 2 or > MaxFrameBytes)
        {
            throw new WindowsNodeException("update_inbound_frame_invalid");
        }
        byte[] payload = new byte[length];
        try
        {
            await tls.ReadExactlyAsync(payload, cancellationToken).ConfigureAwait(false);
        }
        catch (IOException)
        {
            throw new WindowsNodeException("update_frame_read_io");
        }
        using JsonDocument document = JsonDocument.Parse(payload, new JsonDocumentOptions { MaxDepth = 16 });
        return document.RootElement.Clone();
    }

    private async Task DownloadFileAsync(string destination, UpdateFile file, CancellationToken cancellationToken)
    {
        string temporary = destination + ".partial";
        string phase = "open";
        try
        {
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            await using FileStream output = new(temporary, FileMode.Create, FileAccess.Write, FileShare.None, 1024 * 1024, true);
            byte[] buffer = new byte[1024 * 1024];
            long remaining = file.Size;
            while (remaining > 0)
            {
                phase = "read";
                int read = await tls!.ReadAsync(buffer.AsMemory(0, (int)Math.Min(buffer.Length, remaining)), cancellationToken).ConfigureAwait(false);
                if (read == 0)
                {
                    throw new WindowsNodeException("update_file_truncated");
                }
                phase = "write";
                await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken).ConfigureAwait(false);
                hash.AppendData(buffer, 0, read);
                remaining -= read;
            }
            phase = "flush";
            await output.FlushAsync(cancellationToken).ConfigureAwait(false);
            await output.DisposeAsync().ConfigureAwait(false);
            if (Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant() != file.Sha256)
            {
                throw new WindowsNodeException("update_file_hash_mismatch");
            }
            phase = "move";
            File.Move(temporary, destination, true);
        }
        catch (IOException error)
        {
            File.Delete(temporary);
            int nativeError = error.HResult & 0xffff;
            throw new WindowsNodeException($"update_file_{phase}_io_{nativeError}");
        }
        catch
        {
            File.Delete(temporary);
            throw;
        }
    }

    private static UpdateFile ParseFile(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Object
            || value.EnumerateObject().Select(property => property.Name).OrderBy(name => name, StringComparer.Ordinal).ToArray()
                is not ["path", "sha256", "size"])
        {
            throw new WindowsNodeException("update_manifest_file_invalid");
        }
        string path = RequiredString(value, "path", 240);
        if (Path.IsPathRooted(path) || path.Contains('\\') || path.Split('/').Any(part => part is "" or "." or ".."))
        {
            throw new WindowsNodeException("update_path_invalid");
        }
        return new(path, RequiredInt64(value, "size", MaxFileBytes), RequiredHex(value, "sha256", 64));
    }

    private static X509Certificate2 FindCertificate(StoreName name, string thumbprint)
    {
        using X509Store store = new(name, StoreLocation.CurrentUser);
        store.Open(OpenFlags.ReadOnly | OpenFlags.OpenExistingOnly);
        X509Certificate2Collection matches = store.Certificates.Find(X509FindType.FindByThumbprint, thumbprint, false);
        if (matches.Count != 1)
        {
            throw new WindowsNodeException("certificate_store_identity_ambiguous_or_missing");
        }
        return new X509Certificate2(matches[0]);
    }

    private static void EnsureNonExportable(X509Certificate2 certificate)
    {
        CngKey? key = (certificate.GetRSAPrivateKey() as RSACng)?.Key
            ?? (certificate.GetECDsaPrivateKey() as ECDsaCng)?.Key;
        CngExportPolicies forbidden = CngExportPolicies.AllowExport | CngExportPolicies.AllowPlaintextExport
            | CngExportPolicies.AllowArchiving | CngExportPolicies.AllowPlaintextArchiving;
        if (key is null || (key.ExportPolicy & forbidden) != 0)
        {
            throw new WindowsNodeException("node_private_key_not_nonexportable");
        }
        key.Dispose();
    }

    private static bool ValidateServer(X509Certificate? certificate, SslPolicyErrors errors, X509Certificate2 authority)
    {
        if (certificate is null || (errors & (SslPolicyErrors.RemoteCertificateNameMismatch | SslPolicyErrors.RemoteCertificateNotAvailable)) != 0)
        {
            return false;
        }
        using X509Certificate2 leaf = new(certificate);
        using X509Chain chain = new();
        chain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
        chain.ChainPolicy.CustomTrustStore.Add(authority);
        chain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
        return chain.Build(leaf) && chain.ChainElements.Count >= 2
            && string.Equals(chain.ChainElements[^1].Certificate.Thumbprint, authority.Thumbprint, StringComparison.OrdinalIgnoreCase);
    }

    private static void RequireResult(JsonElement value, string requestId, string expectedSessionId)
    {
        if (RequiredString(value, "contract_version", 16) != ContractVersion
            || RequiredString(value, "message_type", 64) != "client.update.result"
            || RequiredString(value, "request_id", 64) != requestId
            || RequiredString(value, "node_session_id", 128) != expectedSessionId)
        {
            throw new WindowsNodeException("update_result_identity_invalid");
        }
        _ = RequiredString(value, "outcome", 16);
        _ = RequiredString(value, "reason_code", 128);
    }

    private static void RequireGatewayResult(JsonElement value, string requestId)
    {
        if (RequiredString(value, "contract_version", 16) != ContractVersion
            || RequiredString(value, "message_type", 64) != "node.result"
            || RequiredString(value, "request_id", 64) != requestId)
        {
            throw new WindowsNodeException("update_gateway_result_identity_invalid");
        }
        _ = RequiredString(value, "outcome", 16);
        _ = RequiredString(value, "reason_code", 128);
    }

    private static string RequiredString(JsonElement parent, string name, int max)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.String)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        string text = value.GetString() ?? "";
        if (text.Length is < 1 || text.Length > max || text != text.Trim() || text.Contains('\0'))
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return text;
    }

    private static string RequiredHex(JsonElement parent, string name, int length)
    {
        string value = RequiredString(parent, name, length);
        if (value.Length != length || value.Any(character => character is < '0' or > '9' and < 'a' or > 'f'))
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return value;
    }

    private static long RequiredInt64(JsonElement parent, string name, long maximum)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || !value.TryGetInt64(out long result) || result < 0 || result > maximum)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return result;
    }

    private static bool RequiredBoolean(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return value.GetBoolean();
    }

    private static JsonElement RequiredArray(JsonElement parent, string name, int maximum)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.Array || value.GetArrayLength() > maximum)
        {
            throw new WindowsNodeException($"{name}_invalid");
        }
        return value;
    }

    public ValueTask DisposeAsync()
    {
        tls?.Dispose();
        tcp?.Dispose();
        nodeCertificate?.Dispose();
        authorityCertificate?.Dispose();
        return ValueTask.CompletedTask;
    }

    private sealed record UpdateFile(string Path, long Size, string Sha256);
}

internal sealed record UpdateDownloadResult(bool Downloaded, string? ReleaseId, string ReasonCode);
