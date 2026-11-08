# -*- coding: utf-8 -*-
"""app/cadena.py

La copia de la cadena que mantiene el conciliador.

El conciliador no emite lotes: recibe los bloques de la PYME y del banco
por API interna y los guarda en su base (una copia completa de la
historia). Con esa copia verifica los archivos recibidos y comprueba que
las tres historias coincidan.

Al arrancar (y a pedido) sincroniza los bloques faltantes de cada par:
pide los bloques posteriores a su ultimo indice y los valida antes de
guardarlos, igual que en una red permisionada.
"""
import time

import httpx

from app import alertas, config, db
from app.nucleo import sellos

# Forma del bloque (campos sellados mas la huella), definida en el nucleo.
CAMPOS_BLOQUE = sellos.CAMPOS_BLOQUE


def ultimo_bloque(origen=None):
    if origen:
        return db.consultar_uno(
            "SELECT * FROM bloques WHERE origen = %s ORDER BY indice DESC LIMIT 1",
            (origen,))
    return db.consultar_uno("SELECT * FROM bloques ORDER BY indice DESC LIMIT 1")


def registrar_bloque_recibido(bloque_recibido, origen_esperado=None):
    """Guarda un bloque que llego de otro servicio, validando el encadenamiento.

    Si el mismo indice ya existe con otra huella, se registra una alerta de
    integridad: las copias no cuentan la misma historia.
    """
    origen = bloque_recibido["origen"]
    if origen not in ("PYME", "BANCO"):
        return {"aceptado": False, "motivo": "origen de bloque no permitido"}
    if origen_esperado and origen != origen_esperado:
        return {"aceptado": False, "motivo": "origen no coincide con el par"}
    if sellos.huella_bloque(bloque_recibido) != bloque_recibido["hash_bloque"]:
        return {"aceptado": False, "motivo": "huella del bloque invalida"}

    existente = db.consultar_uno(
        "SELECT hash_bloque FROM bloques WHERE origen = %s AND indice = %s",
        (origen, bloque_recibido["indice"]))
    if existente:
        if existente["hash_bloque"] == bloque_recibido["hash_bloque"]:
            return {"aceptado": True, "detalle": "ya estaba"}
        alertas.crear("integridad", "alta",
                      "Bloque en conflicto en el indice %s" % bloque_recibido["indice"],
                      "La copia local y el bloque recibido tienen huellas distintas.",
                      referencia=bloque_recibido["lote_codigo"])
        return {"aceptado": False, "motivo": "conflicto: mismo indice con otra huella"}

    ultimo = ultimo_bloque(origen)
    esperado = ultimo["hash_bloque"] if ultimo else ("0" * 64)
    esperado_indice = (ultimo["indice"] + 1) if ultimo else 1
    if bloque_recibido["indice"] != esperado_indice or \
            bloque_recibido["hash_anterior"] != esperado:
        return {"aceptado": False, "motivo": "no encadena con el ultimo bloque local"}

    db.ejecutar(
        "INSERT INTO bloques (indice, origen, lote_codigo, archivo,"
        " n_movimientos, hashes_movimientos, hash_raiz, hash_archivo,"
        " hash_anterior, hash_bloque, emitido_por, sellado_en)"
        " VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)",
        (bloque_recibido["indice"], bloque_recibido["origen"],
         bloque_recibido["lote_codigo"], bloque_recibido["archivo"],
         bloque_recibido["n_movimientos"],
         _json(bloque_recibido["hashes_movimientos"]),
         bloque_recibido["hash_raiz"], bloque_recibido["hash_archivo"],
         bloque_recibido["hash_anterior"], bloque_recibido["hash_bloque"],
         bloque_recibido["emitido_por"], bloque_recibido["sellado_en"]))
    return {"aceptado": True}


def sincronizar_con_pares():
    """Pide a cada emisor los bloques posteriores a su ultimo indice local."""
    resultado = []
    for nombre, url in config.pares():
        origen = config.etiqueta_de_origen(nombre)
        ultimo = ultimo_bloque(origen)
        desde = ultimo["indice"] if ultimo else 0
        ultimo_error = None
        for intento in range(1, 4):
            try:
                respuesta = httpx.get(
                    "%s/interno/bloques/desde/%d" % (url, desde),
                    headers={"X-Servicio-Token": config.token_servicio()},
                    timeout=10)
                respuesta.raise_for_status()
                bloques = respuesta.json()
                if not isinstance(bloques, list):
                    raise ValueError("respuesta de bloques no es una lista")
                aceptados = sum(
                    registrar_bloque_recibido(
                        bloque, origen_esperado=origen).get("aceptado")
                    for bloque in bloques)
                resultado.append({"par": nombre, "nuevos": aceptados,
                                  "recibidos": len(bloques),
                                  "intentos": intento})
                break
            except Exception as excepcion:
                ultimo_error = str(excepcion)[:200]
                if intento < 3:
                    time.sleep(intento)
        else:
            resultado.append({"par": nombre, "error": ultimo_error,
                              "intentos": 3})
    return resultado


def bloques_desde(indice):
    return db.consultar("SELECT * FROM bloques WHERE indice > %s ORDER BY indice",
                        (indice,))


def bloques_completos(limite=300):
    return db.consultar("SELECT * FROM bloques ORDER BY indice DESC LIMIT %s",
                        (limite,))


def sellos_de_origen(origen):
    """Todos los sellos de un origen (la empresa o el banco), mas nuevos primero.

    El origen que llega desde la pantalla es la parte (EMPRESA o BANCO); en la
    cadena cada bloque lleva la etiqueta del servicio que lo emitio (PYME o
    BANCO), asi que se traduce antes de buscar.
    """
    return db.consultar(
        "SELECT * FROM bloques WHERE origen = %s ORDER BY indice DESC",
        (config.etiqueta_de_origen(origen),))


def sello_de_lote(lote_codigo):
    return db.consultar_uno(
        "SELECT lote_codigo, archivo, hash_archivo, hashes_movimientos,"
        " n_movimientos, sellado_en, emitido_por, hash_bloque"
        " FROM bloques WHERE lote_codigo = %s ORDER BY indice DESC LIMIT 1",
        (lote_codigo,))


def verificar_cadena_local():
    """Chequeo (a): verifica por separado la cadena de cada emisor."""
    filas = db.consultar("SELECT * FROM bloques ORDER BY origen, indice")
    problemas = []
    origenes = sorted({fila["origen"] for fila in filas})
    for origen in origenes:
        cadena = [dict(fila) for fila in filas if fila["origen"] == origen]
        problemas.extend(
            "%s: %s" % (origen, problema)
            for problema in sellos.verificar_cadena(cadena))
    return problemas


def _json(dato):
    import json
    return json.dumps(dato, ensure_ascii=False)
