# -*- coding: utf-8 -*-
"""La API interna rechaza bloques adulterados antes de consultar la base."""
from unittest.mock import patch

from app import cadena, config
from app.nucleo import sellos


def main():
    movimientos = [{"fecha": "2026-11-13", "monto": 1000,
                    "referencia": "SEC-1", "descripcion": "PRUEBA"}]
    bloque = sellos.construir_bloque(
        indice=1, origen=(config.ETIQUETA_SERVICIO if
                          config.ETIQUETA_SERVICIO in ("PYME", "BANCO")
                          else "PYME"), lote_codigo="V-2026-11-13-01",
        archivo="prueba.csv", movimientos=movimientos,
        hash_archivo=sellos.huella_archivo("contenido"),
        hash_anterior=None, emitido_por=1,
        sellado_en="2026-11-13T12:00:00+00:00")

    adulterado = dict(bloque, n_movimientos=99)
    with patch.object(cadena.db, "consultar_uno") as consultar:
        resultado = cadena.registrar_bloque_recibido(adulterado)
    assert not resultado["aceptado"]
    assert "huella" in resultado["motivo"]
    consultar.assert_not_called()

    incoherente = dict(bloque, n_movimientos=2,
                       hashes_movimientos=bloque["hashes_movimientos"] * 2)
    incoherente["hash_bloque"] = sellos.huella_bloque(incoherente)
    with patch.object(cadena.db, "consultar_uno") as consultar:
        resultado = cadena.registrar_bloque_recibido(incoherente)
    assert not resultado["aceptado"] and "raiz" in resultado["motivo"]
    consultar.assert_not_called()

    origen_invalido = dict(bloque, origen="ATACANTE")
    origen_invalido["hash_bloque"] = sellos.huella_bloque(origen_invalido)
    with patch.object(cadena.db, "consultar_uno") as consultar:
        resultado = cadena.registrar_bloque_recibido(origen_invalido)
    assert not resultado["aceptado"]
    assert "origen" in resultado["motivo"]
    consultar.assert_not_called()

    print("Bloques adulterados o de origen inválido: rechazados.")


if __name__ == "__main__":
    main()

