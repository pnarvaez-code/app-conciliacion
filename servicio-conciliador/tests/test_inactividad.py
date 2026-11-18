"""Sesiones: diez minutos, refrescos automáticos sin renovación."""
import datetime
from unittest.mock import patch
from starlette.requests import Request
from app import seguridad

def main():
    assert seguridad.DURACION_SESION == datetime.timedelta(minutes=10)
    usuario = {"id": 1, "rol": "administrador"}
    for ruta in ("/visor/estado", "/sesion/actividad"):
        request = Request({"type": "http", "path": ruta, "headers": []})
        with patch.object(seguridad, "_leer_token", return_value="token"), \
             patch.object(seguridad.db, "consultar_uno", return_value=usuario), \
             patch.object(seguridad.db, "ejecutar") as ejecutar:
            from contextlib import ExitStack
            with ExitStack() as stack:
                try:
                    from app import identidad
                    stack.enter_context(patch.object(identidad, "validar_sesion", return_value=True))
                except ImportError:
                    pass
                assert seguridad.usuario_actual(request) == usuario
            ejecutar.assert_not_called()
    request = Request({"type": "http", "path": "/sesion/actividad", "headers": []})
    antes = datetime.datetime.now(datetime.timezone.utc)
    with patch.object(seguridad, "_leer_token", return_value="token"), \
         patch.object(seguridad.db, "ejecutar") as ejecutar:
        seguridad.renovar_actividad(request, 15)
    sql, parametros = ejecutar.call_args.args
    assert "expira_en > now()" in sql
    assert 584 <= (parametros[0] - antes).total_seconds() <= 586
    print("Sesión 10 minutos: refrescos sin renovación y vencimiento protegido.")

if __name__ == "__main__":
    main()
