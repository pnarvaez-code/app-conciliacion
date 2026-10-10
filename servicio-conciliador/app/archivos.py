# -*- coding: utf-8 -*-
"""app/archivos.py

Guardado de los archivos recibidos (extracto del banco y archivo de
ventas de la empresa). Los archivos viven en el volumen
(`DIR_DATOS/archivos`) y en la base se guarda su huella SHA-256, que es
la que se compara contra el sello de la cadena.

La huella se calcula sobre el contenido exacto que llega: si el archivo
fue tocado en el camino, no coincidira con el sello del emisor.
"""
import datetime
import os

from app import config, db
from app.nucleo import sellos


def guardar(nombre, contenido, usuario_id):
    """Guarda el archivo recibido y registra su fila. Devuelve la fila."""
    carpeta = os.path.join(config.dir_datos(), "archivos")
    os.makedirs(carpeta, exist_ok=True)
    marca = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    ruta = os.path.join(carpeta, "%s_%s" % (marca, nombre))
    datos = contenido if isinstance(contenido, bytes) else contenido.encode("utf-8")
    with open(ruta, "wb") as archivo:
        archivo.write(datos)
    return db.ejecutar(
        "INSERT INTO archivos (nombre, ruta, sha256, bytes, origen, subido_por)"
        " VALUES (%s, %s, %s, %s, 'recibido', %s) RETURNING *",
        (nombre, ruta, sellos.huella_archivo(datos), len(datos), usuario_id))


def leer(ruta):
    """Contenido del archivo guardado, como texto."""
    with open(ruta, "rb") as archivo:
        datos = archivo.read()
    return datos.decode("utf-8", errors="replace")
