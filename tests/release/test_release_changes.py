from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_changes  # noqa: E402


class ReleaseChangesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / ".changes" / "pending").mkdir(parents=True)
        (self.tmp / ".changes" / "releases").mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "KeystoneSync.toc", self.tmp / "KeystoneSync.toc")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_changeset(self, name: str, **overrides):
        payload = {
            "components": ["addon"],
            "type": "patch",
            "category": "fixed",
            "summary": "Corrige un problema visible.",
            "details": ["Mantiene el texto en español."],
        }
        payload.update(overrides)
        path = self.tmp / ".changes" / "pending" / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reads_current_version_from_toc(self):
        self.assertEqual(release_changes.read_addon_version(self.tmp / "KeystoneSync.toc"), "0.1.16")

    def test_bump_version_patch_minor_major(self):
        self.assertEqual(release_changes.bump_version("0.1.16", "patch"), "0.1.17")
        self.assertEqual(release_changes.bump_version("0.1.16", "minor"), "0.2.0")
        self.assertEqual(release_changes.bump_version("0.1.16", "major"), "1.0.0")

    def test_invalid_semver_and_bump_fail(self):
        with self.assertRaises(release_changes.ChangesetError):
            release_changes.bump_version("0.1", "patch")
        with self.assertRaises(release_changes.ChangesetError):
            release_changes.bump_version("0.1.16", "build")

    def test_auto_selects_highest_bump(self):
        self.write_changeset("patch.json", type="patch")
        self.write_changeset("minor.json", type="minor")
        plan = release_changes.plan_release(self.tmp, "auto")
        self.assertEqual(plan.bump, "minor")
        self.assertEqual(plan.next_version, "0.2.0")
        self.assertEqual(plan.tag, "v0.2.0")
        self.assertEqual(plan.asset, "KeystoneSync-v0.2.0.zip")

    def test_forced_bump_overrides_auto(self):
        self.write_changeset("minor.json", type="minor")
        plan = release_changes.plan_release(self.tmp, "patch")
        self.assertEqual(plan.bump, "patch")
        self.assertEqual(plan.next_version, "0.1.17")

    def test_no_pending_addon_changeset_fails(self):
        with self.assertRaises(release_changes.ChangesetError):
            release_changes.plan_release(self.tmp, "auto")

    def test_schema_validation(self):
        invalid_cases = [
            {"components": ["client"], "type": "patch", "category": "fixed", "summary": "x", "details": ["x"]},
            {"components": ["addon"], "type": "build", "category": "fixed", "summary": "x", "details": ["x"]},
            {"components": ["addon"], "type": "patch", "category": "misc", "summary": "x", "details": ["x"]},
            {"components": ["addon"], "type": "patch", "category": "fixed", "summary": "", "details": ["x"]},
            {"components": ["addon"], "type": "patch", "category": "fixed", "summary": "x", "details": [1]},
        ]
        for index, payload in enumerate(invalid_cases):
            with self.subTest(index=index):
                path = self.tmp / ".changes" / "pending" / f"bad-{index}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(release_changes.ChangesetError):
                    release_changes.load_changesets(self.tmp)
                path.unlink()

    def test_prepare_updates_only_toc_version_and_consumes_changeset(self):
        self.write_changeset("addon.json", type="minor", category="added", summary="Añade compatibilidad.", details=["Genera notas en español."])
        before_lines = (self.tmp / "KeystoneSync.toc").read_text(encoding="utf-8-sig").splitlines()
        plan = release_changes.plan_release(self.tmp, "auto")
        notes_path, metadata_path = release_changes.write_release_files(self.tmp, plan)
        after_lines = (self.tmp / "KeystoneSync.toc").read_text(encoding="utf-8").splitlines()

        changed = [(before, after) for before, after in zip(before_lines, after_lines) if before != after]
        self.assertEqual(changed, [("## Version: 0.1.16", "## Version: 0.2.0")])
        self.assertFalse((self.tmp / ".changes" / "pending" / "addon.json").exists())
        self.assertTrue(notes_path.is_file())
        self.assertTrue(metadata_path.is_file())
        self.assertIn("## Novedades", notes_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["tag"], "v0.2.0")
        self.assertEqual(metadata["asset"], "KeystoneSync-v0.2.0.zip")

    def test_historical_notes_use_only_the_requested_changelog_section(self):
        changelog = """# Changelog

## [0.1.16] - 2026-08-02

### Fixed
- Reset semanal corregido.

## [0.1.15] - 2026-06-29

### Fixed
- Cambio anterior.
"""
        notes = release_changes.render_historical_notes(changelog, "0.1.16")
        self.assertTrue(notes.startswith("# KeystoneSync 0.1.16\n"))
        self.assertIn("Reset semanal corregido.", notes)
        self.assertNotIn("Cambio anterior.", notes)

    def test_historical_notes_fail_when_version_is_missing(self):
        with self.assertRaises(release_changes.ChangesetError):
            release_changes.render_historical_notes("# Changelog\n", "0.1.16")


if __name__ == "__main__":
    unittest.main()
