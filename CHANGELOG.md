# Changelog

All notable changes to KeystoneSync will be documented here.

## [0.1.4] - 2026-05-27

### Added
- Ignore characters below level 90 (`MAX_LEVEL` constant). Low-level alts are no longer written to `KeystoneSyncDB`, keeping the saved variables clean.

## [0.1.3] - 2026-05-27

### Fixed
- Added `PLAYER_LOGOUT` event to fire a final save just before WoW writes `SavedVariables` to disk. Guarantees the most up-to-date keystone state is always captured, even if no other event triggered during the session.

## [0.1.2] - 2026-05-27

### Fixed
- Listen to `BAG_UPDATE_DELAYED` to detect when WoW places the new weekly keystone into the bag (e.g. after the Wednesday reset). Only saves if the level or dungeon changed vs what was already stored, avoiding unnecessary writes on every bag change.

## [0.1.1] - 2026-05-27

### Fixed
- Added a 5-second delayed read on `PLAYER_LOGIN` so `C_MythicPlus` has time to load keystone data after the weekly reset. The immediate read is kept as a fallback.

## [0.1.0] - 2026-05-26

### Added
- Initial release.
- Tracks the current Mythic+ keystone (level, dungeon name, challenge map ID) for every character that logs in.
- Writes data to `KeystoneSyncDB` SavedVariables on `PLAYER_LOGIN`, `CHALLENGE_MODE_COMPLETED` (with 5 s / 10 s / 20 s delayed reads), and manually via `/ksync`.
- Resolves dungeon name via `C_ChallengeMode.GetMapUIInfo`.
- Compatible with WoW Retail Interface 120005 (patch 12.0.5).
