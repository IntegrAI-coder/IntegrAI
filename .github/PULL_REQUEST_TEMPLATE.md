## Qué cambia

<!-- Describe el cambio en 1-3 líneas. -->

## Por qué

<!-- Problema o requisito que resuelve. Enlaza el issue/PR relacionado si existe. -->

## Cómo probarlo

<!-- Comandos exactos. Recuerda: los tests corren offline con MODO_MOCK=1. -->
```bash
MODO_MOCK=1 pytest -q tests
```

## Checklist

- [ ] `pytest -q tests` pasa en local
- [ ] No hay secretos ni `.env` (lo cubre Gitleaks)
- [ ] No hay PII (nombres, teléfonos, IPs, RUT)
- [ ] Documentación actualizada si aplica
- [ ] Cambio acotado y commits atómicos
