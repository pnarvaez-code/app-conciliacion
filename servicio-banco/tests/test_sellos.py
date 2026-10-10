# -*- coding: utf-8 -*-
"""tests/test_sellos.py

Pruebas del nucleo de sellos (funciones puras, sin base de datos).

Se verifica que los calculos sean estables y que las tres verificaciones
detecten lo que deben detectar. Se ejecutan con:  python -m tests.test_sellos
"""
from app.nucleo import sellos

MOVIMIENTOS = [
    {"fecha": "2026-09-01", "monto": 151000, "referencia": "FV-4001",
     "descripcion": "VENTA TARJETA"},
    {"fecha": "2026-09-01", "monto": 222000, "referencia": "FV-4002",
     "descripcion": "VENTA TARJETA"},
]


def main():
    # La huella canonica es estable (misma entrada, misma salida).
    huella = sellos.huella_movimiento(MOVIMIENTOS[0])
    assert len(huella) == 64, "la huella debe tener 64 caracteres"
    assert huella == sellos.huella_movimiento(dict(MOVIMIENTOS[0])), "estable"

    # El bloque se arma con su huella y encadena con 64 ceros al inicio.
    bloque = sellos.construir_bloque(
        indice=1, origen="PYME", lote_codigo="V-2026-09-01-01",
        archivo="V-2026-09-01-01.csv", movimientos=MOVIMIENTOS,
        hash_archivo=sellos.huella_archivo("contenido del archivo"),
        hash_anterior=None, emitido_por=1, sellado_en="2026-09-01T20:00:00Z")
    assert bloque["hash_anterior"] == "0" * 64
    assert not sellos.verificar_cadena([bloque]), "cadena sana debe verificar"

    # (a) Si se toca un campo del bloque, la verificacion lo detecta.
    tocado = dict(bloque, n_movimientos=99)
    assert sellos.verificar_cadena([tocado]), "bloque alterado debe detectarse"

    # (b) Si cambia el archivo, la verificacion lo detecta.
    assert sellos.verificar_archivo(bloque, "contenido del archivo") is None
    assert sellos.verificar_archivo(bloque, "otro contenido") is not None

    # (c) Si cambia un movimiento, se señala la posicion exacta.
    movidos = [dict(MOVIMIENTOS[0]), dict(MOVIMIENTOS[1], monto=222001)]
    problemas = sellos.verificar_movimientos(bloque, movidos)
    assert problemas and "movimiento #2" in problemas[0], problemas

    # (c) Si se elimina un movimiento, se detecta la cantidad distinta.
    problemas = sellos.verificar_movimientos(bloque, MOVIMIENTOS[:1])
    assert problemas and "cantidad distinta" in problemas[0], problemas

    print("Pruebas del nucleo de sellos: todas correctas.")


if __name__ == "__main__":
    main()
