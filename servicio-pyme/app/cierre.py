# -*- coding: utf-8 -*-
"""app/cierre.py

Cierre del dia y re-emision.

Cerrar el dia toma todas las ventas pendientes, genera el archivo CSV,
lo guarda en el volumen y lo sella en la cadena (bloque nuevo encadenado
al anterior). El archivo es el que despues viaja hacia el conciliador.

Re-emitir vuelve a sellar el MISMO lote con una version nueva del
archivo (sufijo -v2, -v3...): es la correccion legitima, con historial:
la version anterior queda en la cadena.

Todas las acciones quedan auditadas con el usuario que las ejecuta.
"""
import datetime

from app import alertas, archivos, auditoria, cadena, db, movimientos

CABECERA = "fecha;monto;referencia;descripcion"


def cerrar_dia(usuario_id, ip=None):
    """Cierra el lote del dia. Devuelve (lote, bloque) o lanza ValueError."""
    pendientes = movimientos.pendientes()
    if not pendientes:
        raise ValueError("No hay ventas pendientes de cierre.")
    codigo = _codigo_nuevo()
    return _emitir(codigo, pendientes, usuario_id, ip, reemision=False)


def reemitir_ultimo(usuario_id, ip=None):
    """Re-emite el ultimo lote propio (correccion con rastro)."""
    ultimo_lote = db.consultar_uno(
        "SELECT * FROM lotes ORDER BY id DESC LIMIT 1")
    if not ultimo_lote:
        raise ValueError("Todavia no se cerro ningun lote.")
    filas = movimientos.del_lote(ultimo_lote["id"])
    return _emitir(ultimo_lote["codigo"], filas, usuario_id, ip, reemision=True)


def listar_lotes(limite=100):
    return db.consultar(
        "SELECT l.*, a.nombre AS archivo, a.sha256, a.ruta, a.bytes"
        " FROM lotes l LEFT JOIN archivos a ON a.id = l.archivo_id"
        " ORDER BY l.id DESC LIMIT %s", (limite,))


def _emitir(codigo, filas, usuario_id, ip, reemision):
    """Genera el archivo, lo guarda, crea el lote y sella el bloque."""
    version = _siguiente_version(codigo)
    nombre = "%s%s.csv" % (codigo, "" if version == 1 else "-v%d" % version)
    contenido = _csv(filas)

    archivo = archivos.guardar(nombre, contenido, "emitido", usuario_id)

    if reemision:
        lote = db.consultar_uno("SELECT * FROM lotes WHERE codigo = %s", (codigo,))
        db.ejecutar(
            "UPDATE lotes SET archivo_id = %s, n_movimientos = %s,"
            " sellado_en = now(), sellado_por = %s, updated_at = now()"
            " WHERE id = %s", (archivo["id"], len(filas), usuario_id, lote["id"]))
    else:
        lote = db.ejecutar(
            "INSERT INTO lotes (codigo, n_movimientos, archivo_id, sellado_en,"
            " sellado_por) VALUES (%s, %s, %s, now(), %s) RETURNING *",
            (codigo, len(filas), archivo["id"], usuario_id))
        movimientos.marcar_en_lote([f["id"] for f in filas], lote["id"])

    bloque = cadena.sellar_lote(codigo, nombre, contenido,
                                [dict(f) for f in filas], usuario_id)
    auditoria.registrar(
        usuario_id, "reemision_lote" if reemision else "cierre_lote",
        "lotes", lote["id"],
        {"codigo": codigo, "archivo": nombre, "movimientos": len(filas),
         "version": version, "indice_bloque": bloque["indice"]}, ip)
    if reemision:
        alertas.crear("operativa", "baja",
                      "Lote %s re-emitido (version %d)" % (codigo, version),
                      "La version anterior queda como historial en la cadena.",
                      referencia=codigo, usuario_id=usuario_id)
    return lote, bloque


def _codigo_nuevo():
    """Codigo del lote del dia: V-AAAA-MM-DD-NN."""
    hoy = datetime.date.today().isoformat()
    fila = db.consultar_uno(
        "SELECT COUNT(*) AS total FROM lotes WHERE codigo LIKE %s",
        ("V-%s%%" % hoy,))
    return "V-%s-%02d" % (hoy, (fila["total"] if fila else 0) + 1)


def _siguiente_version(codigo):
    fila = db.consultar_uno("SELECT COUNT(*) AS total FROM bloques"
                            " WHERE lote_codigo = %s", (codigo,))
    return (fila["total"] if fila else 0) + 1


def _csv(filas):
    """Archivo CSV con el formato documentado (sin adornos)."""
    lineas = [CABECERA]
    for fila in filas:
        lineas.append("%s;%s;%s;%s" % (fila["fecha"], fila["monto"],
                                       fila["referencia"], fila["descripcion"]))
    return "\n".join(lineas) + "\n"
