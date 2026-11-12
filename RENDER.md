# Despliegue en Render

El archivo [`render.yaml`](render.yaml) crea tres servicios web Docker y tres
bases PostgreSQL separadas. En Render, seleccione **New → Blueprint** y conecte
este repositorio.

Al finalizar la creación, complete estas variables en los tres servicios:

- `TOKEN_SERVICIO`: el mismo valor aleatorio en PYME, Banco y Conciliador.
- `ADMIN_EMAIL` y `ADMIN_CLAVE`: credenciales iniciales.

Después de que Render asigne las URL públicas, configure:

| Servicio | Variables URL |
|---|---|
| PYME | `URL_CONCILIADOR=https://...onrender.com` |
| Banco | `URL_CONCILIADOR=https://...onrender.com` |
| Conciliador | `URL_PYME=https://...onrender.com`; `URL_BANCO=https://...onrender.com` |

Render inyecta `DATABASE_URL` para cada base. Las aplicaciones guardan el
respaldo binario de cada archivo en PostgreSQL, por lo que las verificaciones
no dependen del disco efímero del contenedor.

Pruebe cada servicio con `https://SU_URL/login` y luego verifique la conexión
interna usando `GET /interno/salud` con el encabezado `X-Servicio-Token`.
