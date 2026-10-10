-- Migracion inicial de la base `banco`
--
-- Convenciones: nombres en espanol y plural, id BIGSERIAL, created_at y
-- updated_at con zona horaria (timestamptz, se guarda en UTC), claves
-- foraneas con REFERENCES. Normalizacion basica (3FN). Los detalles que son
-- fotografias historicas se guardan como jsonb.
--
-- Este archivo es el DER en SQL: cada tabla y columna esta comentada.

CREATE TABLE usuarios (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    clave_hash      TEXT NOT NULL,              -- bcrypt; nunca la clave
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por      BIGINT REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sesiones (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,       -- hash del token de la cookie
    expira_en       TIMESTAMPTZ NOT NULL,
    ip              TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE archivos (
    id              BIGSERIAL PRIMARY KEY,
    nombre          TEXT NOT NULL,              -- nombre del archivo
    ruta            TEXT NOT NULL,              -- ubicacion en el volumen
    sha256          CHAR(64) NOT NULL,          -- huella del contenido
    bytes           BIGINT NOT NULL,
    origen          TEXT NOT NULL CHECK (origen IN ('emitido','recibido')),
    subido_por      BIGINT REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE lotes (
    id              BIGSERIAL PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,        -- V-... (pyme) / E-... (banco)
    n_movimientos   INTEGER NOT NULL,
    archivo_id      BIGINT REFERENCES archivos(id),
    sellado_en      TIMESTAMPTZ,
    sellado_por     BIGINT REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Movimientos: ventas (PYME) o movimientos de la cuenta (Banco).
CREATE TABLE movimientos (
    id              BIGSERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    monto           BIGINT NOT NULL CHECK (monto > 0),   -- guaranies, entero
    referencia      TEXT NOT NULL DEFAULT '',
    descripcion     TEXT NOT NULL DEFAULT '',
    estado          TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','en_lote')),
    lote_id         BIGINT REFERENCES lotes(id),
    creado_por      BIGINT REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_movimientos_fecha ON movimientos (fecha);
CREATE INDEX idx_movimientos_lote ON movimientos (lote_id);
CREATE INDEX idx_movimientos_referencia ON movimientos (referencia);


CREATE TABLE bloques (
    id                  BIGSERIAL PRIMARY KEY,
    indice              BIGINT NOT NULL UNIQUE,     -- orden en la cadena
    origen              TEXT NOT NULL,              -- PYME | BANCO | CONCILIADOR
    lote_codigo         TEXT NOT NULL,
    archivo             TEXT NOT NULL,
    n_movimientos       INTEGER NOT NULL,
    hashes_movimientos  JSONB NOT NULL,             -- huellas, en orden
    hash_raiz           CHAR(64) NOT NULL,
    hash_archivo        CHAR(64) NOT NULL,
    hash_anterior       CHAR(64) NOT NULL,
    hash_bloque         CHAR(64) NOT NULL UNIQUE,
    emitido_por         BIGINT REFERENCES usuarios(id),
    sellado_en          TEXT NOT NULL,          -- instante ISO: entra en la huella
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bloques_envios (
    id              BIGSERIAL PRIMARY KEY,
    bloque_id       BIGINT NOT NULL REFERENCES bloques(id) ON DELETE CASCADE,
    destino         TEXT NOT NULL,                  -- servicio destino
    estado          TEXT NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente','enviado','fallido')),
    intentos        INTEGER NOT NULL DEFAULT 0,
    ultimo_error    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bloque_id, destino)
);

CREATE TABLE alertas (
    id              BIGSERIAL PRIMARY KEY,
    tipo            TEXT NOT NULL CHECK (tipo IN ('integridad','diferencia','operativa')),
    severidad       TEXT NOT NULL CHECK (severidad IN ('alta','media','baja')),
    titulo          TEXT NOT NULL,
    detalle         TEXT NOT NULL,
    referencia      TEXT,                        -- lote, archivo o movimiento
    usuario_id      BIGINT REFERENCES usuarios(id),
    estado          TEXT NOT NULL DEFAULT 'nueva'
                    CHECK (estado IN ('nueva','leida','resuelta')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- La auditoria no se actualiza: solo se agregan filas (append-only).
CREATE TABLE auditoria (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      BIGINT REFERENCES usuarios(id),
    accion          TEXT NOT NULL,               -- login, alta_movimiento, sello, carga_archivo...
    entidad         TEXT,                        -- tabla afectada
    entidad_id      TEXT,
    detalle         JSONB,
    ip              TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
