-- Bases de datos de la plataforma.
--
-- La imagen de PostgreSQL crea la base "pyme" al inicializarse; este archivo
-- agrega las otras dos. Se ejecuta UNA sola vez, cuando el volumen de datos
-- esta vacio (primer arranque del servicio postgres).
--
-- Cada servicio aplica despues su propio esquema al iniciar.

CREATE DATABASE banco;
CREATE DATABASE conciliador;
