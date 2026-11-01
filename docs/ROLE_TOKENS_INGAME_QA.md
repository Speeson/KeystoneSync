# Role tokens — checklist en WoW Retail 12.1

Estado: **pendiente de ejecución dentro del juego**. Las pruebas automatizadas no verifican taint, valores `secret` reales ni el comportamiento de la UI de macros.

- [ ] Login y `/reload` con el personaje solo: `/ksrole status` no muestra candidatos y no hay errores Lua.
- [ ] Macro con `[@tank,exists]` en party: apunta al UnitID del tanque; `@tank2` permanece literal si falta segundo tanque.
- [ ] Dos tanques asignados: `@tank` y `@tank2` apuntan a miembros distintos en orden de party.
- [ ] Raid con tanques, sanadores y DPS: índices por rol y prioridad del Main Tank; cambiar la marca actualiza la macro.
- [ ] Jugador local asignado a cada rol: no aparece como candidato de su propio rol.
- [ ] Rol `NONE`: no se infiere ninguna especialización.
- [ ] Modificar el roster o rol en combate: ninguna llamada protegida ni edición hasta `PLAYER_REGEN_ENABLED`.
- [ ] Guardar una macro con `@focus`, `@tank` y fallbacks: preservar lo demás y comprobar el resultado al pulsarla.
- [ ] Macro con `@party1` sin tokens de rol: cuerpo inalterado.
- [ ] Macro de más de 255 bytes tras expansión: cuerpo intacto y un único aviso.
- [ ] Editar manualmente una macro gestionada, quitar token, renombrar, borrar y reutilizar índice: no sobrescribir una macro ajena.
- [ ] Macros generales y específicas de personaje con nombres duplicados; relog y `/reload`: plantillas intactas.
- [ ] `/ksrole disable` y `/ksrole restore`: texto original recuperado; repetir durante combate y comprobar la restauración posterior.
- [ ] RoleTokens cargado a la vez: gestión suspendida, sin oscilación de cuerpos ni spam.
- [ ] En Retail Midnight: sin errores de `secret value`, taint o acción protegida en todos los recorridos anteriores.

Si se desinstala el addon sin ejecutar antes `/ksrole restore`, las macros ya expandidas no pueden restaurarse automáticamente.
