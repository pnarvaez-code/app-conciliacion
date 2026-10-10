# -*- coding: utf-8 -*-
"""app/db.py

Acceso a PostgreSQL con psycopg 3.

Cada consulta abre y cierra una conexion (servicio pequeno, sin pool
externo). Las filas se devuelven como diccionarios. Todas las consultas
del proyecto usan parametros: nunca se concatena SQL con datos del
usuario.

`aplicar_migracion` ejecuta el archivo SQL inicial una sola vez (si la
tabla `usuarios` no existe) y `asegurar_admin` crea el primer usuario a
partir de las variables de entorno, tambien una sola vez.
"""
import os

import psycopg
from psycopg.rows import dict_row

from app import config


def conectar():
    return psycopg.connect(config.base_datos(), row_factory=dict_row)


def consultar(sql, parametros=()):
    """Devuelve todas las filas de una consulta."""
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()


def consultar_uno(sql, parametros=()):
    """Devuelve la primera fila (o None)."""
    filas = consultar(sql, parametros)
    return filas[0] if filas else None


def ejecutar(sql, parametros=()):
    """Ejecuta una sentencia y confirma. Devuelve la fila si hay RETURNING."""
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(sql, parametros)
            fila = cursor.fetchone() if cursor.description else None
            conexion.commit()
            return fila


def aplicar_migracion():
    """Aplica migraciones/001_inicial.sql si la base esta vacia."""
    existe = consultar_uno(
        "SELECT 1 AS hay FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'usuarios'")
    if existe:
        return False
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "migraciones", "001_inicial.sql")
    with open(ruta, encoding="utf-8") as archivo:
        sql = archivo.read()
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(sql)
        conexion.commit()
    return True


def asegurar_admin():
    """Crea el primer usuario (administrador operador) si no hay ninguno."""
    hay = consultar_uno("SELECT COUNT(*) AS total FROM usuarios")
    if hay and hay["total"] > 0:
        return False
    from app import seguridad
    correo, clave = config.admin_inicial()
    ejecutar(
        "INSERT INTO usuarios (email, nombre, clave_hash) VALUES (%s, %s, %s)",
        (correo, "Administrador", seguridad.hash_clave(clave)))
    return True
