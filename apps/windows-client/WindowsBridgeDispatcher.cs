using System.Text.Json;

namespace HearthGhost.WindowsClient;

internal sealed class WindowsBridgeDispatcher : IAsyncDisposable
{
    private const int MaxMessageCharacters = 32 * 1024;
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false,
        MaxDepth = 16,
    };

    private readonly NodeProtocolClient node;

    internal WindowsBridgeDispatcher(NodeProtocolClient node)
    {
        this.node = node;
    }

    internal async Task<string> DispatchAsync(string webMessageJson, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(webMessageJson) || webMessageJson.Length > MaxMessageCharacters)
        {
            return SerializeFailure("invalid", "windows_bridge_request_invalid");
        }

        string requestId = "invalid";
        try
        {
            using JsonDocument document = JsonDocument.Parse(webMessageJson, new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 8,
            });
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return SerializeFailure(requestId, "windows_bridge_request_invalid");
            }
            HashSet<string> names = root.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
            if (!names.SetEquals(["id", "method", "params"]))
            {
                return SerializeFailure(requestId, "windows_bridge_request_shape_invalid");
            }
            requestId = RequireString(root, "id", 80);
            string method = RequireString(root, "method", 64);
            JsonElement parameters = root.GetProperty("params");
            if (parameters.ValueKind != JsonValueKind.Object)
            {
                return SerializeFailure(requestId, "windows_bridge_params_invalid");
            }

            object? result = method switch
            {
                "node.connect" => await RequireNoParams(parameters, () => node.ConnectAsync(cancellationToken)).ConfigureAwait(false),
                "node.disconnect" => await DisconnectAsync(parameters, cancellationToken).ConfigureAwait(false),
                "conversation.open" => await node.OpenConversationAsync(
                    RequireOnlyStringParam(parameters, "nodeSessionId", 128),
                    cancellationToken).ConfigureAwait(false),
                "conversation.text" => await SendTextAsync(parameters, cancellationToken).ConfigureAwait(false),
                "conversation.close" => await node.CloseConversationAsync(
                    RequireOnlyStringParam(parameters, "conversationSessionId", 128),
                    cancellationToken).ConfigureAwait(false),
                _ => throw new WindowsNodeException("windows_bridge_method_denied"),
            };
            return JsonSerializer.Serialize(new BridgeSuccess(requestId, true, result), JsonOptions);
        }
        catch (WindowsNodeException error)
        {
            return SerializeFailure(requestId, SafeReason(error.Message));
        }
        catch (OperationCanceledException)
        {
            return SerializeFailure(requestId, "windows_bridge_timeout");
        }
        catch
        {
            return SerializeFailure(requestId, "windows_bridge_internal_error");
        }
    }

    private async Task<object> DisconnectAsync(JsonElement parameters, CancellationToken cancellationToken)
    {
        RequireNoProperties(parameters);
        await node.DisconnectAsync(cancellationToken).ConfigureAwait(false);
        return new { disconnected = true };
    }

    private async Task<ConversationBridgeResult> SendTextAsync(
        JsonElement parameters,
        CancellationToken cancellationToken)
    {
        HashSet<string> names = parameters.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
        if (!names.SetEquals(["conversationSessionId", "text"]))
        {
            throw new WindowsNodeException("windows_bridge_params_invalid");
        }
        return await node.SendTextAsync(
            RequireString(parameters, "conversationSessionId", 128),
            RequireString(parameters, "text", 4_000),
            cancellationToken).ConfigureAwait(false);
    }

    private static async Task<T> RequireNoParams<T>(JsonElement parameters, Func<Task<T>> action)
    {
        RequireNoProperties(parameters);
        return await action().ConfigureAwait(false);
    }

    private static string RequireOnlyStringParam(JsonElement parameters, string name, int maxLength)
    {
        HashSet<string> names = parameters.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
        if (!names.SetEquals([name]))
        {
            throw new WindowsNodeException("windows_bridge_params_invalid");
        }
        return RequireString(parameters, name, maxLength);
    }

    private static void RequireNoProperties(JsonElement parameters)
    {
        if (parameters.EnumerateObject().Any())
        {
            throw new WindowsNodeException("windows_bridge_params_invalid");
        }
    }

    private static string RequireString(JsonElement parent, string name, int maxLength)
    {
        if (!parent.TryGetProperty(name, out JsonElement value) || value.ValueKind != JsonValueKind.String)
        {
            throw new WindowsNodeException("windows_bridge_request_invalid");
        }
        string? text = value.GetString();
        if (string.IsNullOrWhiteSpace(text)
            || text.Length > maxLength
            || text != text.Trim()
            || text.Contains('\0'))
        {
            throw new WindowsNodeException("windows_bridge_request_invalid");
        }
        return text;
    }

    private static string SafeReason(string value)
    {
        if (value.Length is < 1 or > 160
            || value.Any(character => !(char.IsAsciiLetterOrDigit(character) || character is '_' or '-' or '.')))
        {
            return "windows_bridge_request_failed";
        }
        return value;
    }

    private static string SerializeFailure(string id, string error)
    {
        return JsonSerializer.Serialize(new BridgeFailure(id, false, error), JsonOptions);
    }

    public ValueTask DisposeAsync() => node.DisposeAsync();

    private sealed record BridgeSuccess(string Id, bool Ok, object? Result);
    private sealed record BridgeFailure(string Id, bool Ok, string Error);
}
