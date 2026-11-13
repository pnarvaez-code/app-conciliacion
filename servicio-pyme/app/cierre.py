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
import csv
import datetime
import io
import logging
from pathlib import Path

from app import alertas, archivos, auditoria, cadena, config, db, movimientos

CABECERA = "fecha;monto;referencia;descripcion"
_log = logging.getLogger(__name__)


def cerrar_dia(usuario_id, ip=None):
    """Cierra el lote del dia. Devuelve (lote, bloque) o lanza ValueError."""
    return _emitir(None, None, usuario_id, ip, reemision=False)


def reemitir_ultimo(usuario_id, ip=None):
    """Re-emite el ultimo lote propio (correccion con rastro)."""
    return _emitir(None, None, usuario_id, ip, reemision=True)


def listar_lotes(limite=100):
    return db.consultar(
        "SELECT l.*, a.nombre AS archivo, a.sha256, a.ruta, a.bytes"
        " FROM lotes l LEFT JOIN archivos a ON a.id = l.archivo_id"
        " ORDER BY l.id DESC LIMIT %s", (limite,))


def _emitir(codigo, filas, usuario_id, ip, reemision):
    """Guarda archivo, lote, movimientos, bloque y auditoría atómicamente."""
    archivo = None
    with db.conectar() as conexion:
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(781236)")
                if reemision:
                    cursor.execute(
                        "SELECT * FROM lotes ORDER BY id DESC LIMIT 1 FOR UPDATE")
                    lote = cursor.fetchone()
                    if not lote:
                        raise ValueError("Todavia no se cerro ningun lote.")
                    codigo = lote["codigo"]
                    cursor.execute(
                        "SELECT * FROM movimientos WHERE lote_id = %s ORDER BY id",
                        (lote["id"],))
                    filas = cursor.fetchall()
                else:
                    cursor.execute(
                        "SELECT * FROM movimientos WHERE estado = 'pendiente'"
                        " ORDER BY id FOR UPDATE")
                    filas = cursor.fetchall()
                    if not filas:
                        raise ValueError("No hay ventas pendientes de cierre.")
                    hoy = datetime.date.today().isoformat()
                    cursor.execute(
                        "SELECT COUNT(*) AS total FROM lotes WHERE codigo LIKE %s",
                        ("V-%s%%" % hoy,))
                    codigo = "V-%s-%02d" % (
                        hoy, cursor.fetchone()["total"] + 1)

                cursor.execute("SELECT COUNT(*) AS total FROM bloques"
                               " WHERE lote_codigo = %s", (codigo,))
                version = cursor.fetchone()["total"] + 1
                nombre = _nombre_archivo(version)
                contenido = _csv(filas)
                archivo = archivos.guardar(
                    nombre, contenido, "emitido", usuario_id, cursor=cursor)

                if reemision:
                    cursor.execute(
                        "UPDATE lotes SET archivo_id = %s, n_movimientos = %s,"
                        " sellado_en = now(), sellado_por = %s, updated_at = now()"
                        " WHERE id = %s RETURNING *",
                        (archivo["id"], len(filas), usuario_id, lote["id"]))
                    lote = cursor.fetchone()
                else:
                    cursor.execute(
                        "INSERT INTO lotes (codigo, n_movimientos, archivo_id,"
                        " sellado_en, sellado_por)"
                        " VALUES (%s, %s, %s, now(), %s) RETURNING *",
                        (codigo, len(filas), archivo["id"], usuario_id))
                    lote = cursor.fetchone()
                    cursor.execute(
                        "UPDATE movimientos SET estado = 'en_lote', lote_id = %s,"
                        " updated_at = now() WHERE id = ANY(%s)",
                        (lote["id"], [fila["id"] for fila in filas]))

                bloque = cadena.sellar_lote(
                    codigo, nombre, contenido, [dict(f) for f in filas],
                    usuario_id, cursor=cursor, propagar_ahora=False)
                for destino, _url in config.pares():
                    cursor.execute(
                        "INSERT INTO bloques_envios (bloque_id, destino)"
                        " VALUES (%s, %s)"
                        " ON CONFLICT (bloque_id, destino) DO NOTHING",
                        (bloque["id"], destino))
                auditoria.registrar(
                    usuario_id,
                    "reemision_lote" if reemision else "cierre_lote",
                    "lotes", lote["id"],
                    {"codigo": codigo, "archivo": nombre,
                     "movimientos": len(filas), "version": version,
                     "indice_bloque": bloque["indice"]}, ip, cursor=cursor)
            conexion.commit()
        except Exception:
            conexion.rollback()
            if archivo:
                Path(archivo["ruta"]).unlink(missing_ok=True)
            raise

    # Solo se publica un bloque que ya quedó confirmado junto con su lote. Un
    # fallo de red no convierte un cierre confirmado en un error de pantalla:
    # la cola persistente conserva el envío para el próximo reintento manual.
    try:
        cadena.reintentar_envios()
    except Exception:
        _log.exception("El lote fue sellado, pero no se pudo propagar el bloque")
    if reemision:
        try:
            alertas.crear("operativa", "baja",
                          "Lote %s re-emitido (version %d)" % (codigo, version),
                          "La version anterior queda como historial en la cadena.",
                          referencia=codigo, usuario_id=usuario_id)
        except Exception:
            _log.exception("No se pudo registrar la alerta de reemision %s", codigo)
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


def _nombre_archivo(version):
    """Nombre descargable: servicio y fecha del cierre."""
    fecha = datetime.date.today().isoformat()
    sufijo = "" if version == 1 else "-v%d" % version
    return "pyme-%s%s.csv" % (fecha, sufijo)


def _csv(filas):
    """Archivo CSV con escape estándar para separadores y saltos de línea."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=";", lineterminator="\n")
    escritor.writerow(CABECERA.split(";"))
    for fila in filas:
        escritor.writerow((fila["fecha"], fila["monto"], fila["referencia"],
                           fila["descripcion"]))
    return salida.getvalue()
