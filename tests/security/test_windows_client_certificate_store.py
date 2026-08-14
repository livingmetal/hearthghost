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


if __name__ == "__main__":
    unittest.main()
