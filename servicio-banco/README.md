# Servicio Banco

Movimientos de la cuenta del cliente. Emite el extracto del periodo en CSV
o XML, lo sella en la cadena de bloques y permite re-emitirlo (queda
versionado). Verifica sus propios extractos emitidos.

- Puerto: 8002
- Base: PostgreSQL propia (la migracion se aplica en el arranque)
- Variables: `.env.example` (copiar a `.env`; el `.env` no se versiona)
- Arranque: `python -m app.inicio` y luego `uvicorn app.main:app --port 8002`
- Pruebas sin base: `python -m tests.test_sellos`
