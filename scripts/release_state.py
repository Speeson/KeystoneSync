from __future__ import annotations

from dataclasses import dataclass


RETRYABLE_STATUSES = {500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (2, 5, 10, 20)


@dataclass(frozen=True)
class ReleaseState:
    name: str
    should_prepare: bool
    should_publish: bool
    reason: str


def is_retryable_status(status: int) -> bool:
    return status in RETRYABLE_STATUSES


def determine_release_state(
    *,
    pending_changesets: bool,
    tag_exists: bool,
    release_exists: bool,
    asset_exists: bool,
    tag_version_matches: bool = True,
) -> ReleaseState:
    if tag_exists and not tag_version_matches:
        return ReleaseState("inconsistent", False, False, "Existing tag source has a mismatched TOC version.")

    if pending_changesets:
        if tag_exists and release_exists and asset_exists:
            return ReleaseState("complete", False, False, "Expected release and asset already exist.")
        if tag_exists:
            return ReleaseState("resume", False, True, "Release commit/tag already exist; resume publication.")
        if release_exists:
            return ReleaseState("inconsistent", False, False, "Release exists without the expected tag.")
        return ReleaseState("fresh", True, True, "Prepare a new addon release from pending changesets.")

    if tag_exists and release_exists and asset_exists:
        return ReleaseState("complete", False, False, "Expected release and asset already exist.")
    if tag_exists and not release_exists:
        return ReleaseState("resume", False, True, "Tag exists but GitHub Release is missing.")
    if tag_exists and release_exists and not asset_exists:
        return ReleaseState("resume", False, True, "Release exists but expected ZIP asset is missing.")
    if release_exists and not tag_exists:
        return ReleaseState("inconsistent", False, False, "Release exists without the expected tag.")
    return ReleaseState("inconsistent", False, False, "No pending changesets and no resumable release state.")
