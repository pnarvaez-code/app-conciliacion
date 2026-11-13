# Despliegue en Heroku

El repositorio contiene tres servicios independientes. En Heroku se despliega el mismo repositorio como tres aplicaciones: PYME, banco y conciliador. Cada aplicacion usa el proceso definido en Procfile y selecciona su servicio con `SERVICIO`, `APP_SERVICE` o `SERVICE`, aceptando `pyme`, `banco`, `conciliador` y sus nombres `servicio-*`. No se despliega docker-compose.yml en Heroku; Compose se conserva para desarrollo local.

## 1. Subir el proyecto a GitHub

Sube el contenido de la carpeta proyecto_conciliacion-main como raiz del repositorio (no agregues la carpeta contenedora por fuera). No subas ningun archivo .env; los secretos se configuran en Heroku.

## 2. Crear tres aplicaciones Heroku

Crea tres aplicaciones en Heroku y conecta cada una al mismo repositorio de GitHub desde la pestana Deploy. Selecciona la rama que vas a usar. En las tres, el directorio de despliegue es la raiz del repositorio. Heroku detecta Python por el requirements.txt que esta en la raiz.

Agrega un complemento de Heroku Postgres a cada aplicacion. Cada servicio necesita su propia base; Heroku configura DATABASE_URL al asociar el complemento.

## 3. Configurar las variables

En Settings → Config Vars de cada aplicacion, configura:

| Variable | PYME | Banco | Conciliador |
|---|---|---|---|
| SERVICIO (o APP_SERVICE/SERVICE) | pyme | banco | conciliador |
| CLAVE_SESION | Secreto largo, unico | Secreto largo, unico | Secreto largo, unico |
| TOKEN_SERVICIO | Mismo secreto en las tres | Mismo secreto en las tres | Mismo secreto en las tres |
| ADMIN_EMAIL | Correo administrador | Correo administrador | Correo administrador |
| ADMIN_CLAVE | Clave fuerte | Clave fuerte | Clave fuerte |
| COOKIE_SECURE | true | true | true |
| DIR_DATOS | /tmp/datos | /tmp/datos | /tmp/datos |
| DB_SCHEMA | public o esquema aislado | public o esquema aislado | public o esquema aislado |

Genera claves con: python -c "import secrets; print(secrets.token_urlsafe(48))". No reutilices la clave de sesion entre servicios. No compartas ni subas esos valores a GitHub.

Copia las URL HTTPS asignadas por Heroku en las variables de comunicacion:

| Aplicacion | Variables que debe tener |
|---|---|
| PYME | URL_CONCILIADOR = URL del conciliador |
| Banco | URL_CONCILIADOR = URL del conciliador |
| Conciliador | URL_PYME = URL de PYME; URL_BANCO = URL del banco |

Usa las URL completas con https://. Puedes verlas en los dominios de cada app aunque todavia no este desplegada.

Para los dominios actuales del proyecto, configura exactamente:

```bash
# Aplicación PYME
heroku config:set \
  SERVICIO=pyme \
  URL_CONCILIADOR=https://app-conciliacion-caad17bda026.herokuapp.com \
  --app NOMBRE_APP_PYME

# Aplicación Banco
heroku config:set \
  SERVICIO=banco \
  URL_CONCILIADOR=https://app-conciliacion-caad17bda026.herokuapp.com \
  --app NOMBRE_APP_BANCO

# Aplicación Conciliador
heroku config:set \
  SERVICIO=conciliador \
  URL_PYME=https://app-pyme-32264247d32e.herokuapp.com \
  URL_BANCO=https://app-banco-651db57b86fb.herokuapp.com \
  --app NOMBRE_APP_CONCILIADOR
```

En las tres aplicaciones, `TOKEN_SERVICIO` debe tener exactamente el mismo
valor. Después de guardar las variables, ejecuta `heroku restart --app
NOMBRE_APP` en cada aplicación o realiza un nuevo deploy.

No uses `localhost`, URLs internas de Docker, la URL del panel de Heroku ni
una URL con una ruta adicional. Deben ser las URLs públicas HTTPS base, por
ejemplo `https://mi-pyme-1234.herokuapp.com`.

Antes de guardar una URL, verifica que el dominio exista:

```bash
curl -i https://DOMINIO_CONCILIADOR/interno/salud \
  -H "X-Servicio-Token: TOKEN_COMPARTIDO"
```

La URL `https://app-conciliacion-caad17bda026.herokuapp.com/` no debe
configurarse mientras no responda por DNS. Si `curl` muestra `Could not
resolve host` o HTTP `404`, copia el dominio actual desde **Heroku →
Settings → Domains** de la aplicación Conciliador. La barra final no es
necesaria; el código la elimina automáticamente.

## 4. Verificar las conexiones entre las tres aplicaciones

Las conexiones deben quedar configuradas en una sola direccion: PYME y Banco
envian sus bloques al Conciliador; el Conciliador consulta a ambos para
recuperar bloques que falten. En cada aplicacion se puede comprobar la API
interna con:

```bash
curl -i -H "X-Servicio-Token: VALOR_DE_TOKEN_SERVICIO" \
  https://DOMINIO_DE_LA_APP/interno/salud
```

La respuesta correcta es `200` con `"estado":"ok"`. Una respuesta `401`
indica token distinto o ausente; un error de conexion indica una URL,
dominio o despliegue incorrecto. Repite la comprobacion para PYME, Banco y
Conciliador antes de probar **Cadena → Sincronizar** en el Conciliador.

## 5. Desplegar

Despliega primero PYME y banco; luego el conciliador. En cada app, usa Deploy Branch o habilita despliegues automaticos desde GitHub. Al iniciar, el proceso selecciona el servicio indicado por SERVICE, aplica la migracion inicial si la base esta vacia, crea el administrador inicial y arranca Uvicorn usando el puerto PORT asignado por Heroku.

Tras desplegar los tres, entra al conciliador e inicia la sincronización de la
cadena desde **Cadena → Sincronizar**. La sincronización se hace solo cuando
un usuario la solicita; el arranque no llama a las otras aplicaciones. Esto
permite que los dynos inactivos entren en reposo según el plan de Heroku y evita
despertar PYME o Banco al abrir únicamente Conciliador. Si un origen no responde,
abre su URL o revisa los logs y vuelve a usar **Cadena → Sincronizar** después
de confirmar las URLs y el token. El servidor escucha `PORT` con fallback
`8000`, confía en proxy headers de Heroku y usa `--forwarded-allow-ips=*`.

Los bloques se propagan al momento de **sellar** un lote o extracto. Los envíos
pendientes se reintentan únicamente cuando un usuario presiona **Verificar
conexión** en PYME o Banco. Después de cambiar una Config Var, reinicia o
redeploya las tres aplicaciones para que los procesos lean la configuración.

### Reposo y consumo

El código no ejecuta pings, cron interno ni sincronización periódica: abrir
PYME no llama a Banco o Conciliador, y abrir Conciliador no despierta a los
otros dos servicios. Por tanto, cada URL puede permanecer inactiva de forma
independiente.

El reposo automático lo determina el plan de Heroku, no la aplicación. En un
plan que admite suspensión por inactividad (por ejemplo, Eco), Heroku detiene
el dyno después de su periodo de inactividad y lo despierta al acceder a su
propia URL. Los dynos Basic, Standard o superiores permanecen activos mientras
estén escalados; si se requiere reposo en esos planes, se debe reducir el
proceso web a cero desde Heroku y escalarlo nuevamente cuando sea necesario.

## Almacenamiento y reinicios

Heroku elimina el disco temporal cuando reinicia o reemplaza un dyno. Por ello,
además de la copia de trabajo, la aplicación guarda cada archivo nuevo como
respaldo binario en PostgreSQL. La descarga, verificación y conciliación usan
ese respaldo cuando el archivo ya no está en `/tmp/datos`. Los archivos que se
hubieran perdido antes de desplegar esta versión deben emitirse nuevamente.
