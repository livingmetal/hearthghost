using Microsoft.Web.WebView2.Core;
using System.Windows;

namespace HearthGhost.WindowsClient;

public partial class MainWindow : Window
{
    private readonly WindowsClientOptions options;
    private readonly WindowsBridgeDispatcher bridge;

    public MainWindow()
    {
        InitializeComponent();
        options = WindowsClientOptions.FromEnvironment();
        bridge = new WindowsBridgeDispatcher(new NodeProtocolClient(options));
        Loaded += OnLoaded;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await Browser.EnsureCoreWebView2Async();
            CoreWebView2 core = Browser.CoreWebView2;
            core.Settings.IsWebMessageEnabled = true;
            core.Settings.AreDefaultContextMenusEnabled = false;
            core.Settings.AreBrowserAcceleratorKeysEnabled = true;
            core.Settings.AreDevToolsEnabled = Environment.GetEnvironmentVariable("HEARTHGHOST_WINDOWS_DEVTOOLS") == "1";
            core.Settings.IsPasswordAutosaveEnabled = false;
            core.Settings.IsGeneralAutofillEnabled = false;
            core.NavigationStarting += OnNavigationStarting;
            core.NewWindowRequested += (_, args) => args.Handled = true;
            core.PermissionRequested += (_, args) => args.State = CoreWebView2PermissionState.Deny;
            core.WebMessageReceived += OnWebMessageReceived;
            core.Navigate(options.WebUiUri.AbsoluteUri);
        }
        catch (Exception error)
        {
            MessageBox.Show(
                $"HearthGhost Windows client could not start: {error.Message}",
                "HearthGhost",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            Close();
        }
    }

    private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs args)
    {
        if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out Uri? target) || !SameOrigin(target, options.WebUiUri))
        {
            args.Cancel = true;
        }
    }

    private async void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        try
        {
            if (!Uri.TryCreate(args.Source, UriKind.Absolute, out Uri? source) || !SameOrigin(source, options.WebUiUri))
            {
                return;
            }
            string response = await bridge.DispatchAsync(args.WebMessageAsJson);
            Browser.CoreWebView2.PostWebMessageAsJson(response);
        }
        catch
        {
            // Never leak native exceptions into web content. Per-request failures are
            // already converted to bounded reason codes by WindowsBridgeDispatcher.
        }
    }

    private static bool SameOrigin(Uri left, Uri right)
    {
        return string.Equals(left.Scheme, right.Scheme, StringComparison.OrdinalIgnoreCase)
            && string.Equals(left.Host, right.Host, StringComparison.OrdinalIgnoreCase)
            && left.Port == right.Port
            && left.IsLoopback
            && right.IsLoopback;
    }

    protected override void OnClosed(EventArgs e)
    {
        try
        {
            bridge.DisposeAsync().AsTask().GetAwaiter().GetResult();
        }
        catch
        {
            // Process shutdown remains authoritative.
        }
        base.OnClosed(e);
    }
}
