# -*- coding: utf-8 -*-
"""Pruebas del rechazo de archivos alterados en recepción."""
from unittest.mock import patch

from app import recepciones
from app.nucleo import sellos


def main():
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

    llamadas = []

    def sellos_despues_de_sincronizar(origen):
        llamadas.append(origen)
        return [] if len(llamadas) == 1 else [sello]

    with patch.object(recepciones.cadena, "sellos_de_origen",
                      side_effect=sellos_despues_de_sincronizar), \
            patch.object(recepciones.cadena, "sincronizar_con_pares",
                         return_value=[]):
        estado, _, _ = recepciones._verificar("EMPRESA", archivo, alterado)
    assert llamadas == ["EMPRESA", "EMPRESA"]
    assert estado == "alterado"
    print("Caso 3: la recepción reintenta después de sincronizar sellos")


if __name__ == "__main__":
    main()
