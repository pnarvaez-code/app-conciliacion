# -*- coding: utf-8 -*-
"""app/inicio.py

Arranque del conciliador: carpeta del volumen, migracion y administrador,
sin llamadas de red a los otros dos servicios.

Se ejecuta con:  python -m app.inicio
"""
import os

from app import config, db


def main():
    os.makedirs(os.path.join(config.dir_datos(), "archivos"), exist_ok=True)
    print("Volumen de archivos listo en %s" % config.dir_datos())

    if db.aplicar_migracion():
        print("Migracion inicial aplicada.")
    else:
        print("La base ya tenia el esquema; no se aplica migracion.")
    db.asegurar_esquema()
    db.asegurar_respaldo_archivos()

    if db.asegurar_admin():
        print("Usuario administrador creado desde ADMIN_EMAIL.")
    else:
        print("Usuarios existentes; no se crea administrador.")

    print("Arranque completo.")


if __name__ == "__main__":
    main()
