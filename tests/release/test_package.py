from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import package_addon  # noqa: E402


TOC_FIXTURE = """## Interface: 120100
## Title: KeystoneSync
## Notes: Test fixture.
## Author: Tests
## Version: 0.1.16
## SavedVariables: KeystoneSyncDB

KeystoneSync.lua
"""


class PackageAddonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "KeystoneSync.toc").write_text(TOC_FIXTURE, encoding="utf-8")
        shutil.copy2(REPO_ROOT / "KeystoneSync.lua", self.tmp / "KeystoneSync.lua")
        (self.tmp / "README.md").write_text("not packaged", encoding="utf-8")
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "tool.py").write_text("print('x')", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_package_contains_exact_addon_root_and_runtime_files(self):
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        self.assertEqual(zip_path.name, "KeystoneSync-v0.1.16.zip")
        with zipfile.ZipFile(zip_path) as archive:
            names = sorted(archive.namelist())
        self.assertIn("KeystoneSync/KeystoneSync.toc", names)
        self.assertIn("KeystoneSync/KeystoneSync.lua", names)
        self.assertNotIn("README.md", names)
        self.assertNotIn("scripts/tool.py", names)
        self.assertTrue(all(name.startswith("KeystoneSync/") for name in names))

    def test_toc_loaded_future_file_is_included(self):
        (self.tmp / "Extra.lua").write_text("-- extra", encoding="utf-8")
        toc = self.tmp / "KeystoneSync.toc"
        toc.write_text(toc.read_text(encoding="utf-8-sig") + "\nExtra.lua\n", encoding="utf-8")
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        with zipfile.ZipFile(zip_path) as archive:
            self.assertIn("KeystoneSync/Extra.lua", archive.namelist())

    def test_package_includes_addon_icon_when_present(self):
        (self.tmp / "icon.tga").write_bytes(b"fake-tga-bytes")
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        with zipfile.ZipFile(zip_path) as archive:
            names = sorted(archive.namelist())
        self.assertIn("KeystoneSync/icon.tga", names)

    def test_package_omits_icon_when_absent(self):
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        with zipfile.ZipFile(zip_path) as archive:
            self.assertNotIn("KeystoneSync/icon.tga", archive.namelist())

    def test_package_verification_rejects_tampered_icon(self):
        (self.tmp / "icon.tga").write_bytes(b"original-icon")
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("KeystoneSync/KeystoneSync.toc", (self.tmp / "KeystoneSync.toc").read_bytes())
            archive.writestr("KeystoneSync/KeystoneSync.lua", (self.tmp / "KeystoneSync.lua").read_bytes())
            archive.writestr("KeystoneSync/icon.tga", b"tampered")
        with self.assertRaisesRegex(package_addon.PackageError, "differs from source"):
            package_addon.validate_zip_against_source(zip_path, self.tmp, "0.1.16")

    def test_missing_toc_loaded_file_fails(self):
        toc = self.tmp / "KeystoneSync.toc"
        toc.write_text(toc.read_text(encoding="utf-8-sig") + "\nMissing.lua\n", encoding="utf-8")
        with self.assertRaises(package_addon.PackageError):
            package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")

    def test_version_mismatch_fails(self):
        with self.assertRaises(package_addon.PackageError):
            package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.2.0")

    def test_unexpected_package_structure_fails(self):
        bad_zip = self.tmp / "dist" / "KeystoneSync-v0.1.16.zip"
        bad_zip.parent.mkdir()
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("KeystoneSync.toc", "## Version: 0.1.16\n")
        with self.assertRaises(package_addon.PackageError):
            package_addon.validate_zip(bad_zip, (Path("KeystoneSync.toc"),), "0.1.16")

    def test_cli_default_source_root_still_packages_current_directory(self):
        output = self.tmp / "default-dist"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "package_addon.py"),
                "package",
                "--version",
                "0.1.16",
                "--output-dir",
                str(output),
            ],
            cwd=self.tmp,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((output / "KeystoneSync-v0.1.16.zip").is_file())

    def test_cli_explicit_source_root_packages_historical_tree(self):
        output = self.tmp / "historical-dist"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "package_addon.py"),
                "package",
                "--source-root",
                str(self.tmp),
                "--version",
                "0.1.16",
                "--output-dir",
                str(output),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with zipfile.ZipFile(output / "KeystoneSync-v0.1.16.zip") as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                ["KeystoneSync/KeystoneSync.lua", "KeystoneSync/KeystoneSync.toc"],
            )

    def test_cli_explicit_source_root_rejects_version_mismatch(self):
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "package_addon.py"),
                "validate",
                "--source-root",
                str(self.tmp),
                "--version",
                "0.1.15",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match expected", result.stderr)

    def test_package_verification_rejects_runtime_content_not_from_source(self):
        zip_path = package_addon.package_addon(self.tmp, self.tmp / "dist", version="0.1.16")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "KeystoneSync/KeystoneSync.toc",
                (self.tmp / "KeystoneSync.toc").read_bytes(),
            )
            archive.writestr("KeystoneSync/KeystoneSync.lua", b"-- altered runtime\n")

        with self.assertRaisesRegex(package_addon.PackageError, "differs from source"):
            package_addon.validate_zip_against_source(zip_path, self.tmp, "0.1.16")


if __name__ == "__main__":
    unittest.main()
