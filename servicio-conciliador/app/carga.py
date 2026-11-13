# -*- coding: utf-8 -*-
"""app/carga.py

Lectura de los archivos recibidos: CSV (empresa y banco) y XML (extracto
del banco). Devuelve los movimientos en el esquema canonico que usan los
sellos y el motor de conciliacion: fecha, monto, referencia, descripcion.
"""
import csv
import io
import xml.etree.ElementTree as ET
from datetime import datetime

CABECERA = "fecha;monto;referencia;descripcion"
MAX_MOVIMIENTOS = 10000


def leer(nombre, contenido):
    """Devuelve (movimientos, formato). Lanza ValueError si no se entiende."""
    nombre = (nombre or "").lower()
    if nombre.endswith(".xml"):
        return _leer_xml(contenido), "xml"
    if nombre.endswith(".csv"):
        return _leer_csv(contenido), "csv"
    raise ValueError("formato no soportado: use un archivo CSV o XML")


def _leer_csv(contenido):
    movimientos = []
    lector = csv.reader(io.StringIO(contenido.lstrip("\ufeff")),
                        delimiter=";", strict=True)
    primera = True
    try:
        for partes in lector:
            numero = lector.line_num
            if not partes or not any(valor.strip() for valor in partes):
                continue
            if primera:
                primera = False
                if len(partes) == 1 and "," in partes[0]:
                    raise ValueError(
                        "separador CSV invalido: use punto y coma (;), no coma")
                if (len(partes) >= 2 and
                        partes[0].strip().lower() == "fecha" and
                        partes[1].strip().lower() == "monto"):
                    if len(partes) != 4:
                        raise ValueError(
                            "la cabecera CSV debe tener exactamente 4 campos")
                    continue
            if len(partes) == 1 and "," in partes[0]:
                raise ValueError(
                    "linea %d: separador CSV invalido, use punto y coma (;)"
                    % numero)
            if len(partes) != 4:
                raise ValueError(
                    "linea %d del archivo debe tener exactamente 4 campos"
                    % numero)
            try:
                monto = int(partes[1].strip())
            except ValueError:
                raise ValueError(
                    "linea %d: el monto no es un numero entero" % numero)
            if monto <= 0:
                raise ValueError("linea %d: el monto debe ser positivo" % numero)
            fecha = _normalizar_fecha(partes[0].strip(), numero)
            movimientos.append({"fecha": fecha, "monto": monto,
                                "referencia": partes[2].strip(),
                                "descripcion": partes[3].strip()})
            if len(movimientos) > MAX_MOVIMIENTOS:
                raise ValueError("el archivo supera el maximo de %d movimientos"
                                 % MAX_MOVIMIENTOS)
    except csv.Error as error:
        raise ValueError("linea %d: CSV invalido: %s"
                         % (lector.line_num, error)) from error
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
        fecha = _normalizar_fecha((nodo.get("fecha") or "").strip(), "XML")
        movimientos.append({"fecha": fecha,
                            "monto": monto,
                            "referencia": (nodo.get("referencia") or "").strip(),
                            "descripcion": (nodo.get("descripcion") or "").strip()})
        if len(movimientos) > MAX_MOVIMIENTOS:
            raise ValueError("el archivo supera el maximo de %d movimientos"
                             % MAX_MOVIMIENTOS)
    if not movimientos:
        raise ValueError("el XML no tiene movimientos")
    return movimientos


def _normalizar_fecha(fecha, linea):
    """Acepta fechas de los emisores y las guarda en ISO para el motor."""
    valor = (fecha or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            pass
    raise ValueError("linea %s: fecha invalida (use AAAA-MM-DD o DD/MM/AAAA)"
                     % linea)
