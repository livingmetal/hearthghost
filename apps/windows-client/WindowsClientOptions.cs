using System.Globalization;
using System.IO;

namespace HearthGhost.WindowsClient;

internal sealed record WindowsClientOptions(
    Uri WebUiUri,
    string? BundledWebRoot,
    string CoreHost,
    int CorePort,
    string NodeId,
    string NodeCertificateThumbprint,
    string AuthorityCertificateThumbprint)
{
    internal const string CredentialReference = "hearthghost.windows.current-user-store";
    internal const string Alpn = "hearthghost-node/1";
    internal const string BundledWebHost = "hearthghost.local";
    private const string UnprovisionedThumbprint = "0000000000000000000000000000000000000000";

    internal static WindowsClientOptions FromEnvironment()
    {
        string? developmentUrl = Environment.GetEnvironmentVariable("HEARTHGHOST_WEB_DEV_URL");
        string? bundledWebRoot = null;
        Uri webUi;
        if (string.IsNullOrWhiteSpace(developmentUrl))
        {
            bundledWebRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "web"));
            if (!File.Exists(Path.Combine(bundledWebRoot, "windows.html")))
            {
                throw new InvalidOperationException("bundled Windows web client is missing");
            }
            webUi = new Uri($"https://{BundledWebHost}/windows.html");
        }
        else
        {
            webUi = ParseLoopbackUri(developmentUrl);
        }
        string host = Required("HEARTHGHOST_WINDOWS_CORE_HOST", "192.168.55.100");
        string nodeId = Required("HEARTHGHOST_WINDOWS_NODE_ID", "windows-development-01");
        string nodeThumbprint = NormalizeOptionalThumbprint(
            Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CERT_THUMBPRINT"));
        string caThumbprint = NormalizeOptionalThumbprint(
            Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CA_THUMBPRINT"));
        int port = ParsePort(Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_CORE_PORT") ?? "38443");
        return new WindowsClientOptions(webUi, bundledWebRoot, host, port, nodeId, nodeThumbprint, caThumbprint);
    }

    internal bool IdentityConfigured =>
        NodeCertificateThumbprint != UnprovisionedThumbprint
        && AuthorityCertificateThumbprint != UnprovisionedThumbprint;

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

    private static string NormalizeOptionalThumbprint(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return UnprovisionedThumbprint;
        }
        string normalized = string.Concat(value.Where(character => !char.IsWhiteSpace(character))).ToUpperInvariant();
        if (normalized.Length != 40 || normalized.Any(character => !Uri.IsHexDigit(character)))
        {
            throw new InvalidOperationException("Windows certificate thumbprint must be a SHA-1 thumbprint");
        }
        return normalized;
    }
}
