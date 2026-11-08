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

Tras desplegar los tres, entra al conciliador e inicia la sincronizacion de la cadena desde Cadena → Sincronizar. El arranque realiza hasta tres intentos por cada origen para tolerar el despertar tardio de dynos en Heroku. Si un origen no responde, revisa los logs y vuelve a usar **Cadena → Sincronizar** después de confirmar las URLs y el token. El servidor escucha `PORT` con fallback `8000`, confía en proxy headers de Heroku y usa `--forwarded-allow-ips=*`. Inicia sesion en cada servicio con ADMIN_EMAIL y ADMIN_CLAVE configurados en Heroku.

## Limite de almacenamiento

Heroku elimina los archivos guardados en el disco temporal cuando reinicia o reemplaza un dyno. Este proyecto guarda alli los archivos de ventas, extractos y recepciones; por eso, este paquete permite desplegarlo para pruebas o demostracion, pero no conserva esos archivos de forma duradera. Antes de usarlo con datos reales, hay que adaptar el almacenamiento de archivos a un servicio persistente (por ejemplo, almacenamiento de objetos compatible con S3). La informacion relacional queda en PostgreSQL.
