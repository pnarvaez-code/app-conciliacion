-- Bases de datos de la plataforma.
--
-- La imagen de PostgreSQL crea la base "pyme" al inicializarse; este archivo
-- agrega las otras dos. Se ejecuta UNA sola vez, cuando el volumen de datos
-- esta vacio (primer arranque del servicio postgres).
--
-- Cada servicio aplica despues su propio esquema al iniciar.

SELECT 'CREATE DATABASE banco'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'banco')\gexec

SELECT 'CREATE DATABASE conciliador'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'conciliador')\gexec
