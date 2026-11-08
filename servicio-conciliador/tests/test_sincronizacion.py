"""Pruebas de validacion de bloques recibidos sin base de datos."""
from app import cadena
from app.nucleo import sellos


def main():
    bloque = sellos.construir_bloque(
        indice=1,
        origen="PYME",
        lote_codigo="V-2026-09-01-01",
        archivo="ventas.csv",
        movimientos=[{"fecha": "2026-09-01", "monto": 100,
                      "referencia": "FV-1", "descripcion": "VENTA"}],
        hash_archivo=sellos.huella_archivo("contenido"),
        hash_anterior=None,
        emitido_por=1,
        sellado_en="2026-09-01T20:00:00Z",
    )

    resultado = cadena.registrar_bloque_recibido(
        bloque, origen_esperado="BANCO")
    assert resultado == {
        "aceptado": False,
        "motivo": "origen no coincide con el par",
    }

    alterado = dict(bloque, lote_codigo="V-ALTERADO")
    resultado = cadena.registrar_bloque_recibido(alterado,
                                                 origen_esperado="PYME")
    assert resultado == {
        "aceptado": False,
        "motivo": "huella del bloque invalida",
    }

    print("Validacion de sincronizacion: todas correctas.")


if __name__ == "__main__":
    main()
