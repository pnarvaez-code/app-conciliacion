# -*- coding: utf-8 -*-
"""tests/test_arranque.py

Prueba de arranque del conciliador (no necesita base de datos): la app
importa, el ingreso se sirve y todo lo demas exige sesion; la API interna
rechaza peticiones sin token valido.
Se ejecuta con:  python -m tests.test_arranque
"""
from fastapi.testclient import TestClient
from unittest.mock import patch

import app.main as principal
from app.main import app


def main():
    cliente = TestClient(app, follow_redirects=False)

    respuesta = cliente.get("/login")
    assert respuesta.status_code == 200, respuesta.status_code
    assert "Correo" in respuesta.text and "Clave" in respuesta.text
    print("GET /login -> 200 con formulario de ingreso")

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

    for ruta in ("/recepciones", "/conciliacion", "/cadena", "/visor",
                 "/usuarios", "/alertas", "/auditoria", "/reporte"):
        assert cliente.get(ruta).status_code == 303, ruta
    print("Pantallas protegidas: todas redirigen al ingreso")

    respuesta = cliente.post(
        "/recepciones",
        data={"origen": "EMPRESA"},
        files={"archivo": ("ventas.csv", b"fecha;monto;referencia;descripcion\n",
                            "text/csv")},
    )
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"
    print("Recepcion de archivos: ruta protegida y multipart correcta")

    with patch.object(principal, "_exigir_usuario", return_value={"id": 1}), \
         patch.object(principal.recepciones, "recibir",
                      side_effect=ValueError("formato no soportado")), \
         patch.object(principal.alertas, "crear"), \
         patch.object(principal.auditoria, "registrar"):
        respuesta = cliente.post(
            "/recepciones", data={"origen": "EMPRESA"},
            files={"archivo": ("movimientos.txt", b"contenido", "text/plain")})
    assert respuesta.status_code == 303, respuesta.status_code
    assert "No+se+pudo+recibir+el+archivo" in respuesta.headers["location"]
    print("Carga de formato invalido -> aviso sin error interno")

    assert cliente.get("/interno/salud").status_code == 401
    assert cliente.get("/interno/salud",
                       headers={"X-Servicio-Token": "incorrecto"}).status_code == 401
    print("API interna: 401 sin token o con token incorrecto")

    print("Prueba de arranque: todas correctas.")


if __name__ == "__main__":
    main()
