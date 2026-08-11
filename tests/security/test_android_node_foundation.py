from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web-client"
ANDROID = WEB / "android"
ANDROID_NAMESPACE = "{http://schemas.android.com/apk/res/android}"


class AndroidNodeFoundationTests(unittest.TestCase):
    def test_only_reviewed_runtime_permissions_are_requested(self):
        root = ET.parse(
            ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
        ).getroot()
        permissions = {
            item.attrib[f"{ANDROID_NAMESPACE}name"]
            for item in root.findall("uses-permission")
        }
        self.assertEqual(
            permissions,
            {
                "android.permission.INTERNET",
                "android.permission.RECORD_AUDIO",
                "android.permission.POST_NOTIFICATIONS",
                "android.permission.RECEIVE_BOOT_COMPLETED",
            },
        )
        self.assertNotIn("android.permission.SCHEDULE_EXACT_ALARM", permissions)
        self.assertNotIn("android.permission.USE_EXACT_ALARM", permissions)
        application = root.find("application")
        self.assertIsNotNone(application)
        self.assertEqual(application.attrib[f"{ANDROID_NAMESPACE}allowBackup"], "false")
        self.assertEqual(
            application.attrib[f"{ANDROID_NAMESPACE}usesCleartextTraffic"],
            "false",
        )

    def test_capacitor_and_bouncy_castle_versions_are_pinned(self):
        package = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["dependencies"]["@capacitor/core"], "8.5.0")
        self.assertEqual(package["dependencies"]["@capacitor/android"], "8.5.0")
        self.assertEqual(package["devDependencies"]["@capacitor/cli"], "8.5.0")
        gradle = (ANDROID / "app" / "build.gradle").read_text(encoding="utf-8")
        self.assertIn("org.bouncycastle:bcpkix-jdk18on:1.84", gradle)

    def test_native_bridge_owns_identity_and_fixed_gateway(self):
        source_root = (
            ANDROID
            / "app"
            / "src"
            / "main"
            / "java"
            / "io"
            / "hearthghost"
            / "client"
        )
        identity = (source_root / "NodeIdentityStore.java").read_text(encoding="utf-8")
        connection = (source_root / "NodeConnection.java").read_text(encoding="utf-8")
        plugin = (source_root / "NodeTransportPlugin.java").read_text(encoding="utf-8")
        self.assertIn('private static final String KEYSTORE = "AndroidKeyStore"', identity)
        self.assertIn("KeyGenParameterSpec.Builder", identity)
        self.assertIn("privateKey.getEncoded() != null", identity)
        self.assertNotIn("OPENAI_API_KEY", identity + connection + plugin)
        self.assertIn('private static final String HOST = "192.168.55.100"', connection)
        self.assertIn("private static final int PORT = 38443", connection)
        self.assertIn('setEnabledProtocols(new String[] { "TLSv1.3" })', connection)
        self.assertIn('setApplicationProtocols(new String[] { ALPN })', connection)
        self.assertIn("Executors.newSingleThreadExecutor()", plugin)
        self.assertIn("operationInFlight.compareAndSet(false, true)", plugin)
        self.assertNotIn("@Permission", plugin)

    def test_generated_credentials_and_apks_are_ignored(self):
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "*.jks",
            "*.keystore",
            "*.csr",
            "*.crt",
            "*.pem",
            "*.apk",
            "*.aab",
        ):
            self.assertIn(pattern, ignored)


if __name__ == "__main__":
    unittest.main()
