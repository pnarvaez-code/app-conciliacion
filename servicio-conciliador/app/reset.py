# -*- coding: utf-8 -*-
"""Restablecimiento de los datos operativos del servicio."""
import json
import os

from app import db, seguridad


def ejecutar(email, clave, usuario_id, ip):
    """Borra los datos operativos si se reautentica el usuario actual."""
    rutas = []
    with db.conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT id, clave_hash FROM usuarios "
                "WHERE id = %s AND email = %s AND activo",
                (usuario_id, email.strip().lower()))
            usuario = cursor.fetchone()
            if not usuario or not seguridad.verificar_clave(
                    clave, usuario["clave_hash"]):
                return False

            cursor.execute("SELECT ruta FROM archivos")
            rutas = [fila["ruta"] for fila in cursor.fetchall()]
            cursor.execute(
                "TRUNCATE TABLE conciliacion_pendientes, conciliacion_pares,"
                " conciliaciones, recepciones, bloques, archivos, alertas"
                " RESTART IDENTITY CASCADE")
            cursor.execute("DELETE FROM auditoria")
            cursor.execute(
                "INSERT INTO auditoria (usuario_id, accion, entidad, detalle, ip)"
                " VALUES (%s, 'reset_datos', 'aplicacion', %s, %s)",
                (usuario_id, json.dumps({"archivos": len(rutas)}), ip))
        conexion.commit()

    for ruta in rutas:
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass
    return True
