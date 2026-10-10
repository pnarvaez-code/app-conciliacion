# -*- coding: utf-8 -*-
"""app/seguridad.py

Autenticacion y sesiones.

  * Las claves se guardan con bcrypt: nunca la clave en claro.
  * Al iniciar sesion se genera un token aleatorio; en la base se guarda
    solo su SHA-256 y en el navegador viaja como cookie firmada
    (itsdangerous). Asi la sesion se puede revocar desde la base.
  * La cookie es HttpOnly y SameSite=Lax; bajo HTTPS el despliegue debe
    agregar Secure (ver README).

El usuario actual se resuelve en cada peticion contra la tabla `sesiones`
(solo sesiones vigentes y usuarios activos): toda accion queda asociada a
un responsable.
"""
import datetime
import hashlib
import secrets

import bcrypt
from fastapi import Request
from itsdangerous import BadSignature, URLSafeSerializer

from app import config, db

CLAVE_COOKIE = "sesion_banco"
DURACION_SESION = datetime.timedelta(hours=8)
LIMITE_BCRYPT = 72   # bcrypt solo considera los primeros 72 bytes de la clave


def hash_clave(clave):
    """Hash bcrypt de una clave (para guardar en usuarios.clave_hash)."""
    return bcrypt.hashpw(_bytes(clave), bcrypt.gensalt()).decode("ascii")


def verificar_clave(clave, clave_hash):
    """True si la clave coincide con el hash guardado."""
    try:
        return bcrypt.checkpw(_bytes(clave), clave_hash.encode("ascii"))
    except ValueError:      # hash guardado con otro formato
        return False


def _bytes(clave):
    """La clave en bytes, recortada al limite de bcrypt."""
    return clave.encode("utf-8")[:LIMITE_BCRYPT]


def _huella_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _firmador():
    return URLSafeSerializer(config.clave_sesion(), salt="sesion")


def iniciar_sesion(usuario_id, ip, user_agent):
    """Crea la sesion en la base y devuelve el valor de la cookie."""
    token = secrets.token_urlsafe(32)
    expira = datetime.datetime.now(datetime.timezone.utc) + DURACION_SESION
    db.ejecutar(
        "INSERT INTO sesiones (usuario_id, token_hash, expira_en, ip, user_agent)"
        " VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, _huella_token(token), expira, ip, user_agent))
    return _firmador().dumps(token)


def cerrar_sesion(valor_cookie):
    """Elimina la sesion de la base a partir de la cookie."""
    token = _leer_token(valor_cookie)
    if token:
        db.ejecutar("DELETE FROM sesiones WHERE token_hash = %s",
                    (_huella_token(token),))


def usuario_actual(request: Request):
    """Devuelve la fila del usuario de la sesion, o None."""
    valor = request.cookies.get(CLAVE_COOKIE)
    token = _leer_token(valor)
    if not token:
        return None
    fila = db.consultar_uno(
        "SELECT u.id, u.email, u.nombre FROM sesiones s "
        "JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = %s AND s.expira_en > now() AND u.activo",
        (_huella_token(token),))
    return fila


def ip_de(request: Request):
    """IP del cliente (detras de proxy se usa la cabecera reenviada)."""
    reenviada = request.headers.get("x-forwarded-for", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else ""


def _leer_token(valor_cookie):
    if not valor_cookie:
        return None
    try:
        return _firmador().loads(valor_cookie)
    except BadSignature:
        return None
