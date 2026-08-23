from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ReleaseWorkflowTests(unittest.TestCase):
    def test_resume_keeps_modern_tooling_and_stages_tagged_runtime(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "release-addon.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('git checkout "${{ steps.release-meta.outputs.tag }}"', workflow)
        self.assertIn('git -c core.autocrlf=false archive "${tag}"', workflow)
        self.assertIn('--source-root "${{ steps.addon-source.outputs.root }}"', workflow)
        self.assertIn("historical-notes", workflow)


if __name__ == "__main__":
    unittest.main()
