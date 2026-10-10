# Servicio Conciliador

Herramienta del auditor. Recibe los archivos de la empresa y del banco
(CSV o XML), verifica cada uno contra el sello de su emisor (intacto,
alterado con el movimiento exacto, o sin sello), concilia en tres niveles e
informa las diferencias agrupadas por tipo.

- Puerto: 8000
- Base: PostgreSQL propia (la migracion se aplica en el arranque)
- Variables: `.env.example` (copiar a `.env`; el `.env` no se versiona)
- Arranque: `python -m app.inicio` y luego `uvicorn app.main:app --port 8000`
- Pruebas sin base: `python -m tests.test_sellos` y `python -m tests.test_conciliacion`
