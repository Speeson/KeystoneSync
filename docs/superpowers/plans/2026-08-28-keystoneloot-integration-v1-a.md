# KeystoneLoot Integration V1-A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture the current character's optional KeystoneLoot wishlist and Voidcore state in `KeystoneSyncDB[key].keystoneLoot` without allowing integration failures or delayed work to affect normal KeystoneSync tracking.

**Architecture:** A new `KeystoneLootIntegration.lua` module owns the entire external-addon boundary, normalization, callbacks, debounce, generation, and diagnostics. `KeystoneSync.lua` invokes only the module's small lifecycle/refresh interface after normal saves, with explicit login, logout, and slash-command ordering. Real Lua behavior is exercised from Python `unittest` through pinned `lupa==2.8`.

**Tech Stack:** World of Warcraft Lua, Python 3 `unittest`, `lupa==2.8`, GitHub Actions, existing Python packaging/release tools.

**Spec:** `docs/superpowers/specs/2026-08-28-keystoneloot-integration-v1-a-design.md`

## Global Constraints

- Work only in `Speeson/KeystoneSync` on `feature/keystoneloot-integration-v1`, based on `5703e67`.
- Support only verified public KeystoneLoot API version `2`; detect readiness only with `IsReady()` and `READY`.
- Use public API calls for favorites, source, and item data; access only `KeystoneLootCharDB.voidcore` and `voidcoreChecked` directly and read-only.
- Preserve arbitrary numeric tiers; do not validate against or encode a fixed tier range.
- Only the currently logged-in character processed by `SaveCharacterData()` may be updated; never backfill historical records.
- A supported, ready empty favorites response is authoritative and replaces old favorites.
- After `PLAYER_LOGOUT` handling completes, no KeystoneLoot callback or timer may write.
- `/ksync` performs exactly one authoritative KeystoneLoot refresh and reports that stored result.
- Do not change KeystoneClient, Worker, D1, Web, weeklyChar, item names/UI/scoring, or V1-B behavior.
- Add a Spanish pending patch changeset but do not bump version, commit, push, merge, tag, or release.

---

### Task 1: Provide a reproducible real-Lua runtime test harness

**Files:**
- Create: `tests/runtime/requirements.txt`
- Create: `tests/runtime/lua_harness.py`
- Create: `tests/runtime/test_keystoneloot_integration.py`
- Modify: `.github/workflows/build-addon.yml`
- Modify: `.github/workflows/release-addon.yml`

**Interfaces:**
- Consumes: repository-root Lua source files and Python `unittest` discovery.
- Produces: `LuaAddonHarness`, which executes addon chunks with the same addon namespace table and exposes captured frames, timers, prints, globals, and SavedVariables to tests.

- [ ] **Step 1: Pin the test-only Lua runtime**

Create `tests/runtime/requirements.txt`:

```text
lupa==2.8
```

- [ ] **Step 2: Add the minimal harness and first failing module-load test**

Create `LuaAddonHarness` around `lupa.LuaRuntime(unpack_returned_tuples=True)`. Its bootstrap Lua must define `CreateFrame`, `C_Timer.After`, `C_AddOns.GetAddOnInfo`, a captured `print`, `time`, and the table helpers required by the integration module. Add:

```python
class KeystoneLootIntegrationRuntimeTests(unittest.TestCase):
    def test_module_exposes_isolated_integration_interface(self):
        harness = LuaAddonHarness()
        namespace = harness.load_addon_file("KeystoneLootIntegration.lua")
        integration = namespace["KeystoneLootIntegration"]
        self.assertIsNotNone(integration)
        self.assertIsNotNone(integration["Start"])
        self.assertIsNotNone(integration["RefreshCurrent"])
        self.assertIsNotNone(integration["Stop"])
        self.assertIsNotNone(integration["FormatDiagnostic"])
```

- [ ] **Step 3: Verify RED**

Run:

```text
python -m pip install -r tests/runtime/requirements.txt
python -m unittest tests.runtime.test_keystoneloot_integration.KeystoneLootIntegrationRuntimeTests.test_module_exposes_isolated_integration_interface
```

Expected: FAIL because `KeystoneLootIntegration.lua` does not exist.

- [ ] **Step 4: Make CI install and execute the real-Lua tests**

In both addon workflows, add a dependency step before tests:

```yaml
- name: Install test dependencies
  run: python -m pip install -r tests/runtime/requirements.txt
```

Add this command to each existing test step:

```text
python -m unittest discover -s tests/runtime
```

Do not rely on a machine-global `lua` executable.

### Task 2: Implement detection, authoritative snapshots, and normalization

**Files:**
- Create: `KeystoneLootIntegration.lua`
- Modify: `tests/runtime/test_keystoneloot_integration.py`

**Interfaces:**
- Consumes: `_G.KeystoneLootAPI`, `C_AddOns.GetAddOnInfo`, current `KeystoneSyncDB`, read-only `KeystoneLootCharDB`, and a `getKeystoneSyncKey()` provider.
- Produces:
  - `Integration:RefreshCurrent()` -> stored snapshot table or `nil`.
  - `Integration:FormatDiagnostic(snapshot)` -> concise localized string.
  - states `not_installed`, `installed_not_ready`, `supported`, `unsupported_api`.

- [ ] **Step 1: Write failing unavailable and unsupported tests**

Add fixtures that pre-create only `KeystoneSyncDB["Zul'jin-Spee"]`. Assert API absence writes:

```python
{
    "state": "not_installed",
    "installed": False,
    "supported": False,
    "favorites": [],
}
```

When `C_AddOns.GetAddOnInfo("KeystoneLoot")` reports an installed addon but the API is absent, assert `installed_not_ready`, `installed=true`, and `favorites={}`. With `GetVersion()` returning `99, "9.9.9"`, assert `unsupported_api`, preserved versions, and no exception.

- [ ] **Step 2: Verify RED for unavailable states**

Run the three named tests and confirm they fail because `RefreshCurrent` has no implementation.

- [ ] **Step 3: Implement defensive detection and state persistence**

Create the addon namespace module:

```lua
local _, KeystoneSync = ...
KeystoneSync.KeystoneLootIntegration = {}
local Integration = KeystoneSync.KeystoneLootIntegration
local SUPPORTED_API_VERSION = 2
```

Type-check every external method and invoke it through a small `SafeCall(api, methodName, ...)` helper using `pcall`. Detect installed files with protected `C_AddOns.GetAddOnInfo("KeystoneLoot")`. `RefreshCurrent()` must call only the configured key provider, require `KeystoneSyncDB[key]` to already exist, and replace only that record's `keystoneLoot` block.

- [ ] **Step 4: Verify GREEN for unavailable states**

Run the named tests, then the entire new runtime test module.

- [ ] **Step 5: Write failing ready-snapshot tests**

Provide API v2 favorites covering dungeon, raid, Catalyst, custom, duplicate item IDs in different specs, tier `5`, and a synthetic future numeric tier such as `7`. Return source/item enrichment and optional modifiers. Assert literal normalized entries with no localized names.

Set prior favorites, return an empty Lua array, and assert the stored list becomes empty. Set Voidcore keys with numeric/string numeric IDs mapped to true/false and assert only true numeric IDs survive in ascending order while `checked=false` remains false.

- [ ] **Step 6: Verify RED for supported snapshots**

Run the ready, empty, and Voidcore tests and confirm the failure is missing normalization.

- [ ] **Step 7: Implement supported snapshot normalization**

Call in order:

```lua
api:GetVersion()
api:IsReady()
api:GetCurrentCharacterKey()
api:GetFavorites(characterKey)
api:GetSourceInfo(entry.sourceId)
api:GetItemInfo(entry.itemId)
```

Copy only `sourceId`, `sourceType`, `specId`, `itemId`, `tier`, `slotId`, `icon`, `bonusIds`, `gems`, and `enchant`. Copy array fields into KeystoneSync-owned tables, preserve arbitrary numeric tier values, sort Voidcore item IDs numerically, and write an authoritative empty array when returned.

- [ ] **Step 8: Verify GREEN for supported snapshots**

Run the new test module and confirm all state, normalization, empty, and Voidcore tests pass.

### Task 3: Implement READY, aggregate change debounce, and stale-character safety

**Files:**
- Modify: `KeystoneLootIntegration.lua`
- Modify: `tests/runtime/test_keystoneloot_integration.py`

**Interfaces:**
- Produces:
  - `Integration:Start(getKeystoneSyncKey)` -> current stored snapshot or `nil`.
  - `Integration:Stop()` -> no return; invalidates generation and unregisters callbacks.
  - stable callback owner token used only with `READY` and `FAVORITES_CHANGED`.

- [ ] **Step 1: Write failing READY and aggregate-event tests**

Use a fake API that captures callback registrations and implements immediate READY delivery when already ready. Assert `Start()` registers only `READY` and `FAVORITES_CHANGED`, an already-ready API writes once, a later READY writes once, and one aggregate change refreshes only the integration block.

- [ ] **Step 2: Verify RED**

Run the READY and event tests; confirm failure is missing lifecycle registration.

- [ ] **Step 3: Implement lifecycle registration without duplicate ready captures**

`Start()` stores the key provider, activates a new generation, registers callbacks through `pcall`, and tracks whether READY fired synchronously. If READY did not fire, it writes the current unavailable/not-ready state or captures once when `IsReady()` already returns true. Never register individual mutation events.

- [ ] **Step 4: Verify GREEN for readiness**

Run the READY tests and confirm each scenario writes exactly once.

- [ ] **Step 5: Write failing debounce and stale-key tests**

Queue multiple `FAVORITES_CHANGED` events and assert one timer and one final snapshot. Before executing the queued timer, separately change the KeystoneSync key and KeystoneLoot current-character key; assert neither stale case writes. Assert events for a non-current KeystoneLoot character never schedule work.

- [ ] **Step 6: Verify RED for stale-key safety**

Run the debounce and stale-character tests and confirm they fail because delayed validation is absent.

- [ ] **Step 7: Implement coalescing and dual-key validation**

On aggregate change, capture generation, KeystoneSync key, and KeystoneLoot key. Schedule at most one `C_Timer.After` call. Before writing, require active generation equality and exact equality for both freshly read keys. Clear the pending flag even when rejecting a stale write.

- [ ] **Step 8: Write and pass the logout-stop test**

Queue delayed work, call `Stop()`, run the queued timer, and assert no write. Assert `Stop()` increments generation, sets inactive state, clears pending bookkeeping, and protectedly unregisters `READY` and `FAVORITES_CHANGED` with the stable owner.

### Task 4: Integrate the module with the normal save lifecycle exactly once

**Files:**
- Modify: `KeystoneSync.toc`
- Modify: `KeystoneSync.lua`
- Modify: `tests/runtime/lua_harness.py`
- Modify: `tests/runtime/test_keystoneloot_integration.py`

**Interfaces:**
- Consumes: the module interface from Tasks 2-3.
- Produces: login/start, ordinary save/refresh, logout save-then-stop, and `/ksync` save-once-then-diagnostic behavior.

- [ ] **Step 1: Write failing TOC and full-runtime lifecycle tests**

Assert TOC metadata contains `## OptionalDeps: KeystoneLoot` and file order is:

```text
KeystoneLootIntegration.lua
KeystoneSync.lua
```

Load both Lua files into one namespace with WoW API stubs. Inject an integration spy and assert:

- `PLAYER_LOGIN`: normal record is written before `Start(GetCharacterKey)`;
- ordinary save events invoke exactly one protected `RefreshCurrent()`;
- `PLAYER_LOGOUT`: one final synchronous refresh occurs, then `Stop()`, with no later queued write;
- `/ksync`: exactly one refresh occurs and diagnostic uses that stored snapshot;
- a throwing integration spy still leaves normal character, keystone, vault, currency, money, and timestamps written.

- [ ] **Step 2: Verify RED**

Run the full-runtime lifecycle tests and confirm the current single-file runtime lacks the integration calls.

- [ ] **Step 3: Add TOC metadata and namespace access**

Add the optional dependency and module file before `KeystoneSync.lua`. Change the main chunk header to receive the shared addon namespace without changing `ADDON_NAME` semantics.

- [ ] **Step 4: Add one protected post-save refresh path**

Make `SaveCharacterData(reason, updateSeason, refreshKeystoneLoot)` finish all normal writes first. Unless `refreshKeystoneLoot == false`, invoke exactly one `Integration:RefreshCurrent()` inside `pcall` and return the resulting block for diagnostics. Do not let `RefreshCurrent()` register callbacks or schedule timers.

- [ ] **Step 5: Implement explicit event ordering**

Use these flows:

```text
PLAYER_LOGIN -> SaveCharacterData(..., false refresh) -> protected Start()
PLAYER_LOGOUT -> SaveCharacterData(..., one synchronous refresh) -> protected Stop()
other save event -> SaveCharacterData(..., one synchronous refresh)
/ksync -> SaveCharacterData(..., one synchronous refresh) -> print stored diagnostic
```

The slash handler must not call `RefreshCurrent()` again. `Stop()` is always after the final logout save.

- [ ] **Step 6: Verify GREEN and regression safety**

Run the focused full-runtime tests, all runtime tests, and confirm the existing seven Season 2 tests still pass.

### Task 5: Document the local contract and add release metadata

**Files:**
- Modify: `README.md`
- Create: `.changes/pending/keystoneloot-integration-v1-a.json`

**Interfaces:**
- Documents: optional dependency, state meanings, local-only SavedVariables shape, empty-list semantics, and `/ksync` diagnostics.
- Produces: valid Spanish addon patch changeset without changing `KeystoneSync.toc` version `0.2.2`.

- [ ] **Step 1: Update README**

Add `keystoneLoot` to the SavedVariables field table and document that KeystoneLoot is optional. Include the state values and normalized fields, explicitly noting the block is current-character/local-only and empty favorites are authoritative.

- [ ] **Step 2: Add the pending changeset**

Create:

```json
{
  "components": ["addon"],
  "type": "patch",
  "category": "added",
  "summary": "Integra de forma opcional la lista de deseos de KeystoneLoot.",
  "details": [
    "Guarda favoritos normalizados y el estado de Voidcore del personaje actual en SavedVariables.",
    "KeystoneSync sigue funcionando aunque KeystoneLoot no esté disponible, listo o use una API incompatible."
  ]
}
```

- [ ] **Step 3: Validate release metadata without bumping**

Run release tests and `python scripts/package_addon.py validate --version 0.2.2`.

### Task 6: Final verification, contract inspection, and self-review

**Files:**
- Review all changed files only.

**Interfaces:**
- Produces: verified V1-A worktree and representative fixture-generated snapshot for handoff.

- [ ] **Step 1: Run all automated validation without creating bytecode noise**

Set `PYTHONDONTWRITEBYTECODE=1` and run:

```text
python -m compileall -q scripts tests
python -m unittest discover -s tests/runtime
python -m unittest discover -s tests/deploy_impact
python -m unittest discover -s tests/release
python scripts/package_addon.py validate --version 0.2.2
python scripts/package_addon.py package --version 0.2.2 --output-dir <temporary-directory> --print-path
```

- [ ] **Step 2: Generate and inspect the representative contract**

Run the ready fixture through the real Lua module, convert only the stored Lua table to a Python display structure, and print the resulting `KeystoneSyncDB[key].keystoneLoot`. Verify numeric IDs/tiers, source type, optional modifiers, Voidcore sorting, versions, state, character key, and timestamp.

- [ ] **Step 3: Run deterministic deployment impact**

Pass every changed path to:

```text
python scripts/deploy_impact.py --files <changed-paths> --json --strict
```

Report required consideration only; perform no remote operation.

- [ ] **Step 4: Review the diff**

Run `git diff --check`, inspect `git diff`, confirm version remains `0.2.2`, and run the code-review checklist for correctness, security, scope, and consistency. Remove generated caches/artifacts from the worktree.

- [ ] **Step 5: Report without committing or publishing**

Report files changed, API version/functions/events, final contract and unavailable states, tests/results, assumptions, branch/status, representative fixture snapshot, and manual in-game checks. Do not commit, push, merge, tag, release, or start V1-B.
