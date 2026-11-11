# -*- coding: utf-8 -*-
"""Pruebas del rechazo de archivos alterados en recepción."""
from unittest.mock import patch

from app import recepciones
from app import archivos
from app.nucleo import sellos


def main():
    assert archivos._nombre_seguro("../archivo.csv") == "archivo.csv"
    assert archivos._nombre_seguro(r"C:\cargas\archivo.csv") == "archivo.csv"
    try:
        archivos._nombre_seguro("")
    except ValueError:
        pass
    else:
        raise AssertionError("un nombre vacio debio rechazarse")
    print("Nombre de archivo: normalizado correctamente")

    original = b"fecha;monto;referencia;descripcion\n2026-09-01;100;R-1;VENTA\n"
    alterado = b"fecha;monto;referencia;descripcion\n2026-09-01;999;R-1;VENTA\n"
    sello = {
        "hash_archivo": sellos.huella_archivo(original),
        "lote_codigo": "V-2026-09-01-01",
        "sellado_en": "2026-09-01T20:00:00Z",
        "hashes_movimientos": [],
        "n_movimientos": 1,
    }
    archivo = {"nombre": "alterado.csv",
               "sha256": sellos.huella_archivo(alterado)}
    with patch.object(recepciones.cadena, "sellos_de_origen",
                      return_value=[sello]):
        estado, lote, detalle = recepciones._verificar(
            "EMPRESA", archivo, alterado)
    assert estado == "alterado"
    assert lote == sello["lote_codigo"]
    assert "no coincide" in detalle
    assert archivo["sha256"] != sello["hash_archivo"]
    print("Caso 3: archivo alterado detectado antes de guardar la recepción")

    # Aunque el hash del archivo fuera aceptado indebidamente, los hashes de
    # movimientos sellados deben coincidir también; de otro modo no se puede
    # usar esa recepción para conciliar.
    contenido = b"fecha;monto;referencia;descripcion\n2026-09-01;100;R-1;VENTA\n"
    sello_inconsistente = dict(sello, hash_archivo=sellos.huella_archivo(contenido),
                               hashes_movimientos=["0" * 64])
    archivo_intacto = {"nombre": "inconsistente.csv",
                       "sha256": sellos.huella_archivo(contenido)}
    with patch.object(recepciones.cadena, "sellos_de_origen",
                      return_value=[sello_inconsistente]):
        estado, lote, detalle = recepciones._verificar(
            "EMPRESA", archivo_intacto, contenido)
    assert estado == "alterado" and lote == sello["lote_codigo"]
    assert "movimientos no coinciden" in detalle
    print("SHA-256 y huellas de movimientos: verificacion doble correcta")

    with patch.object(recepciones.cadena, "sellos_de_origen",
                      return_value=[]), \
            patch.object(recepciones.cadena, "sincronizar_con_pares") as sincronizar:
        estado, _, _ = recepciones._verificar("EMPRESA", archivo, alterado)
    assert estado == "sin_sello"
    sincronizar.assert_not_called()
    print("Carga sin sello: no bloquea por sincronización de Internet")


if __name__ == "__main__":
    main()
