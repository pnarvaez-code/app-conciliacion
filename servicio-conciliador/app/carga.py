# -*- coding: utf-8 -*-
"""app/carga.py

Lectura de los archivos recibidos: CSV (empresa y banco) y XML (extracto
del banco). Devuelve los movimientos en el esquema canonico que usan los
sellos y el motor de conciliacion: fecha, monto, referencia, descripcion.
"""
import xml.etree.ElementTree as ET
from datetime import date
import re

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
            if ";" not in linea:
                raise ValueError("separador CSV invalido: use punto y coma (;), no coma")
            continue
        if ";" not in linea and "," in linea:
            raise ValueError("linea %d: separador CSV invalido, use punto y coma (;)"
                             % numero)
        partes = linea.split(";")
        if len(partes) != 4:
            raise ValueError("linea %d del archivo debe tener exactamente 4 campos"
                             % numero)
        try:
            monto = int(partes[1].strip())
        except ValueError:
            raise ValueError("linea %d: el monto no es un numero entero" % numero)
        if monto <= 0:
            raise ValueError("linea %d: el monto debe ser positivo" % numero)
        fecha = partes[0].strip()
        _validar_fecha(fecha, numero)
        movimientos.append({"fecha": fecha, "monto": monto,
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
        if monto <= 0:
            raise ValueError("un movimiento del XML debe tener monto positivo")
        fecha = (nodo.get("fecha") or "").strip()
        _validar_fecha(fecha, "XML")
        movimientos.append({"fecha": fecha,
                            "monto": monto,
                            "referencia": (nodo.get("referencia") or "").strip(),
                            "descripcion": (nodo.get("descripcion") or "").strip()})
    if not movimientos:
        raise ValueError("el XML no tiene movimientos")
    return movimientos


def _validar_fecha(fecha, linea):
    """Rechaza fechas que romperian el motor de conciliacion."""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            raise ValueError
        date.fromisoformat(fecha)
    except ValueError:
        raise ValueError("linea %s: la fecha debe tener formato AAAA-MM-DD"
                         % linea)
