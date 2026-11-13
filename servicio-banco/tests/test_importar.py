from app.cierre import _csv
from app.importar import leer_texto, leer_xml


def main():
    filas = leer_texto(
        "fecha;monto;referencia;descripcion\n"
        "01/11/2026;1.250.000;;VENTA TARJETA")
    assert filas == [{
        "fecha": "2026-11-01", "monto": 1250000,
        "referencia": "", "descripcion": "VENTA TARJETA"}]
    filas = leer_xml(
        "<extracto><movimiento><fecha>01/11/2026</fecha><monto>900</monto>"
        "<descripcion>TRANSFERENCIA</descripcion></movimiento></extracto>")
    assert filas[0]["fecha"] == "2026-11-01"
    assert filas[0]["monto"] == 900
    contenido = _csv([{"fecha": "2026-11-01", "monto": 900,
                       "referencia": "TRX;001",
                       "descripcion": "ABONO; POS"}])
    filas = leer_texto(contenido)
    assert filas[0]["referencia"] == "TRX;001"
    assert filas[0]["descripcion"] == "ABONO; POS"
    try:
        leer_texto("fecha,monto,referencia,descripcion\n"
                   "01/11/2026,900,,VENTA")
    except ValueError as error:
        assert "separador CSV invalido" in str(error)
    else:
        raise AssertionError("CSV separado por comas debio rechazarse")
    print("Prueba de importacion BANCO: todas correctas.")


if __name__ == "__main__":
    main()
