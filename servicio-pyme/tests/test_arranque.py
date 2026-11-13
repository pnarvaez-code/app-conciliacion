# -*- coding: utf-8 -*-
"""tests/test_arranque.py

Prueba de arranque de la aplicacion (no necesita base de datos).

Verifica que la app importe, que el ingreso se sirva y que todo lo demas
exija sesion, y que la API interna rechace peticiones sin token valido.
Se ejecuta con:  python -m tests.test_arranque
"""
from fastapi.testclient import TestClient
from unittest.mock import patch
import psycopg

import app.main as principal
from app.main import app


def main():
    cliente = TestClient(app, follow_redirects=False)

    respuesta = cliente.get("/login")
    assert respuesta.status_code == 200, respuesta.status_code
    assert "Correo" in respuesta.text and "Clave" in respuesta.text
    print("GET /login -> 200 con formulario de ingreso")

    # Una contraseña incorrecta debe volver al formulario; nunca producir 500.
    with patch.object(principal.db, "consultar_uno", return_value=None), \
         patch.object(principal.auditoria, "registrar"):
        respuesta = cliente.post("/login", data={"email": "invalido@ejemplo.com",
                                                  "clave": "incorrecta"})
    assert respuesta.status_code == 401, respuesta.status_code
    assert "Correo o clave incorrectos" in respuesta.text
    print("POST /login invalido -> 401 con mensaje de ingreso")

    respuesta = cliente.get("/")
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"
    print("GET / sin sesion -> 303 a /login")

    for ruta in ("/lotes", "/usuarios", "/alertas", "/auditoria", "/reporte"):
        assert cliente.get(ruta).status_code == 303, ruta
    print("Pantallas protegidas: todas redirigen al ingreso")

    # Un archivo con extensión no permitida se informa al usuario sin excepción.
    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.importar, "importar_filas") as importar_filas:
        respuesta = cliente.post(
            "/movimientos/importar",
            files={"archivo": ("movimientos.txt", b"contenido", "text/plain")})
    assert respuesta.status_code == 303, respuesta.status_code
    assert "formato+no+soportado" in respuesta.headers["location"]
    assert not importar_filas.called
    print("Carga de formato invalido -> aviso sin error interno")

    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.importar, "importar_filas",
                      side_effect=psycopg.OperationalError("base no disponible")):
        respuesta = cliente.post(
            "/movimientos/importar",
            files={"archivo": ("ventas.csv",
                                b"fecha;monto;referencia;descripcion\n2026-11-11;1000;FV-1;VENTA\n",
                                "text/csv")})
    assert respuesta.status_code == 303, respuesta.status_code
    assert "No+se+pudieron+guardar+los+movimientos" in respuesta.headers["location"]
    print("Error de base durante importacion -> aviso sin error interno")

    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.importar, "importar_filas", return_value=(1, 0)):
        respuesta = cliente.post(
            "/movimientos/importar",
            files={"archivo": ("ventas.csv",
                                b"fecha;monto;referencia;descripcion\n2026-11-11;1000;FV-2;VENTA\n",
                                "text/csv")})
    assert respuesta.status_code == 303, respuesta.status_code
    assert "Importados+1+movimientos" in respuesta.headers["location"]
    print("Importacion valida -> movimiento registrado")

    # Una referencia manual repetida debe producir un aviso, no un error 500.
    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.movimientos, "alta",
                      side_effect=psycopg.errors.UniqueViolation()):
        respuesta = cliente.post(
            "/movimientos", data={"fecha": "2026-11-11", "monto": "1000",
                                  "referencia": "FV-1", "descripcion": "VENTA"})
    assert respuesta.status_code == 303
    assert "referencia+ya+esta+registrada" in respuesta.headers["location"]
    print("Referencia repetida -> aviso controlado")

    # El usuario de la sesión no puede dejarse sin acceso a sí mismo.
    with patch.object(principal, "_exigir_usuario", return_value={"id": 7}), \
         patch.object(principal.db, "ejecutar") as ejecutar:
        respuesta = cliente.post("/usuarios/7/estado", data={"activo": "0"})
    assert respuesta.status_code == 303
    assert "No+puede+desactivar" in respuesta.headers["location"]
    ejecutar.assert_not_called()
    print("Autodesactivacion de usuario -> rechazada")

    # La descarga debe usar el respaldo de PostgreSQL si el volumen se perdió.
    lote_resguardado = {"codigo": "V-2026-11-11-01", "nombre": "ventas.csv",
                        "ruta": "", "contenido": b"fecha;monto;referencia;descripcion\n"}
    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.db, "consultar_uno", return_value=lote_resguardado), \
         patch.object(principal.auditoria, "registrar"):
        respuesta = cliente.get("/lotes/1/descargar")
    assert respuesta.status_code == 200, respuesta.status_code
    assert respuesta.content == lote_resguardado["contenido"]
    print("Descarga desde respaldo -> correcta")

    assert cliente.get("/interno/salud").status_code == 401
    assert cliente.get("/interno/salud",
                       headers={"X-Servicio-Token": "incorrecto"}).status_code == 401
    print("API interna: 401 sin token o con token incorrecto")

    print("Prueba de arranque: todas correctas.")


if __name__ == "__main__":
    main()
