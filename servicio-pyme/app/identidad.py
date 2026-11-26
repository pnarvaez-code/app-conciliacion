"""Acceso centralizado: el Conciliador es la autoridad de usuarios."""
import httpx
from fastapi import HTTPException
from app import config, db, seguridad

# Cliente compartido: reutiliza conexiones sin almacenar respuestas de identidad.
_cliente = httpx.Client(timeout=30, follow_redirects=False)

def consultar(ruta, datos=None):
    url = config.url_conciliador()
    try:
        respuesta = _cliente.request(
            "POST" if datos is not None else "GET", url + "/interno/identidad/" + ruta,
            json=datos, headers={"X-Servicio-Token": config.token_servicio()},
            timeout=30, follow_redirects=False)
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(503, "No se puede verificar el acceso con el Conciliador. Intente nuevamente.") from error
    if respuesta.status_code in (401,404):
        # Un 401 en autenticación puede indicar token mal configurado: nunca usar
        # contraseña local como alternativa, pues permitiría claves revocadas.
        return None
    if not respuesta.is_success:
        raise HTTPException(503, "El Conciliador no está disponible para validar el acceso.")
    try:
        identidad = respuesta.json()
        if identidad["rol"] not in ("administrador","operador","consulta"):
            raise ValueError("Perfil inválido")
        for campo in ("id","email","nombre","version"):
            if not identidad.get(campo):
                raise ValueError("Identidad incompleta")
        return identidad
    except (ValueError,KeyError,TypeError) as error:
        raise HTTPException(503,"Respuesta de identidad no válida.") from error

def autenticar(email, clave):
    if not config.url_conciliador():
        usuario = db.consultar_uno(
            "SELECT * FROM usuarios WHERE email=%s AND activo AND NOT eliminado",
            (email.strip().lower(),))
        return usuario if usuario and seguridad.verificar_clave(clave,usuario["clave_hash"]) else None
    persona = consultar("autenticar", {"email":email,"clave":clave})
    if not persona:
        return None
    with db.conectar() as conexion:
        with conexion.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(781240)")
            c.execute("SELECT * FROM usuarios WHERE central_id=%s FOR UPDATE",(persona["id"],))
            usuario = c.fetchone()
            if not usuario:
                # Vincula una cuenta local existente sin cambiar su id histórico.
                c.execute("SELECT * FROM usuarios WHERE email=%s AND central_id IS NULL FOR UPDATE",
                          (persona["email"],))
                usuario = c.fetchone()
            if usuario:
                c.execute("UPDATE usuarios SET email=%s,nombre=%s,rol=%s,clave_hash=%s,"
                          "central_id=%s,central_version=%s,activo=TRUE,eliminado=FALSE "
                          "WHERE id=%s RETURNING *",
                          (persona["email"],persona["nombre"],persona["rol"],
                           seguridad.hash_clave(clave),persona["id"],persona["version"],usuario["id"]))
            else:
                c.execute("INSERT INTO usuarios (email,nombre,rol,clave_hash,central_id,central_version)"
                          " VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                          (persona["email"],persona["nombre"],persona["rol"],
                           seguridad.hash_clave(clave),persona["id"],persona["version"]))
            usuario = c.fetchone()
        conexion.commit()
    return usuario

def validar_sesion(usuario):
    if not config.url_conciliador():
        return True
    if not usuario.get("central_id"):
        return False
    persona = consultar(str(usuario["central_id"]))
    if not persona or persona["version"] != usuario.get("central_version"):
        db.ejecutar("DELETE FROM sesiones WHERE usuario_id=%s",(usuario["id"],))
        return False
    return True
