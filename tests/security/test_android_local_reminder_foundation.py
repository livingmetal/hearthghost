from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "apps" / "web-client" / "android" / "app" / "src" / "main"
JAVA = ANDROID / "java" / "io" / "hearthghost" / "client"
WEB = ROOT / "apps" / "web-client" / "src" / "reminder"


class AndroidLocalReminderFoundationTests(unittest.TestCase):
    def source(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_manifest_requests_notification_and_boot_but_no_exact_alarm_access(self):
        manifest = self.source(ANDROID / "AndroidManifest.xml")
        self.assertIn("android.permission.POST_NOTIFICATIONS", manifest)
        self.assertIn("android.permission.RECEIVE_BOOT_COMPLETED", manifest)
        self.assertNotIn("SCHEDULE_EXACT_ALARM", manifest)
        self.assertNotIn("USE_EXACT_ALARM", manifest)
        self.assertIn('android:name=".ReminderAlarmReceiver"', manifest)
        self.assertIn('android:name=".ReminderBootReceiver"', manifest)
        for receiver in (".ReminderAlarmReceiver", ".ReminderBootReceiver"):
            start = manifest.index(f'android:name="{receiver}"')
            self.assertIn('android:exported="false"', manifest[start:start + 220])

    def test_alarm_store_is_redacted_and_uses_inexact_allow_while_idle(self):
        source = self.source(JAVA / "LocalReminderStore.java")
        self.assertIn("setAndAllowWhileIdle", source)
        self.assertNotIn("setExact", source)
        self.assertNotIn("setAlarmClock", source)
        self.assertIn("putLong(schedule.reminderId, schedule.fireAtMillis)", source)
        self.assertNotIn("todoText", source)
        self.assertNotIn("responseText", source)
        self.assertNotIn("conversation", source.casefold())

    def test_receiver_uses_only_fixed_redacted_notification_copy(self):
        source = self.source(JAVA / "ReminderAlarmReceiver.java")
        self.assertIn('TITLE = "HearthGhost"', source)
        self.assertIn('BODY = "Reminder"', source)
        self.assertIn("POST_NOTIFICATIONS", source)
        self.assertNotIn("getStringExtra", source)
        self.assertNotIn("todo", source.casefold())

    def test_notification_permission_request_requires_recent_foreground_touch(self):
        source = self.source(JAVA / "LocalReminderPlugin.java")
        self.assertIn("recentForegroundTouch()", source)
        self.assertIn("hasRecentUserInteraction", source)
        self.assertIn("hasWindowFocus", source)
        self.assertIn("requestPermissionForAlias", source)
        self.assertIn("notification_permission_required", source)
        self.assertNotIn("SCHEDULE_EXACT_ALARM", source)

    def test_sync_transport_is_one_shot_mtls_notification_capability_only(self):
        source = self.source(JAVA / "ReminderSyncConnection.java")
        self.assertIn('CAPABILITY = "notification.local"', source)
        self.assertIn('"TLSv1.3"', source)
        self.assertIn("setEndpointIdentificationAlgorithm(\"HTTPS\")", source)
        self.assertIn('ALPN = "hearthghost-node/1"', source)
        self.assertIn('"message_type", "reminder.sync"', source)
        self.assertIn('setOf("reminder_id", "fire_at")', source)
        self.assertNotIn("todo_text", source)

    def test_web_bootstrap_never_requests_permission_without_click(self):
        source = self.source(WEB / "bootstrap.ts")
        click_position = source.index('button.addEventListener("click"')
        request_position = source.index("local.requestPermission()")
        self.assertLess(request_position, click_position)  # inside refresh; call path is gated by boolean
        self.assertIn("refresh(true)", source[click_position:])
        self.assertIn("refresh(false)", source)
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)


if __name__ == "__main__":
    unittest.main()
