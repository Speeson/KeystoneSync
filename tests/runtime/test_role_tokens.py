import unittest

from lua_harness import ROOT, LuaAddonHarness, lua_to_python


STUBS = r"""
KeystoneSyncDB = {}
SlashCmdList = {}
MAX_ACCOUNT_MACROS = 120
_test.macros = {}
_test.accountCount = 0
_test.characterCount = 0
_test.inRaid = false
_test.inGroup = false
_test.inCombat = false
_test.otherAddon = false
_test.failEdit = false
_test.units = {}
_test.editCount = 0
function IsInRaid() return _test.inRaid end
function IsInGroup() return _test.inGroup end
function GetNumGroupMembers() return _test.inRaid and _test.groupCount or 0 end
function GetNumSubgroupMembers() return _test.inGroup and _test.groupCount or 0 end
function UnitExists(unit) return _test.units[unit] ~= nil end
function UnitIsUnit(a, b) return _test.units[a] and _test.units[b] and _test.units[a].id == _test.units[b].id end
function UnitGroupRolesAssigned(unit) return _test.units[unit] and _test.units[unit].role or "NONE" end
function GetPartyAssignment(kind, unit) return kind == "MAINTANK" and _test.units[unit] and _test.units[unit].mainTank or false end
function UnitName(unit) return _test.units[unit] and _test.units[unit].name or "Tester" end
function GetRealmName() return "Realm" end
function InCombatLockdown() return _test.inCombat end
function GetNumMacros() return _test.accountCount, _test.characterCount end
function GetMacroInfo(index)
    local macro = _test.macros[index]
    if macro then return macro.name, macro.icon, macro.body end
end
function EditMacro(index, name, icon, body)
    if _test.inCombat then error("protected edit") end
    if _test.failEdit then error("edit failed") end
    local macro = _test.macros[index]
    if not macro then error("missing macro") end
    if name ~= nil then macro.name = name end
    if icon ~= nil then macro.icon = icon end
    macro.body = body
    _test.editCount = _test.editCount + 1
    return index
end
C_AddOns.IsAddOnLoaded = function(name) return name == "RoleTokens" and _test.otherAddon end
function issecretvalue(value) return false end
_test.units.player = { id = "self", name = "Tester", role = "DAMAGER" }
"""


class RoleTokensTests(unittest.TestCase):
    def test_toc_loads_role_modules_after_existing_runtime(self):
        from scripts.package_addon import read_toc

        files = [path.as_posix() for path in read_toc(ROOT).files]
        self.assertLess(files.index("KeystoneSync.lua"), files.index("RoleTokenResolver.lua"))
        self.assertLess(files.index("RoleTokenResolver.lua"), files.index("RoleTokenMacros.lua"))

    def make_harness(self, macros=True):
        harness = LuaAddonHarness()
        harness.execute(STUBS)
        namespace = harness.load_addon_file("RoleTokenResolver.lua")
        if macros:
            harness.load_addon_file("RoleTokenMacros.lua")
        return harness, namespace

    @staticmethod
    def group(harness, raid=False):
        harness.execute(
            f"""
            _test.inRaid = {str(raid).lower()}
            _test.inGroup = true
            _test.groupCount = 4
            _test.units.{ 'raid1' if raid else 'party1' } = {{ id = "a", name = "A", role = "HEALER" }}
            _test.units.{ 'raid2' if raid else 'party2' } = {{ id = "b", name = "B", role = "TANK" }}
            _test.units.{ 'raid3' if raid else 'party3' } = {{ id = "c", name = "C", role = "TANK" }}
            _test.units.{ 'raid4' if raid else 'party4' } = {{ id = "self", name = "Tester", role = "DAMAGER" }}
            """
        )

    @staticmethod
    def macro(harness, body, index=1, name="Tricks", icon=123):
        harness.globals._test.macros[index] = harness.lua.table_from(
            {"name": name, "icon": icon, "body": body}
        )
        if index <= 120:
            harness.globals._test.accountCount = max(harness.globals._test.accountCount, index)
        else:
            harness.globals._test.characterCount = max(
                harness.globals._test.characterCount, index - 120
            )

    @staticmethod
    def login(harness):
        frame = harness.globals._test.frames[len(harness.globals._test.frames)]
        frame.OnEvent(frame, "PLAYER_LOGIN")
        harness.run_timers()
        return frame

    def test_resolver_orders_roles_and_excludes_player(self):
        harness, namespace = self.make_harness(macros=False)
        self.group(harness)
        units = lua_to_python(namespace.RoleTokenResolver.Resolve())
        self.assertEqual(units, {"tank1": "party2", "tank2": "party3", "healer1": "party1"})

    def test_raid_main_tank_is_first_even_at_later_index(self):
        harness, namespace = self.make_harness(macros=False)
        self.group(harness, raid=True)
        harness.execute("_test.units.raid3.mainTank = true")
        units = lua_to_python(namespace.RoleTokenResolver.Resolve())
        self.assertEqual(units["tank1"], "raid3")
        self.assertEqual(units["tank2"], "raid2")

    def test_raid_multiple_main_tanks_keep_raid_order(self):
        harness, namespace = self.make_harness(macros=False)
        self.group(harness, raid=True)
        harness.execute("_test.units.raid2.mainTank = true; _test.units.raid3.mainTank = true")
        units = lua_to_python(namespace.RoleTokenResolver.Resolve())
        self.assertEqual(units["tank1"], "raid2")
        self.assertEqual(units["tank2"], "raid3")

    def test_none_role_and_secret_role_are_not_inferred(self):
        harness, namespace = self.make_harness(macros=False)
        self.group(harness)
        harness.execute('''
            _test.units.party2.role = "NONE"
            issecretvalue = function(value) return value == "HEALER" end
        ''')
        units = lua_to_python(namespace.RoleTokenResolver.Resolve())
        self.assertEqual(units, {"tank1": "party3"})

    def test_expansion_only_changes_role_selectors_in_macro_conditions(self):
        harness, namespace = self.make_harness()
        body = '# comment @tank\n/run print("[@tank]")\n/cast [@Tank,help][@TANK2][@party1] Heal\n/say [@tank]'
        units = harness.lua.table_from({"tank1": "raid7", "tank2": "raid12"})
        self.assertEqual(
            namespace.RoleTokenMacros.Expand(body, units),
            '# comment @tank\n/run print("[@tank]")\n/cast [@raid7,help][@raid12][@party1] Heal\n/say [@tank]',
        )

    def test_spell_text_after_macro_condition_is_not_rewritten(self):
        harness, namespace = self.make_harness()
        units = harness.lua.table_from({"tank1": "party2"})
        self.assertEqual(
            namespace.RoleTokenMacros.Expand("/cast [@tank] Heal [@tank]", units),
            "/cast [@party2] Heal [@tank]",
        )

    def test_unresolved_and_longer_identifiers_remain_unchanged(self):
        harness, namespace = self.make_harness()
        body = '/cast [@tank2,exists][@tanky][@healer0][@healer41] Heal'
        units = harness.lua.table_from({"tank1": "party1"})
        self.assertEqual(namespace.RoleTokenMacros.Expand(body, units), body)

    def test_healer_and_dps_aliases_expand_case_insensitively(self):
        harness, namespace = self.make_harness()
        units = harness.lua.table_from({"healer1": "party1", "dps2": "party4"})
        self.assertEqual(
            namespace.RoleTokenMacros.Expand("/cast [@Healer1][@DPS2] Heal", units),
            "/cast [@party1][@party4] Heal",
        )

    def test_default_enabled_sync_restores_template_after_group_change(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        frame = self.login(harness)
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2,exists] Heal")
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank,exists] Heal")
        harness.execute('_test.units.party2.role = "DAMAGER"')
        frame.OnEvent(frame, "PLAYER_ROLES_ASSIGNED")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party3,exists] Heal")

    def test_combat_defers_edit_until_regen(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        harness.execute("_test.inCombat = true")
        frame = self.login(harness)
        self.assertEqual(harness.globals._test.editCount, 0)
        harness.execute("_test.inCombat = false")
        frame.OnEvent(frame, "PLAYER_REGEN_ENABLED")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2,exists] Heal")

    def test_no_group_restores_unresolved_token_in_expanded_body(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        frame = self.login(harness)
        harness.execute("_test.inGroup = false")
        frame.OnEvent(frame, "GROUP_ROSTER_UPDATE")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@tank,exists] Heal")

    def test_repeated_roster_events_do_not_edit_unchanged_body(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        frame = self.login(harness)
        frame.OnEvent(frame, "GROUP_ROSTER_UPDATE")
        frame.OnEvent(frame, "GROUP_ROSTER_UPDATE")
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.editCount, 1)

    def test_disable_restores_original_and_reenable_updates(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        self.login(harness)
        harness.globals.SlashCmdList["KSROLE"]("disable")
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@tank,exists] Heal")
        self.assertFalse(harness.globals.KeystoneSyncDB.roleTokens.enabled)
        harness.globals.SlashCmdList["KSROLE"]("enable")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2,exists] Heal")

    def test_status_shows_unumbered_alias_and_managed_count(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        self.login(harness)
        harness.globals.SlashCmdList["KSROLE"]("status")
        lines = lua_to_python(harness.globals._test.prints)
        self.assertTrue(any("macros gestionadas: 1" in line for line in lines))
        self.assertTrue(any("@tank=party2" in line for line in lines))

    def test_manual_edit_with_token_becomes_new_template(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        frame = self.login(harness)
        harness.execute('_test.macros[1].body = "/use [@tank2,exists] Thing"')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/use [@party3,exists] Thing")
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/use [@tank2,exists] Thing")

    def test_manual_edit_without_token_is_not_overwritten(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        frame = self.login(harness)
        harness.execute('_test.macros[1].body = "/cast [@party1] Heal"')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party1] Heal")

    def test_index_reuse_does_not_overwrite_unrelated_macro(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank,exists] Heal")
        frame = self.login(harness)
        self.macro(harness, "/cast [@party1] Heal", name="Other", icon=456)
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party1] Heal")

    def test_index_shift_with_same_metadata_keeps_original_template(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        frame = self.login(harness)
        old = harness.globals._test.macros[1]
        harness.globals._test.macros[2] = old
        self.macro(harness, "/cast [@party1] Heal", name="Other")
        harness.globals._test.accountCount = 2
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party1] Heal")
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[2].template, "/cast [@tank] Heal")

    def test_rename_with_expanded_body_is_left_intact_as_ambiguous(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        frame = self.login(harness)
        harness.execute('_test.macros[1].name = "Renamed"; _test.units.party2.role = "DAMAGER"')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2] Heal")
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank] Heal")

    def test_deleted_macro_does_not_attach_to_static_macro_with_same_body(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal", name="Dynamic", icon=123)
        frame = self.login(harness)
        self.macro(harness, "/cast [@party2] Heal", name="Static", icon=456)
        harness.execute('_test.units.party2.role = "DAMAGER"')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2] Heal")

    def test_ambiguous_duplicate_names_and_bodies_preserve_template(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal", name="Same")
        frame = self.login(harness)
        self.macro(harness, "/cast [@party1] Heal", name="Other")
        self.macro(harness, "/cast [@party2] Heal", index=2, name="Same")
        self.macro(harness, "/cast [@party2] Heal", index=3, name="Same")
        harness.execute('_test.units.party2.role = "DAMAGER"')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals._test.macros[2].body, "/cast [@party2] Heal")
        self.assertEqual(harness.globals._test.macros[3].body, "/cast [@party2] Heal")
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank] Heal")

    def test_character_macro_is_saved_in_character_bucket(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal", index=121)
        self.login(harness)
        self.assertEqual(harness.globals._test.macros[121].body, "/cast [@party2] Heal")
        self.assertEqual(
            harness.globals.KeystoneSyncDB.roleTokens.characters["Realm-Tester"][121].template,
            "/cast [@tank] Heal",
        )

    def test_edit_api_error_keeps_template_and_macro(self):
        harness, _ = self.make_harness()
        self.group(harness)
        body = "/cast [@tank] Heal"
        self.macro(harness, body)
        harness.execute("_test.failEdit = true")
        self.login(harness)
        self.assertEqual(harness.globals._test.macros[1].body, body)
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, body)

    def test_secret_macro_body_does_not_drop_saved_template(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        frame = self.login(harness)
        harness.execute('''
            issecretvalue = function(value)
                return type(value) == "string" and value:find("/cast", 1, true) ~= nil
            end
        ''')
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank] Heal")

    def test_edit_that_writes_but_returns_nil_keeps_last_body_tracking(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        harness.execute("local original = EditMacro; EditMacro = function(...) original(...); return nil end")
        frame = self.login(harness)
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2] Heal")
        self.assertEqual(
            harness.globals.KeystoneSyncDB.roleTokens.account[1].lastBody,
            "/cast [@party2] Heal",
        )
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank] Heal")

    def test_unexpected_api_truncation_keeps_original_template(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        harness.execute('''
            EditMacro = function(index, name, icon, body)
                _test.macros[index].body = body:sub(1, -2)
                return index
            end
        ''')
        frame = self.login(harness)
        frame.OnEvent(frame, "UPDATE_MACROS")
        harness.run_timers()
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.account[1].template, "/cast [@tank] Heal")
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@party2] Hea")

    def test_too_long_expansion_does_not_truncate(self):
        harness, _ = self.make_harness()
        self.group(harness)
        body = "/cast [@tank] " + "A" * 241
        self.macro(harness, body)
        self.login(harness)
        self.assertEqual(harness.globals._test.macros[1].body, body)

    def test_role_tokens_addon_suspends_management(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        harness.execute("_test.otherAddon = true")
        self.login(harness)
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@tank] Heal")

    def test_unknown_newer_schema_is_not_downgraded(self):
        harness, _ = self.make_harness()
        self.group(harness)
        self.macro(harness, "/cast [@tank] Heal")
        harness.execute("KeystoneSyncDB.roleTokens = { schema = 2, enabled = true, account = {}, characters = {} }")
        self.login(harness)
        self.assertEqual(harness.globals.KeystoneSyncDB.roleTokens.schema, 2)
        self.assertEqual(harness.globals._test.macros[1].body, "/cast [@tank] Heal")


if __name__ == "__main__":
    unittest.main()
