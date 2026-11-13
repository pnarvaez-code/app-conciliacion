# -*- coding: utf-8 -*-
"""app/auditoria.py

Registro de auditoria: quien hizo que, cuando y desde donde.

La tabla `auditoria` es append-only (no se actualiza ni se borra): es la
memoria del sistema y la base para identificar responsables de cada
emision, carga o modificacion. Se registran tambien los inicios de
sesion y las acciones administrativas.
"""
import json

from app import db


def registrar(usuario_id, accion, entidad=None, entidad_id=None,
              detalle=None, ip=None):
    """Agrega una fila de auditoria. `detalle` se guarda como jsonb."""
    db.ejecutar(
        "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id,"
        " detalle, ip) VALUES (%s, %s, %s, %s, %s, %s)",
        (usuario_id, accion, entidad,
         str(entidad_id) if entidad_id is not None else None,
         json.dumps(detalle or {}, ensure_ascii=False), ip))


def listar(limite=200):
    return db.consultar(
        "SELECT a.id, a.accion, a.entidad, a.entidad_id, a.detalle, a.ip,"
        " a.created_at, u.email AS usuario "
        "FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id "
        "ORDER BY a.id DESC LIMIT %s", (limite,))


def listar_rechazos_carga(limite=100):
    """Devuelve archivos rechazados con sus datos forenses de carga."""
    return db.consultar(
        "SELECT a.id, a.created_at, a.ip, u.email AS usuario,"
        " a.detalle->>'origen' AS origen,"
        " a.detalle->>'archivo' AS archivo,"
        " a.detalle->>'ruta_reportada' AS ruta_reportada,"
        " a.detalle->>'sha256' AS sha256,"
        " a.detalle->>'bytes' AS bytes,"
        " a.detalle->>'motivo' AS motivo"
        " FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id"
        " WHERE a.accion = 'recepcion_rechazada'"
        " AND NOT EXISTS ("
        " SELECT 1 FROM recepciones r"
        " JOIN archivos ar ON ar.id = r.archivo_id"
        " WHERE r.estado_integridad = 'rechazado'"
        " AND r.origen = a.detalle->>'origen'"
        " AND ar.sha256 = a.detalle->>'sha256')"
        " ORDER BY a.id DESC LIMIT %s", (limite,))
