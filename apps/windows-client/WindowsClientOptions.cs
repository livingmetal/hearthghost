using System.Globalization;

namespace HearthGhost.WindowsClient;

internal sealed record WindowsClientOptions(
    Uri WebUiUri,
    string CoreHost,
    int CorePort,
    string NodeId,
    string NodeCertificateThumbprint,
    string AuthorityCertificateThumbprint)
{
    internal const string CredentialReference = "hearthghost.windows.current-user-store";
    internal const string Alpn = "hearthghost-node/1";

    internal static WindowsClientOptions FromEnvironment()
    {
        Uri webUi = ParseLoopbackUri(
            Environment.GetEnvironmentVariable("HEARTHGHOST_WEB_DEV_URL")
                ?? "http://127.0.0.1:5173/windows.html");
        string host = Required("HEARTHGHOST_WINDOWS_CORE_HOST", "192.168.55.100");
        string nodeId = Required("HEARTHGHOST_WINDOWS_NODE_ID", "windows-development-01");
        string nodeThumbprint = NormalizeThumbprint(
            Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CERT_THUMBPRINT"));
        string caThumbprint = NormalizeThumbprint(
            Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CA_THUMBPRINT"));
        int port = ParsePort(Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CORE_PORT") ?? "38443");
        return new WindowsClientOptions(webUi, host, port, nodeId, nodeThumbprint, caThumbprint);
    }

    private static Uri ParseLoopbackUri(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? uri)
            || uri.Scheme != Uri.UriSchemeHttp
            || !uri.IsLoopback
            || uri.UserInfo.Length != 0
            || !string.IsNullOrEmpty(uri.Fragment))
        {
            throw new InvalidOperationException("HEARTHGHOST_WEB_DEV_URL must be a loopback HTTP URL");
        }
        return uri;
    }

    private static int ParsePort(string value)
    {
        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out int port)
            || port is < 1 or > 65535)
        {
            throw new InvalidOperationException("HEARTHGHOST_WINDOWS_CORE_PORT is invalid");
        }
        return port;
    }

    private static string Required(string name, string fallback)
    {
        string value = Environment.GetEnvironmentVariable(name) ?? fallback;
        if (string.IsNullOrWhiteSpace(value) || value.Length > 128 || value != value.Trim())
        {
            throw new InvalidOperationException($"{name} is invalid");
        }
        return value;
    }

    private static string NormalizeThumbprint(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException(
                "Windows Node and CA certificate thumbprints must be configured in the environment");
        }
        string normalized = string.Concat(value.Where(character => !char.IsWhiteSpace(character))).ToUpperInvariant();
        if (normalized.Length != 40 || normalized.Any(character => !Uri.IsHexDigit(character)))
        {
            throw new InvalidOperationException("Windows certificate thumbprint must be a SHA-1 thumbprint");
        }
        return normalized;
    }
}
