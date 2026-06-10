# Changelog

All notable changes to KeystoneSync will be documented here.

## [0.1.10] - 2026-06-10

### Fixed
- Ignore transient `0` item-level reads from WoW and preserve the previous valid item level instead.

## [0.1.9] - 2026-06-10

### Added
- Capture character item level directly from WoW via `GetAverageItemLevel()`, storing `ilvl` in `KeystoneSyncDB`.

## [0.1.8] - 2026-05-30

### Added
- Capture currency and dungeon icon metadata (`iconFileID`, `iconPath`, `texture`, `texturePath`) so external clients can render clearer summary tables.
- Capture Mythic+ affix score data per dungeon using `C_MythicPlus.GetSeasonBestAffixScoreInfoForMap`, including `bestOverAllScore`, `bestAffixScore`, `affixScores`, `bestTimedRun`, and `bestNotTimedRun`.

### Changed
- Mythic+ dungeon `rating` and upgrade tier (`+1`, `+2`, `+3`) now prefer Blizzard's affix-score data, matching AlterEgo's source more closely.

## [0.1.7] - 2026-05-30

### Added
- Capture Great Vault progress split by raid, dungeon, and world activity slots.
- Capture weekly Prey Hunt completion counts split by Normal, Hard, and Nightmare.
- Capture Midnight Season 1 currencies: Adventurer, Veteran, Champion, Hero, and Myth Dawncrests; Dawnlight Manaflux; Radiant Spark Dust; Spark of Radiance item count; Coffer Key Shards; Restored Coffer Key; and Nebulous Voidcore.
- Capture current-season Mythic+ dungeon bests with challenge map ID, dungeon name, best level, timed status, rating, and computed upgrade level (`+1`, `+2`, `+3`) when duration data is available.

## [0.1.6] - 2026-05-30

### Fixed
- Added a bag-scan fallback for Mythic Keystone detection. If `C_MythicPlus.GetOwnedKeystoneLevel()` or `C_MythicPlus.GetOwnedKeystoneChallengeMapID()` returns empty during login/logout, the addon now scans the character bags, detects the Mythic Keystone item, and parses its item link to recover the keystone level and challenge map ID.
- Prevented valid saved keystone data from being overwritten by a transient empty read. If the current scan fails but the character already has a valid keystone stored, the addon keeps the previous keystone data instead of writing `hasKeystone = false`.

## [0.1.5] - 2026-05-30

### Changed
- Simplified event handling: only `PLAYER_LOGIN` and `PLAYER_LOGOUT` are now registered. Removed `BAG_UPDATE_DELAYED`, `CHALLENGE_MODE_COMPLETED` (with its 3 delayed timers), and the 5-second `PLAYER_LOGIN` delay. Login and logout captures are sufficient for normal use, and the simpler model avoids redundant writes.

### Fixed
- Dungeon name (`keystoneDungeon`) no longer disappears from `KeystoneSyncDB` after a login. `C_ChallengeMode.GetMapUIInfo` can return `nil` at login time because challenge mode data is not yet loaded by the game engine. The addon now falls back to the previously stored name when the lookup fails and the keystone has not changed (`keystoneChallengeMapId` matches), so the name is preserved until a successful read overwrites it.

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
