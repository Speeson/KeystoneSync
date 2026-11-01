# Tokens de rol en macros — diseño V1

## Objetivo

Aplicar el plan de `docs/KEYSTONESYNC_ROLE_TOKENS_IMPLEMENTATION_PLAN.md` sin alterar la captura de datos existente. La función comienza activada; solo administra macros con selectores `@tank`, `@healer` o `@dps` (y sus índices).

## Arquitectura

- `RoleTokenResolver.lua`: enumera UnitIDs de party/raid fuera de combate, excluye `player`, usa exclusivamente `UnitGroupRolesAssigned` y prioriza el Main Tank de banda.
- `RoleTokenMacros.lua`: detecta selectores en cláusulas de comandos de macro, guarda plantilla y último cuerpo, aplica cambios fuera de combate y ofrece `/ksrole enable|disable|status|refresh|restore`.
- `KeystoneSync.toc`: añade ambos archivos después del runtime existente. `KeystoneSync.lua` y `KeystoneLootIntegration.lua` no cambian.
- Persistencia en `KeystoneSyncDB.roleTokens` con esquema propio. Las macros generales se guardan por cuenta y las de personaje por `reino-personaje`.

`GetMacroInfo` solo devuelve nombre, icono y cuerpo; el índice puede cambiar. Un registro se vincula por cuerpo previamente escrito y metadatos; ante coincidencias ambiguas se deja intacto y se avisa. La edición manual con tokens pasa a ser la nueva plantilla cuando se puede identificar con seguridad; quitar los tokens desvincula la macro. `EditMacro` recibe solo índice y cuerpo, para preservar nombre e icono. Después se lee el cuerpo para comprobar la escritura.

La detección se limita a cláusulas `[...]` de comandos conocidos que aceptan condiciones de macro. Los tokens sin candidato permanecen en la plantilla expandida. Si RoleTokens está cargado, se suspende toda la gestión para evitar competencia por macros. No se copia código de RoleTokens.

## Verificación

Pruebas de resolución, expansión, identidad de macro, restauración, combate, conflictos y límites con el harness Lua. Validación del `.toc`, empaquetado y `scripts/deploy_impact.py --json --strict`. Las pruebas dentro de WoW Retail quedan registradas como pendientes hasta ejecutarse realmente.

## Fuera de alcance

KeystoneClient, sincronización, UI grande, casting automático, Classic y cambios de temporada.
