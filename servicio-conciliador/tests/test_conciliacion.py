# -*- coding: utf-8 -*-
"""tests/test_conciliacion.py

Pruebas del motor de conciliacion (funciones puras): niveles de cruce y
clasificacion de diferencias. Se ejecuta con:
    python -m tests.test_conciliacion
"""
from app.nucleo import conciliacion


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

    # Diferencia: en la empresa y no en el banco.
    empresa = [_movimiento("2026-09-01", 812345, "", "VENTA LOCAL")]
    pares, pend_e, pend_b = conciliacion.conciliar(empresa, [])
    tipo, motivo = conciliacion.clasificar_pendiente(pend_e[0], [])
    assert tipo == "en_empresa_no_banco" or tipo == "en_banco_no_empresa"
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

    print("Pruebas del motor de conciliacion: todas correctas.")


if __name__ == "__main__":
    main()
