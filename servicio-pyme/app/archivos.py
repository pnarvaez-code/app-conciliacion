# -*- coding: utf-8 -*-
"""app/archivos.py

Guardado y lectura de archivos (los lotes emitidos y, cuando corresponda,
los recibidos). Los archivos viven en el volumen (`DIR_DATOS/archivos`) y
en la base se guarda su huella SHA-256, que es la que sella la cadena.

La huella se calcula siempre sobre el contenido exacto que se guarda: si
alguien modifica el archivo en disco, la verificacion lo detecta.
"""
import datetime
import os

from app import config, db
from app.nucleo import sellos


def guardar(nombre, contenido, origen, usuario_id):
    """Guarda el archivo en el volumen y registra su fila. Devuelve la fila."""
    carpeta = os.path.join(config.dir_datos(), "archivos")
    os.makedirs(carpeta, exist_ok=True)
    marca = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    ruta = os.path.join(carpeta, "%s_%s" % (marca, nombre))
    datos = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    with open(ruta, "wb") as archivo:
        archivo.write(datos)
    return db.ejecutar(
        "INSERT INTO archivos (nombre, ruta, sha256, bytes, origen, subido_por)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
        (nombre, ruta, sellos.huella_archivo(datos), len(datos), origen,
         usuario_id))


def leer(ruta):
    """Contenido del archivo guardado (texto utf-8)."""
    with open(ruta, encoding="utf-8", errors="replace") as archivo:
        return archivo.read()
