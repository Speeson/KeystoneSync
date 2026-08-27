from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import deploy_impact  # noqa: E402


class DeployImpactTests(unittest.TestCase):
    def assertImpact(self, paths, expected_true, *, toc_version_only=False):
        impact = deploy_impact.classify_paths(paths, repo_root=REPO_ROOT, toc_version_only=toc_version_only)
        for dimension in deploy_impact.DIMENSIONS:
            self.assertEqual(
                impact.dimensions[dimension],
                dimension in expected_true,
                f"{dimension} mismatch for {paths}",
            )
        return impact

    def test_lua_runtime_impacts_build_and_release(self):
        self.assertImpact(["KeystoneSync.lua"], {"addon_build", "addon_release"})

    def test_functional_toc_impacts_build_and_release(self):
        with patch.object(deploy_impact, "is_toc_version_only_diff", return_value=False):
            self.assertImpact(["KeystoneSync.toc"], {"addon_build", "addon_release"})

    def test_version_only_toc_change_is_no_release(self):
        impact = self.assertImpact(["KeystoneSync.toc"], set(), toc_version_only=True)
        self.assertEqual(impact.known_no_impact_paths, ["KeystoneSync.toc"])

    def test_changeset_and_docs_are_no_release(self):
        self.assertImpact([".changes/pending/example.json", "README.md", "CHANGELOG.md"], set())

    def test_release_tooling_tests_and_workflows_are_build_only(self):
        self.assertImpact(
            [
                "scripts/release_changes.py",
                "scripts/release_state.py",
                "scripts/package_addon.py",
                "tests/release/test_package.py",
                ".github/workflows/deploy.yml",
            ],
            {"addon_build"},
        )

    def test_future_runtime_file_impacts_release(self):
        self.assertImpact(["Frames.xml", "modules/example.lua"], {"addon_build", "addon_release"})

    def test_unknown_path_is_reported(self):
        impact = self.assertImpact(["unknown/config.toml"], set())
        self.assertEqual(impact.unknown_paths, ["unknown/config.toml"])

    def test_strict_cli_fails_for_unknown_path(self):
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "deploy_impact.py"),
                "--files",
                "unknown/config.toml",
                "--json",
                "--strict",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["unknown_paths"], ["unknown/config.toml"])

    def test_cli_can_allow_empty(self):
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "deploy_impact.py"),
                "--allow-empty",
                "--json",
                "--strict",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertFalse(payload["addon_build"])
        self.assertFalse(payload["addon_release"])


if __name__ == "__main__":
    unittest.main()
