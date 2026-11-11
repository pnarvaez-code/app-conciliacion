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
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from app import config


def conectar():
    conexion = psycopg.connect(config.base_datos(), row_factory=dict_row)
    with conexion.cursor() as cursor:
        esquema = sql.Identifier(config.esquema())
        cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(esquema))
        cursor.execute(sql.SQL("SET search_path TO {}, public").format(esquema))
    conexion.commit()
    return conexion


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
        "WHERE table_schema = %s AND table_name = 'usuarios'",
        (config.esquema(),))
    if existe:
        return False
    ruta = Path(__file__).resolve().parent.parent / "migraciones" / "001_inicial.sql"
    with ruta.open(encoding="utf-8") as archivo:
        sql = archivo.read()
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(sql)
        conexion.commit()
    return True


def asegurar_indices():
    """Crea invariantes de concurrencia también en bases ya existentes."""
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_movimientos_referencia_no_vacia "
                "ON movimientos (referencia) WHERE referencia <> ''")
        conexion.commit()


def asegurar_respaldo_archivos():
    """Añade el respaldo binario a bases creadas antes de esta versión."""
    with conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("ALTER TABLE archivos ADD COLUMN IF NOT EXISTS contenido BYTEA")
        conexion.commit()


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
