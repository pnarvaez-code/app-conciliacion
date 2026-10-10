# -*- coding: utf-8 -*-
"""app/verificacion.py

Verificacion de los lotes emitidos por este servicio.

Es la responsabilidad del emisor detectar si algo cambio despues del
sellado: aca se aplican los dos chequeos sobre cada lote propio (la
version vigente, el ultimo bloque de cada lote):

  (b) el archivo guardado en el volumen conserva la huella de su emision;
  (c) los movimientos actuales de la base coinciden con el sello.

Cuando se ejecuta desde la interfaz, ademas deja auditoria y genera una
alerta de integridad por cada lote alterado: la deteccion queda con
responsable y no depende de que alguien mas avise.
"""
import os

from app import alertas, auditoria, config, db, movimientos
from app.nucleo import sellos


def verificar_lotes_propios():
    """Recorre los lotes propios y devuelve su estado de integridad."""
    bloques = db.consultar(
        "SELECT * FROM bloques WHERE origen = %s ORDER BY indice",
        (config.ETIQUETA_SERVICIO,))
    vigentes = {}
    for bloque in bloques:                      # el ultimo de cada lote queda
        vigentes[bloque["lote_codigo"]] = bloque

    resultados = []
    for lote_codigo, bloque in sorted(vigentes.items(), reverse=True):
        detalle = []
        archivo = db.consultar_uno(
            "SELECT * FROM archivos WHERE nombre = %s ORDER BY id DESC LIMIT 1",
            (bloque["archivo"],))
        if not archivo or not os.path.isfile(archivo["ruta"]):
            estado = "sin_archivo"
            detalle.append("el archivo emitido no esta en el volumen")
        else:
            with open(archivo["ruta"], "rb") as guardado:
                problema = sellos.verificar_archivo(bloque, guardado.read())
            if problema:
                detalle.append(problema)
            estado = "alterado" if detalle else "intacto"

        lote = db.consultar_uno("SELECT id FROM lotes WHERE codigo = %s",
                                (lote_codigo,))
        if not lote:
            detalle.append("el lote no figura en la base")
            estado = "alterado"
        else:
            filas = movimientos.del_lote(lote["id"])
            problemas = sellos.verificar_movimientos(bloque, [dict(f) for f in filas])
            if problemas:
                detalle.extend(problemas)
                estado = "alterado"

        resultados.append({"lote": lote_codigo, "archivo": bloque["archivo"],
                           "movimientos": bloque["n_movimientos"],
                           "sellado_en": bloque["sellado_en"],
                           "estado": estado, "detalle": detalle})
    return resultados


def verificar_y_alertar(usuario_id, ip=None):
    """Verifica los lotes propios, deja auditoria y alerta si hay problemas."""
    resultados = verificar_lotes_propios()
    alterados = [r for r in resultados if r["estado"] != "intacto"]
    for resultado in alterados:
        alertas.crear("integridad", "alta",
                      "Lote %s no coincide con su sello" % resultado["lote"],
                      "; ".join(resultado["detalle"]) or "sin detalle",
                      referencia=resultado["lote"], usuario_id=usuario_id)
    auditoria.registrar(usuario_id, "verificar_lotes", "bloques", None,
                        {"lotes": len(resultados), "alterados": len(alterados)},
                        ip)
    return resultados
