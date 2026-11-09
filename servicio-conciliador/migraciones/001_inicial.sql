-- Migracion inicial de la base `conciliador`
--
-- Convenciones: nombres en espanol y plural, id BIGSERIAL, created_at y
-- updated_at con zona horaria (timestamptz, se guarda en UTC), claves
-- foraneas con REFERENCES. Normalizacion basica (3FN). Los detalles que son
-- fotografias historicas se guardan como jsonb.
--
-- Este archivo es el DER en SQL: cada tabla y columna esta comentada.

CREATE TABLE IF NOT EXISTS usuarios (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    clave_hash      TEXT NOT NULL,              -- bcrypt; nunca la clave
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado_por      BIGINT REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sesiones (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      BIGINT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,       -- hash del token de la cookie
    expira_en       TIMESTAMPTZ NOT NULL,
    ip              TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS archivos (
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


-- El conciliador no produce movimientos propios: recibe archivos y los
-- verifica contra los sellos. Estas tablas reflejan ese trabajo.

CREATE TABLE IF NOT EXISTS recepciones (
    id                  BIGSERIAL PRIMARY KEY,
    archivo_id          BIGINT NOT NULL REFERENCES archivos(id),
    origen              TEXT NOT NULL CHECK (origen IN ('EMPRESA','BANCO')),
    lote_codigo         TEXT,
    estado_integridad   TEXT NOT NULL
                        CHECK (estado_integridad IN ('intacto','alterado','sin_sello')),
    detalle             TEXT,
    verificado_en       TIMESTAMPTZ,
    verificado_por      BIGINT REFERENCES usuarios(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conciliaciones (
    id                  BIGSERIAL PRIMARY KEY,
    desde               DATE,
    hasta               DATE,
    total_empresa       INTEGER NOT NULL DEFAULT 0,
    total_banco         INTEGER NOT NULL DEFAULT 0,
    conciliados         INTEGER NOT NULL DEFAULT 0,
    porcentaje          INTEGER NOT NULL DEFAULT 0,
    recepcion_empresa_id BIGINT REFERENCES recepciones(id),
    recepcion_banco_id  BIGINT REFERENCES recepciones(id),
    ejecutada_por       BIGINT REFERENCES usuarios(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pares conciliados: se guarda la fotografia de ambos movimientos (jsonb).
CREATE TABLE IF NOT EXISTS conciliacion_pares (
    id                  BIGSERIAL PRIMARY KEY,
    conciliacion_id     BIGINT NOT NULL REFERENCES conciliaciones(id) ON DELETE CASCADE,
    nivel               INTEGER NOT NULL CHECK (nivel IN (1,2,3)),
    movimiento_empresa  JSONB NOT NULL,
    movimiento_banco    JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Diferencias y pendientes, clasificados por tipo (escenarios del tribunal).
CREATE TABLE IF NOT EXISTS conciliacion_pendientes (
    id                  BIGSERIAL PRIMARY KEY,
    conciliacion_id     BIGINT NOT NULL REFERENCES conciliaciones(id) ON DELETE CASCADE,
    origen              TEXT NOT NULL CHECK (origen IN ('EMPRESA','BANCO')),
    tipo_diferencia     TEXT NOT NULL CHECK (tipo_diferencia IN
                        ('en_banco_no_empresa','en_empresa_no_banco',
                         'monto_distinto','fuera_de_ventana','referencia_distinta')),
    movimiento          JSONB NOT NULL,
    motivo              TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE IF NOT EXISTS bloques (
    id                  BIGSERIAL PRIMARY KEY,
    indice              BIGINT NOT NULL,            -- orden dentro del origen
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_bloques_origen_indice
    ON bloques (origen, indice);

-- El conciliador no propaga bloques (solo los recibe y verifica), asi que no
-- lleva la tabla de envios que si tienen PYME y Banco.

CREATE TABLE IF NOT EXISTS alertas (
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
CREATE TABLE IF NOT EXISTS auditoria (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      BIGINT REFERENCES usuarios(id),
    accion          TEXT NOT NULL,               -- login, alta_movimiento, sello, carga_archivo...
    entidad         TEXT,                        -- tabla afectada
    entidad_id      TEXT,
    detalle         JSONB,
    ip              TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
