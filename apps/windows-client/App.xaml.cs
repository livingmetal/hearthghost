namespace HearthGhost.WindowsClient;

public partial class App : System.Windows.Application
{
    protected override async void OnStartup(System.Windows.StartupEventArgs e)
    {
        base.OnStartup(e);
        ShutdownMode = System.Windows.ShutdownMode.OnExplicitShutdown;
        try
        {
            if (await WindowsAutoUpdater.HandleHelperModeAsync(e.Args).ConfigureAwait(true))
            {
                Shutdown();
                return;
            }

            WindowsClientOptions options = WindowsClientOptions.FromEnvironment();
            if (await WindowsAutoUpdater.TryStartUpdateAsync(options).ConfigureAwait(true))
            {
                Shutdown();
                return;
            }

            MainWindow window = new(options);
            MainWindow = window;
            ShutdownMode = System.Windows.ShutdownMode.OnMainWindowClose;
            window.Show();
        }
        catch (Exception error)
        {
            System.Windows.MessageBox.Show(
                $"HearthGhost Windows client could not start: {error.Message}",
                "HearthGhost",
                System.Windows.MessageBoxButton.OK,
                System.Windows.MessageBoxImage.Error);
            Shutdown(1);
        }
    }
}
