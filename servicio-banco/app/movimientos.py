# -*- coding: utf-8 -*-
"""app/movimientos.py

Movimientos de la cuenta bancaria de la empresa.

Reglas:
  * solo se pueden editar o eliminar mientras estan pendientes de cierre;
  * una vez que pertenecen a un lote sellado son inmutables: corregirlos
    exige una re-emision del lote (queda historial y auditoria);
  * la referencia es opcional (los movimientos de cuenta no siempre
    traen comprobante; se guarda vacia cuando no hay).
"""
import datetime

from app import db


def listar(limite=300):
    return db.consultar(
        "SELECT m.*, l.codigo AS lote_codigo FROM movimientos m "
        "LEFT JOIN lotes l ON l.id = m.lote_id "
        "ORDER BY m.fecha DESC, m.id DESC LIMIT %s", (limite,))


def pendientes():
    """Movimientos sin lote, en orden de alta (los del proximo cierre)."""
    return db.consultar(
        "SELECT * FROM movimientos WHERE estado = 'pendiente' ORDER BY id")


def resumen():
    fila = db.consultar_uno(
        "SELECT COUNT(*) AS total, COALESCE(SUM(monto), 0) AS monto_total,"
        " COUNT(*) FILTER (WHERE estado = 'pendiente') AS pendientes,"
        " COUNT(*) FILTER (WHERE estado = 'en_lote') AS en_lote"
        " FROM movimientos")
    return fila


def proxima_referencia():
    """El banco no asigna referencias automaticas: se deja vacio."""
    return ""


def alta(fecha, monto, referencia, descripcion, usuario_id):
    """Registra una venta. Devuelve la fila creada."""
    if not fecha:
        fecha = datetime.date.today().isoformat()
    referencia = (referencia or "").strip().upper()
    descripcion = (descripcion or "").strip().upper()
    return db.ejecutar(
        "INSERT INTO movimientos (fecha, monto, referencia, descripcion,"
        " creado_por) VALUES (%s, %s, %s, %s, %s) RETURNING *",
        (fecha, int(monto), referencia, descripcion, usuario_id))


def obtener(movimiento_id):
    return db.consultar_uno("SELECT * FROM movimientos WHERE id = %s",
                            (movimiento_id,))


def actualizar(movimiento_id, fecha, monto, referencia, descripcion):
    db.ejecutar(
        "UPDATE movimientos SET fecha = %s, monto = %s, referencia = %s,"
        " descripcion = %s, updated_at = now() WHERE id = %s",
        (fecha, int(monto), (referencia or "").strip().upper(),
         (descripcion or "").strip().upper(), movimiento_id))


def eliminar(movimiento_id):
    db.ejecutar("DELETE FROM movimientos WHERE id = %s", (movimiento_id,))


def del_lote(lote_id):
    """Movimientos de un lote, en el mismo orden en que se sellaron."""
    return db.consultar(
        "SELECT * FROM movimientos WHERE lote_id = %s ORDER BY id", (lote_id,))


def marcar_en_lote(ids, lote_id):
    if not ids:
        return
    db.ejecutar(
        "UPDATE movimientos SET estado = 'en_lote', lote_id = %s,"
        " updated_at = now() WHERE id = ANY(%s)", (lote_id, list(ids)))
