# -*- coding: utf-8 -*-
"""Obtención autenticada de lotes emitidos por PYME y BANCO."""
import httpx

from app import config, seguridad


def obtener_ultimo(origen):
    """Descarga el último archivo sellado de una parte, limitado a 5 MB."""
    origen = (origen or "").upper()
    if origen not in ("EMPRESA", "BANCO"):
        raise ValueError("el origen debe ser EMPRESA o BANCO")
    url = config.url_pyme() if origen == "EMPRESA" else config.url_banco()
    if not url:
        raise ValueError("No está configurada la URL de %s." %
                         ("PyME" if origen == "EMPRESA" else "Banco"))
    try:
        with httpx.stream(
                "GET", "%s/interno/lotes/ultimo/archivo" % url,
                headers={"X-Servicio-Token": config.token_servicio()},
                timeout=15, follow_redirects=False) as respuesta:
            if respuesta.status_code == 404:
                raise ValueError("%s aún no tiene un lote emitido." %
                                 ("PyME" if origen == "EMPRESA" else "Banco"))
            if not respuesta.is_success:
                raise ValueError("%s respondió HTTP %d al solicitar el archivo."
                                 % ("PyME" if origen == "EMPRESA" else "Banco",
                                    respuesta.status_code))
            contenido = bytearray()
            for bloque in respuesta.iter_bytes():
                contenido.extend(bloque)
                if len(contenido) > seguridad.LIMITE_ARCHIVO:
                    raise ValueError("El archivo remoto supera el máximo de 5 MB.")
            nombre = _nombre(respuesta.headers.get("content-disposition"), origen)
            return nombre, bytes(contenido), respuesta.headers.get("x-lote-codigo", "")
    except httpx.HTTPError as error:
        raise ValueError("No se pudo conectar con %s: %s" %
                         ("PyME" if origen == "EMPRESA" else "Banco", str(error)[:140])) from error


def _nombre(content_disposition, origen):
    """Obtiene un nombre seguro; los emisores solo publican nombres propios."""
    valor = content_disposition or ""
    if "filename=" in valor:
        nombre = valor.split("filename=", 1)[1].strip().strip('"')
        if nombre.lower().endswith((".csv", ".xml")):
            return nombre.replace("\\", "/").rsplit("/", 1)[-1]
    return "lote-pyme.csv" if origen == "EMPRESA" else "extracto-banco.csv"
