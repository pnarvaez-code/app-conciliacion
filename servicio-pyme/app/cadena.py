# -*- coding: utf-8 -*-
"""app/cadena.py

La cadena de bloques del servicio: almacenamiento, sellado, propagacion
y verificacion.

Cada servicio guarda una copia completa de la cadena en su base (tabla
`bloques`) y la mantiene sincronizada con los otros dos por API interna:
al sellar un lote, el bloque se envia a los demas; si alguno esta caido
queda encolado en `bloques_envios` y se reintenta. Un bloque recibido se
acepta solo si encadena con el ultimo bloque local (mismo criterio que
una red permisionada, donde cada nodo valida antes de escribir).

Los calculos estan en app/nucleo/sellos.py (SHA-256, solo biblioteca
estandar). Aqui solo se persiste y se transporta.
"""
import datetime
import json

import httpx

from app import alertas, config, db
from app.nucleo import sellos

# Forma del bloque (campos sellados mas la huella), definida en el nucleo.
CAMPOS_BLOQUE = sellos.CAMPOS_BLOQUE


def ultimo_bloque():
    return db.consultar_uno("SELECT * FROM bloques ORDER BY indice DESC LIMIT 1")


def siguiente_indice():
    ultimo = ultimo_bloque()
    return (ultimo["indice"] + 1) if ultimo else 1


def sellar_lote(lote_codigo, archivo, contenido, movimientos, usuario_id):
    """Crea el bloque del lote, lo guarda y lo propaga.

    `contenido` es el texto del archivo emitido (su huella queda sellada);
    `movimientos` son los movimientos del lote, en orden.
    """
    ultimo = ultimo_bloque()
    sellado_en = datetime.datetime.now(datetime.timezone.utc)
    bloque = sellos.construir_bloque(
        indice=siguiente_indice(),
        origen=config.ETIQUETA_SERVICIO,
        lote_codigo=lote_codigo,
        archivo=archivo,
        movimientos=movimientos,
        hash_archivo=sellos.huella_archivo(contenido),
        hash_anterior=ultimo["hash_bloque"] if ultimo else ("0" * 64),
        emitido_por=usuario_id,
        sellado_en=sellado_en.isoformat())

    fila = db.ejecutar(
        "INSERT INTO bloques (indice, origen, lote_codigo, archivo,"
        " n_movimientos, hashes_movimientos, hash_raiz, hash_archivo,"
        " hash_anterior, hash_bloque, emitido_por, sellado_en)"
        " VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)"
        " RETURNING id",
        (bloque["indice"], bloque["origen"], bloque["lote_codigo"],
         bloque["archivo"], bloque["n_movimientos"],
         _json(bloque["hashes_movimientos"]), bloque["hash_raiz"],
         bloque["hash_archivo"], bloque["hash_anterior"],
         bloque["hash_bloque"], bloque["emitido_por"], bloque["sellado_en"]))
    bloque["id"] = fila["id"]
    propagar(bloque)
    return bloque


def propagar(bloque):
    """Encola y envia el bloque a los otros servicios configurados."""
    for destino, url in config.pares():
        db.ejecutar(
            "INSERT INTO bloques_envios (bloque_id, destino) VALUES (%s, %s)"
            " ON CONFLICT (bloque_id, destino) DO NOTHING",
            (bloque["id"], destino))
        _intentar_envio(bloque, destino, url)


def reintentar_envios():
    """Reintenta los envios pendientes o fallidos (se puede llamar al inicio)."""
    urls = dict(config.pares())
    pendientes = db.consultar(
        "SELECT e.id AS envio_id, e.destino, b.* FROM bloques_envios e "
        "JOIN bloques b ON b.id = e.bloque_id "
        "WHERE e.estado <> 'enviado' ORDER BY b.indice")
    for fila in pendientes:
        url = urls.get(fila["destino"])
        if url:
            _intentar_envio(fila, fila["destino"], url, envio_id=fila["envio_id"])


def registrar_bloque_recibido(bloque_recibido):
    """Guarda un bloque que llego de otro servicio, validando el encadenamiento.

    Respuestas posibles:
      aceptado: se guardo (o ya estaba);
      conflicto: no encadena con la copia local (posible manipulacion o
                 desincronizacion): se registra una alerta de integridad.
    """
    existente = db.consultar_uno("SELECT hash_bloque FROM bloques WHERE indice = %s",
                                 (bloque_recibido["indice"],))
    if existente:
        if existente["hash_bloque"] == bloque_recibido["hash_bloque"]:
            return {"aceptado": True, "detalle": "ya estaba"}
        alertas.crear("integridad", "alta",
                      "Bloque en conflicto en el indice %s" % bloque_recibido["indice"],
                      "La copia local y el bloque recibido tienen huellas distintas.",
                      referencia=bloque_recibido["lote_codigo"])
        return {"aceptado": False, "motivo": "conflicto: mismo indice con otra huella"}

    ultimo = ultimo_bloque()
    esperado = ultimo["hash_bloque"] if ultimo else ("0" * 64)
    esperado_indice = (ultimo["indice"] + 1) if ultimo else 1
    if bloque_recibido["indice"] != esperado_indice or \
            bloque_recibido["hash_anterior"] != esperado:
        return {"aceptado": False,
                "motivo": "no encadena con el ultimo bloque local"}

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


def bloques_desde(indice):
    return db.consultar("SELECT * FROM bloques WHERE indice > %s ORDER BY indice",
                        (indice,))


def sello_de_lote(lote_codigo):
    """Ultimo sello (version vigente) de un lote, para verificar archivos."""
    return db.consultar_uno(
        "SELECT lote_codigo, archivo, hash_archivo, hashes_movimientos,"
        " n_movimientos, sellado_en, emitido_por, hash_bloque"
        " FROM bloques WHERE lote_codigo = %s ORDER BY indice DESC LIMIT 1",
        (lote_codigo,))


def verificar_cadena_local():
    """Chequeo (a): recorre la copia local y devuelve los problemas."""
    filas = db.consultar("SELECT * FROM bloques ORDER BY indice")
    return sellos.verificar_cadena([dict(f) for f in filas])


def _intentar_envio(bloque, destino, url, envio_id=None):
    """Envia el bloque al servicio destino y actualiza el estado del envio."""
    # Cuerpo con los campos de la cadena; las fechas viajan como texto ISO.
    cuerpo = {}
    for campo in CAMPOS_BLOQUE:
        valor = bloque[campo]
        cuerpo[campo] = valor.isoformat() if hasattr(valor, "isoformat") else valor
    try:
        respuesta = httpx.post(
            "%s/interno/bloques" % url, json=cuerpo,
            headers={"X-Servicio-Token": config.token_servicio()}, timeout=10)
        respuesta.raise_for_status()
        estado, error = "enviado", None
    except Exception as excepcion:  # red caida, servicio apagado, etc.
        estado, error = "fallido", str(excepcion)[:300]
        alertas.crear("operativa", "media",
                      "No se pudo propagar el bloque %s a %s"
                      % (bloque["indice"], destino),
                      "El envio queda en cola y se reintenta. Detalle: %s" % error,
                      referencia=bloque["lote_codigo"])
    if envio_id:
        db.ejecutar(
            "UPDATE bloques_envios SET estado = %s, intentos = intentos + 1,"
            " ultimo_error = %s, updated_at = now() WHERE id = %s",
            (estado, error, envio_id))
    else:
        db.ejecutar(
            "UPDATE bloques_envios SET estado = %s, intentos = intentos + 1,"
            " ultimo_error = %s, updated_at = now()"
            " WHERE bloque_id = %s AND destino = %s",
            (estado, error, bloque["id"], destino))


def _json(dato):
    return json.dumps(dato, ensure_ascii=False)
