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
| `keystoneLoot` | Optional local snapshot of the current character's KeystoneLoot wishlist and Voidcore state, including explicit availability/API status |
| `keystoneLevel` | Keystone level (e.g. `8`) |
| `keystoneDungeon` | Dungeon name (e.g. `"The Stonevault"`) |
| `keystoneChallengeMapId` | Challenge mode ID |
| `keystoneMapId` | UI map ID |
| `updatedAt` | Unix timestamp of the last save |
| `updatedReason` | Event that triggered the save (`PLAYER_LOGIN`, `PLAYER_LOGOUT`, `MANUAL_COMMAND`) |

Only characters at level 90 or above are tracked.

### Spark of Tides storage semantics

Spark of Tides (`itemId = 274476`) is a physical-item count for the current
character. `currencies.sparksOfTides.itemQuantity` (also exposed through the
compatibility aliases `quantity` and `totalItemQuantity`) is the carried amount
plus the last trustworthy character-specific bank amount. `inventoryQuantity`
is the amount carried in normal bags and the equipped reagent bag.

`bankQuantity` includes the normal personal character bank and personal Reagent
Bank. It never includes the Warband/Account Bank. The addon uses explicit
`C_Item.GetItemCount` arguments and captures a trustworthy bank snapshot while
the personal bank is open. `bankQuantityKnown` identifies a valid snapshot and
`bankUpdatedAt` records its capture time. Before the first bank access the bank
amount is unknown; after a trustworthy capture, login and reload preserve that
character's last known amount instead of replacing it with a false zero.

Tidal Spark Dust (`currencyId = 3509`) remains independent progression data and
is never used to derive the current physical Spark count.

## Optional KeystoneLoot integration

[KeystoneLoot](https://github.com/Wolkenschutz/KeystoneLoot) is an optional dependency.
KeystoneSync continues saving its normal data when KeystoneLoot is missing, disabled, not
ready, incompatible, or returns no favorites.

For each current character processed by KeystoneSync, the local-only
`KeystoneSyncDB[key].keystoneLoot` block uses one of these states:

- `not_installed`
- `installed_not_ready`
- `supported`
- `unsupported_api`

A supported snapshot contains the detected API/addon versions, KeystoneLoot's current
character key, capture timestamp, normalized favorites, and read-only Voidcore state.
Favorite identity uses `sourceId`, `specId`, `itemId`, numeric `tier`, and a normalized
bonus-based `variantKey`; optional enrichment includes `sourceType`, `slotId`, `icon`,
`bonusIds`, `gems`, `enchant`, exact item level, and exact in-game quality. Item level
and quality remain nullable while WoW loads an item. Normal KeystoneLoot UI Favorites do
not store the selected upgrade-track bonuses, so KeystoneSync captures the exact public
item-tooltip hyperlink when `FAVORITE_ADDED` fires and retains that variant in its own
character record. Guarded callbacks refresh only the same active character snapshot.
Dungeon `sourceId` values remain KeystoneLoot challenge mode IDs. Voidcore `usedItems` is
a sorted list of numeric item IDs marked as used.

Favorites created before this capture support, or imported without trustworthy bonus IDs,
remain deliberately nullable: KeystoneSync never labels the sparse base item level or quality
as exact. Remove the Favorite, select the intended track/rank, and add it again once to capture
the exact variant. Later filter changes do not alter an already captured Favorite; removing it
clears the capture so a subsequent add can replace it.

An empty `favorites = {}` from a supported, ready KeystoneLoot API is authoritative and
replaces an older wishlist. KeystoneSync never backfills historical character entries
with the logged-in character's KeystoneLoot data. KeystoneClient and the Worker consume
these additive exact-variant fields while remaining compatible with older snapshots.

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
When available, the same save performs exactly one KeystoneLoot refresh and prints one
concise integration diagnostic without listing wishlist items.

Use `/ksync kl` for a safe per-Favorite KeystoneLoot diagnostic. It reports only item/source/spec
identity, Favorite bonus IDs, captured track/rank context, variant key, exact item level/quality,
and metadata source. It never prints account identifiers, authentication data, or unrelated
SavedVariables.

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
