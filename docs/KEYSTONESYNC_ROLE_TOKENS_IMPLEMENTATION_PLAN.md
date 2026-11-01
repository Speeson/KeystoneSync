# KeystoneSync — Plan de implementación de tokens dinámicos por rol

**Estado:** Implementado en código; pruebas in-game pendientes (véase `docs/ROLE_TOKENS_INGAME_QA.md`)
**Objetivo:** Incorporar al **addon de World of Warcraft Retail de KeystoneSync** la resolución automática de los tokens `@tank`, `@tank2`, `@healer`, `@healer2`, `@dps`, etc. dentro de macros normales de WoW.
**Alcance:** Solo addon Lua de WoW; **sin cambios** en KeystoneClient, web, API, sincronización o addon export/import, salvo que el repositorio obligue a ajustar el empaquetado del addon.

## 0. Instrucciones iniciales para Codex

1. Inspeccionar la estructura real del repositorio, su fichero `.toc`, módulos Lua, SavedVariables, sistema de eventos, pruebas, empaquetado y convenciones. **No asumir rutas ni nombres**.
2. Revisar como referencia el proyecto [RoleTokens](https://github.com/Druiddeleted/RoleTokens), especialmente la detección de roles, gestión de macros, recuperación de las plantillas originales y funcionamiento fuera de combate. Su licencia es MIT: si se copia/adapta código sustancial, conservar los avisos de copyright/licencia correspondientes y documentarlo. No copiar funcionalidades no solicitadas.
3. Confirmar contra la API de la versión Retail objetivo (12.x/Midnight) los nombres, firmas, valores `secret` y restricciones de seguridad de todas las funciones utilizadas. No dar por hecho que un ejemplo de versiones anteriores sigue funcionando.
4. Escribir un plan de cambios compatible con la arquitectura encontrada y ejecutar incrementalmente. No refactorizar otras partes de KeystoneSync sin necesidad.

## 1. Alcance funcional (V1)

Los usuarios podrán escribir en **macros estándar del juego** los tokens de rol:

| Token | Significado |
| --- | --- |
| `@tank` y `@tank1` | Primer tanque elegible |
| `@tank2`, `@tank3`, ... | Segundo, tercer, etc. tanque elegible |
| `@healer` y `@healer1` | Primer sanador elegible |
| `@healer2`, `@healer3`, ... | Segundo, tercer, etc. sanador elegible |
| `@dps` y `@dps1` | Primer DPS elegible |
| `@dps2`, `@dps3`, ... | Segundo, tercer, etc. DPS elegible |

- Reconocer tokens de forma **insensible a mayúsculas/minúsculas** cuando estén en el lugar de un unit selector de una macro (`@tank`, `@Tank2`, etc.). Evitar sustituir apariciones en nombres, texto libre, comentarios o identificadores más largos.
- Resolver cada token a un **UnitID de WoW válido** (`party1`...`party4` o `raid1`...`raid40`), nunca a un nombre ambiguo de personaje.
- **Excluir al jugador local** del listado de candidatos de todos los roles, como hace RoleTokens. Documentar esta decisión; no añadir un ajuste para incluirlo en V1.
- No detectar o inferir especializaciones: utilizar el rol **asignado por el grupo** mediante `UnitGroupRolesAssigned(unit)` (`TANK`, `HEALER`, `DAMAGER`, `NONE`). Si está `NONE`, no clasificarlo por conjetura.
- En una party, ordenar por índice `party1` a `party4`. En raid, ordenar por índice `raid1` a `raid40`, con la **excepción del Main Tank designado** cuando sea aplicable.
- Si en banda existe un tanque asignado explícitamente como **Main Tank** (`GetPartyAssignment("MAINTANK", unit)`), priorizarlo para `@tank`/`@tank1`; los restantes tanques se ordenan establemente por índice de banda. Si varios tienen la marca, desempatar por índice. Confirmar compatibilidad de la API antes de implementarlo.
- Si un token no tiene candidato (`@tank2` con un solo tanque, sin grupo, etc.), **dejarlo sin resolver en la plantilla expandida**; no reemplazarlo por `target`, `player` ni por otro compañero. Documentar que las macros deben incluir `exists` y/o `help`/`nodead` para fallbacks seguros.
- No alterar `focus`, `target`, barras de acción, asignaciones de teclado ni hacer casts desde el addon.

### Ejemplo de resultado

Macro que el usuario define:

```lua
#showtooltip Tricks of the Trade
/cast [@focus,help,nodead][@tank,exists,help,nodead][@tank2,exists,help,nodead] Tricks of the Trade
```

En una raid donde el primer tanque elegible es `raid7` y el segundo `raid12`, el cuerpo operativo será:

```lua
#showtooltip Tricks of the Trade
/cast [@focus,help,nodead][@raid7,exists,help,nodead][@raid12,exists,help,nodead] Tricks of the Trade
```

> **Nota importante:** los tokens `@tank`/`@healer` **no son unitIDs nativos**. Es KeystoneSync quien los sustituye por UnitIDs reales **fuera de combate**. Las condiciones de la macro (por ejemplo, `nodead`) las evalúa WoW en el momento de pulsarla.

## 2. Diseño técnico propuesto

Separar la lógica en módulos o funciones equivalentes según la arquitectura real:

1. **RoleResolver**: recopila miembros de party/raid, roles, identidad del jugador y marca de Main Tank; devuelve listas deterministas por rol y una tabla de tokens → UnitIDs.
2. **MacroTemplateStore**: mantiene de forma persistente el **texto original** de las macros gestionadas (con `@tank`, etc.) y metadatos mínimos para reconocerlas sin confundirlas después de renombrados, eliminaciones o cambios de índice.
3. **MacroManager**: encuentra macros candidatas, genera las versiones expandidas, compara cuerpos, comprueba límites, edita exclusivamente cuando es seguro y permite recuperar la plantilla.
4. **EventCoordinator**: escucha cambios de grupo/rol/macros, agrupa actualizaciones redundantes y aplaza los cambios durante el combate.

**SavedVariables:** reutilizar el sistema existente si lo hay. Definir migración/versionado de esquema si procede. **No sobrescribir otras claves o estructuras de KeystoneSync.**

### Ciclo de vida y detección

- En login / entrada al mundo, descubrir estado de grupo y macros.
- Escuchar como mínimo `PLAYER_ENTERING_WORLD`, `GROUP_ROSTER_UPDATE`, `PLAYER_ROLES_ASSIGNED`, `PLAYER_REGEN_ENABLED` y `UPDATE_MACROS` (verificar nombres/disponibilidad en Retail objetivo).
- Cubrir cambios de Main Tank / asignaciones de raid con el evento apropiado si fuera necesario; verificarlo en la API real.
- Cuando aparezca, desaparezca o cambie una macro con tokens, incorporarla o actualizar su plantilla; **no capturar por error como plantilla una versión ya expandida por el propio addon**.
- Durante `InCombatLockdown()`: **no llamar a `EditMacro` ni a otras APIs protegidas**; guardar `dirty/pending` y recalcular/aplicar después de `PLAYER_REGEN_ENABLED`.
- Prevenir bucles de `UPDATE_MACROS` originados por ediciones del propio addon; procesar por lotes y editar solo si el cuerpo resultante ha cambiado.
- No ejecutar escaneos continuos por frame, ni un `OnUpdate` permanente.

### Integridad de las macros (obligatorio)

- **No crear una segunda macro por cada macro detectada**: se deben administrar las macros estándares que el usuario ya tiene, preservando icono, nombre, ámbito y posición si las APIs lo permiten.
- El cuerpo editado por KeystoneSync debe poder reconstruirse a partir de la **plantilla original**, no de una expansión previa (evita UnitIDs obsoletos y reemplazos acumulativos).
- Definir explícitamente cómo se distingue un **cambio manual del usuario** de una edición del addon. Si no se puede recuperar con seguridad la intención del usuario, **no sobrescribir silenciosamente**: mostrar aviso y dejar la macro intacta hasta resolución.
- Manejar correctamente macros generales y específicas de personaje; índices reutilizados, macros eliminadas, renombradas y nombres duplicados. Codex debe investigar la identidad disponible en la API y diseñar el almacenamiento conforme a ella; no asumir que `GetMacroIndexByName` ofrece un identificador único estable.
- Cuando un usuario elimine un token manualmente, dejar de gestionar esa macro (o proporcionar opción clara de desvinculación). Ofrecer una forma segura de **restaurar texto de plantilla** al desactivar la función o desinstalar el addon; documentar que desinstalar directamente sin restaurar no puede ejecutar código de limpieza.
- Antes de editar, validar el **límite real de caracteres** permitido por `EditMacro`/la versión Retail, incluyendo la expansión. Si supera el límite, conservar el cuerpo anterior, informar del error y **no truncar**.
- Ante errores de API, límites, datos `secret` o macros con formato no admitido: degradación segura, sin bloquear la carga del addon.

## 3. Interfaz y control (V1 mínima)

Mantener la integración ligera y coherente con KeystoneSync:

- Estado **activado/desactivado** de la función, persistente por el ámbito apropiado según SavedVariables actuales (predeterminado: **activado**). Solo se gestionan macros con tokens de rol reconocidos; si se detecta otro addon que gestione la misma macro, aplicar la protección conservadora de la sección 4.
- Comando(s) de chat con prefijo libre que **no colisione** con comandos existentes de KeystoneSync. Funciones mínimas: `enable`, `disable`, `status`, `refresh`, `restore` (nombres definitivos según convenciones del proyecto).
- `status`: mostrar grupo detectado, asignaciones de `@tank/@tank2`, `@healer/...`, `@dps/...` y cantidad de macros gestionadas; indicar si hay una actualización pendiente de salir de combate.
- `restore`: restaurar con seguridad las plantillas originales de las macros gestionadas; aplazar si se está en combate.
- Mensajes de error discretos, sin spam, especialmente cuando no hay grupo o un token queda sin candidato.
- **No desarrollar en V1** una página de opciones grande, minimap button, selección manual de nombres, listas personalizadas, perfiles complejos ni integración con la app desktop.

## 4. Límites y compatibilidad

- **Retail solamente**: no prometer que funcione en Classic o WoW Forever. Conservar separación de entornos que ya exista en KeystoneSync.
- Las API de Midnight pueden devolver **secret values** en determinados contextos. Codex debe evitar operaciones prohibidas con esos valores y probar los recorridos reales dentro del juego.
- **No es un sistema de casting automático**; no intenta sortear el sistema secure de Blizzard.
- La resolución de roles refleja roles *asignados*, no necesariamente la especialización o el jugador que está tanqueando de verdad. Si no hay rol asignado, no improvisar.
- Puede coexistir con addons que no editen las mismas macros. Si se detecta **RoleTokens** u otro gestor de macros que pueda competir por ellas, implementar una protección conservadora: advertencia y suspensión de gestión de macros compartidas o de toda la funcionalidad hasta que el usuario decida; no entrar en ciclos de sobrescritura.
- Las alteraciones de roster o roles durante combate quedan pendientes hasta que termine el lockdown. Avisar cuando proceda.

## 5. Plan de ejecución para Codex

### Fase A — Análisis del proyecto y API

- [ ] Localizar el addon, TOC, dependencias, SavedVariables, entrypoints, comandos y pruebas.
- [ ] Revisar el fuente de RoleTokens, documentar decisiones relevantes y licencia.
- [ ] Verificar APIs y eventos de Retail objetivo, valores secret y límite de macros.
- [ ] Proponer archivos a crear/modificar y estrategia de persistencia y recuperación.

**Entregable:** breve nota de arquitectura antes de implementar.

### Fase B — RoleResolver

- [ ] Enumerar party, raid y estado solo; excluir jugador local.
- [ ] Clasificar por `TANK` / `HEALER` / `DAMAGER`; ignorar `NONE`.
- [ ] Resolver `@tank`, `@tankN`, `@healer`, `@healerN`, `@dps`, `@dpsN` de forma determinista.
- [ ] Priorizar Main Tank de banda si está designado y la API lo permite.
- [ ] Crear pruebas unitarias de orden, índices, roles múltiples, ausencias y cambios.

**Entregable:** componente de resolución testeable sin tocar macros.

### Fase C — Plantillas y expansión segura

- [ ] Implementar detección de tokens en selectores de unidad de macros, sin sustituciones accidentales.
- [ ] Guardar y recuperar plantillas originales con metadatos.
- [ ] Resolver solo los tokens disponibles; conservar los que no tengan candidato.
- [ ] Validar tamaño resultante y comparar con cuerpo existente.
- [ ] Cubrir rename/delete/reuse/edit manual/cambios de ámbito.

**Entregable:** motor de expansión no destructivo con pruebas.

### Fase D — Eventos, combate y aplicación

- [ ] Integrar eventos relevantes; evitar actualizaciones redundantes.
- [ ] Aplicar `EditMacro` solo fuera de combate.
- [ ] Reintentar cambios pendientes al terminar el combate.
- [ ] Prevenir bucles de eventos por cambios propios.
- [ ] Proteger ante conflicto con otros addons gestores de macros.

**Entregable:** actualización automática de macros cuando cambia el grupo.

### Fase E — Control, documentación y QA

- [ ] Añadir comandos mínimos de activación, estado, refresh y restore.
- [ ] Documentar instalación, activación, ejemplos y `exists`/`help`/`nodead`.
- [ ] Ejecutar pruebas, linter/validaciones disponibles y empaquetado.
- [ ] Crear checklist de pruebas manuales *in-game* y anotar cualquier caso no comprobado.
- [ ] Resumir archivos modificados, compatibilidad, límites y riesgos restantes.

**Entregable:** V1 documentada y apta para prueba manual en WoW Retail.

## 6. Matriz de pruebas / criterios de aceptación

| Escenario | Resultado esperado |
| --- | --- |
| Personaje solo | Sin candidatos; macro no apunta automáticamente a nadie |
| Party de 5 con un tank | `@tank` → UnitID del tanque; `@tank2` sin resolver |
| Party con dos tanks asignados | `@tank` y `@tank2` apuntan a miembros distintos según orden |
| Raid con 2 tanks y 4 healers | `@tank`/`@tank2` y `@healer`...`@healer4` resuelven correctamente |
| Main Tank marcado en raid | `@tank` prioriza Main Tank; orden restante estable |
| Player es tank o healer | El jugador no aparece en su propio listado de rol |
| Un healer cambia a DPS | El listado se reordena correctamente fuera de combate |
| Cambia el grupo durante combate | No se edita macro en combate; se actualiza al salir |
| Macro usa `@focus` y `@tank` | Se preserva `@focus` y resto de sintaxis |
| No existe `@tank2` | No redirige silenciosamente a otro destino; fallbacks quedan a cargo de condiciones de WoW |
| Macro demasiado larga | No truncar ni corromper; aviso controlado |
| El usuario modifica macro | Su cambio no se pierde sin consentimiento; plantilla reconciliada o conflicto señalado |
| Macro eliminada, renombrada o índice reutilizado | No sobrescribir otra macro por error |
| Addon desactivado/restauración | Macro recupera plantilla original fuera de combate |
| RoleTokens simultáneo | No hay bucle ni sobrescritura entre addons |
| Cambios repetidos / `UPDATE_MACROS` | No hay bucles ni spam ni edición redundante |
| Reload UI / relog | Persistencia consistente; no se pierde plantilla |
| Retail Midnight | Sin errores de Lua, `secret values`, taint o acciones protegidas al usar la función |

**Se considerará completado solo cuando pasen los tests automatizables y se hayan realizado o declarado pendientes las pruebas manuales in-game.** No declarar resultados in-game sin haberlos ejecutado.

## 7. Fuera de alcance (no implementar)

- Crear una macro específica de Tricks of the Trade o de cualquier clase.
- Seleccionar manualmente amigos preferidos, nombres, reinos, BattleTags o alts.
- Copiar toda la configuración o interfaz de RoleTokens.
- Casting automático o modificación de teclas/barras de acción.
- Integración con KeystoneClient, backend, web, API, inventario, equipo, talentos o sincronización.
- Soporte oficial para WoW Forever / Classic en esta iteración.

## 8. Recursos de referencia

- [RoleTokens — repositorio y documentación](https://github.com/Druiddeleted/RoleTokens)
- [RoleTokens — CurseForge (versión Retail)](https://www.curseforge.com/wow/addons/role-tokens)
- [WoW API: UnitGroupRolesAssigned](https://warcraft.wiki.gg/wiki/API:UnitGroupRolesAssigned)
- [WoW API: GetPartyAssignment](https://warcraft.wiki.gg/wiki/API:GetPartyAssignment)
- [WoW API: InCombatLockdown](https://warcraft.wiki.gg/wiki/API:InCombatLockdown)

> Nota para Codex: estas referencias sirven para orientación, **no** sustituyen la verificación de código y API de la versión del juego realmente soportada.

## 9. Definición de terminado

- [ ] El addon habilita el uso de `@tank`, `@tankN`, `@healer`, `@healerN`, `@dps`, `@dpsN` en macros habituales del juego.
- [ ] Funciona en party y raid, también con varios miembros por rol.
- [ ] Conserva/reconstruye plantillas y restaura sin destruir macros del usuario.
- [ ] Respeta el lockdown de combate y maneja actualizaciones pendientes.
- [ ] Se integra con el proyecto sin alterar otras funciones de KeystoneSync.
- [ ] Pruebas automatizadas y checklist de pruebas manuales documentados.
- [ ] README/changelog actualizado según las convenciones del repositorio.
