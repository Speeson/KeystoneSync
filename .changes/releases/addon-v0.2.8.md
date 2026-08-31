# KeystoneSync 0.2.8

## Correcciones

- Corrige las variantes exactas de favoritos de KeystoneLoot entre especializaciones.
  - Reutiliza de forma segura la variante mostrada para todas las especializaciones concretas que KeystoneLoot emite al usar Todas las especializaciones.
  - Conserva correctamente nivel de objeto, calidad y variante exacta, y evita favoritos genéricos duplicados derivados de variantes base.
- Permite detectar reinicializaciones reales de los datos locales del addon.
  - Añade un identificador persistente de la instancia de SavedVariables para que KeystoneClient pueda reconciliar favoritos obsoletos de KeystoneLoot sin borrar personajes.
