# KeystoneLoot Exact Favorite Variant Metadata

## Goal

Preserve the exact KeystoneLoot Favorite variant through KeystoneSync without changing
KeystoneLoot or inventing item metadata. A Favorite's stored bonus IDs define its stable
variant identity; WoW supplies the exact loaded item level and quality when available.

## Contract

- `variantKey` is `base` for no bonus IDs, otherwise `bonus:<sorted comma-separated IDs>`.
- `itemLevel` is a positive safe integer or absent while unresolved.
- `qualityType` is one of WoW's stable quality names or absent while unresolved.
- Existing Favorite fields remain unchanged and older readers may ignore these additions.

KeystoneLoot API v2 currently stores one Favorite per source/spec/item tuple. KeystoneSync
nevertheless keeps variant identity explicit so downstream aggregation remains correct if
the upstream API returns multiple variants now or in the future.

## Runtime behavior

KeystoneSync constructs an item link from KeystoneLoot's saved bonus IDs using its verified
item-string layout, then reads detailed item level and numeric quality from WoW. Synchronous
results are captured immediately. Incomplete results schedule one guarded asynchronous item
load and refresh only if both the active KeystoneSync character key and KeystoneLoot character
key still match. A session cache prevents load loops and repeated resolution.

No Favorite, equipment, or SavedVariables data is sent anywhere by the addon itself. The
existing KeystoneClient sync path remains the only transport boundary.
