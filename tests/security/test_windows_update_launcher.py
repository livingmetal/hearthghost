from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "apps" / "windows-client" / "scripts" / "Start-HearthGhost.ps1"


class WindowsUpdateLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = LAUNCHER.read_text(encoding="utf-8")

    def test_remote_branch_is_explicit_and_exact(self) -> None:
        self.assertIn("HEARTHGHOST_WINDOWS_UPDATE_BRANCH", self.source)
        self.assertIn('"refs/heads/${UpdateBranch}:$remoteRef"', self.source)
        self.assertNotIn("git pull", self.source.lower())

    def test_install_root_is_resolved_after_parameter_binding(self) -> None:
        self.assertIn('[string]$InstallRoot = ""', self.source)
        self.assertIn("$InstallRoot = $PSScriptRoot", self.source)
        self.assertNotIn("[string]$InstallRoot = $PSScriptRoot", self.source)

    def test_update_is_built_from_detached_remote_commit(self) -> None:
        self.assertIn('"worktree", "add", "--detach"', self.source)
        self.assertIn('Arguments @("test")', self.source)
        self.assertIn('Arguments @("run", "windows:assets")', self.source)
        self.assertIn('Arguments @("run", "build")', self.source)
        self.assertIn('"publish", $project', self.source)

    def test_failed_update_preserves_previous_install(self) -> None:
        self.assertIn("previous installed build was preserved", self.source)
        self.assertIn('Join-Path $installRootPath "web.previous"', self.source)
        self.assertIn('Join-Path $installRootPath "native.previous"', self.source)
        self.assertIn("Restore-PreviousInstall", self.source)
        self.assertIn('State "rolled_back"', self.source)

    def test_swap_failure_only_removes_new_candidate_directories(self) -> None:
        self.assertIn("$newWebInstalled = $false", self.source)
        self.assertIn("$newNativeInstalled = $false", self.source)
        self.assertIn(
            "$newWebInstalled -and (Test-Path -LiteralPath $webRoot)",
            self.source,
        )
        self.assertIn(
            "$newNativeInstalled -and (Test-Path -LiteralPath $nativeRoot)",
            self.source,
        )

    def test_owned_loopback_server_is_observed_stopped_before_swap(self) -> None:
        self.assertIn("$listenerProcessId = [int]$listener.OwningProcess", self.source)
        self.assertIn("Get-Process -Id $listenerProcessId", self.source)
        self.assertIn("loopback server did not stop before update", self.source)

    def test_launcher_does_not_reference_provider_credentials(self) -> None:
        self.assertNotIn("OPENAI_API_KEY", self.source)
        self.assertNotIn("sk-proj", self.source)
        self.assertIn("Remove-BuildSecrets", self.source)
        self.assertIn("origin URL must not contain embedded credentials", self.source)

    def test_signed_install_requires_a_verified_signed_update(self) -> None:
        self.assertIn("Protect-NativeSignature", self.source)
        self.assertIn("Get-AuthenticodeSignature", self.source)
        self.assertIn("Set-AuthenticodeSignature", self.source)
        self.assertIn("HasPrivateKey", self.source)


if __name__ == "__main__":
    unittest.main()
