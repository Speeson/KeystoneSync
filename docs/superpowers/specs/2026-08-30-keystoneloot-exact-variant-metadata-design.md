# KeystoneLoot Exact Favorite Variant Metadata

## Goal

Preserve the exact KeystoneLoot Favorite variant through KeystoneSync without changing
KeystoneLoot or inventing item metadata. Explicit Favorite bonus IDs remain trustworthy;
normal UI Favorites require a capture of the exact preview shown when they are added.

## Contract

- `variantKey` is `base` for no bonus IDs, otherwise `bonus:<sorted comma-separated IDs>`.
- `itemLevel` is a positive safe integer or absent while unresolved.
- `qualityType` is one of WoW's stable quality names or absent while unresolved.
- Existing Favorite fields remain unchanged and older readers may ignore these additions.

KeystoneLoot API v2 currently stores one Favorite per source/spec/item tuple. KeystoneSync
nevertheless keeps variant identity explicit so downstream aggregation remains correct if
the upstream API returns multiple variants now or in the future.

## Verified KeystoneLoot 2.14.0 behavior

The installed addon and upstream tag `2.14.0` agree:

- `ui/templates/mixins/icon_button.lua` calls
  `Favorites:Add(sourceId, specId, itemId, tier)` in the normal UI flow, without bonus IDs.
- `modules/favorites.lua` stores only bonus IDs explicitly passed to `Favorites:Add` and fires
  `FAVORITE_ADDED` without the selected preview link.
- `modules/api.lua` exposes `KeystoneLootAPI` v2 and `GetFavorites`, but it does not expose
  `Upgrade:BuildItemLink` or the resolved upgrade track.
- `modules/upgrade.lua` builds the displayed preview from current character filters, an extensive
  item-level bonus table, upgrade-track data, stored Favorite extras, special-item bonuses, an
  item-quality bonus, and ring/neck rules.
- `modules/db.lua` stores the read-only current selection in `KeystoneLootCharDB.ui.selectedTab`,
  `filters.dungeon.track/rank`, `filters.raid.difficulty/rank`, plus class/spec/slot filters.

The internal `KeystoneLoot.Upgrade` namespace is private to KeystoneLoot's addon environment and
has no supported cross-addon entry point. KeystoneSync therefore does not duplicate its volatile
upgrade tables or call hidden globals.

## Runtime behavior

KeystoneSync registers a Blizzard `TooltipDataProcessor` item callback. The normal KeystoneLoot
interaction displays its fully resolved preview before the user chooses a Favorite tier, so the
callback retains only the most recent structurally valid item hyperlink. On `FAVORITE_ADDED`, the
capture is accepted only when it is recent, its item and bound source match the event, its filter
context still matches, and its parsed item payload contains a positive, correctly positioned
`numBonusIDs` list. The public API supplies the source ID. The spec embedded in the hyperlink is
stored as diagnostic `linkSpecId`; the `FAVORITE_ADDED` spec is the target storage identity.

A single preview remains reusable throughout the synchronous mutation burst produced by
`All Specializations`. Each concrete spec emitted by KeystoneLoot receives the same exact variant;
KeystoneSync never expands spec `0` or invents specs. Every accompanying `FAVORITES_CHANGED`
updates the preview scheduled for expiry, and the debounced refresh expires that same preview after
the burst. A newer tooltip preview is not cleared by an older pending refresh. TTL, item, source,
filter context, track/rank, generation, and character guards continue to reject stale association.

The captured record lives under the current KeystoneSync character as
`keystoneLootFavoriteCaptures` and contains character/source/spec/item identity, canonical bonus
IDs and variant key, exact item string fields, selected context/track/rank, capture timestamp,
item level, quality type, and metadata source. KeystoneLoot SavedVariables are read-only.

Explicit Favorite bonus IDs continue to use a constructed exact item link. A Favorite without
explicit bonus IDs and without a capture remains `variantKey = base`, `itemLevel = nil`, and
`qualityType = nil`; the sparse base item is never queried as exact metadata. Historical Favorites
are not inferred from the user's current filters and can be recaptured by remove/select/add.

`FAVORITE_REMOVED` deletes matching captures, re-adding replaces them, and
`FAVORITES_IMPORTED` clears captures for that KeystoneLoot character rather than resurrecting
stale variants. Later filter changes do not mutate a stored capture.

WoW supplies detailed item level and numeric quality from the exact link. Incomplete results
schedule one asynchronous item load and refresh only if generation, KeystoneSync character,
KeystoneLoot character, and capture identity still match. The persisted exact link permits one
safe retry after reload without using current filter state.

`/ksync kl` prints a compact, non-sensitive diagnostic for captured and legacy Favorites.

No Favorite, equipment, or SavedVariables data is sent anywhere by the addon itself. The
existing KeystoneClient sync path remains the only transport boundary.
