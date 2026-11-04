from app.importar import leer_texto, leer_xml


def main():
    filas = leer_texto(
        "fecha;monto;referencia;descripcion\n"
        "01/11/2026;1.250.000;FV-4029;VENTA TARJETA")
    assert filas == [{
        "fecha": "2026-11-01", "monto": 1250000,
        "referencia": "FV-4029", "descripcion": "VENTA TARJETA"}]
    filas = leer_xml(
        '<extracto><movimiento fecha="01/11/2026" monto="900" '
        'descripcion="TRANSFERENCIA"/></extracto>')
    assert filas[0]["fecha"] == "2026-11-01"
    assert filas[0]["monto"] == 900
    print("Prueba de importacion PYME: todas correctas.")


if __name__ == "__main__":
    main()
