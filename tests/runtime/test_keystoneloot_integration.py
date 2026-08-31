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

    @staticmethod
    def show_item_tooltip(harness, item_link: str) -> None:
        harness.globals._test.previewLink = item_link
        harness.execute(
            """
            local callback = _test.tooltipCallbacks[Enum.TooltipDataType.Item]
            assert(callback, "item tooltip callback must be registered")
            callback({
                KeystoneLootOwned = true,
                GetItem = function()
                    return "Preview item", _test.previewLink
                end,
            }, {})
            """
        )

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
        self.assertIsNotNone(integration["FormatFavoriteDiagnostics"])

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
                Event = {{
                    READY = "READY",
                    FAVORITE_ADDED = "FAVORITE_ADDED",
                    FAVORITE_REMOVED = "FAVORITE_REMOVED",
                    FAVORITES_IMPORTED = "FAVORITES_IMPORTED",
                    FAVORITES_CHANGED = "FAVORITES_CHANGED",
                }},
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
                GetItemSource = function(self, itemId)
                    if itemId == 251121 then return "catalyst" end
                    if itemId == 251122 then return "custom" end
                    return 558
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
                    "variantKey": "bonus:1498,6652",
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
                    "variantKey": "base",
                },
                {
                    "sourceId": "catalyst",
                    "sourceType": "catalyst",
                    "specId": 255,
                    "itemId": 251121,
                    "tier": 5,
                    "slotId": 1,
                    "icon": 7259238,
                    "variantKey": "base",
                },
                {
                    "sourceId": "custom",
                    "sourceType": "custom",
                    "specId": 255,
                    "itemId": 251122,
                    "tier": 2,
                    "icon": 7259239,
                    "variantKey": "base",
                },
            ],
        )
        self.assertEqual(harness.evaluate("_test.lastFavoriteCharacterKey"), "Zul'jin-Spee-3")

    def test_exact_favorite_variant_metadata_uses_saved_bonus_ids(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3,
                  bonusIds = { 6652, 1498 } },
            }""",
        )
        harness.execute(
            """
            _test.loadedLinks = {}
            C_Item = {
                GetDetailedItemLevelInfo = function(link)
                    _test.lastDetailedLink = link
                    return 402
                end,
                GetItemInfo = function(link)
                    _test.lastInfoLink = link
                    return "Exact favorite", link, 4
                end,
            }
            Item = {
                CreateFromItemLink = function(link)
                    table.insert(_test.loadedLinks, link)
                    return { ContinueOnItemLoad = function(_, callback) callback() end }
                end,
            }
            """
        )

        self.start(harness, integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["bonusIds"], [6652, 1498])
        self.assertEqual(favorite["variantKey"], "bonus:1498,6652")
        self.assertEqual(favorite["itemLevel"], 402)
        self.assertEqual(favorite["qualityType"], "EPIC")
        self.assertIn(":2:6652:1498", harness.evaluate("_test.lastDetailedLink"))

    def test_normal_ui_favorite_without_bonus_ids_never_persists_base_metadata_as_exact(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{{ sourceId = 558, specId = 255, itemId = 251119, tier = 3 }}""",
        )
        harness.execute(
            """
            _test.metadataReads = 0
            C_Item = {
                GetDetailedItemLevelInfo = function()
                    _test.metadataReads = _test.metadataReads + 1
                    return 28
                end,
                GetItemInfo = function()
                    _test.metadataReads = _test.metadataReads + 1
                    return "Sparse base item", "item:251119", 3
                end,
            }
            """
        )

        self.start(harness, integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["variantKey"], "base")
        self.assertNotIn("itemLevel", favorite)
        self.assertNotIn("qualityType", favorite)
        self.assertEqual(harness.evaluate("_test.metadataReads"), 0)

    def test_non_keystoneloot_item_tooltip_is_never_used_for_favorite_capture(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 255, dungeon = { track = "hero", rank = 1 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 305 end,
                GetItemInfo = function(link) return "Unrelated item", link, 4 end,
            }
            _test.previewLink = "item:251119::::::::90:255:::2:3206:12841"
            _test.favorites = {
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3 },
            }
            """
        )
        self.start(harness, integration)
        harness.execute(
            """
            _test.tooltipCallbacks[Enum.TooltipDataType.Item]({
                GetItem = function() return "Unrelated item", _test.previewLink end,
            }, {})
            """
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["variantKey"], "base")
        self.assertNotIn("itemLevel", favorite)

    def test_favorite_added_captures_the_recent_exact_keystoneloot_preview(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = {
                    classId = 3,
                    specId = 255,
                    slotId = 10,
                    dungeon = { track = "hero", rank = 5 },
                    raid = { difficulty = "heroic", rank = 1 },
                },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function(link)
                    _test.capturedMetadataLink = link
                    return 318
                end,
                GetItemInfo = function(link)
                    return "Hero preview", link, 4
                end,
            }
            """
        )
        self.start(harness, integration)
        exact_link = "item:251119::::::::90:255:::3:3206:12845:1674"
        self.show_item_tooltip(harness, exact_link)
        harness.execute(
            """
            _test.favorites = {
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3 },
            }
            """
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        self.callback(harness, "FAVORITES_CHANGED")(
            "FAVORITES_CHANGED", "Zul'jin-Spee-3"
        )
        harness.run_timers()

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["bonusIds"], [3206, 12845, 1674])
        self.assertEqual(favorite["variantKey"], "bonus:1674,3206,12845")
        self.assertEqual(favorite["itemLevel"], 318)
        self.assertEqual(favorite["qualityType"], "EPIC")
        capture = lua_to_python(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["keystoneLootFavoriteCaptures"]
        )
        self.assertEqual(len(capture), 1)
        captured = next(iter(capture.values()))
        self.assertEqual(captured["selectedContext"], "dungeon")
        self.assertEqual(captured["selectedTrack"], "hero")
        self.assertEqual(captured["selectedRank"], 5)
        self.assertEqual(captured["linkLevel"], 90)
        self.assertEqual(captured["specId"], 255)
        self.assertEqual(captured["itemContext"], 0)
        self.assertEqual(captured["numBonusIds"], 3)

    def test_exact_preview_can_be_captured_for_a_different_target_spec(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 65, dungeon = { track = "hero", rank = 3 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 311 end,
                GetItemInfo = function(link) return "Hero preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:70:::3:1564:12843:1674"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 65, itemId = 251119, tier = 3 } }"
        )

        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 65, 3
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["bonusIds"], [1564, 12843, 1674])
        self.assertEqual(favorite["variantKey"], "bonus:1564,1674,12843")
        self.assertEqual(favorite["itemLevel"], 311)
        self.assertEqual(favorite["qualityType"], "EPIC")
        capture = next(
            iter(
                harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                    "keystoneLootFavoriteCaptures"
                ].values()
            )
        )
        self.assertEqual(capture["specId"], 65)
        self.assertEqual(capture["linkSpecId"], 70)

    def test_all_specializations_reuses_one_exact_preview_for_each_emitted_spec(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 0, dungeon = { track = "hero", rank = 3 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 311 end,
                GetItemInfo = function(link) return "Hero preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:70:::3:1564:12843:1674"
        )
        harness.execute(
            """
            _test.favorites = {
                { sourceId = 558, specId = 65, itemId = 251119, tier = 3 },
                { sourceId = 558, specId = 66, itemId = 251119, tier = 3 },
                { sourceId = 558, specId = 70, itemId = 251119, tier = 3 },
            }
            """
        )

        callback = self.callback(harness, "FAVORITE_ADDED")
        changed_callback = self.callback(harness, "FAVORITES_CHANGED")
        for spec_id in (65, 66, 70):
            callback("FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, spec_id, 3)
            changed_callback("FAVORITES_CHANGED", "Zul'jin-Spee-3")
        harness.run_timers()

        favorites = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"]
        self.assertEqual([favorite["specId"] for favorite in favorites], [65, 66, 70])
        self.assertEqual(
            {favorite["variantKey"] for favorite in favorites},
            {"bonus:1564,1674,12843"},
        )
        self.assertTrue(all(favorite["itemLevel"] == 311 for favorite in favorites))
        self.assertTrue(all(favorite["qualityType"] == "EPIC" for favorite in favorites))
        self.assertTrue(all(favorite["variantKey"] != "base" for favorite in favorites))
        captures = lua_to_python(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                "keystoneLootFavoriteCaptures"
            ]
        )
        self.assertEqual({capture["specId"] for capture in captures.values()}, {65, 66, 70})
        self.assertEqual({capture["linkSpecId"] for capture in captures.values()}, {70})
        self.assertIsNone(integration["recentPreview"])

    def test_single_emitted_spec_does_not_invent_other_spec_captures(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 70, dungeon = { track = "hero", rank = 3 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 311 end,
                GetItemInfo = function(link) return "Hero preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:70:::3:1564:12843:1674"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 70, itemId = 251119, tier = 3 } }"
        )

        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 70, 3
        )

        captures = lua_to_python(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                "keystoneLootFavoriteCaptures"
            ]
        )
        self.assertEqual([capture["specId"] for capture in captures.values()], [70])

    def test_reusable_preview_is_invalidated_by_item_source_and_ttl_mismatches(self):
        for mismatch in ("item", "source", "ttl"):
            with self.subTest(mismatch=mismatch):
                harness, integration = self.make_harness()
                self.install_ready_api(harness, "_test.favorites")
                harness.execute(
                    """
                    _test.favorites = {}
                    _test.captureSourceId = 558
                    KeystoneLootAPI.GetItemSource = function() return _test.captureSourceId end
                    KeystoneLootCharDB = {
                        ui = { selectedTab = "dungeons" },
                        filters = { specId = 0, dungeon = { track = "hero", rank = 3 } },
                    }
                    C_Item = {
                        GetDetailedItemLevelInfo = function() return 311 end,
                        GetItemInfo = function(link) return "Hero preview", link, 4 end,
                    }
                    """
                )
                self.start(harness, integration)
                self.show_item_tooltip(
                    harness, "item:251119::::::::90:70:::3:1564:12843:1674"
                )
                callback = self.callback(harness, "FAVORITE_ADDED")

                if mismatch == "source":
                    callback("FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 70, 3)
                    harness.execute("_test.captureSourceId = 9001")
                    callback("FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 65, 3)
                    captures = lua_to_python(
                        harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                            "keystoneLootFavoriteCaptures"
                        ]
                    )
                    self.assertEqual(
                        [capture["specId"] for capture in captures.values()], [70]
                    )
                    self.assertIsNone(integration["recentPreview"])
                else:
                    if mismatch == "ttl":
                        harness.execute("_test.now = _test.now + 31")
                    item_id = 251120 if mismatch == "item" else 251119
                    callback("FAVORITE_ADDED", "Zul'jin-Spee-3", item_id, 65, 3)
                    self.assertIsNone(
                        harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                            "keystoneLootFavoriteCaptures"
                        ]
                    )
                    self.assertIsNone(integration["recentPreview"])

    def test_filter_changes_after_capture_do_not_mutate_the_favorite_variant(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = {
                    specId = 255,
                    classId = 3,
                    slotId = 10,
                    dungeon = { track = "hero", rank = 1 },
                },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function(link)
                    return string.find(link, ":12841", 1, true) and 305 or 334
                end,
                GetItemInfo = function(link) return "Preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12841"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        harness.execute(
            'KeystoneLootCharDB.filters.dungeon.track = "greatvault"; '
            "KeystoneLootCharDB.filters.dungeon.rank = 6"
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["itemLevel"], 305)
        self.assertEqual(favorite["bonusIds"], [3206, 12841])

    def test_captured_variant_async_resolution_refreshes_once_and_survives_reload_state(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            _test.itemCallbacks = {}
            _test.itemReady = false
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 255, dungeon = { track = "hero", rank = 5 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function()
                    return _test.itemReady and 318 or nil
                end,
                GetItemInfo = function(link)
                    if not _test.itemReady then return nil end
                    return "Hero preview", link, 4
                end,
            }
            Item = { CreateFromItemLink = function()
                return { ContinueOnItemLoad = function(_, callback)
                    table.insert(_test.itemCallbacks, callback)
                end }
            end }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12845"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)
        self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["bonusIds"], [3206, 12845])
        self.assertNotIn("itemLevel", favorite)

        harness.execute("_test.itemReady = true; _test.itemCallbacks[1]()")
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["itemLevel"], 318)
        self.assertEqual(favorite["qualityType"], "EPIC")
        integration["RefreshCurrent"](integration)
        self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)

        integration["Stop"](integration)
        self.start(harness, integration)
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["itemLevel"], 318)
        self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)

    def test_stale_captured_variant_async_callbacks_honor_all_character_and_generation_guards(self):
        for stale_action in ("generation", "keystonesync_character", "keystoneloot_character"):
            with self.subTest(stale_action=stale_action):
                harness, integration = self.make_harness()
                self.install_ready_api(harness, "_test.favorites")
                harness.execute(
                    """
                    _test.favorites = {}
                    _test.itemCallbacks = {}
                    _test.itemReady = false
                    KeystoneLootCharDB = {
                        ui = { selectedTab = "dungeons" },
                        filters = { specId = 255, dungeon = { track = "hero", rank = 5 } },
                    }
                    C_Item = {
                        GetDetailedItemLevelInfo = function()
                            return _test.itemReady and 318 or nil
                        end,
                        GetItemInfo = function(link)
                            if not _test.itemReady then return nil end
                            return "Hero preview", link, 4
                        end,
                    }
                    Item = { CreateFromItemLink = function()
                        return { ContinueOnItemLoad = function(_, callback)
                            table.insert(_test.itemCallbacks, callback)
                        end }
                    end }
                    """
                )
                self.start(harness, integration)
                self.show_item_tooltip(
                    harness, "item:251119::::::::90:255:::2:3206:12845"
                )
                harness.execute(
                    "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
                )
                self.callback(harness, "FAVORITE_ADDED")(
                    "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
                )
                self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)

                if stale_action == "generation":
                    integration["Stop"](integration)
                elif stale_action == "keystonesync_character":
                    harness.execute('_test.ksKey = "Other-Realm-Historical"')
                else:
                    harness.execute('_test.klKey = "Other-Realm-2"')
                harness.execute("_test.itemReady = true; _test.itemCallbacks[1]()")

                capture = next(
                    iter(
                        harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                            "keystoneLootFavoriteCaptures"
                        ].values()
                    )
                )
                self.assertIsNone(capture["itemLevel"])
                self.assertIsNone(capture["qualityType"])

    def test_remove_then_readd_replaces_the_captured_variant(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 255, classId = 3, slotId = 10,
                    dungeon = { track = "hero", rank = 1 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function(link)
                    return string.find(link, ":12841", 1, true) and 305 or 334
                end,
                GetItemInfo = function(link) return "Preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12841"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )

        harness.execute("_test.favorites = {}")
        self.callback(harness, "FAVORITE_REMOVED")(
            "FAVORITE_REMOVED", "Zul'jin-Spee-3", 251119, 255
        )
        self.assertEqual(
            len(
                list(
                    harness.globals.KeystoneSyncDB["Zul'jin-Spee"][
                        "keystoneLootFavoriteCaptures"
                    ].keys()
                )
            ),
            0,
        )

        harness.execute(
            'KeystoneLootCharDB.filters.dungeon.track = "greatvault"; '
            "KeystoneLootCharDB.filters.dungeon.rank = 6"
        )
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12854"
        )
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["itemLevel"], 334)
        self.assertEqual(favorite["bonusIds"], [3206, 12854])

    def test_exact_item_link_parser_rejects_base_or_misaligned_bonus_payloads(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { dungeon = { track = "hero", rank = 1 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 28 end,
                GetItemInfo = function(link) return "Sparse", link, 3 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(harness, "item:251119")
        harness.execute(
            "_test.favorites = { { sourceId = 558, specId = 255, itemId = 251119, tier = 3 } }"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertNotIn("itemLevel", favorite)
        self.assertNotIn("qualityType", favorite)

        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::3:3206:12841"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertNotIn("itemLevel", favorite)
        self.assertNotIn("qualityType", favorite)

    def test_preview_is_rejected_when_keystoneloot_filter_context_changes_before_add(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {}
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 255, dungeon = { track = "hero", rank = 1 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 305 end,
                GetItemInfo = function(link) return "Hero", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12841"
        )
        harness.execute(
            """
            KeystoneLootCharDB.filters.dungeon.track = "greatvault"
            KeystoneLootCharDB.filters.dungeon.rank = 6
            _test.favorites = {
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3 },
            }
            """
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)

        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["variantKey"], "base")
        self.assertNotIn("itemLevel", favorite)
        self.assertIsNone(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["keystoneLootFavoriteCaptures"]
        )
        harness.execute(
            'KeystoneLootCharDB.filters.dungeon.track = "hero"; '
            "KeystoneLootCharDB.filters.dungeon.rank = 1"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        self.assertIsNone(
            harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["keystoneLootFavoriteCaptures"]
        )

    def test_exact_variant_quality_maps_rare_and_unknown_safely(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3, bonusIds = { 10 } },
                { sourceId = 558, specId = 255, itemId = 251120, tier = 3, bonusIds = { 20 } },
            }""",
        )
        harness.execute(
            """
            C_Item = {
                GetDetailedItemLevelInfo = function(link) return 389 end,
                GetItemInfo = function(link)
                    if string.find(link, ":10", 1, true) then return "Rare", link, 3 end
                    return "Future", link, 99
                end,
            }
            Item = { CreateFromItemLink = function()
                return { ContinueOnItemLoad = function(_, callback) callback() end }
            end }
            """
        )

        self.start(harness, integration)

        favorites = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"]
        self.assertEqual(favorites[0]["qualityType"], "RARE")
        self.assertNotIn("qualityType", favorites[1])

    def test_multiple_variants_of_the_same_item_keep_distinct_identity_and_metadata(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3, bonusIds = { 10 } },
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3, bonusIds = { 20 } },
            }""",
        )
        harness.execute(
            """
            C_Item = {
                GetDetailedItemLevelInfo = function(link)
                    return string.find(link, ":10", 1, true) and 389 or 402
                end,
                GetItemInfo = function(link) return "Exact", link, 4 end,
            }
            """
        )

        self.start(harness, integration)

        favorites = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"]
        self.assertEqual(
            [(favorite["variantKey"], favorite["itemLevel"]) for favorite in favorites],
            [("bonus:10", 389), ("bonus:20", 402)],
        )

    def test_async_variant_resolution_refreshes_current_generation_only(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3, bonusIds = { 6652 } },
            }""",
        )
        harness.execute(
            """
            _test.itemCallbacks = {}
            _test.itemReady = false
            C_Item = {
                GetDetailedItemLevelInfo = function() return _test.itemReady and 402 or nil end,
                GetItemInfo = function(link)
                    if not _test.itemReady then return nil end
                    return "Exact favorite", link, 4
                end,
            }
            Item = { CreateFromItemLink = function()
                return { ContinueOnItemLoad = function(_, callback)
                    table.insert(_test.itemCallbacks, callback)
                end }
            end }
            """
        )

        self.start(harness, integration)
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertNotIn("itemLevel", favorite)
        self.assertNotIn("qualityType", favorite)
        self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)

        harness.execute("_test.itemReady = true; _test.itemCallbacks[1]()")
        favorite = harness.stored_keystone_loot("Zul'jin-Spee")["favorites"][0]
        self.assertEqual(favorite["itemLevel"], 402)
        self.assertEqual(favorite["qualityType"], "EPIC")

        integration["RefreshCurrent"](integration)
        self.assertEqual(harness.evaluate("#_test.itemCallbacks"), 1)

    def test_stale_variant_callback_cannot_write_another_character(self):
        harness, integration = self.make_harness()
        self.install_ready_api(
            harness,
            """{{ sourceId = 558, specId = 255, itemId = 251119, tier = 3, bonusIds = { 6652 } }}""",
        )
        harness.execute(
            """
            _test.itemCallbacks = {}
            C_Item = {
                GetDetailedItemLevelInfo = function() return nil end,
                GetItemInfo = function() return nil end,
            }
            Item = { CreateFromItemLink = function()
                return { ContinueOnItemLoad = function(_, callback)
                    table.insert(_test.itemCallbacks, callback)
                end }
            end }
            """
        )

        self.start(harness, integration)
        harness.execute("_test.ksKey = 'Other-Realm-Historical'; _test.klKey = 'Other-Realm-2'")
        harness.execute("_test.itemCallbacks[1]()")

        self.assertIsNone(harness.globals.KeystoneSyncDB["Other-Realm-Historical"]["keystoneLoot"])

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

    def test_favorite_diagnostics_distinguish_captured_and_legacy_metadata(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "_test.favorites")
        harness.execute(
            """
            _test.favorites = {
                { sourceId = 558, specId = 255, itemId = 251119, tier = 3 },
                { sourceId = 558, specId = 255, itemId = 251120, tier = 2 },
            }
            KeystoneLootCharDB = {
                ui = { selectedTab = "dungeons" },
                filters = { specId = 255, dungeon = { track = "hero", rank = 5 } },
            }
            C_Item = {
                GetDetailedItemLevelInfo = function() return 318 end,
                GetItemInfo = function(link) return "Hero preview", link, 4 end,
            }
            """
        )
        self.start(harness, integration)
        self.show_item_tooltip(
            harness, "item:251119::::::::90:255:::2:3206:12845"
        )
        self.callback(harness, "FAVORITE_ADDED")(
            "FAVORITE_ADDED", "Zul'jin-Spee-3", 251119, 255, 3
        )
        integration["RefreshCurrent"](integration)

        lines = lua_to_python(
            integration["FormatFavoriteDiagnostics"](
                integration, harness.globals.KeystoneSyncDB["Zul'jin-Spee"]["keystoneLoot"]
            )
        )
        self.assertEqual(lines[0], "KeystoneSync KeystoneLoot diagnostic")
        captured = next(line for line in lines if "itemId=251119" in line)
        legacy = next(line for line in lines if "itemId=251120" in line)
        self.assertIn("selectedTrack=hero", captured)
        self.assertIn("selectedRank=5", captured)
        self.assertIn("linkSpecId=255", captured)
        self.assertIn("itemLevel=318", captured)
        self.assertIn("qualityTypeExact=EPIC", captured)
        self.assertIn("metadataSource=captured_variant", captured)
        self.assertIn("itemLevel=unavailable", legacy)
        self.assertIn("qualityTypeExact=unavailable", legacy)
        self.assertIn("metadataSource=legacy/no-capture", legacy)

    def test_start_registers_only_public_ready_and_aggregate_change_callbacks(self):
        harness, integration = self.make_harness()
        self.install_ready_api(harness, "{}")

        self.start(harness, integration)

        events = set(harness.globals._test.callbacks.keys())
        self.assertEqual(
            events,
            {
                "READY",
                "FAVORITE_ADDED",
                "FAVORITE_REMOVED",
                "FAVORITES_IMPORTED",
                "FAVORITES_CHANGED",
            },
        )
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

    def test_new_savedvariables_database_gets_one_persistent_instance_id(self):
        harness = self.make_runtime()

        self.fire(harness, "PLAYER_LOGIN")
        instance_id = harness.globals.KeystoneSyncDB["savedVariablesInstanceId"]
        self.assertIsInstance(instance_id, str)
        self.assertRegex(instance_id, r"^ksv1-[a-zA-Z0-9-]+$")

        self.fire(harness, "BAG_UPDATE_DELAYED")
        self.assertEqual(
            harness.globals.KeystoneSyncDB["savedVariablesInstanceId"], instance_id
        )

    def test_legacy_database_enrolls_without_losing_existing_character_data(self):
        harness = self.make_runtime()
        harness.execute(
            """
            KeystoneSyncDB = {
                ["Other-Realm-Historical"] = { normalData = "preserved" },
            }
            """
        )

        self.fire(harness, "PLAYER_LOGIN")

        self.assertIsInstance(
            harness.globals.KeystoneSyncDB["savedVariablesInstanceId"], str
        )
        self.assertEqual(
            harness.globals.KeystoneSyncDB["Other-Realm-Historical"]["normalData"],
            "preserved",
        )

    def test_savedvariables_instance_id_survives_addon_reload(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        instance_id = harness.globals.KeystoneSyncDB["savedVariablesInstanceId"]
        self.assertIsInstance(instance_id, str)

        harness.load_addon_file("KeystoneSync.lua")
        reloaded_frame = harness.globals._test.frames[2]
        reloaded_frame["OnEvent"](reloaded_frame, "PLAYER_LOGIN")

        self.assertEqual(
            harness.globals.KeystoneSyncDB["savedVariablesInstanceId"], instance_id
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

    def test_keystoneloot_diagnostic_command_prints_safe_favorite_details(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("_test.integrationCalls = {}; _test.prints = {}")

        harness.globals.SlashCmdList["KEYSTONESYNC"]("kl")

        self.assertEqual(self.calls(harness), ["refresh", "favorite-diagnostic"])
        prints = lua_to_python(harness.globals._test.prints)
        self.assertTrue(any("KeystoneSync KeystoneLoot diagnostic" in line for line in prints))
        self.assertTrue(any("metadataSource=legacy/no-capture" in line for line in prints))

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
