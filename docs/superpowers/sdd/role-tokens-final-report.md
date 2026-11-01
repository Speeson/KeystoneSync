# Tokens de rol — informe de implementación

## Entregado

Dos módulos Lua nuevos resuelven roles de party/raid y administran plantillas de macros. La función empieza activada, edita solo selectores de rol en condiciones de comandos admitidos, aplaza cambios durante combate y restaura al desactivar. RoleTokens cargado suspende la gestión. La lógica anterior de KeystoneSync permanece sin cambios; el `.toc` solo añade las entradas de los módulos.

## Validación local

- `python -m unittest discover -s tests/runtime -p 'test_*.py' -q`
- `python -m unittest discover -s tests/deploy_impact -p 'test_*.py' -q`
- `python -m unittest discover -s tests/release -p 'test_*.py' -q`
- `python scripts/release_changes.py validate`
- `python scripts/package_addon.py validate`
- `python scripts/package_addon.py package --output-dir .role-package --print-path`
- `python scripts/package_addon.py verify-package --version 0.8.0 --zip .role-package/KeystoneSync-v0.8.0.zip`
- `python scripts/deploy_impact.py --files KeystoneSync.toc RoleTokenResolver.lua RoleTokenMacros.lua tests/runtime/test_role_tokens.py README.md docs/KEYSTONESYNC_ROLE_TOKENS_IMPLEMENTATION_PLAN.md docs/superpowers/specs/2026-11-01-role-tokens-design.md docs/ROLE_TOKENS_INGAME_QA.md .changes/pending/role-tokens-macros.json --json --strict`

## Límites pendientes de comprobar

La API de macros no ofrece un identificador persistente. Si nombre, icono, índice y último cuerpo no permiten distinguir un renombrado de una sustitución, el addon conserva la plantilla y deja la macro intacta hasta que el usuario reintroduce el token. El chequeo de 255 **bytes** es conservador para texto UTF-8. No se han ejecutado las pruebas dentro de WoW Retail; `docs/ROLE_TOKENS_INGAME_QA.md` registra los recorridos pendientes, incluidos `secret values`, taint y llamadas protegidas.
