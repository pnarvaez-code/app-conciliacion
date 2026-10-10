# -*- coding: utf-8 -*-
"""tests/test_arranque.py

Prueba de arranque del conciliador (no necesita base de datos): la app
importa, el ingreso se sirve y todo lo demas exige sesion; la API interna
rechaza peticiones sin token valido.
Se ejecuta con:  python -m tests.test_arranque
"""
from fastapi.testclient import TestClient

from app.main import app


def main():
    cliente = TestClient(app, follow_redirects=False)

    respuesta = cliente.get("/login")
    assert respuesta.status_code == 200, respuesta.status_code
    assert "Correo" in respuesta.text and "Clave" in respuesta.text
    print("GET /login -> 200 con formulario de ingreso")

    respuesta = cliente.get("/")
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == "/login"
    print("GET / sin sesion -> 303 a /login")

    for ruta in ("/recepciones", "/conciliacion", "/cadena", "/visor",
                 "/usuarios", "/alertas", "/auditoria"):
        assert cliente.get(ruta).status_code == 303, ruta
    print("Pantallas protegidas: todas redirigen al ingreso")

    assert cliente.get("/interno/salud").status_code == 401
    assert cliente.get("/interno/salud",
                       headers={"X-Servicio-Token": "incorrecto"}).status_code == 401
    print("API interna: 401 sin token o con token incorrecto")

    print("Prueba de arranque: todas correctas.")


if __name__ == "__main__":
    main()
