from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import package_addon  # noqa: E402


class PackageAddonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy2(REPO_ROOT / "KeystoneSync.toc", self.tmp / "KeystoneSync.toc")
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


if __name__ == "__main__":
    unittest.main()
