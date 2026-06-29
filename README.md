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
| `ilvl` | Average item level reported by WoW |
| `money` | Character money from `GetMoney()`: total copper plus gold/silver/copper breakdown |
| `preyHunts` | Weekly Prey Hunt completion data split by Normal, Hard, and Nightmare, including completed quest IDs, the full quest completion map, and the weekly reset key |
| `keystoneLevel` | Keystone level (e.g. `8`) |
| `keystoneDungeon` | Dungeon name (e.g. `"The Stonevault"`) |
| `keystoneChallengeMapId` | Challenge mode ID |
| `keystoneMapId` | UI map ID |
| `updatedAt` | Unix timestamp of the last save |
| `updatedReason` | Event that triggered the save (`PLAYER_LOGIN`, `PLAYER_LOGOUT`, `MANUAL_COMMAND`) |

Only characters at level 90 or above are tracked.

## Installation

1. Download the latest release.
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

## Compatibility

| Field | Value |
|---|---|
| Interface | 120005 (The War Within, patch 12.0.5) |
| Retail only | Yes |

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
