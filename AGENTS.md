# KeystoneSync Addon Agent Instructions

## Scope

These instructions apply to this standalone addon repository.

## Repository Role

`Speeson/KeystoneSync` is the canonical World of Warcraft addon source. KeystoneClient consumes this repository's GitHub Releases and must not embed or manually mirror addon runtime files.

## Release Rules

- Runtime addon changes such as `KeystoneSync.lua` and functional `KeystoneSync.toc` changes are release-impacting.
- Release-impacting changes require a valid addon changeset under `.changes/pending/`.
- Changeset `type` must be `patch`, `minor`, or `major`.
- Generated release notes are user-facing Spanish text.
- Git tag, GitHub Release asset version, ZIP root content, and `KeystoneSync.toc` `## Version` must match.
- Addon releases are independent from KeystoneClient releases.
- Do not start WoW patch/season work unless explicitly requested. Phase 12 gameplay and season updates are separate.

## Validation

- Run `python scripts/deploy_impact.py --files <changed-paths> --json --strict` for changed files.
- Run the relevant unit tests before reporting completion.
- Do not push, tag, publish GitHub Releases, or perform any remote write unless explicitly authorized in the current task.
