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
from pathlib import Path

from app import config, db
from app.nucleo import sellos


def guardar(nombre, contenido, usuario_id):
    """Guarda el archivo recibido y registra su fila. Devuelve la fila."""
    nombre = _nombre_seguro(nombre)
    carpeta = Path(config.dir_datos()) / "archivos"
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    ruta = carpeta / ("%s_%s" % (marca, nombre))
    datos = contenido if isinstance(contenido, bytes) else contenido.encode("utf-8")
    with ruta.open("wb") as archivo:
        archivo.write(datos)
    return db.ejecutar(
        "INSERT INTO archivos (nombre, ruta, sha256, bytes, contenido, origen, subido_por)"
        " VALUES (%s, %s, %s, %s, %s, 'recibido', %s) RETURNING *",
        (nombre, str(ruta), sellos.huella_archivo(datos), len(datos), datos, usuario_id))


def leer(ruta):
    """Contenido del archivo guardado, como texto."""
    with Path(ruta).open("rb") as archivo:
        datos = archivo.read()
    return datos.decode("utf-8", errors="replace")


def obtener_contenido(archivo):
    """Lee del volumen o del respaldo PostgreSQL si el dyno fue reiniciado."""
    ruta = archivo.get("ruta")
    if ruta and Path(ruta).is_file():
        return Path(ruta).read_bytes()
    contenido = archivo.get("contenido")
    if contenido is not None:
        return bytes(contenido)
    raise FileNotFoundError("el archivo no está en el volumen ni en el respaldo")


def _nombre_seguro(nombre):
    """Conserva solo el nombre base para que una carga no salga del volumen."""
    nombre = (nombre or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not nombre or nombre in (".", ".."):
        raise ValueError("el archivo debe tener un nombre valido")
    return nombre
