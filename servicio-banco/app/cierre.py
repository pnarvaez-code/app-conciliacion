# -*- coding: utf-8 -*-
"""app/cierre.py

Emision del extracto bancario y re-emision.

Emitir toma todos los movimientos pendientes de la cuenta, genera el
extracto (CSV o XML), lo guarda en el volumen y lo sella en la cadena
(bloque nuevo encadenado al anterior). El archivo es el que despues
viaja hacia la empresa y el conciliador.

Re-emitir vuelve a sellar el MISMO extracto con una version nueva del
archivo (sufijo -v2, -v3...): es la correccion legitima, con historial:
la version anterior queda en la cadena.

Todas las acciones quedan auditadas con el usuario que las ejecuta.
"""
import datetime
import csv
import io
import json
import logging
import uuid
from pathlib import Path

from app import cadena, config, db
from app.nucleo import sellos

CABECERA = "fecha;monto;referencia;descripcion"
_log = logging.getLogger(__name__)


def _xml(filas):
    """Extracto en XML: una etiqueta por movimiento (formato documentado)."""
    from xml.sax.saxutils import quoteattr
    partes = ['<?xml version="1.0" encoding="UTF-8"?>', '<extracto version="1.0">']
    for fila in filas:
        partes.append(
            "  <movimiento fecha=%s monto=\"%s\" referencia=%s descripcion=%s/>"
            % (quoteattr(str(fila["fecha"])), fila["monto"],
               quoteattr(fila["referencia"] or ""),
               quoteattr(fila["descripcion"] or "")))
    partes.append("</extracto>")
    return "\n".join(partes) + "\n"


def cerrar_dia(usuario_id, ip=None, formato="csv"):
    """Emite el extracto del dia. Devuelve (lote, bloque) o lanza ValueError."""
    return _emitir(None, usuario_id, ip, reemision=False, formato=formato)


def reemitir_ultimo(usuario_id, ip=None, formato="csv"):
    """Re-emite el ultimo extracto propio (correccion con rastro)."""
    return _emitir(None, usuario_id, ip, reemision=True, formato=formato)


def listar_lotes(limite=100):
    return db.consultar(
        "SELECT l.*, a.nombre AS archivo, a.sha256, a.ruta, a.bytes"
        " FROM lotes l LEFT JOIN archivos a ON a.id = l.archivo_id"
        " ORDER BY l.id DESC LIMIT %s", (limite,))


def _emitir(_codigo, usuario_id, ip, reemision, formato="csv"):
    """Crea archivo, lote y bloque en una única transacción.

    La copia en disco se escribe después del commit: PostgreSQL ya conserva el
    contenido binario, así que un fallo del volumen no rompe la descarga ni la
    verificación. La propagación HTTP también ocurre después del commit.
    """
    if formato not in ("csv", "xml"):
        raise ValueError("Formato no soportado: use CSV o XML.")
    extension = formato
    ruta = None

    with db.conectar() as conexion:
        with conexion.cursor() as cursor:
            # Serializa cierres y reemisiones para que dos solicitudes
            # simultáneas no usen el mismo código, versión o movimientos.
            cursor.execute("SELECT pg_advisory_xact_lock(781236)")
            if reemision:
                cursor.execute("SELECT * FROM lotes ORDER BY id DESC LIMIT 1 FOR UPDATE")
                lote_anterior = cursor.fetchone()
                if not lote_anterior:
                    raise ValueError("Todavia no se emitio ningun extracto.")
                codigo = lote_anterior["codigo"]
                cursor.execute(
                    "SELECT * FROM movimientos WHERE lote_id = %s ORDER BY id FOR UPDATE",
                    (lote_anterior["id"],))
                filas = cursor.fetchall()
            else:
                cursor.execute(
                    "SELECT * FROM movimientos WHERE estado = 'pendiente'"
                    " ORDER BY id FOR UPDATE")
                filas = cursor.fetchall()
                if not filas:
                    raise ValueError("No hay movimientos pendientes de emision.")
                codigo = _codigo_nuevo(cursor)

            version = _siguiente_version(codigo, cursor)
            nombre = _nombre_archivo(version, extension)
            contenido = _xml(filas) if formato == "xml" else _csv(filas)
            datos = contenido.encode("utf-8")
            carpeta = Path(config.dir_datos()) / "archivos"
            ruta = carpeta / ("%s_%s" % (uuid.uuid4().hex, nombre))

            cursor.execute(
                "INSERT INTO archivos (nombre, ruta, sha256, bytes, contenido,"
                " origen, subido_por) VALUES (%s, %s, %s, %s, %s, 'emitido', %s)"
                " RETURNING *",
                (nombre, str(ruta), sellos.huella_archivo(datos), len(datos),
                 datos, usuario_id))
            archivo = cursor.fetchone()

            if reemision:
                cursor.execute(
                    "UPDATE lotes SET archivo_id = %s, n_movimientos = %s,"
                    " sellado_en = now(), sellado_por = %s, updated_at = now()"
                    " WHERE id = %s RETURNING *",
                    (archivo["id"], len(filas), usuario_id,
                     lote_anterior["id"]))
            else:
                cursor.execute(
                    "INSERT INTO lotes (codigo, n_movimientos, archivo_id, sellado_en,"
                    " sellado_por) VALUES (%s, %s, %s, now(), %s) RETURNING *",
                    (codigo, len(filas), archivo["id"], usuario_id))
            lote = cursor.fetchone()
            if not reemision:
                cursor.execute(
                    "UPDATE movimientos SET estado = 'en_lote', lote_id = %s,"
                    " updated_at = now() WHERE id = ANY(%s)",
                    (lote["id"], [fila["id"] for fila in filas]))

            cursor.execute("SELECT * FROM bloques ORDER BY indice DESC LIMIT 1")
            ultimo = cursor.fetchone()
            bloque = sellos.construir_bloque(
                indice=(ultimo["indice"] + 1) if ultimo else 1,
                origen=config.ETIQUETA_SERVICIO, lote_codigo=codigo,
                archivo=nombre, movimientos=[dict(fila) for fila in filas],
                hash_archivo=sellos.huella_archivo(datos),
                hash_anterior=ultimo["hash_bloque"] if ultimo else ("0" * 64),
                emitido_por=usuario_id,
                sellado_en=datetime.datetime.now(datetime.timezone.utc).isoformat())
            cursor.execute(
                "INSERT INTO bloques (indice, origen, lote_codigo, archivo,"
                " n_movimientos, hashes_movimientos, hash_raiz, hash_archivo,"
                " hash_anterior, hash_bloque, emitido_por, sellado_en)"
                " VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)"
                " RETURNING id",
                (bloque["indice"], bloque["origen"], bloque["lote_codigo"],
                 bloque["archivo"], bloque["n_movimientos"],
                 json.dumps(bloque["hashes_movimientos"]), bloque["hash_raiz"],
                 bloque["hash_archivo"], bloque["hash_anterior"],
                 bloque["hash_bloque"], bloque["emitido_por"],
                 bloque["sellado_en"]))
            bloque["id"] = cursor.fetchone()["id"]
            for destino, _url in config.pares():
                cursor.execute(
                    "INSERT INTO bloques_envios (bloque_id, destino) VALUES (%s, %s)"
                    " ON CONFLICT (bloque_id, destino) DO NOTHING",
                    (bloque["id"], destino))
            detalle = {"codigo": codigo, "archivo": nombre,
                       "movimientos": len(filas), "version": version,
                       "indice_bloque": bloque["indice"], "formato": extension}
            cursor.execute(
                "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id,"
                " detalle, ip) VALUES (%s, %s, 'lotes', %s, %s::jsonb, %s)",
                (usuario_id, "reemision_lote" if reemision else "cierre_lote",
                 str(lote["id"]), json.dumps(detalle), ip))
            if reemision:
                cursor.execute(
                    "INSERT INTO alertas (tipo, severidad, titulo, detalle,"
                    " referencia, usuario_id) VALUES"
                    " ('operativa', 'baja', %s, %s, %s, %s)",
                    ("Extracto %s re-emitido (version %d)" % (codigo, version),
                     "La version anterior queda como historial en la cadena.",
                     codigo, usuario_id))
        conexion.commit()

    # La base es la copia persistente. El archivo local es una optimización.
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(ruta.name + ".tmp")
        temporal.write_bytes(datos)
        temporal.replace(ruta)
    except OSError:
        _log.exception("No se pudo escribir la copia local del extracto %s", nombre)
    try:
        cadena.reintentar_envios()
    except Exception:
        _log.exception("El extracto fue sellado, pero no se pudo propagar el bloque")
    return lote, bloque


def _codigo_nuevo(cursor=None):
    """Codigo del extracto del dia: E-AAAA-MM-DD-NN."""
    hoy = datetime.date.today().isoformat()
    if cursor is None:
        fila = db.consultar_uno(
            "SELECT COUNT(*) AS total FROM lotes WHERE codigo LIKE %s",
            ("E-%s%%" % hoy,))
    else:
        cursor.execute("SELECT COUNT(*) AS total FROM lotes WHERE codigo LIKE %s",
                       ("E-%s%%" % hoy,))
        fila = cursor.fetchone()
    return "E-%s-%02d" % (hoy, (fila["total"] if fila else 0) + 1)


def _siguiente_version(codigo, cursor=None):
    if cursor is None:
        fila = db.consultar_uno("SELECT COUNT(*) AS total FROM bloques"
                                " WHERE lote_codigo = %s", (codigo,))
    else:
        cursor.execute("SELECT COUNT(*) AS total FROM bloques WHERE lote_codigo = %s",
                       (codigo,))
        fila = cursor.fetchone()
    return (fila["total"] if fila else 0) + 1


def _nombre_archivo(version, extension):
    """Nombre descargable: servicio y fecha del extracto."""
    fecha = datetime.date.today().isoformat()
    sufijo = "" if version == 1 else "-v%d" % version
    return "banco-%s%s.%s" % (fecha, sufijo, extension)


def _csv(filas):
    """Archivo CSV con el formato documentado (sin adornos)."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=";", lineterminator="\n")
    escritor.writerow(CABECERA.split(";"))
    for fila in filas:
        escritor.writerow((fila["fecha"], fila["monto"],
                           fila["referencia"], fila["descripcion"]))
    return salida.getvalue()
