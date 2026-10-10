# -*- coding: utf-8 -*-
"""app/importar.py

Carga de movimientos desde un archivo del sistema de origen.

    python -m app.importar ejemplos/ventas_ejemplo.csv

Es la via de integracion: en la operacion real los movimientos no se tipean
de a uno, llegan desde el sistema de facturacion de la empresa en un archivo.
Se usa la misma funcion de alta que la pantalla, asi que quedan con las
mismas validaciones, el mismo estado y el registro en auditoria con el
usuario responsable.

Las referencias que ya existen se omiten, asi que se puede ejecutar mas de
una vez sin duplicar movimientos.
"""
import sys

from app import auditoria, db, movimientos


def leer(ruta):
    """Lee el archivo (fecha;monto;referencia;descripcion) y devuelve sus filas."""
    filas = []
    with open(ruta, encoding="utf-8") as archivo:
        for numero, linea in enumerate(archivo, start=1):
            linea = linea.strip().lstrip("﻿")
            if not linea:
                continue
            if numero == 1 and linea.lower().startswith("fecha"):
                continue
            partes = [parte.strip() for parte in linea.split(";")]
            if len(partes) < 4:
                raise ValueError("linea %d: no tiene 4 campos" % numero)
            try:
                monto = int(partes[1])
            except ValueError:
                raise ValueError("linea %d: el monto no es un numero entero" % numero)
            if monto <= 0:
                raise ValueError("linea %d: el monto debe ser positivo" % numero)
            filas.append({"fecha": partes[0], "monto": monto,
                          "referencia": partes[2].upper(),
                          "descripcion": partes[3].upper()})
    if not filas:
        raise ValueError("el archivo no tiene movimientos")
    return filas


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

    creados, omitidos = 0, 0
    for fila in filas:
        repetido = db.consultar_uno(
            "SELECT id FROM movimientos WHERE referencia = %s", (fila["referencia"],))
        if repetido:
            omitidos += 1
            continue
        movimientos.alta(fila["fecha"], fila["monto"], fila["referencia"],
                         fila["descripcion"], usuario["id"])
        creados += 1

    auditoria.registrar(usuario["id"], "importar_movimientos", "movimientos", None,
                        {"archivo": ruta, "creados": creados, "omitidos": omitidos})
    print("Importados %d movimientos de %s (%d omitidos por referencia repetida)."
          % (creados, ruta, omitidos))
    print("Responsable: %s" % usuario["email"])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python -m app.importar <archivo.csv>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
