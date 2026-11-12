# Despliegue en Coolify

1. Cree un proyecto y añada un recurso de tipo **Docker Compose** desde este
   repositorio de GitHub.
2. Seleccione `docker-compose.yml` como archivo Compose y la rama `main`.
3. Defina las variables de `.env.example` en Coolify. Reemplace las claves de
   ejemplo por valores propios; `TOKEN_SERVICIO` debe ser idéntico en los tres
   servicios y cada `CLAVE_SESION_*` debe ser distinta.
4. Asigne un dominio a cada servicio:
   - `pyme`, puerto `8001`;
   - `banco`, puerto `8002`;
   - `conciliador`, puerto `8000`.
5. Despliegue. Compose crea PostgreSQL, las tres bases lógicas y los volúmenes
   persistentes `datos-*`.

Las aplicaciones se comunican dentro de la red privada de Compose usando
`http://pyme:8001`, `http://banco:8002` y `http://conciliador:8000`. No cambie
estas URL por los dominios públicos: los dominios se usan solamente desde el
navegador.

Después del primer despliegue, inicie sesión en las tres aplicaciones y abra
**Cadena → Sincronizar** en el Conciliador. Verifique las tres rutas
`/interno/salud` con el mismo `TOKEN_SERVICIO` antes de la demostración.
