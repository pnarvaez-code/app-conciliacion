# -*- coding: utf-8 -*-
"""app/internos.py

API interna entre servicios (no es para navegadores): propagacion de
bloques, sincronizacion y consulta de sellos.

Todas las rutas exigen el encabezado `X-Servicio-Token` con el secreto
compartido entre servicios (variable de entorno TOKEN_SERVICIO). En el
VPS la red de Coolify no expone estas rutas al publico, pero el token
agrega una segunda barrera.
"""
import hmac

from fastapi import APIRouter, Header, HTTPException

from app import cadena, config

router = APIRouter(prefix="/interno")


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
    return {"estado": "ok", "servicio": config.NOMBRE_SERVICIO,
            "ultimo_indice": ultimo["indice"] if ultimo else 0}


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
