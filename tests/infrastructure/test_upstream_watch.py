import json
import tempfile
import unittest
from pathlib import Path

from tools.upstream_watch import ManifestError, load_manifest, matching_files


ROOT = Path(__file__).resolve().parents[2]


class UpstreamWatchTests(unittest.TestCase):
    def test_repository_manifest_is_valid(self):
        manifest = load_manifest(ROOT / "upstream/character-sources.json")

        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual({source["id"] for source in manifest["sources"]}, {"airi", "pngal"})

    def test_matching_files_only_returns_watched_paths(self):
        changed = [
            "packages/stage-ui-three/src/composables/vrm/animation.ts",
            "packages/stage-ui/src/composables/use-scroll-to-hash.ts",
            "README.md",
        ]

        self.assertEqual(
            matching_files(changed, ["packages/stage-ui-three/**"]),
            ["packages/stage-ui-three/src/composables/vrm/animation.ts"],
        )

    def test_exact_and_glob_paths_can_be_combined(self):
        changed = [
            "resources/web/app.js",
            "pipeline_server.py",
            "setup.bat",
        ]

        self.assertEqual(
            matching_files(changed, ["resources/web/**", "pipeline_server.py"]),
            ["pipeline_server.py", "resources/web/app.js"],
        )

    def test_duplicate_source_ids_are_rejected(self):
        source = {
            "id": "airi",
            "displayName": "AIRI",
            "repository": "moeru-ai/airi",
            "branch": "main",
            "baselineSha": "a" * 40,
            "license": "MIT",
            "licensePath": "LICENSE",
            "integrationPolicy": "reference-only",
            "focus": ["VRM"],
            "watchPaths": ["packages/stage-ui-three/**"],
        }
        payload = {"schemaVersion": 1, "sources": [source, dict(source)]}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
