# Plataforma de conciliacion con integridad verificable

Tres servicios independientes que trabajan en conjunto: la PYME emite sus
ventas, el banco emite su extracto y el conciliador recibe ambos archivos,
verifica los sellos y concilia.

Cada servicio es una aplicacion FastAPI con su propia base PostgreSQL, su
propio ingreso con sesion, su auditoria y una copia de la cadena de bloques.
PYME y Banco mantienen cadenas independientes y solo propagan sus bloques al
Conciliador por una API interna protegida con un token compartido. El
Conciliador sincroniza y verifica cada origen por separado.

| Carpeta | Puerto | Rol |
|---|---|---|
| `servicio-pyme` | 8001 | Ventas de la empresa y cierre del dia (CSV + sello) |
| `servicio-banco` | 8002 | Movimientos de la cuenta y extracto (CSV o XML + sello) |
| `servicio-conciliador` | 8000 | Recepcion de archivos, verificacion de sellos y conciliacion |

## Puesta en marcha en local

Hace falta Docker con Compose (en Windows, Docker Desktop). Los comandos son
los mismos en Windows, macOS y Linux, y se ejecutan dentro de la carpeta del
repositorio.

### 1. Levantar todo desde cero

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v --remove-orphans
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

El primer arranque tarda un poco: PostgreSQL crea las tres bases y despues
cada servicio aplica su migracion y crea su usuario administrador.

### 2. Cargar los movimientos de ejemplo

Cuando las direcciones de la tabla ya respondan en el navegador:

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T pyme python -m app.importar ejemplos/ventas_ejemplo.csv
docker compose -f docker-compose.yml -f docker-compose.local.yml exec -T banco python -m app.importar ejemplos/extracto_ejemplo.csv
```

Cada comando informa cuantos movimientos cargo y quien quedo como responsable
en la auditoria. Se pueden repetir: las referencias ya cargadas se omiten.

### 3. Entrar

| Servicio | Direccion | Usuario y clave iniciales |
|---|---|---|
| PYME | http://localhost:8001 | `admin@ejemplo.com` / `conciliacion2026` |
| Banco | http://localhost:8002 | idem |
| Conciliador | http://localhost:8080 | idem |

### Otros comandos

```bash
# Registros de un servicio (Ctrl+C para salir)
docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f pyme

# Apagar (conserva los datos)
docker compose -f docker-compose.yml -f docker-compose.local.yml down

# Apagar y borrar los datos
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v
```

Las variables de entorno son opcionales: todas tienen valores por defecto.
Para cambiarlas, copiar `.env.example` a `.env` (`copy .env.example .env` en
CMD, `Copy-Item .env.example .env` en PowerShell) y editar el archivo.

### Recorrido de prueba

Con los movimientos de ejemplo ya cargados:

1. **PYME**: *Cerrar lote y exportar* y descargar el archivo.
2. **Banco**: *Emitir extracto* en CSV o XML y descargarlo.
3. **Conciliador**: subir los dos archivos en *Recepciones* y ejecutar la
   conciliacion: el informe muestra los pares por nivel y las diferencias.
4. **Alteracion**: subir `ejemplos/extracto_alterado.csv` (un monto cambiado,
   mismo formato) y queda marcado como `ALTERADO` señalando el movimiento
   exacto. Con `ejemplos/extracto_tocado_por_excel.csv` se ve el otro caso:
   un archivo reescrito por Excel que ya no se puede interpretar.

### Demostracion estructurada

El recorrido está preparado para presentar los tres escenarios:

1. **Conciliación exitosa**: los archivos de ejemplo contienen coincidencias
   de nivel 1 (referencia), nivel 2 (monto y fecha cercana) y nivel 3
   (descripción y monto aproximado). Después de cerrar y sellar en PYME y
   Banco, sincronice la cadena en el Conciliador, reciba ambos archivos como
   `intactos`, ejecute la conciliación y muestre el resultado en **Visor**.
2. **Diferencias genuinas**: agregue una venta pendiente de acreditación o
   una comisión bancaria en uno solo de los servicios, cierre nuevamente,
   reciba los archivos intactos y ejecute la conciliación. Use **Re-emitir
   ultimo** para generar `-v2`; el bloque anterior queda visible en
   **Cadena**, y la auditoría conserva ambas acciones.
3. **Conciliación adulterada**: en Recepciones suba
   `ejemplos/extracto_alterado.csv`; se marca `alterado` y el detalle señala
   el movimiento `#3`. Suba después
   `ejemplos/extracto_tocado_por_excel.csv`; el parser rechaza la línea 2.
   Ambos casos generan alerta de severidad alta y quedan registrados con el
   usuario responsable en **Auditoría**.

Para editar a mano un archivo ya sellado (y ver la deteccion de integridad),
se entra al contenedor con
`docker compose -f docker-compose.yml -f docker-compose.local.yml exec pyme sh`
y los archivos estan en `/datos/archivos`. Tambien se puede cambiar el volumen
por una carpeta propia: `datos-pyme:/datos` -> `./datos/pyme:/datos`.

## Despliegue en Heroku

Heroku requiere tres aplicaciones (una por servicio) conectadas al mismo repositorio, cada una con su propia base PostgreSQL y variables de entorno. Segui la guia paso a paso en [HEROKU.md](HEROKU.md). El despliegue de Heroku usa Procfile y heroku_start.py; Docker Compose sigue siendo para uso local.

## Despliegue en un servidor (Coolify)

Un unico recurso de tipo **Docker Compose** desde este repositorio, con
`docker-compose.yml` como archivo. Los dominios se asignan definiendo
`SERVICE_FQDN_PYME_8001`, `SERVICE_FQDN_BANCO_8002` y
`SERVICE_FQDN_CONCILIADOR_8000` con la URL de cada uno; si no se definen,
Coolify genera uno por servicio. En ese entorno no se usa
`docker-compose.local.yml`: el ruteo lo hace el proxy por la red interna.

## Un servicio suelto

Cada carpeta trae su Dockerfile, su `.env.example` y su `docker-compose.yml`
para levantarlo por separado y conectarlo a otra base.

## Pruebas

No necesitan base de datos:

```
python -m tests.test_sellos          # calculos de la cadena (los tres)
python -m tests.test_conciliacion    # motor de conciliacion (conciliador)
python -m tests.test_arranque        # pantallas y API interna (los tres)
```

## Archivos de ejemplo

Cada servicio trae una carpeta `ejemplos/` con archivos reales. PYME y Banco
los importan con `python -m app.importar <archivo>`: es la via de integracion
con el sistema de origen (no se tipean los movimientos de a uno) y queda
registrada en la auditoria.

El conciliador recibe los archivos **emitidos y sellados** por los otros dos
servicios; ademas incluye copias modificadas fuera del sistema para mostrar
la deteccion de alteraciones y el detalle de la diferencia.

## Notas

* El archivo `.env` y la carpeta `datos/` (archivos emitidos) no se
  versionan.
* Los archivos se sellan con SHA-256 y la huella queda en la cadena: el
  sistema no cifra los datos, garantiza que no cambien sin que se note.
