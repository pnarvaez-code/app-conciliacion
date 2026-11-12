# Plataforma de conciliación con integridad verificable

## Documentación de la tesis

La memoria académica del proyecto está disponible en
[`docs/TCC.md`](docs/TCC.md). Incluye portada institucional, resumen,
abstract, problema, objetivos, marco teórico, metodología, arquitectura de
los tres servicios, seguridad, reportes PDF, validación, conclusiones,
referencias y anexos de despliegue.

Aplicación compuesta por tres servicios FastAPI que trabajan como una
plataforma de conciliación:

1. **PYME** administra las ventas y genera el archivo de ventas.
2. **Banco** administra los movimientos bancarios y genera el extracto.
3. **Conciliador** recibe ambos archivos, verifica sus sellos y ejecuta la
   conciliación.

Cada servicio tiene su propia aplicación, base de datos PostgreSQL, usuarios,
sesiones, auditoría y copia de los bloques que le corresponden.

## Arquitectura actual

| Servicio | Carpeta | Puerto local | Función |
|---|---|---:|---|
| PYME | `servicio-pyme` | `8001` | Ventas, cierres, CSV y sellado |
| Banco | `servicio-banco` | `8002` | Movimientos, extractos CSV/XML y sellado |
| Conciliador | `servicio-conciliador` | `8000` interno / `8080` local | Recepción, verificación y conciliación |

### Sincronización de la cadena

PYME y Banco mantienen **cadenas independientes**. Cada servicio propaga sus
bloques únicamente al Conciliador mediante la API interna protegida por
`X-Servicio-Token`.

El Conciliador también puede recuperar bloques faltantes consultando a PYME y
Banco desde **Cadena → Sincronizar**. Cada respuesta se valida contra el
origen esperado y la huella del bloque antes de guardarse:

```text
PYME  ──propaga──> Conciliador
Banco ──propaga──> Conciliador
PYME  <──consulta── Conciliador
Banco <──consulta── Conciliador
```

No se mezclan los índices de PYME y Banco. El Conciliador valida cada cadena
por separado y conserva conflictos o errores como alertas de integridad.

## Requisitos

- Python 3.11 o superior.
- Docker y Docker Compose para la instalación local recomendada.
- PostgreSQL 14 o superior si se ejecuta sin Docker.
- Para Heroku: tres aplicaciones Heroku y una base Heroku Postgres para cada
  aplicación.

## Instalación local con Docker Compose

Todos los comandos se ejecutan desde la raíz del repositorio.

### 1. Configurar el entorno

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Para una demostración local se pueden conservar los valores de ejemplo. Para
un entorno compartido, cambiar como mínimo `CLAVE_BASE_DATOS`,
`TOKEN_SERVICIO`, las tres claves de sesión y `ADMIN_CLAVE`.

### 2. Iniciar los cuatro contenedores

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.local.yml \
  up -d --build
```

## Despliegue desde GitHub con Docker

Cada publicación en la rama `main` construye las imágenes de PYME, Banco y
Conciliador y las publica en GitHub Container Registry (GHCR). En un servidor
con Docker, clone el repositorio, copie `.env.example` a `.env` y ejecute:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  -f docker-compose.images.yml pull
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  -f docker-compose.images.yml up -d
```

Para actualizar el servidor después de un nuevo `git push`, ejecute los mismos
dos comandos. Las imágenes se descargan desde `ghcr.io/pnarvaez-code/` y los
datos permanecen en los volúmenes Docker de PostgreSQL y de cada servicio.

La primera ejecución:

- inicia PostgreSQL;
- crea las bases `pyme`, `banco` y `conciliador`;
- ejecuta la migración inicial de cada servicio;
- crea el administrador inicial;
- inicia las tres aplicaciones.

Para iniciar desde cero y borrar los datos existentes:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.local.yml \
  down -v --remove-orphans
docker compose \
  -f docker-compose.yml \
  -f docker-compose.local.yml \
  up -d --build
```

El comando `down -v` elimina las bases y los archivos almacenados. Usarlo
solo cuando se quiera reiniciar la demostración.

### 3. Abrir las aplicaciones

| Servicio | URL | Usuario inicial |
|---|---|---|
| PYME | `http://localhost:8001` | `admin@ejemplo.com` |
| Banco | `http://localhost:8002` | `admin@ejemplo.com` |
| Conciliador | `http://localhost:8080` | `admin@ejemplo.com` |

La clave inicial se toma de `ADMIN_CLAVE`. El valor de ejemplo es
`conciliacion2026`; debe cambiarse antes de usar información real.

### 4. Revisar logs y estado

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml ps
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f pyme
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f banco
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f conciliador
```

## Flujo funcional completo

### 1. Cargar movimientos

Desde la interfaz se pueden registrar movimientos o importar archivos. Para
importar los ejemplos dentro de los contenedores:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml \
  exec -T pyme python -m app.importar ejemplos/ventas_ejemplo.csv

docker compose -f docker-compose.yml -f docker-compose.local.yml \
  exec -T banco python -m app.importar ejemplos/extracto_ejemplo.csv
```

Las referencias duplicadas se omiten y la importación queda registrada en
Auditoría.

### 2. Cerrar y sellar

En PYME:

1. Abrir **Lotes**.
2. Seleccionar **Cerrar lote y exportar**.
3. Descargar el archivo de ventas.

En Banco:

1. Abrir **Lotes**.
2. Seleccionar **Emitir extracto**.
3. Descargar el extracto CSV o XML.

Cada cierre crea un bloque con:

- hash SHA-256 del archivo;
- hash de cada movimiento;
- hash raíz de los movimientos;
- índice y hash del bloque anterior;
- fecha, origen y usuario emisor.

Los bloques nuevos se envían automáticamente al Conciliador. Si un servicio
está temporalmente fuera de línea, el envío queda en `bloques_envios` y se
reintenta durante el arranque.

### 3. Sincronizar en el Conciliador

En el Conciliador:

1. Abrir **Cadena**.
2. Pulsar **Sincronizar**.
3. Confirmar que aparecen bloques de origen `PYME` y `BANCO`.

La sincronización consulta a cada origen desde su último índice local y hace
hasta tres intentos para tolerar dynos que están despertando en Heroku. Un
bloque repetido se acepta como ya existente; un conflicto de hash o de
encadenamiento genera una alerta.

### 4. Recibir y verificar archivos

En **Recepciones** subir:

1. el archivo emitido por PYME con origen `EMPRESA`;
2. el extracto emitido por Banco con origen `BANCO`.

El Conciliador compara cada archivo con su sello. Los estados principales son:

- `intacto`: el archivo coincide con el sello;
- `alterado`: cambió el contenido o un movimiento;
- `formato_invalido`: el archivo no puede interpretarse;
- `sin_sello`: no existe un bloque correspondiente.

### 5. Ejecutar la conciliación

En **Conciliación**, ejecutar el proceso para obtener:

- movimientos conciliados por referencia exacta;
- coincidencias por monto y fecha;
- coincidencias por descripción y monto aproximado;
- movimientos pendientes;
- diferencias de existencia, monto, fecha o referencia.

El **Visor** muestra el estado actualizado de la cadena, recepciones,
conciliación y alertas.

### Reportes PDF

Las tres aplicaciones incluyen el botón **Reporte PDF** en el menú principal.
La descarga genera un documento profesional con:

- usuario y fecha de generación;
- resumen de usuarios, operaciones auditadas, alertas y bloques;
- últimas operaciones registradas en Auditoría;
- alertas recientes y su severidad;
- identificación del servicio que emitió el reporte.

La ruta `/reporte` requiere una sesión activa y registra la descarga en
Auditoría. El PDF se genera en memoria, por lo que no crea archivos
temporales en Heroku.

## Verificación de las tres conexiones

La API interna de cada aplicación requiere el mismo `TOKEN_SERVICIO`. Para
probar una aplicación desplegada:

```bash
curl -i \
  -H "X-Servicio-Token: VALOR_REAL_DEL_TOKEN" \
  https://DOMINIO_DE_LA_APLICACION/interno/salud
```

Una conexión correcta devuelve HTTP `200` y un resultado similar a:

```json
{"estado":"ok","servicio":"PYME","ultimo_indice":0}
```

Probar los tres dominios:

```text
https://DOMINIO-PYME/interno/salud
https://DOMINIO-BANCO/interno/salud
https://DOMINIO-CONCILIADOR/interno/salud
```

Interpretación de errores:

| Resultado | Significado |
|---|---|
| `200` | Servicio disponible y token correcto |
| `401` | Falta `X-Servicio-Token` o no coincide |
| `404` | URL o ruta incorrecta |
| Timeout / error DNS | Dominio, despliegue o conexión incorrecta |
| `500` | Revisar logs y conexión `DATABASE_URL` |

## Despliegue detallado en Heroku

Heroku ejecuta este monorepo como **tres aplicaciones independientes**. No
se despliega `docker-compose.yml` en Heroku.

### 1. Crear las aplicaciones

Crear tres aplicaciones, por ejemplo:

```bash
heroku create nombre-pyme
heroku create nombre-banco
heroku create nombre-conciliador
```

Conectar las tres al mismo repositorio y a la misma rama. Cada aplicación
debe usar la raíz del repositorio como directorio de despliegue.

### 2. Agregar una base PostgreSQL a cada aplicación

```bash
heroku addons:create heroku-postgresql:essential-0 --app nombre-pyme
heroku addons:create heroku-postgresql:essential-0 --app nombre-banco
heroku addons:create heroku-postgresql:essential-0 --app nombre-conciliador
```

Heroku crea `DATABASE_URL` automáticamente. No copiar la URL de una base a
otra aplicación: cada servicio necesita su propia base.

### 3. Configurar variables

En Heroku, la conexión entre las aplicaciones no se configura con
`localhost`. Para los dominios actuales, usa:

| Aplicación | Variable | Valor |
|---|---|---|
| PYME | `URL_CONCILIADOR` | `https://app-conciliacion-caad17bda026.herokuapp.com` |
| Banco | `URL_CONCILIADOR` | `https://app-conciliacion-caad17bda026.herokuapp.com` |
| Conciliador | `URL_PYME` | `https://app-pyme-32264247d32e.herokuapp.com` |
| Conciliador | `URL_BANCO` | `https://app-banco-651db57b86fb.herokuapp.com` |

El valor de `TOKEN_SERVICIO` debe ser idéntico en las tres aplicaciones.
Después de cambiar Config Vars, reinicia los tres dynos.

Generar secretos:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configurar cada aplicación:

```bash
heroku config:set SERVICE=pyme \
  CLAVE_SESION="SECRETO_UNICO_PYME" \
  TOKEN_SERVICIO="TOKEN_COMPARTIDO" \
  ADMIN_EMAIL="admin@tu-dominio.com" \
  ADMIN_CLAVE="CLAVE_ADMIN_SEGURA" \
  COOKIE_SECURE=true \
  DIR_DATOS=/tmp/datos \
  URL_CONCILIADOR="https://nombre-conciliador.herokuapp.com" \
  --app nombre-pyme
```

```bash
heroku config:set SERVICE=banco \
  CLAVE_SESION="SECRETO_UNICO_BANCO" \
  TOKEN_SERVICIO="TOKEN_COMPARTIDO" \
  ADMIN_EMAIL="admin@tu-dominio.com" \
  ADMIN_CLAVE="CLAVE_ADMIN_SEGURA" \
  COOKIE_SECURE=true \
  DIR_DATOS=/tmp/datos \
  URL_CONCILIADOR="https://nombre-conciliador.herokuapp.com" \
  --app nombre-banco
```

```bash
heroku config:set SERVICE=conciliador \
  CLAVE_SESION="SECRETO_UNICO_CONCILIADOR" \
  TOKEN_SERVICIO="TOKEN_COMPARTIDO" \
  ADMIN_EMAIL="admin@tu-dominio.com" \
  ADMIN_CLAVE="CLAVE_ADMIN_SEGURA" \
  COOKIE_SECURE=true \
  DIR_DATOS=/tmp/datos \
  URL_PYME="https://nombre-pyme.herokuapp.com" \
  URL_BANCO="https://nombre-banco.herokuapp.com" \
  --app nombre-conciliador
```

`TOKEN_SERVICIO` debe ser idéntico en las tres aplicaciones. `CLAVE_SESION`
debe ser diferente en cada una. Las URL deben incluir `https://` y no terminar
en una ruta adicional.

### 4. Proceso de arranque

El `Procfile` usa:

```text
web: python heroku_start.py
```

`heroku_start.py`:

1. lee `SERVICE`;
2. cambia al directorio del servicio correspondiente;
3. usa `/tmp/datos` como almacenamiento temporal;
4. crea o actualiza el esquema de base de datos;
5. crea el administrador inicial si la base está vacía;
6. sincroniza el Conciliador con PYME y Banco;
7. inicia Uvicorn en `0.0.0.0:$PORT`.

Desplegar primero PYME y Banco, y después el Conciliador:

```bash
git push heroku main --app nombre-pyme
git push heroku main --app nombre-banco
git push heroku main --app nombre-conciliador
```

Si se usa despliegue desde GitHub, seleccionar la misma rama en las tres
aplicaciones y activar el despliegue manual o automático.

### 5. Verificar el despliegue

```bash
heroku ps --app nombre-pyme
heroku ps --app nombre-banco
heroku ps --app nombre-conciliador

heroku logs --tail --app nombre-pyme
heroku logs --tail --app nombre-banco
heroku logs --tail --app nombre-conciliador
```

Después ejecutar las tres llamadas `/interno/salud` descritas arriba y, por
último, usar **Cadena → Sincronizar** desde el Conciliador.

### Limitación de Heroku

`/tmp/datos` es efímero. Heroku puede eliminarlo al reiniciar o reemplazar el
dyno, por lo que los archivos generados y recibidos no deben considerarse
almacenamiento permanente. PostgreSQL conserva la información relacional,
pero para producción se debe mover el almacenamiento de archivos a S3,
Cloudinary, Backblaze B2 u otro servicio de objetos persistente.

## Despliegue con Coolify

Crear un único recurso Docker Compose apuntando al repositorio y usar
`docker-compose.yml`. No usar `docker-compose.local.yml`: Coolify realiza el
ruteo mediante su proxy.

Configurar los dominios públicos para:

```text
SERVICE_FQDN_PYME_8001=https://pyme.tudominio.com
SERVICE_FQDN_BANCO_8002=https://banco.tudominio.com
SERVICE_FQDN_CONCILIADOR_8000=https://conciliador.tudominio.com
```

Dentro de Compose, los servicios se conectan por `http://pyme:8001`,
`http://banco:8002` y `http://conciliador:8000`. No es necesario usar
dominios públicos para la propagación interna.

## Pruebas

Las pruebas de sellos y conciliación no necesitan base de datos:

```bash
for servicio in servicio-pyme servicio-banco servicio-conciliador; do
  (cd "$servicio" && python -m tests.test_sellos)
done

(cd servicio-conciliador && python -m tests.test_conciliacion)
```

Las pruebas de arranque requieren las dependencias de `requirements.txt`:

```bash
python -m pip install -r requirements.txt

for servicio in servicio-pyme servicio-banco servicio-conciliador; do
  (cd "$servicio" && python -m tests.test_arranque)
done
```

También se puede compilar el código sin iniciar PostgreSQL:

```bash
python -m compileall -q heroku_start.py \
  servicio-pyme/app servicio-banco/app servicio-conciliador/app
```

## Estructura principal

```text
.
├── Procfile
├── heroku_start.py
├── docker-compose.yml
├── docker-compose.local.yml
├── infra/postgres/
├── servicio-pyme/
├── servicio-banco/
└── servicio-conciliador/
```

Cada servicio contiene su aplicación FastAPI, migración SQL, Dockerfile,
ejemplos y pruebas. Los archivos `.env`, secretos y directorios de datos no
deben subirse al repositorio.

## Seguridad y operación

- No usar los secretos de ejemplo en producción.
- Mantener el mismo `TOKEN_SERVICIO` únicamente entre las tres aplicaciones.
- Usar una `CLAVE_SESION` diferente por aplicación.
- Mantener `COOKIE_SECURE=true` cuando se acceda mediante HTTPS.
- Revisar **Alertas** y **Auditoría** después de cada sincronización.
- No borrar una base o volumen sin respaldo.
- El sistema garantiza integridad mediante hashes, pero no cifra el contenido
  de los archivos.

Para el procedimiento específico de Heroku también se puede consultar
[`HEROKU.md`](HEROKU.md).
