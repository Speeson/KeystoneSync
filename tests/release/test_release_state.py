from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_state  # noqa: E402


class ReleaseStateTests(unittest.TestCase):
    def test_fresh(self):
        state = release_state.determine_release_state(
            pending_changesets=True,
            tag_exists=False,
            release_exists=False,
            asset_exists=False,
        )
        self.assertEqual(state.name, "fresh")
        self.assertTrue(state.should_prepare)
        self.assertTrue(state.should_publish)

    def test_resume_tag_only_and_release_without_asset(self):
        tag_only = release_state.determine_release_state(
            pending_changesets=False,
            tag_exists=True,
            release_exists=False,
            asset_exists=False,
        )
        self.assertEqual(tag_only.name, "resume")
        release_without_asset = release_state.determine_release_state(
            pending_changesets=False,
            tag_exists=True,
            release_exists=True,
            asset_exists=False,
        )
        self.assertEqual(release_without_asset.name, "resume")

    def test_complete(self):
        state = release_state.determine_release_state(
            pending_changesets=False,
            tag_exists=True,
            release_exists=True,
            asset_exists=True,
        )
        self.assertEqual(state.name, "complete")
        self.assertFalse(state.should_publish)

    def test_inconsistent_version_and_release_without_tag(self):
        mismatch = release_state.determine_release_state(
            pending_changesets=False,
            tag_exists=True,
            release_exists=False,
            asset_exists=False,
            tag_version_matches=False,
        )
        self.assertEqual(mismatch.name, "inconsistent")
        release_without_tag = release_state.determine_release_state(
            pending_changesets=False,
            tag_exists=False,
            release_exists=True,
            asset_exists=True,
        )
        self.assertEqual(release_without_tag.name, "inconsistent")

    def test_retryable_statuses(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                self.assertTrue(release_state.is_retryable_status(status))
        for status in (401, 403, 404, 422):
            with self.subTest(status=status):
                self.assertFalse(release_state.is_retryable_status(status))
        self.assertEqual(release_state.RETRY_DELAYS_SECONDS, (2, 5, 10, 20))


if __name__ == "__main__":
    unittest.main()
