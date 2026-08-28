import unittest

from lua_harness import ROOT, LuaAddonHarness, lua_to_python


class KeystoneLootIntegrationRuntimeTests(unittest.TestCase):
    def make_harness(self):
        harness = LuaAddonHarness()
        namespace = harness.load_addon_file("KeystoneLootIntegration.lua")
        harness.execute(
            """
            _test.ksKey = "Zul'jin-Spee"
            _test.klKey = "Zul'jin-Spee-3"
            KeystoneSyncDB = {
                [_test.ksKey] = { normalData = "preserved" },
                ["Other-Realm-Historical"] = { normalData = "historical" },
            }
            """
        )
        return harness, namespace["KeystoneLootIntegration"]

    @staticmethod
    def start(harness, integration):
        provider = harness.evaluate("function() return _test.ksKey end")
        return integration["Start"](integration, provider)

    def callback(self, harness, event):
        registration = harness.globals._test.callbacks[event]
        self.assertIsNotNone(registration, f"{event} callback must be registered")
        return registration["callback"]

    def test_module_exposes_isolated_integration_interface(self):
        self.assertTrue(
            (ROOT / "KeystoneLootIntegration.lua").is_file(),
            "production integration module must exist",
        )
        harness = LuaAddonHarness()
        namespace = harness.load_addon_file("KeystoneLootIntegration.lua")

        integration = namespace["KeystoneLootIntegration"]

        self.assertIsNotNone(integration)
        self.assertIsNotNone(integration["Start"])
        self.assertIsNotNone(integration["RefreshCurrent"])
        self.assertIsNotNone(integration["Stop"])
        self.assertIsNotNone(integration["FormatDiagnostic"])

    def test_api_absent_writes_explicit_not_installed_state(self):
        harness, integration = self.make_harness()

        self.start(harness, integration)

        self.assertEqual(
            harness.stored_keystone_loot("Zul'jin-Spee"),
            {
                "state": "not_installed",
                "installed": False,
                "supported": False,
                "favorites": [],
            },
        )
        self.assertEqual(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["normalData"],
            "preserved",
        )

    def test_installed_file_without_api_is_installed_not_ready(self):
        harness, integration = self.make_harness()
        harness.execute("_test.addonInstalled = true")

        self.start(harness, integration)

        self.assertEqual(
            harness.stored_keystone_loot("Zul'jin-Spee"),
            {
                "state": "installed_not_ready",
                "installed": True,
                "supported": False,
                "favorites": [],
            },
        )

    def test_unsupported_api_preserves_detected_versions(self):
        harness, integration = self.make_harness()
        harness.execute(
            """
            _test.addonInstalled = true
            KeystoneLootAPI = {
                GetVersion = function() return 99, "9.9.9" end,
            }
            """
        )

        self.start(harness, integration)

        self.assertEqual(
            harness.stored_keystone_loot("Zul'jin-Spee"),
            {
                "state": "unsupported_api",
                "installed": True,
                "supported": False,
                "apiVersion": 99,
                "addonVersion": "9.9.9",
                "favorites": [],
            },
        )

    def test_api_v2_missing_callback_contract_is_unsupported(self):
        harness, integration = self.make_harness()
        harness.execute(
            """
            _test.addonInstalled = true
            KeystoneLootAPI = {
                GetVersion = function() return 2, "broken-v2" end,
                IsReady = function() return true end,
                GetCurrentCharacterKey = function() return _test.klKey end,
                GetFavorites = function() return {} end,
            }
            """
        )

        self.start(harness, integration)

        self.assertEqual(
            harness.stored_keystone_loot("Zul'jin-Spee"),
            {
                "state": "unsupported_api",
                "installed": True,
                "supported": False,
                "apiVersion": 2,
                "addonVersion": "broken-v2",
                "favorites": [],
            },
        )

    def install_ready_api(self, harness, favorites_source: str) -> None:
        harness.execute(
            f"""
            _test.addonInstalled = true
            _test.favoriteCalls = 0
            _test.callbacks = {{}}
            _test.ready = true
            KeystoneLootAPI = {{
                Event = {{ READY = "READY", FAVORITES_CHANGED = "FAVORITES_CHANGED" }},
                GetVersion = function() return 2, "2.6.0" end,
                IsReady = function() return _test.ready end,
                GetCurrentCharacterKey = function() return _test.klKey end,
                GetFavorites = function(self, characterKey)
                    _test.favoriteCalls = _test.favoriteCalls + 1
                    _test.lastFavoriteCharacterKey = characterKey
                    return {favorites_source}
                end,
                GetSourceInfo = function(self, sourceId)
                    if sourceId == 558 then return {{ type = "dungeon", name = "Localized Dungeon" }} end
                    if sourceId == 9001 then return {{ type = "raid", name = "Localized Boss" }} end
                    if sourceId == "catalyst" then return {{ type = "catalyst" }} end
                    if sourceId == "custom" then return {{ type = "custom" }} end
                    return nil
                end,
                GetItemInfo = function(self, itemId)
                    local items = {{
                        [251119] = {{ itemId = 251119, slotId = 10, icon = 7259236 }},
                        [251120] = {{ itemId = 251120, slotId = 12, icon = 7259237 }},
                        [251121] = {{ itemId = 251121, slotId = 1, icon = 7259238, isCatalyst = true }},
                        [251122] = {{ itemId = 251122, icon = 7259239, isCustom = true }},
                    }}
                    return items[itemId]
                end,
                RegisterCallback = function(self, event, callback, owner)
                    _test.callbacks[event] = {{ callback = callback, owner = owner }}
                    if event == "READY" and _test.ready then callback("READY") end
                    return true
                end,
                UnregisterCallback = function(self, event, owner)
                    if _test.callbacks[event] and _test.callbacks[event].owner == owner then
                        _test.callbacks[event] = nil
                    end
                    return true
                end,
            }}
            """
        )

    def test_ready_api_normalizes_public_favorites_and_generic_numeric_tiers(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3,
                  bonusIds = { 6652, 1498 }, gems = { 213743 }, enchant = 7334 },
                { sourceId = 9001, specId = 254, itemId = 251119, tier = 7 },
                { sourceId = "catalyst", specId = 255, itemId = 251121, tier = 5 },
                { sourceId = "custom", specId = 255, itemId = 251122, tier = 2 },
            }""",
        )
        harness.execute(
            """
            KeystoneLootCharDB = {
                voidcoreChecked = true,
                voidcore = { [251079] = true, [249343] = true, [999999] = false },
            }
            """
        )

        self.start(harness, integration)

        snapshot = harness.stored_keystone_loot("Zul'jin-Spee")
        self.assertIsNotNone(snapshot, "ready API must write an authoritative snapshot")
        self.assertEqual(snapshot["state"], "supported")
        self.assertEqual(snapshot["apiVersion"], 2)
        self.assertEqual(snapshot["addonVersion"], "2.6.0")
        self.assertEqual(snapshot["characterKey"], "Zul'jin-Spee-3")
        self.assertEqual(snapshot["updatedAt"], 1780000000)
        self.assertEqual(snapshot["voidcore"], {"checked": True, "usedItems": [249343, 251079]})
        self.assertEqual(
            snapshot["favorites"],
            [
                {
                    "sourceId": 558,
                    "sourceType": "dungeon",
                    "specId": 255,
                    "itemId": 251119,
                    "tier": 3,
                    "slotId": 10,
                    "icon": 7259236,
                    "bonusIds": [6652, 1498],
                    "gems": [213743],
                    "enchant": 7334,
                },
                {
                    "sourceId": 9001,
                    "sourceType": "raid",
                    "specId": 254,
                    "itemId": 251119,
                    "tier": 7,
                    "slotId": 10,
                    "icon": 7259236,
                },
                {
                    "sourceId": "catalyst",
                    "sourceType": "catalyst",
                    "specId": 255,
                    "itemId": 251121,
                    "tier": 5,
                    "slotId": 1,
                    "icon": 7259238,
                },
                {
                    "sourceId": "custom",
                    "sourceType": "custom",
                    "specId": 255,
                    "itemId": 251122,
                    "tier": 2,
                    "icon": 7259239,
                },
            ],
        )
        self.assertEqual(harness.evaluate("_test.lastFavoriteCharacterKey"), "Zul'jin-Spee-3")

    def test_ready_empty_favorites_replace_stale_snapshot(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        harness.execute(
            """
            KeystoneSyncDB[_test.ksKey].keystoneLoot = {
                state = "supported",
                favorites = { { itemId = 12345 } },
            }
            """
        )

        self.start(harness, integration)

        self.assertEqual(harness.stored_keystone_loot("Zul'jin-Spee")["favorites"], [])

    def test_favorites_api_failure_cannot_leave_a_stale_supported_snapshot(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        harness.execute(
            """
            KeystoneSyncDB[_test.ksKey].keystoneLoot = {
                state = "supported",
                favorites = { { itemId = 12345 } },
            }
            KeystoneLootAPI.GetFavorites = function() error("upstream failure") end
            """
        )

        self.start(harness, integration)

        snapshot = harness.stored_keystone_loot("Zul'jin-Spee")
        self.assertEqual(snapshot["state"], "installed_not_ready")
        self.assertEqual(snapshot["favorites"], [])

    def test_voidcore_unchecked_and_false_entries_are_preserved_correctly(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        harness.execute(
            """
            KeystoneLootCharDB = {
                voidcoreChecked = false,
                voidcore = { [251079] = true, [249343] = false, ["251080"] = true },
            }
            """
        )

        self.start(harness, integration)

        snapshot = harness.stored_keystone_loot("Zul'jin-Spee")
        self.assertIsNotNone(snapshot, "ready API must write Voidcore state")
        self.assertEqual(
            snapshot["voidcore"],
            {"checked": False, "usedItems": [251079, 251080]},
        )

    def test_refresh_updates_only_the_current_existing_character_record(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")

        self.start(harness, integration)

        historical = harness.globals.KeystoneSyncDB["Other-Realm-Historical"]
        self.assertIsNone(historical["keystoneLoot"])
        self.assertEqual(historical["normalData"], "historical")

    def test_diagnostics_are_concise_and_report_the_stored_state(self):
        harness, integration = self.make_harness()
        cases = [
            (
                '{ state = "supported", apiVersion = 2, favorites = { {}, {}, {} } }',
                "KeystoneLoot: detectado, API v2, 3 favoritos.",
            ),
            (
                '{ state = "unsupported_api", apiVersion = 99, favorites = {} }',
                "KeystoneLoot detectado, pero la API v99 no es compatible.",
            ),
            (
                '{ state = "installed_not_ready", favorites = {} }',
                "KeystoneLoot detectado, pero todavía no está listo.",
            ),
            (
                '{ state = "not_installed", favorites = {} }',
                "KeystoneLoot no detectado.",
            ),
        ]

        for source, expected in cases:
            with self.subTest(expected=expected):
                snapshot = harness.evaluate(source)
                self.assertEqual(
                    integration["FormatDiagnostic"](integration, snapshot),
                    expected,
                )

    def test_start_registers_only_public_ready_and_aggregate_change_callbacks(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")

        self.start(harness, integration)

        events = set(harness.globals._test.callbacks.keys())
        self.assertEqual(events, {"READY", "FAVORITES_CHANGED"})
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)

    def test_later_ready_callback_writes_one_authoritative_snapshot(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        harness.execute("_test.ready = false")

        self.start(harness, integration)
        self.assertEqual(harness.stored_keystone_loot("Zul'jin-Spee")["state"], "installed_not_ready")
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 0)

        ready_callback = self.callback(harness, "READY")
        harness.execute("_test.ready = true")
        ready_callback("READY")

        self.assertEqual(harness.stored_keystone_loot("Zul'jin-Spee")["state"], "supported")
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)

    def test_favorites_changed_events_are_debounced_into_one_refresh(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        self.start(harness, integration)
        callback = self.callback(harness, "FAVORITES_CHANGED")

        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")
        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")
        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")

        self.assertEqual(harness.timer_count(), 1)
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)
        harness.run_timers()
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 2)

    def test_non_current_favorite_change_does_not_schedule_refresh(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        self.start(harness, integration)
        callback = self.callback(harness, "FAVORITES_CHANGED")

        callback("FAVORITES_CHANGED", "Other-Realm-2")

        self.assertEqual(harness.timer_count(), 0)
        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)

    def test_debounced_refresh_rejects_changed_keystonesync_character(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        self.start(harness, integration)
        callback = self.callback(harness, "FAVORITES_CHANGED")
        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")

        harness.execute("_test.ksKey = \"Other-Realm-Historical\"")
        harness.run_timers()

        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)
        self.assertIsNone(
            harness.globals.KeystoneSyncDB["Other-Realm-Historical"]["keystoneLoot"]
        )

    def test_debounced_refresh_rejects_changed_keystoneloot_character(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        self.start(harness, integration)
        callback = self.callback(harness, "FAVORITES_CHANGED")
        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")

        harness.execute("_test.klKey = \"Other-Realm-2\"")
        harness.run_timers()

        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)

    def test_stop_unregisters_callbacks_and_rejects_previously_pending_work(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")
        self.start(harness, integration)
        callback = self.callback(harness, "FAVORITES_CHANGED")
        callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")
        self.assertEqual(harness.timer_count(), 1)

        integration["Stop"](integration)
        harness.run_timers()

        self.assertEqual(harness.evaluate("_test.favoriteCalls"), 1)
        self.assertEqual(list(harness.globals._test.callbacks.keys()), [])


class KeystoneSyncIntegrationLifecycleTests(unittest.TestCase):
    def make_runtime(self):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.install_integration_spy()
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    @staticmethod
    def fire(harness, event):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, event)

    @staticmethod
    def calls(harness):
        return lua_to_python(harness.globals._test.integrationCalls)

    def test_toc_declares_optional_dependency_and_loads_isolated_module_first(self):
        toc = (ROOT / "KeystoneSync.toc").read_text(encoding="utf-8")
        lines = [line.strip() for line in toc.splitlines() if line.strip()]

        self.assertIn("## OptionalDeps: KeystoneLoot", lines)
        self.assertLess(
            lines.index("KeystoneLootIntegration.lua"),
            lines.index("KeystoneSync.lua"),
        )

    def test_player_login_saves_normal_record_before_starting_integration(self):
        harness = self.make_runtime()

        self.fire(harness, "PLAYER_LOGIN")

        self.assertEqual(self.calls(harness), ["start"])
        self.assertTrue(harness.evaluate("_test.recordExistsAtStart"))
        record = harness.globals.KeystoneSyncDB["Zul'jin-Spee"]
        self.assertEqual(record["updatedReason"], "PLAYER_LOGIN")
        self.assertEqual(record["money"]["copper"], 12345)

    def test_ordinary_save_performs_one_protected_integration_refresh(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.integrationCalls = {}")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        self.assertEqual(self.calls(harness), ["refresh"])
        self.assertEqual(harness.evaluate("_test.reasonAtRefresh"), "BAG_UPDATE_DELAYED")

    def test_player_logout_saves_once_then_stops_integration(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.integrationCalls = {}")

        self.fire(harness, "PLAYER_LOGOUT")

        self.assertEqual(self.calls(harness), ["refresh", "stop"])
        self.assertEqual(harness.evaluate("_test.reasonAtRefresh"), "PLAYER_LOGOUT")

    def test_manual_command_refreshes_once_and_diagnoses_the_stored_snapshot(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.integrationCalls = {}; _test.prints = {}")

        harness.globals.SlashCmdList["KEYSTONESYNC"]()

        self.assertEqual(self.calls(harness), ["refresh", "diagnostic"])
        self.assertEqual(harness.evaluate("_test.diagnosticState"), "supported")
        self.assertTrue(
            any(
                "KeystoneLoot diagnostic" in line
                for line in lua_to_python(harness.globals._test.prints)
            )
        )

    def test_integration_exception_cannot_interrupt_normal_character_save(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.integrationCalls = {}; _test.throwIntegration = true")

        self.fire(harness, "BAG_UPDATE_DELAYED")

        self.assertEqual(self.calls(harness), ["refresh"])
        record = harness.globals.KeystoneSyncDB["Zul'jin-Spee"]
        self.assertEqual(record["character"], "Spee")
        self.assertEqual(record["realm"], "Zul'jin")
        self.assertEqual(record["ilvl"], 700)
        self.assertEqual(record["money"]["copper"], 12345)
        self.assertEqual(record["updatedReason"], "BAG_UPDATE_DELAYED")


if __name__ == "__main__":
    unittest.main()
