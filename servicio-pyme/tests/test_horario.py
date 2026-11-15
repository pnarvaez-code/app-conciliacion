"""Regresión: Paraguay usa UTC-3 también durante el invierno de 2026."""
from datetime import datetime, date, timezone
from app import horario


def main():
    for mes in (1, 7, 11):
        instante = datetime(2026, mes, 2, 2, 30, tzinfo=timezone.utc)
        assert horario.presentar(instante) == "01/%02d/2026 23:30:00 GMT-03:00" % mes
    fecha_contable = date(2026, 7, 2)
    assert horario.presentar(fecha_contable) == fecha_contable
    assert horario.presentar(None) is None
    print("Horario Paraguay: UTC-3 y fechas contables correctos.")


if __name__ == "__main__":
    main()
