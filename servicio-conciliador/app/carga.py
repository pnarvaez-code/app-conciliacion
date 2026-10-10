# -*- coding: utf-8 -*-
"""app/carga.py

Lectura de los archivos recibidos: CSV (empresa y banco) y XML (extracto
del banco). Devuelve los movimientos en el esquema canonico que usan los
sellos y el motor de conciliacion: fecha, monto, referencia, descripcion.
"""
import xml.etree.ElementTree as ET

CABECERA = "fecha;monto;referencia;descripcion"


def leer(nombre, contenido):
    """Devuelve (movimientos, formato). Lanza ValueError si no se entiende."""
    if nombre.lower().endswith(".xml") or contenido.lstrip().startswith("<"):
        return _leer_xml(contenido), "xml"
    return _leer_csv(contenido), "csv"


def _leer_csv(contenido):
    movimientos = []
    for numero, linea in enumerate(contenido.splitlines(), start=1):
        linea = linea.strip().lstrip("\ufeff")
        if not linea:
            continue
        if numero == 1 and linea.lower().startswith("fecha"):
            continue
        partes = linea.split(";")
        if len(partes) < 4:
            raise ValueError("linea %d del archivo no tiene 4 campos" % numero)
        try:
            monto = int(partes[1].strip())
        except ValueError:
            raise ValueError("linea %d: el monto no es un numero entero" % numero)
        movimientos.append({"fecha": partes[0].strip(), "monto": monto,
                            "referencia": partes[2].strip(),
                            "descripcion": partes[3].strip()})
    if not movimientos:
        raise ValueError("el archivo no tiene movimientos")
    return movimientos


def _leer_xml(contenido):
    try:
        raiz = ET.fromstring(contenido)
    except ET.ParseError as error:
        raise ValueError("el XML no se puede leer: %s" % error)
    movimientos = []
    for nodo in raiz.iter("movimiento"):
        try:
            monto = int(nodo.get("monto", ""))
        except ValueError:
            raise ValueError("un movimiento del XML no tiene monto entero")
        movimientos.append({"fecha": (nodo.get("fecha") or "").strip(),
                            "monto": monto,
                            "referencia": (nodo.get("referencia") or "").strip(),
                            "descripcion": (nodo.get("descripcion") or "").strip()})
    if not movimientos:
        raise ValueError("el XML no tiene movimientos")
    return movimientos
