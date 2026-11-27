"""Usuarios y permisos por perfil."""
import json
import psycopg
from fastapi import Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from urllib.parse import quote_plus
from app import db, seguridad

def verificar(request, usuario):
    rol = usuario.get("rol", "consulta")
    if rol not in ("administrador", "operador", "consulta"):
        raise HTTPException(403, "Perfil de usuario no válido.")
    if request.url.path.startswith("/usuarios") or request.url.path in ("/reset", "/auditoria/reset"):
        if rol != "administrador":
            raise HTTPException(403, "Se requieren privilegios de administrador.")
    elif (request.method not in ("GET", "HEAD") and request.url.path != "/sesion/actividad") or (
            request.url.path.startswith("/movimientos/") and request.url.path.endswith("/editar")):
        if rol not in ("administrador", "operador"):
            raise HTTPException(403, "Su perfil solo permite consultar.")

def migrar():
    with db.conectar() as conexion:
        with conexion.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(781240)")
            c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol TEXT")
            c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS eliminado BOOLEAN NOT NULL DEFAULT FALSE")
            c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS central_id BIGINT UNIQUE")
            c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS central_version TEXT")
            c.execute("UPDATE usuarios SET rol=CASE WHEN id=(SELECT MIN(id) FROM usuarios WHERE activo) "
                      "THEN 'administrador' ELSE 'operador' END WHERE rol IS NULL")
            c.execute("ALTER TABLE usuarios ALTER COLUMN rol SET DEFAULT 'operador'")
            c.execute("ALTER TABLE usuarios ALTER COLUMN rol SET NOT NULL")
        conexion.commit()

def instalar(app, plantillas, exigir, contexto):
    @app.get("/usuarios")
    def listar(request: Request):
        actor = exigir(request)
        verificar(request, actor)
        return plantillas.TemplateResponse(request, "usuarios.html", contexto(
            request, actor, usuarios=db.consultar(
                "SELECT id,email,nombre,rol,activo,created_at FROM usuarios WHERE NOT eliminado ORDER BY id")))

    @app.post("/usuarios")
    def crear(request: Request, email: str=Form(...), nombre: str=Form(...),
              clave: str=Form(...), rol: str=Form("consulta")):
        return guardar(request, None, email, nombre, clave, rol, 1)

    @app.post("/usuarios/{usuario_id}/editar")
    def editar(request: Request, usuario_id: int, email: str=Form(...),
               nombre: str=Form(...), clave: str=Form(""), rol: str=Form(...),
               activo: int=Form(1)):
        return guardar(request, usuario_id, email, nombre, clave, rol, activo)

    def guardar(request, usuario_id, email, nombre, clave, rol, activo):
        actor = exigir(request)
        verificar(request, actor)
        try:
            if rol not in ("administrador", "operador", "consulta") or not nombre.strip() or "@" not in email:
                raise ValueError("Revise nombre, correo y perfil.")
            if (not usuario_id or clave) and not 8 <= len(clave.encode()) <= 72:
                raise ValueError("La clave debe tener entre 8 y 72 bytes.")
            with db.conectar() as conexion:
                with conexion.cursor() as c:
                    c.execute("SELECT pg_advisory_xact_lock(781240)")
                    if usuario_id:
                        c.execute("SELECT * FROM usuarios WHERE id=%s AND NOT eliminado FOR UPDATE", (usuario_id,))
                        previo = c.fetchone()
                        if not previo:
                            raise ValueError("Usuario no encontrado.")
                        if actor["id"] == usuario_id and (not activo or rol != "administrador"):
                            raise ValueError("No puede desactivar su cuenta ni quitarse administración.")
                        proteger(c, previo, rol, bool(activo))
                        c.execute("UPDATE usuarios SET email=%s,nombre=%s,rol=%s,activo=%s,clave_hash=%s,"
                                  "updated_at=now() WHERE id=%s",
                                  (email.strip().lower(),nombre.strip(),rol,bool(activo),
                                   seguridad.hash_clave(clave) if clave else previo["clave_hash"],usuario_id))
                        c.execute("DELETE FROM sesiones WHERE usuario_id=%s", (usuario_id,))
                    else:
                        c.execute("INSERT INTO usuarios (email,nombre,clave_hash,rol,creado_por) "
                                  "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                                  (email.strip().lower(),nombre.strip(),seguridad.hash_clave(clave),rol,actor["id"]))
                        usuario_id = c.fetchone()["id"]
                    auditar(c,actor["id"],"guardar_usuario",usuario_id)
                conexion.commit()
            return aviso("Usuario guardado. Inicie sesión nuevamente si cambió sus datos.")
        except psycopg.errors.UniqueViolation:
            return aviso("El correo ya está registrado.")
        except ValueError as error:
            return aviso(str(error))

    @app.post("/usuarios/{usuario_id}/eliminar")
    def eliminar(request: Request, usuario_id: int):
        actor = exigir(request)
        verificar(request, actor)
        try:
            if usuario_id == actor["id"]:
                raise ValueError("No puede eliminar su propio usuario.")
            with db.conectar() as conexion:
                with conexion.cursor() as c:
                    c.execute("SELECT pg_advisory_xact_lock(781240)")
                    c.execute("SELECT * FROM usuarios WHERE id=%s AND NOT eliminado FOR UPDATE",(usuario_id,))
                    previo = c.fetchone()
                    if not previo:
                        raise ValueError("Usuario no encontrado.")
                    proteger(c,previo,"consulta",False)
                    c.execute("UPDATE usuarios SET activo=FALSE,eliminado=TRUE,updated_at=now() WHERE id=%s",(usuario_id,))
                    c.execute("DELETE FROM sesiones WHERE usuario_id=%s",(usuario_id,))
                    auditar(c,actor["id"],"eliminar_usuario",usuario_id)
                conexion.commit()
            return aviso("Acceso eliminado. Se conserva el historial de auditoría.")
        except ValueError as error:
            return aviso(str(error))

def proteger(c, previo, rol, activo):
    if previo["rol"] == "administrador" and previo["activo"] and (rol != "administrador" or not activo):
        c.execute("SELECT COUNT(*) AS total FROM usuarios WHERE rol='administrador' AND activo AND NOT eliminado")
        if c.fetchone()["total"] <= 1:
            raise ValueError("Debe conservar un administrador activo.")

def auditar(c, actor, accion, usuario_id):
    c.execute("INSERT INTO auditoria (usuario_id,accion,entidad,entidad_id,detalle) "
              "VALUES (%s,%s,'usuarios',%s,%s::jsonb)",(actor,accion,str(usuario_id),json.dumps({})))

def aviso(texto):
    return RedirectResponse("/usuarios?aviso="+quote_plus(texto),status_code=303)
