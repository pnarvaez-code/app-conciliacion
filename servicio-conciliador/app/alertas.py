# -*- coding: utf-8 -*-
"""app/alertas.py

Alertas del servicio: integridad, operativas y (en el conciliador)
diferencias de conciliacion. Cada alerta tiene severidad y estado
(nueva, leida, resuelta) y queda asociada al usuario que la origino
cuando corresponde.
"""
from app import db


def crear(tipo, severidad, titulo, detalle, referencia=None, usuario_id=None):
    """Registra una alerta y devuelve su id."""
    fila = db.ejecutar(
        "INSERT INTO alertas (tipo, severidad, titulo, detalle, referencia,"
        " usuario_id) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (tipo, severidad, titulo, detalle, referencia, usuario_id))
    return fila["id"]


def listar(estado=None, limite=200):
    if estado:
        return db.consultar(
            "SELECT * FROM alertas WHERE estado = %s ORDER BY id DESC LIMIT %s",
            (estado, limite))
    return db.consultar("SELECT * FROM alertas ORDER BY id DESC LIMIT %s",
                        (limite,))


def contar_nuevas():
    fila = db.consultar_uno(
        "SELECT COUNT(*) AS total FROM alertas WHERE estado = 'nueva'")
    return fila["total"] if fila else 0


def cambiar_estado(alerta_id, estado):
    db.ejecutar("UPDATE alertas SET estado = %s, updated_at = now()"
                " WHERE id = %s", (estado, alerta_id))
