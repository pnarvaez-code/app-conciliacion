# -*- coding: utf-8 -*-
"""app/importar.py

Carga de movimientos desde un archivo del sistema de origen.

    python -m app.importar ejemplos/extracto_ejemplo.csv

Es la via de integracion: en la operacion real el banco no tipea los
movimientos de la cuenta de a uno, los carga desde su sistema central en un
lote. Se usa la misma funcion de alta que la pantalla, asi que quedan con
las mismas validaciones, el mismo estado y el registro en auditoria con el
usuario responsable.

Las referencias no vacías que ya existen se omiten. Las referencias vacías se
conservan para que el conciliador pueda aplicar los cruces por monto y fecha.
"""
import csv
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

from app import db


MAX_FILAS = 10000


def _fecha(valor, numero):
    valor = (valor or "").strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            pass
    raise ValueError("linea %d: fecha invalida (use dd/mm/aaaa)" % numero)


def _monto(valor, numero):
    limpio = str(valor or "").strip().replace(".", "").replace(" ", "")
    if limpio.endswith(",00"):
        limpio = limpio[:-3]
    try:
        monto = int(limpio.replace(",", ""))
    except ValueError:
        raise ValueError("linea %d: el monto no es un numero entero" % numero)
    if monto <= 0:
        raise ValueError("linea %d: el monto debe ser positivo" % numero)
    return monto


def _fila(fecha, monto, referencia, descripcion, numero):
    return {"fecha": _fecha(fecha, numero), "monto": _monto(monto, numero),
            "referencia": (referencia or "").strip().upper(),
            "descripcion": (descripcion or "").strip().upper()}


def leer_texto(texto):
    """Lee filas separadas por punto y coma con cabecera opcional."""
    filas = []
    lineas = [linea for linea in texto.lstrip("\ufeff").splitlines() if linea.strip()]
    if not lineas:
        raise ValueError("el texto no tiene movimientos")
    tiene_cabecera = "fecha" in lineas[0].lower() and "monto" in lineas[0].lower()
    inicio = 1 if tiene_cabecera else 0
    if ";" not in lineas[0] and "," in lineas[0]:
        raise ValueError("separador CSV invalido: use punto y coma (;), no coma")
    delimitador = ";"
    for numero, linea in enumerate(lineas[inicio:], start=inicio + 1):
        if ";" not in linea and "," in linea:
            raise ValueError("linea %d: separador CSV invalido, use punto y coma (;)"
                             % numero)
        partes = next(csv.reader([linea], delimiter=delimitador), [])
        if len(partes) < 4:
            raise ValueError("linea %d: se esperan fecha;monto;referencia;descripcion" % numero)
        filas.append(_fila(partes[0], partes[1], partes[2], delimitador.join(partes[3:]), numero))
        if len(filas) > MAX_FILAS:
            raise ValueError("el archivo supera el maximo de %d movimientos" % MAX_FILAS)
    if not filas:
        raise ValueError("el archivo no tiene movimientos")
    return filas


def leer_xml(texto):
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as error:
        raise ValueError("XML invalido: %s" % error)
    filas = []
    elementos = [elemento for elemento in raiz.iter()
                 if elemento.tag.lower().split("}")[-1] in ("movimiento", "venta", "transaction")]
    for numero, elemento in enumerate(elementos, start=1):
        valores = dict(elemento.attrib)
        for hijo in elemento:
            valores[hijo.tag.lower().split("}")[-1]] = (hijo.text or "").strip()
        filas.append(_fila(valores.get("fecha"), valores.get("monto"),
                           valores.get("referencia"), valores.get("descripcion"), numero))
    if not filas:
        raise ValueError("el XML no tiene movimientos")
    return filas


def leer_archivo(nombre, contenido):
    extension = (nombre.rsplit(".", 1)[-1].lower() if "." in nombre else "csv")
    if extension not in ("csv", "xml"):
        raise ValueError("formato no soportado: use un archivo CSV o XML")
    return leer_xml(contenido) if extension == "xml" else leer_texto(contenido)


def importar_filas(filas, usuario_id, archivo):
    creados, omitidos = 0, 0
    with db.conectar() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(781234)")
            for fila in filas:
                referencia = fila["referencia"]
                cursor.execute(
                    "INSERT INTO movimientos (fecha, monto, referencia,"
                    " descripcion, creado_por) VALUES (%s, %s, %s, %s, %s)"
                    " ON CONFLICT (referencia) WHERE referencia <> ''"
                    " DO NOTHING RETURNING id",
                    (fila["fecha"], fila["monto"], referencia,
                     fila["descripcion"], usuario_id))
                if cursor.fetchone():
                    creados += 1
                else:
                    omitidos += 1
            cursor.execute(
                "INSERT INTO auditoria (usuario_id, accion, entidad, detalle)"
                " VALUES (%s, %s, %s, %s::jsonb)",
                (usuario_id, "importar_movimientos", "movimientos",
                 json.dumps({"archivo": archivo, "creados": creados,
                             "omitidos": omitidos}, ensure_ascii=False)))
        conexion.commit()
    return creados, omitidos


def leer(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        return leer_archivo(ruta, archivo.read())


def main(ruta):
    usuario = db.consultar_uno(
        "SELECT id, email FROM usuarios WHERE activo ORDER BY id LIMIT 1")
    if not usuario:
        print("No hay usuarios activos: arranque el servicio antes de importar.")
        return 1
    try:
        filas = leer(ruta)
    except (OSError, ValueError) as error:
        print("No se pudo leer %s: %s" % (ruta, error))
        return 1

    creados, omitidos = importar_filas(filas, usuario["id"], ruta)
    print("Importados %d movimientos de %s (%d omitidos por referencia repetida)."
          % (creados, ruta, omitidos))
    print("Responsable: %s" % usuario["email"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python -m app.importar <archivo.csv>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
