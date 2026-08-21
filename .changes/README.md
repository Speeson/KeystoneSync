# Changesets

Release-impacting addon changes must add one JSON file under `.changes/pending/`.

Schema:

```json
{
  "components": ["addon"],
  "type": "patch",
  "category": "fixed",
  "summary": "Corrige un problema visible.",
  "details": [
    "Detalle visible para usuarios."
  ]
}
```

Allowed `components`: `addon`.

Allowed `type` values: `patch`, `minor`, `major`.

Allowed `category` values: `added`, `changed`, `fixed`, `removed`, `security`.

User-facing `summary`, `details`, and generated release notes must be written in Spanish.
