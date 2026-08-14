from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class WindowsClientCertificateStoreTests(unittest.TestCase):
    def test_development_ca_is_connection_scoped_not_a_windows_trusted_root(self):
        client = (
            ROOT / "apps/windows-client/NodeProtocolClient.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("StoreName.CertificateAuthority", client)
        self.assertNotIn("StoreName.Root", client)
        self.assertIn("X509ChainTrustMode.CustomRootTrust", client)
        self.assertIn("FindByThumbprint", client)

    def test_auto_update_is_mtls_hash_verified_and_capability_gated(self):
        updater = (ROOT / "apps/windows-client/WindowsAutoUpdater.cs").read_text(encoding="utf-8")
        protocol = (ROOT / "apps/assistant/src/adapters/client_update_protocol.py").read_text(encoding="utf-8")

        self.assertIn('"client.update"', updater)
        self.assertIn("IncrementalHash.CreateHash(HashAlgorithmName.SHA256)", updater)
        self.assertIn("X509ChainTrustMode.CustomRootTrust", updater)
        self.assertIn("SslProtocols.Tls13", updater)
        self.assertIn("await output.DisposeAsync()", updater)
        self.assertIn("WorkingDirectory = staging", updater)
        self.assertIn('UPDATE_CAPABILITY = "client.update"', protocol)
        self.assertIn("admit_request", protocol)
        self.assertNotIn("StoreName.Root", updater)


if __name__ == "__main__":
    unittest.main()
