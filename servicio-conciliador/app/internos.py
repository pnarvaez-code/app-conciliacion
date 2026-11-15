# -*- coding: utf-8 -*-
"""app/internos.py

API interna entre servicios (no es para navegadores): el conciliador
recibe bloques para su copia y expone su propia copia y sellos.

Todas las rutas exigen el encabezado `X-Servicio-Token` con el secreto
compartido entre servicios (variable de entorno TOKEN_SERVICIO). En el
VPS la red de Coolify no expone estas rutas al publico, pero el token
agrega una segunda barrera.
"""
import hmac

from fastapi import APIRouter, Header, HTTPException

from app import cadena, config
from app import db, seguridad
from pydantic import BaseModel, Field
router = APIRouter(prefix="/interno")


class Credenciales(BaseModel):
    email: str = Field(max_length=320)
    clave: str = Field(max_length=256)


def identidad(usuario):
    return {campo: usuario[campo] for campo in ("id", "email", "nombre", "rol")} | {
        "version": usuario["updated_at"].isoformat()}


@router.post("/identidad/autenticar")
def autenticar_identidad(datos: Credenciales, x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    usuario = db.consultar_uno(
        "SELECT * FROM usuarios WHERE email=%s AND activo AND NOT eliminado",
        (datos.email.strip().lower(),))
    if not usuario or not seguridad.verificar_clave(datos.clave, usuario["clave_hash"]):
        raise HTTPException(401, "Correo o clave incorrectos.")
    return identidad(usuario)


@router.get("/identidad/{usuario_id}")
def consultar_identidad(usuario_id: int, x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    usuario = db.consultar_uno(
        "SELECT * FROM usuarios WHERE id=%s AND activo AND NOT eliminado", (usuario_id,))
    if not usuario:
        raise HTTPException(404, "Usuario no disponible.")
    return identidad(usuario)



def _verificar_token(token):
    """Valida el token compartido. Si no hay token configurado, la API
    interna queda cerrada (nadie puede entrar sin credencial valida)."""
    configurado = config.token_servicio_configurado()
    if not configurado or not token or not hmac.compare_digest(token, configurado):
        raise HTTPException(status_code=401, detail="token de servicio invalido")


@router.get("/salud")
def salud(x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    ultimo = cadena.ultimo_bloque()
    problemas = cadena.verificar_cadena_local()
    return {"estado": "ok" if not problemas else "advertencia",
            "servicio": config.NOMBRE_SERVICIO,
            "ultimo_indice": ultimo["indice"] if ultimo else 0,
            "cadena_integra": not problemas,
            "problemas_cadena": problemas[:3]}


@router.post("/bloques")
def recibir_bloque(bloque: dict, x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    faltantes = [c for c in cadena.CAMPOS_BLOQUE if c not in bloque]
    if faltantes:
        raise HTTPException(status_code=400,
                            detail="faltan campos: %s" % ", ".join(faltantes))
    return cadena.registrar_bloque_recibido(bloque)


@router.get("/bloques/desde/{indice}")
def bloques_desde(indice: int, x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    return cadena.bloques_desde(indice)


@router.get("/sellos/{lote_codigo}")
def sello(lote_codigo: str, x_servicio_token: str = Header(default="")):
    _verificar_token(x_servicio_token)
    sello_lote = cadena.sello_de_lote(lote_codigo)
    if not sello_lote:
        raise HTTPException(status_code=404, detail="lote sin sello")
    return sello_lote
