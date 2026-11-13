# -*- coding: utf-8 -*-
"""app/archivos.py

Guardado y lectura de archivos (los lotes emitidos y, cuando corresponda,
los recibidos). Los archivos viven en el volumen (`DIR_DATOS/archivos`) y
en la base se guarda su huella SHA-256, que es la que sella la cadena.

La huella se calcula siempre sobre el contenido exacto que se guarda: si
alguien modifica el archivo en disco, la verificacion lo detecta.
"""
import datetime
from pathlib import Path

from app import config, db
from app.nucleo import sellos


def guardar(nombre, contenido, origen, usuario_id):
    """Guarda el archivo en el volumen y registra su fila. Devuelve la fila."""
    carpeta = Path(config.dir_datos()) / "archivos"
    carpeta.mkdir(parents=True, exist_ok=True)
    # Los microsegundos evitan que dos emisiones del mismo nombre, creadas en
    # el mismo segundo, compartan ruta y sobrescriban su evidencia local.
    marca = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    ruta = carpeta / ("%s_%s" % (marca, nombre))
    datos = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
    with ruta.open("wb") as archivo:
        archivo.write(datos)
    return db.ejecutar(
        "INSERT INTO archivos (nombre, ruta, sha256, bytes, contenido, origen, subido_por)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (nombre, str(ruta), sellos.huella_archivo(datos), len(datos), datos,
         origen, usuario_id))


def leer(ruta):
    """Contenido del archivo guardado (texto utf-8)."""
    with Path(ruta).open(encoding="utf-8", errors="replace") as archivo:
        return archivo.read()


def obtener_contenido(archivo):
    """Lee el archivo del volumen o, tras un reinicio de Heroku, de PostgreSQL."""
    ruta = archivo.get("ruta")
    if ruta and Path(ruta).is_file():
        return Path(ruta).read_bytes()
    contenido = archivo.get("contenido")
    if contenido is not None:
        return bytes(contenido)
    raise FileNotFoundError("el archivo no está en el volumen ni en el respaldo")
