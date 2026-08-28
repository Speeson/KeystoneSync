# KeystoneLoot Integration V1-A Design

## Objective

Capture the current character's KeystoneLoot favorites and Voidcore state in the local
`KeystoneSyncDB[key].keystoneLoot` block without changing the existing KeystoneSync
tracking contract or requiring KeystoneLoot to be installed, enabled, supported, or ready.

This delivery is addon-local V1-A only. It does not transport KeystoneLoot data through
KeystoneClient, Worker, D1, or Web.

## Verified upstream contract

The design was verified against `Wolkenschutz/KeystoneLoot` `main` commit
`bb4328fe2bb8ee0417262610f84a00d7d7e3a6be` on 2026-08-28.

- Public API version: `2`.
- Readiness: `KeystoneLootAPI:IsReady()` and the `READY` callback registered with
  `KeystoneLootAPI:RegisterCallback()`.
- A `READY` callback registered after readiness fires immediately.
- Current character identity: `GetCurrentCharacterKey()`.
- Favorites: `GetFavorites(characterKey)`.
- Enrichment: `GetSourceInfo(sourceId)` and `GetItemInfo(itemId)`.
- Aggregate mutation event: `FAVORITES_CHANGED`, emitted after add, remove, tier change,
  and import operations.
- Current tiers include numeric values `1` through `5`, with Catalyst at `5`. The
  integration preserves numeric tier values generically and does not encode that range.
- Voidcore remains character-local at `KeystoneLootCharDB.voidcore` and
  `KeystoneLootCharDB.voidcoreChecked` and has no public read API.
- KeystoneLoot clears seasonal favorites when its current season changes.

## Architecture

### `KeystoneLootIntegration.lua`

Add a focused module loaded before `KeystoneSync.lua` through the KeystoneSync TOC. TOC
order only makes the helper available to KeystoneSync; it is not evidence that
KeystoneLoot itself is initialized.

The module owns:

- installation and API-version detection;
- public API calls and `pcall` boundaries;
- READY and `FAVORITES_CHANGED` callback registration;
- favorite normalization and optional source/item enrichment;
- direct, read-only Voidcore normalization;
- debouncing and stale-character callback rejection;
- concise diagnostic formatting.

The module receives a KeystoneSync character-key provider from the normal runtime. It
does not own or duplicate ordinary keystone, vault, currency, money, or season tracking.

### `KeystoneSync.lua`

The existing save flow remains authoritative for normal data. After ordinary fields and
timestamps have been written, it makes one protected integration call. Failure in that
call cannot prevent or roll back normal SavedVariables writes.

On `PLAYER_LOGIN`, the integration registers its official callbacks and evaluates
readiness. On `PLAYER_LOGOUT`, KeystoneSync performs the final normal character save and
allows at most one immediate, synchronous KeystoneLoot snapshot when the API is ready.
That snapshot cannot register callbacks or schedule debounce work. Only after the final
save does the integration invalidate its generation, unregister callbacks, and reject
previously pending work. After logout handling completes, no KeystoneLoot callback or
timer may write anything.

`/ksync` has exactly one authoritative KeystoneLoot refresh. The manual save path writes
normal data, performs the immediate integration refresh once, and returns the resulting
stored integration state for one concise diagnostic. The slash-command handler does not
perform a second refresh.

### `KeystoneSync.toc`

Declare `## OptionalDeps: KeystoneLoot` and load `KeystoneLootIntegration.lua` before
`KeystoneSync.lua`. KeystoneLoot never becomes a required dependency.

## State and SavedVariables contract

Every level-90-or-higher character processed by `SaveCharacterData()` from this version
onward receives a small explicit block even when the integration is unavailable:

```lua
keystoneLoot = {
    state = "not_installed", -- or installed_not_ready, supported, unsupported_api
    installed = false,
    supported = false,
    favorites = {},
}
```

A successful authoritative snapshot has this shape:

```lua
keystoneLoot = {
    state = "supported",
    installed = true,
    supported = true,
    apiVersion = 2,
    addonVersion = "...",
    characterKey = "Zul'jin-Spee-3",
    updatedAt = 1780000000,
    favorites = {
        {
            sourceId = 558,
            sourceType = "dungeon",
            specId = 255,
            itemId = 251119,
            tier = 3,
            slotId = 10,
            icon = 7259236,
            bonusIds = { 6652, 1498 },
            gems = { 213743 },
            enchant = 7334,
        },
    },
    voidcore = {
        checked = true,
        usedItems = { 249343, 251079 },
    },
}
```

Optional favorite enrichment and item-modification fields may be absent. `sourceId`,
`specId`, `itemId`, and `tier` preserve canonical numeric/string identity from the public
API. Numeric dungeon `sourceId` remains the challenge mode ID. `usedItems` is a sorted
list containing only numeric item IDs whose Voidcore value is exactly `true`.

An unsupported API preserves detected version information when available, uses
`state = "unsupported_api"`, `installed = true`, `supported = false`, and
`favorites = {}`. An installed but unavailable/not-ready API uses
`state = "installed_not_ready"`. Missing or disabled KeystoneLoot remains safe and uses
the best detectable explicit unavailable state. The integration updates only the
currently logged-in character record. It never iterates over or backfills historical
`KeystoneSyncDB` entries with the current character's KeystoneLoot state.

When a supported, ready API returns an empty favorites table, the module writes
`favorites = {}` and replaces any earlier non-empty list.

## Callback and character safety

Register only `READY` and `FAVORITES_CHANGED`, using a stable owner token so callbacks
can be unregistered safely.

`FAVORITES_CHANGED` refreshes only when its event character key equals
`GetCurrentCharacterKey()`. Debounced work captures both:

1. the current KeystoneSync SavedVariables key; and
2. the current KeystoneLoot character key.

Before writing, the callback reads both keys again and rejects the write if either has
changed. A generation token invalidates pending work during logout or reinitialization.
Logout first permits the one non-registering, non-debounced final snapshot described
above, then increments the generation and unregisters callbacks. The debounce coalesces
bursts without polling KeystoneLoot.

## Error handling

All external-addon methods are type-checked and invoked through protected calls.
Failures return a diagnostic state or skip optional enrichment; they never raise into
the normal KeystoneSync save/event handler. The integration never writes to KeystoneLoot
or mutates tables returned by its API or SavedVariables.

## Tests

Use a Python `unittest` harness backed by `lupa==2.8` so tests execute the real
`KeystoneLootIntegration.lua` module with controlled WoW and KeystoneLoot globals. Pin
it in `tests/runtime/requirements.txt`, install that file in every CI workflow that runs runtime
tests, and run `tests/runtime` in those workflows. Tests must not depend on a
machine-global Lua installation.

Cover:

- API absent and normal save continuity;
- unsupported API version and preserved diagnostics;
- supported ready API with multiple sources/specs/tiers, duplicate item IDs across specs,
  optional item modifiers, and Catalyst;
- authoritative empty favorites replacing stale favorites;
- Voidcore `true` entries normalized to sorted numeric IDs while false/nil entries are
  excluded and `checked` is preserved;
- READY registration and immediate capture;
- aggregate `FAVORITES_CHANGED` refresh;
- debounce coalescing;
- stale KeystoneSync-key rejection;
- stale KeystoneLoot-character-key rejection;
- logout performs at most one synchronous snapshot and rejects previously pending work;
- `/ksync` performs exactly one snapshot and reports that stored result;
- integration exceptions not interrupting normal `SaveCharacterData()` behavior.

Existing Season 2, deployment-impact, release, and package tests remain required.

## Documentation and release metadata

Update the addon README with the optional dependency and local SavedVariables block. Add
a Spanish pending patch changeset for the addon. Do not bump `KeystoneSync.toc` version.

## Verification

Run:

```text
python -m unittest discover -s tests/runtime
python -m unittest discover -s tests/deploy_impact
python -m unittest discover -s tests/release
python scripts/package_addon.py validate --version 0.2.2
python scripts/package_addon.py package --version 0.2.2 --output-dir <temporary-dir>
python scripts/deploy_impact.py --files <changed-paths> --json --strict
```

Install the runtime-test dependency first with
`python -m pip install -r tests/runtime/requirements.txt` in a disposable virtual environment or
the CI runner environment.

Inspect the fixture-generated SavedVariables table and final package contents. Manual
in-game verification remains required for actual addon load order, chat output, READY
timing, favorite mutations/imports, Voidcore data, logout safety, and coexistence with
normal KeystoneSync tracking.

## Out of scope

- KeystoneClient, Worker, D1, Web, or weeklyChar changes.
- Item names, item-cache loading, wishlist UI, rendering, recommendation scoring, or team
  planning.
- KeystoneLoot writes or behavioral changes.
- Addon version bump, commit, push, merge, tag, release, or V1-B work.
