import unittest

from lua_harness import LuaAddonHarness, lua_to_python


CHARACTER_KEY = "Zul'jin-Spee"


class CharacterSnapshotTests(unittest.TestCase):
    def make_runtime(self):
        harness = LuaAddonHarness()
        harness.install_keystonesync_wow_stubs()
        harness.execute(
            r'''
            function UnitClass() return "Druid", "DRUID", 11 end
            function GetInventoryItemLink(_, slotID)
                _test.equipmentSlotsSeen = _test.equipmentSlotsSeen or {}
                _test.equipmentSlotsSeen[slotID] = true
                if slotID == 1 then
                    return "|cffa335ee|Hitem:123:456:1001:1002:::7:8:90:102:0:9:2:2001:2002:1:28:777:::|h[Test Helm]|h|r"
                end
                return nil
            end
            C_Item.GetItemInfo = function(itemLink)
                if string.find(itemLink, "item:123:", 1, true) then
                    return "Test Helm", itemLink, 4, 331, 90, "Armor", "Leather", 1,
                        "INVTYPE_HEAD", 9876, 0, 4, 2, 1, 12, 9001, false
                end
                if string.find(itemLink, "item:1001:", 1, true) then
                    return "Gem One", itemLink, 3, 1, 1, "Gem", "Gem", 1, "", 5001
                end
                if string.find(itemLink, "item:1002:", 1, true) then
                    return "Gem Two", itemLink, 3, 1, 1, "Gem", "Gem", 1, "", 5002
                end
                return nil
            end
            C_Item.GetItemGem = function(_, index)
                if index == 1 then return "Gem One", "|cff0070dd|Hitem:1001::::::::90:::::::|h[Gem One]|h|r" end
                if index == 2 then return "Gem Two", "|cff0070dd|Hitem:1002::::::::90:::::::|h[Gem Two]|h|r" end
                return nil, nil
            end
            C_Item.GetItemIconByID = function(itemInfo)
                local value = tostring(itemInfo)
                if string.find(value, "1001", 1, true) then return 5001 end
                if string.find(value, "1002", 1, true) then return 5002 end
                return 9876
            end
            C_Item.GetItemUpgradeInfo = function() return { trackString = "Hero", currentLevel = 4, maxLevel = 6 } end
            ENCHANTED_TOOLTIP_LINE = "Enchanted: %s"
            C_TooltipInfo = C_TooltipInfo or {}
            C_TooltipInfo.GetInventoryItem = function(_, slotID)
                if slotID == 1 then return { lines = { { leftText = "Enchanted: Authority of the Depths|A:test-enchant:20:20|a" } } } end
            end
            C_Texture.GetAtlasInfo = function(atlas)
                if atlas == "test-enchant" then return { file = 6543 } end
                if atlas == "hero-atlas" then return { file = 7654 } end
            end
            C_Texture.GetFilenameFromFileDataID = function(id) return "Interface/Icons/" .. id end

            C_SpecializationInfo = {
                GetSpecialization = function() return 1 end,
                GetSpecializationInfo = function() return 102, "Balance", "", 136096, "DAMAGER", "DRUID" end,
            }
            C_Spell = {
                GetSpellInfo = function(spellID) return { name = "Spell " .. spellID, iconID = spellID + 1000 } end,
                GetSpellDescription = function(spellID) return "Description " .. spellID end,
            }
            C_ClassTalents = {
                GetActiveConfigID = function() return 77 end,
                GetHeroTalentSpecsForClassSpec = function() return { 55, 56 }, 71 end,
                GetActiveHeroTalentSpec = function() return 55 end,
            }
            C_MythicPlus.GetRunHistory = function()
                return {
                    { level = 11, mapChallengeModeID = 501 },
                    { level = 13, mapChallengeModeID = 502 },
                }
            end
            C_ChallengeMode.GetMapUIInfo = function(mapID) return mapID == 502 and "High Dungeon" or "Low Dungeon" end
            C_WeeklyRewards.GetActivities = function()
                return {
                    { id = 11, index = 1, type = 1, level = 16, progress = 1, threshold = 2, activityTierID = 101 },
                    { id = 21, index = 1, type = 2, level = 13, progress = 2, threshold = 1, activityTierID = 201 },
                    { id = 31, index = 1, type = 3, level = 8, progress = 3, threshold = 2, activityTierID = 301 },
                }
            end
            C_WeeklyRewards.GetActivityEncounterInfo = function(_, index)
                if index == 1 then return { { encounterID = 7001, bestDifficulty = 16, uiOrder = 1, instanceID = 8001 } } end
                return {}
            end
            C_WeeklyRewards.GetSortedProgressForActivity = function()
                return { { activityTierID = 301, difficulty = 8, numPoints = 3 } }
            end
            function EJ_GetEncounterInfo() return "Test Boss" end
            function EJ_GetInstanceInfo() return "Test Raid" end
            local nodes = {
                [1] = { ID = 1, posX = 10, posY = 20, type = 0, ranksPurchased = 2, maxRanks = 2,
                    activeEntry = { entryID = 101, rank = 2 }, entryIDs = { 101 },
                    visibleEdges = { { targetNode = 2, type = 3, visualStyle = 1, isActive = true } }, isVisible = true },
                [2] = { ID = 2, posX = 30, posY = 40, type = 2, ranksPurchased = 1, maxRanks = 1,
                    activeEntry = { entryID = 201, rank = 1 }, entryIDs = { 201, 202 }, visibleEdges = {}, isVisible = true },
                [3] = { ID = 3, posX = 50, posY = 60, type = 0, ranksPurchased = 1, maxRanks = 1,
                    activeEntry = { entryID = 301, rank = 1 }, entryIDs = { 301 }, visibleEdges = {},
                    subTreeID = 55, subTreeActive = true, isVisible = true },
                [4] = { ID = 4, posX = 15, posY = 25, type = 0, ranksPurchased = 1, maxRanks = 2,
                    activeEntry = { entryID = 401, rank = 1 }, entryIDs = { 401 },
                    visibleEdges = { { targetNode = 5, type = 2, visualStyle = 1, isActive = false } }, isVisible = true },
                [5] = { ID = 5, posX = 35, posY = 45, type = 0, ranksPurchased = 0, maxRanks = 1,
                    activeEntry = { entryID = 501, rank = 0 }, entryIDs = { 501 }, visibleEdges = {}, isVisible = true },
            }
            C_Traits = {
                GetConfigIDBySystemID = function(systemID) if systemID == 48 then return 88 end end,
                GetConfigInfo = function(configID)
                    if configID == 77 then return { ID = 77, type = 1, name = "Raid", treeIDs = { 900 } } end
                    if configID == 88 then return { ID = 88, type = 3, name = "Omnium", treeIDs = { 1186 } } end
                end,
                GetTreeNodes = function(treeID) return treeID == 900 and { 1, 2, 3 } or { 4, 5 } end,
                GetNodeInfo = function(_, nodeID) return nodes[nodeID] end,
                GetTreeCurrencyInfo = function(_, treeID)
                    if treeID == 900 then return { { traitCurrencyID = 10 }, { traitCurrencyID = 20 } } end
                    return { { traitCurrencyID = 30 } }
                end,
                GetNodeCost = function(_, nodeID)
                    if nodeID == 1 then return { { ID = 10, amount = 1 } } end
                    if nodeID == 2 then return { { ID = 20, amount = 1 } } end
                    if nodeID == 3 then return { { ID = 99, amount = 1 } } end
                    return { { ID = 30, amount = 1 } }
                end,
                GetEntryInfo = function(_, entryID)
                    if entryID == 302 then return { subTreeID = 56, type = 0, maxRanks = 1, isAvailable = true } end
                    return { definitionID = entryID + 1000, type = entryID == 201 and 2 or 0, maxRanks = 2, isAvailable = true }
                end,
                GetDefinitionInfo = function(definitionID)
                    return { spellID = definitionID + 10000, overriddenSpellID = definitionID + 20000 }
                end,
                GetTraitDescription = function(entryID, rank) return "Trait " .. entryID .. " rank " .. rank end,
                GetSubTreeInfo = function(_, subTreeID)
                    return { ID = subTreeID, name = subTreeID == 55 and "Elune's Chosen" or "Keeper of the Grove",
                        description = "Hero", iconElementID = "hero-atlas", traitCurrencyID = 99,
                        isActive = subTreeID == 55, posX = 50, posY = 10 }
                end,
                GenerateImportString = function(configID) return configID == 77 and "IMPORT-STRING" or "" end,
            }
            '''
        )
        harness.load_addon_file("KeystoneSync.lua")
        return harness

    @staticmethod
    def fire(harness, event):
        frame = harness.globals._test.frames[1]
        frame["OnEvent"](frame, event)

    def record(self, harness):
        return lua_to_python(harness.globals.KeystoneSyncDB[CHARACTER_KEY])

    def test_currency_total_tooltip_supplies_dynamic_season_cap(self):
        harness = self.make_runtime()
        harness.execute(
            r'''
            C_CurrencyInfo.GetCurrencyInfo = function(currencyID)
                if currencyID ~= 3509 then return nil end
                return {
                    name = "Tidal Spark Dust",
                    quantity = 6,
                    maxQuantity = 0,
                    maxWeeklyQuantity = 0,
                    totalEarned = 6,
                    quantityEarnedThisWeek = 0,
                    useTotalEarnedForMaxQty = true,
                    canEarnPerWeek = false,
                    discovered = true,
                    quality = 4,
                    iconFileID = 5929576,
                }
            end
            C_TooltipInfo.GetCurrencyByID = function(currencyID)
                if currencyID ~= 3509 then return nil end
                return { lines = {
                    { type = 0, leftText = "Earn 1 each week" },
                    { type = 14, leftText = "Current Season Maximum", rightText = "6 / 6" },
                } }
            end
            '''
        )

        self.fire(harness, "PLAYER_LOGIN")
        currency = self.record(harness)["currencies"]["tidalSparkDust"]

        self.assertEqual(currency["maxWeeklyQuantity"], 0)
        self.assertEqual(currency["maxQuantity"], 6)
        self.assertEqual(currency["totalEarned"], 6)
        self.assertTrue(currency["useTotalEarnedForMaxQty"])
        self.assertTrue(currency["isSeasonMaxed"])
        self.assertTrue(currency["isMaxed"])

    def test_equipment_preserves_real_variant_and_gems(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        equipment = self.record(harness)["equipment"]
        self.assertEqual(equipment["averageItemLevel"], 700)
        self.assertEqual(equipment["setPieces"], [{"setId": 9001, "count": 1}])
        [item] = equipment["items"]
        self.assertEqual(item["slotId"], 1)
        self.assertEqual(item["slotName"], "Head")
        self.assertEqual(item["itemId"], 123)
        self.assertIn("Hitem:123:456:1001:1002", item["itemLink"])
        self.assertEqual(item["enchant"]["enchantId"], 456)
        self.assertEqual(item["enchant"]["name"], "Authority of the Depths")
        self.assertEqual(item["enchant"]["iconFileID"], 6543)
        self.assertEqual(item["enchant"]["iconPath"], "Interface/Icons/6543")
        self.assertNotIn("spellId", item["enchant"])
        self.assertEqual(item["bonusIds"], [2001, 2002])
        self.assertEqual(item["itemContext"], 9)
        self.assertEqual(item["suffixId"], 7)
        self.assertEqual([gem["itemId"] for gem in item["gems"]], [1001, 1002])
        self.assertEqual(
            sorted(lua_to_python(harness.globals._test.equipmentSlotsSeen).keys()),
            [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
        )

    def test_talents_are_split_by_currency_and_hero_subtree(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        talents = self.record(harness)["talents"]
        self.assertEqual(talents["configId"], 77)
        self.assertEqual(talents["specId"], 102)
        self.assertEqual(talents["specName"], "Balance")
        self.assertEqual(talents["specIconFileID"], 136096)
        self.assertEqual(talents["className"], "Druid")
        self.assertEqual(talents["class"], "Druid")
        self.assertEqual(talents["loadoutName"], "Raid")
        self.assertEqual(talents["importString"], "IMPORT-STRING")
        trees = {tree["type"]: tree for tree in talents["trees"]}
        self.assertEqual([node["nodeId"] for node in trees["class"]["nodes"]], [1])
        self.assertEqual([node["nodeId"] for node in trees["spec"]["nodes"]], [2])
        self.assertEqual([node["nodeId"] for node in trees["hero"]["nodes"]], [3])
        self.assertEqual(trees["hero"]["name"], "Elune's Chosen")
        self.assertEqual(trees["hero"]["iconFileID"], 7654)
        self.assertEqual(trees["hero"]["iconPath"], "Interface/Icons/7654")
        self.assertTrue(trees["hero"]["active"])
        self.assertEqual(trees["class"]["nodes"][0]["ranksPurchased"], 2)
        self.assertEqual(trees["class"]["nodes"][0]["visibleEdges"][0]["targetNodeId"], 2)
        choice_entries = trees["spec"]["nodes"][0]["entries"]
        self.assertEqual(len(choice_entries), 2)
        self.assertTrue(choice_entries[0]["selected"])
        self.assertFalse(choice_entries[1]["selected"])
        self.assertGreater(choice_entries[1]["spellId"], 0)

    def test_active_entry_rank_wins_over_transient_zero_node_rank(self):
        harness = self.make_runtime()
        harness.execute("_test.originalGetNodeInfo = C_Traits.GetNodeInfo; C_Traits.GetNodeInfo = function(configID, nodeID) local node = _test.originalGetNodeInfo(configID, nodeID); if nodeID == 3 then node.ranksPurchased = 0; node.activeEntry.rank = 1 end; return node end")
        self.fire(harness, "PLAYER_LOGIN")
        talents = self.record(harness)["talents"]
        hero = next(tree for tree in talents["trees"] if tree["type"] == "hero")
        self.assertEqual(hero["nodes"][0]["ranksPurchased"], 1)
        self.assertTrue(hero["nodes"][0]["entries"][0]["selected"])

    def test_vault_keeps_blizzard_progress_details_for_tooltips(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        vault = self.record(harness)["vault"]
        self.assertEqual(vault["dungeons"]["topRuns"][0], {
            "level": 13, "mapChallengeModeID": 502, "name": "High Dungeon"
        })
        self.assertEqual(vault["world"]["tierProgress"][0]["difficulty"], 8)
        self.assertEqual(vault["world"]["tierProgress"][0]["numPoints"], 3)
        self.assertEqual(vault["raid"]["slots"][0]["encounters"][0]["name"], "Test Boss")
        self.assertEqual(vault["raid"]["slots"][0]["encounters"][0]["instanceName"], "Test Raid")

    def test_transient_vault_api_results_do_not_erase_same_week_details(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute(
            "C_MythicPlus.GetRunHistory = function() return {} end; "
            "C_WeeklyRewards.GetActivityEncounterInfo = function() return {} end; "
            "C_WeeklyRewards.GetSortedProgressForActivity = function() return {} end"
        )
        self.fire(harness, "WEEKLY_REWARDS_UPDATE")
        vault = self.record(harness)["vault"]
        self.assertEqual(vault["dungeons"]["topRuns"][0]["level"], 13)
        self.assertEqual(vault["raid"]["slots"][0]["encounters"][0]["name"], "Test Boss")
        self.assertEqual(vault["world"]["tierProgress"][0]["difficulty"], 8)

    def test_logout_keeps_last_equipment_talents_and_vault_snapshots(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("KeystoneSyncDB[\"Zul'jin-Spee\"].omniumFolio = nil")
        before = self.record(harness)
        harness.execute(
            "GetInventoryItemLink = function() return nil end; "
            "C_ClassTalents.GetActiveConfigID = function() return nil end; "
            "C_Traits.GetConfigIDBySystemID = function() return nil end; "
            "C_MythicPlus.GetRunHistory = function() return {} end; "
            "C_WeeklyRewards.GetActivityEncounterInfo = function() return {} end"
        )
        self.fire(harness, "PLAYER_LOGOUT")
        after = self.record(harness)
        self.assertEqual(after["equipment"], before["equipment"])
        self.assertEqual(after["talents"], before["talents"])
        self.assertNotIn("omniumFolio", after)
        self.assertEqual(after["vault"], before["vault"])

    def test_omnium_is_discovered_from_system_and_keeps_edges(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        folio = self.record(harness)["omniumFolio"]
        self.assertEqual(folio["systemId"], 48)
        self.assertEqual(folio["configId"], 88)
        self.assertEqual(folio["treeIds"], [1186])
        self.assertEqual(folio["trees"][0]["nodes"][0]["nodeId"], 4)
        self.assertEqual(folio["trees"][0]["nodes"][0]["visibleEdges"][0]["targetNodeId"], 5)

    def test_transient_empty_traits_do_not_replace_valid_snapshots(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute("C_ClassTalents.GetActiveConfigID = function() return nil end; C_Traits.GetConfigIDBySystemID = function() return nil end")
        self.fire(harness, "TRAIT_CONFIG_LIST_UPDATED")
        harness.run_timers()
        record = self.record(harness)
        self.assertEqual(record["talents"]["configId"], 77)
        self.assertEqual(record["omniumFolio"]["configId"], 88)

    def test_snapshot_events_are_registered_and_coalesced(self):
        harness = self.make_runtime()
        events = lua_to_python(harness.globals._test.frames[1]["events"])
        for event in (
            "PLAYER_EQUIPMENT_CHANGED",
            "UNIT_INVENTORY_CHANGED",
            "TRAIT_CONFIG_LIST_UPDATED",
            "TRAIT_CONFIG_UPDATED",
            "ACTIVE_COMBAT_CONFIG_CHANGED",
            "PLAYER_SPECIALIZATION_CHANGED",
            "TRAIT_SUB_TREE_CHANGED",
        ):
            self.assertTrue(events[event])

        self.fire(harness, "TRAIT_CONFIG_UPDATED")
        self.fire(harness, "TRAIT_CONFIG_UPDATED")
        self.assertEqual(harness.timer_count(), 1)

    def test_spec_and_loadout_events_replace_the_valid_talent_snapshot(self):
        harness = self.make_runtime()
        self.fire(harness, "PLAYER_LOGIN")
        harness.execute(
            '''
            C_SpecializationInfo.GetSpecializationInfo = function() return 103, "Feral" end
            C_Traits.GenerateImportString = function(configID) return configID == 77 and "UPDATED-IMPORT" or "" end
            local originalConfigInfo = C_Traits.GetConfigInfo
            C_Traits.GetConfigInfo = function(configID)
                local info = originalConfigInfo(configID)
                if configID == 77 then info.name = "Dungeon Loadout" end
                return info
            end
            '''
        )
        self.fire(harness, "PLAYER_SPECIALIZATION_CHANGED")
        self.fire(harness, "TRAIT_CONFIG_UPDATED")
        harness.run_timers()
        talents = self.record(harness)["talents"]
        self.assertEqual(talents["specId"], 103)
        self.assertEqual(talents["specName"], "Feral")
        self.assertEqual(talents["loadoutName"], "Dungeon Loadout")
        self.assertEqual(talents["importString"], "UPDATED-IMPORT")


if __name__ == "__main__":
    unittest.main()
