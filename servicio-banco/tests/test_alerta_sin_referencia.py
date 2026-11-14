# -*- coding: utf-8 -*-
"""Verifica que una carga válida sin referencia quede advertida."""
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as principal


def main():
    cliente = TestClient(principal.app, follow_redirects=False)
    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.importar, "importar_filas", return_value=(1, 0)), \
         patch.object(principal.alertas, "crear") as crear_alerta, \
         patch.object(principal.auditoria, "registrar"):
        respuesta = cliente.post(
            "/movimientos/importar",
            files={"archivo": ("sin-referencia.csv",
                                b"fecha;monto;referencia;descripcion\n"
                                b"2026-11-11;1000;;ABONO POS\n",
                                "text/csv")})
    assert respuesta.status_code == 303
    assert "Alerta%3A+1+sin+referencia" in respuesta.headers["location"]
    crear_alerta.assert_called_once()
    assert crear_alerta.call_args.args[0:3] == (
        "operativa", "media", "Movimientos sin referencia detectados")
    print("Carga sin referencia: alerta operativa creada en BANCO.")


if __name__ == "__main__":
    main()
