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
