# -*- coding: utf-8 -*-
"""tests/test_conciliacion.py

Pruebas del motor de conciliacion (funciones puras): niveles de cruce y
clasificacion de diferencias. Se ejecuta con:
    python -m tests.test_conciliacion
"""
from app.nucleo import conciliacion
from app import carga
from app.nucleo import sellos


def _movimiento(fecha, monto, referencia="", descripcion=""):
    return {"fecha": fecha, "monto": monto, "referencia": referencia,
            "descripcion": descripcion}


def main():
    # Nivel 1: referencia exacta.
    empresa = [_movimiento("2026-09-01", 151000, "FV-4001", "VENTA TARJETA")]
    banco = [_movimiento("2026-09-01", 151000, "FV-4001", "COBRO TARJETA")]
    pares, pend_e, pend_b = conciliacion.conciliar(empresa, banco)
    assert len(pares) == 1 and pares[0][2] == 1 and not pend_e and not pend_b
    print("Nivel 1 (referencia exacta): correcto")

    # Nivel 2: mismo monto, fechas a un dia.
    empresa = [_movimiento("2026-09-01", 745000, "", "VENTA EFECTIVO")]
    banco = [_movimiento("2026-09-02", 745000, "", "DEPOSITO EFECTIVO")]
    pares, _, _ = conciliacion.conciliar(empresa, banco)
    assert len(pares) == 1 and pares[0][2] == 2
    print("Nivel 2 (monto y fecha cercana): correcto")

    # Nivel 3: descripcion parecida y comision del 2 %.
    empresa = [_movimiento("2026-09-01", 1350000, "", "VENTA POR TRANSFERENCIA BANCARIA")]
    banco = [_movimiento("2026-09-03", 1323000, "", "ABONO POR TRANSFERENCIA")]
    pares, _, _ = conciliacion.conciliar(empresa, banco)
    assert len(pares) == 1 and pares[0][2] == 3
    print("Nivel 3 (descripcion y monto aproximado): correcto")

    # Los niveles se priorizan globalmente: una coincidencia aproximada no
    # puede consumir un comprobante que otra fila identifica exactamente.
    empresa = [_movimiento("2026-09-01", 100, "", "VENTA"),
               _movimiento("2026-09-01", 100, "R-1", "VENTA")]
    banco = [_movimiento("2026-09-01", 100, "R-1", "COBRO")]
    pares, pend_e, _ = conciliacion.conciliar(empresa, banco)
    assert len(pares) == 1 and pares[0][2] == 1 and pend_e[0]["referencia"] == ""
    print("Prioridad global de referencia: correcto")

    # Una referencia igual con datos distintos no es una conciliacion exitosa.
    empresa = [_movimiento("2026-09-01", 100000, "R-2", "VENTA POS")]
    banco = [_movimiento("2026-09-01", 98000, "R-2", "ABONO POS")]
    pares, pend_e, _ = conciliacion.conciliar(empresa, banco)
    tipo, _ = conciliacion.clasificar_pendiente(pend_e[0], banco)
    assert not pares and tipo == "referencia_distinta"
    print("Referencia con datos distintos: detectada")

    # El nivel 3 requiere fecha cercana y palabras significativas.
    empresa = [_movimiento("2026-09-01", 100, "", "PAGO DE VENTA")]
    banco = [_movimiento("2025-01-01", 99, "", "COMISION DE CUENTA")]
    assert not conciliacion.conciliar(empresa, banco)[0]
    print("Nivel 3: evita coincidencias lejanas o genericas")

    # Diferencia: en la empresa y no en el banco.
    empresa = [_movimiento("2026-09-01", 812345, "", "VENTA LOCAL")]
    pares, pend_e, pend_b = conciliacion.conciliar(empresa, [])
    tipo, motivo = conciliacion.clasificar_pendiente(pend_e[0], [])
    assert tipo is None
    tipo = tipo or "en_empresa_no_banco"
    assert tipo == "en_empresa_no_banco"
    assert pend_e and not pares
    print("Diferencia por existencia: correcto")

    # Diferencia por monto distinto el mismo dia.
    empresa = [_movimiento("2026-09-01", 500000, "", "VENTA LOCAL")]
    banco = [_movimiento("2026-09-01", 430000, "", "DEPOSITO EFECTIVO")]
    pares, pend_e, pend_b = conciliacion.conciliar(empresa, banco)
    tipo, motivo = conciliacion.clasificar_pendiente(pend_e[0], banco)
    assert tipo == "monto_distinto", (tipo, motivo)
    assert "430.000" in motivo and "500.000" in motivo
    print("Diferencia por monto distinto: correcto")

    # Diferencia por fecha fuera de la ventana: mismo monto, fechas lejanas y
    # descripciones sin palabras en comun (si compartieran palabras, el nivel 3
    # los cruzaria por aproximacion, que es su regla).
    empresa = [_movimiento("2026-09-01", 745000, "", "VENTA EFECTIVO")]
    banco = [_movimiento("2026-09-15", 745000, "", "CREDITO VARIOS")]
    pares, pend_e, pend_b = conciliacion.conciliar(empresa, banco)
    assert not pares, pares
    tipo, motivo = conciliacion.clasificar_pendiente(pend_e[0], banco)
    assert tipo == "fuera_de_ventana", (tipo, motivo)
    assert "14 dias" in motivo
    print("Diferencia por ventana de fechas: correcto")

    ventas = """fecha;monto;referencia;descripcion
2026-09-01;151000;FV-4001;VENTA TARJETA
2026-09-01;222000;;VENTA EFECTIVO
2026-09-01;293000;;VENTA TRANSFERENCIA BANCARIA
"""
    extracto = """fecha;monto;referencia;descripcion
2026-09-01;151000;FV-4001;COBRO TARJETA
2026-09-02;222000;;DEPOSITO EFECTIVO
2026-09-03;287140;;ABONO TRANSFERENCIA
"""
    movimientos_empresa, _ = carga.leer("ventas.csv", ventas)
    movimientos_banco, _ = carga.leer("banco.csv", extracto)
    pares, _, _ = conciliacion.conciliar(movimientos_empresa, movimientos_banco)
    assert [nivel for _, _, nivel in pares] == [1, 2, 3]
    print("Escenario exitoso: niveles 1, 2 y 3 correctos")

    bloque = sellos.construir_bloque(
        1, "BANCO", "E-2026-09-01-01", "banco-2026-09-01.csv",
        movimientos_banco, sellos.huella_archivo(extracto),
        "0" * 64, 1, "2026-09-01T00:00:00+00:00")
    adulterado = list(movimientos_banco)
    adulterado[2] = dict(adulterado[2], monto=999999)
    problemas = sellos.verificar_movimientos(bloque, adulterado)
    assert any("movimiento #3" in problema for problema in problemas)
    print("Escenario adulterado: movimiento #3 identificado")

    excel = "fecha;monto;referencia;descripcion\n45236;151.000;FV-4001;COBRO\n"
    try:
        carga.leer("extracto_tocado_por_excel.csv", excel)
    except ValueError as error:
        assert "linea 2" in str(error)
        print("Escenario Excel: formato corrupto detectado en linea 2")
    else:
        raise AssertionError("el formato corrupto de Excel debio rechazarse")

    try:
        carga.leer("extracto_comas.csv",
                   "fecha,monto,referencia,descripcion\n"
                   "2026-09-01,151000,FV-4001,COBRO\n")
    except ValueError as error:
        assert "separador CSV invalido" in str(error)
        print("Escenario CSV separado por comas: rechazado")
    else:
        raise AssertionError("el CSV separado por comas debio rechazarse")

    for fecha in ("20260901", "2026-W36-2"):
        try:
            carga.leer("fecha_invalida.csv", "fecha;monto;referencia;descripcion\n"
                       "%s;100;;COBRO\n" % fecha)
        except ValueError:
            pass
        else:
            raise AssertionError("la fecha invalida debio rechazarse: %s" % fecha)
    print("Fechas no ISO: rechazadas")

    print("Pruebas del motor de conciliacion: todas correctas.")


if __name__ == "__main__":
    main()
