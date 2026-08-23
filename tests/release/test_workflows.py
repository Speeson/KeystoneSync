from __future__ import annotations

import json
import subprocess
import sys
import textwrap
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

    def test_release_state_booleans_are_parsed_from_argv(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "release-addon.yml").read_text(
            encoding="utf-8"
        )
        for interpolation in (
            "pending_changesets=${pending}",
            "tag_exists=${tag_exists}",
            "release_exists=${release_exists}",
            "asset_exists=${asset_exists}",
            "tag_version_matches=${tag_version_matches}",
        ):
            with self.subTest(interpolation=interpolation):
                self.assertNotIn(interpolation, workflow)
        command = (
            'state_json="$(python - "$pending" "$tag_exists" "$release_exists" '
            '"$asset_exists" "$tag_version_matches" <<\'PY\'\n'
        )
        script_start = workflow.index(command) + len(command)
        script_end = workflow.index("\n          PY\n", script_start)
        script = textwrap.dedent(workflow[script_start:script_end])

        result = subprocess.run(
            [sys.executable, "-", "false", "true", "false", "false", "true"],
            input=script,
            text=True,
            capture_output=True,
            cwd=REPO_ROOT,
            check=True,
        )
        state = json.loads(result.stdout)
        self.assertEqual(state["name"], "resume")
        self.assertFalse(state["should_prepare"])
        self.assertTrue(state["should_publish"])


if __name__ == "__main__":
    unittest.main()
