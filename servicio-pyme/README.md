# Servicio PYME

Ventas de la empresa. Registra los movimientos del dia, cierra el lote
generando el archivo CSV del periodo y lo sella en la cadena de bloques.
Permite re-emitir (queda versionado) y verificar sus propios lotes.

- Puerto: 8001
- Base: PostgreSQL propia (la migracion se aplica en el arranque)
- Variables: `.env.example` (copiar a `.env`; el `.env` no se versiona)
- Arranque: `python -m app.inicio` y luego `uvicorn app.main:app --port 8001`
- Pruebas sin base: `python -m tests.test_sellos`
