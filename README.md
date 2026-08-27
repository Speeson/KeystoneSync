# KeystoneSync

A lightweight World of Warcraft addon that saves your Mythic+ keystone data to `SavedVariables` so external tools can read it without interacting with the game client.

## What it does

On every login and logout, KeystoneSync writes the current character's keystone information to `KeystoneSyncDB`:

| Field | Description |
|---|---|
| `character` | Character name |
| `realm` | Realm name |
| `region` | Region (default: `eu`) |
| `hasKeystone` | Whether the character currently holds a keystone |
| `keystoneWeeklyResetKey` | EU weekly reset key for the saved keystone. Used to clear stale keystones after Wednesday reset |
| `ilvl` | Average item level reported by WoW |
| `money` | Character money from `GetMoney()`: total copper plus gold/silver/copper breakdown |
| `preyHunts` | Weekly Prey Hunt completion data split by Normal, Hard, and Nightmare, including completed quest IDs, the full quest completion map, and the weekly reset key |
| `currencies` | Midnight Season 2 Mistcrests, Venomblight Manaflux, Tidal Spark Dust, Spark of Tides, keys, Nebulous Voidcore, and Trovehunter's Bounty bag/buff/weekly completion state |
| `mythicPlusSeason` | Current-season Mythic+ dungeon bests. Captured after a delayed login pass or reliable Mythic+ events to avoid stale WoW cache data from another character |
| `keystoneLevel` | Keystone level (e.g. `8`) |
| `keystoneDungeon` | Dungeon name (e.g. `"The Stonevault"`) |
| `keystoneChallengeMapId` | Challenge mode ID |
| `keystoneMapId` | UI map ID |
| `updatedAt` | Unix timestamp of the last save |
| `updatedReason` | Event that triggered the save (`PLAYER_LOGIN`, `PLAYER_LOGOUT`, `MANUAL_COMMAND`) |

Only characters at level 90 or above are tracked.

## Installation

1. Download the dedicated addon release asset `KeystoneSync-vX.Y.Z.zip` from GitHub Releases.
2. Extract the `KeystoneSync` folder into your WoW AddOns directory:
   ```
   World of Warcraft\_retail_\Interface\AddOns\KeystoneSync\
   ```
3. Enable the addon in-game from the AddOns menu on the character select screen.

## Slash command

```
/ksync
```

Forces an immediate save and prints the stored keystone for the current character in the chat window.

## SavedVariables location

```
World of Warcraft\_retail_\WTF\Account\<ACCOUNT>\SavedVariables\KeystoneSync.lua
```

This is the file external tools (e.g. [KeystoneClient](https://github.com/Speeson/weeklyChar)) poll to sync keystone data to a backend API and display it in a desktop client or web dashboard.

## Release automation

Addon releases are owned by this repository. A release-impacting addon change requires a Spanish changeset under `.changes/pending/*.json`. On qualifying pushes to `main`, GitHub Actions publishes automatically only when the `ADDON_RELEASE_ENABLED` repository variable is `true`. Manual `workflow_dispatch` releases remain available independently of that automatic-release gate. Release automation plans the bump, updates `KeystoneSync.toc`, packages `KeystoneSync-vX.Y.Z.zip` with root `KeystoneSync/`, and publishes the GitHub Release under tag `vX.Y.Z`.

Build-only workflow/tooling changes validate and package the addon without publishing. KeystoneClient consumes only the dedicated `KeystoneSync-vX.Y.Z.zip` asset, not GitHub's automatic source archives.

Release tooling always runs from the current release infrastructure on `main`. When a missing or incomplete GitHub Release is resumed for an existing historical tag, the workflow exports the immutable tagged addon source into a temporary directory and packages that exact runtime through the current validator; it never rewrites or globally checks out the historical tag.

## Compatibility

| Field | Value |
|---|---|
| Interface | 120100 (Midnight, patch 12.1) |
| Retail only | Yes |

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
