# -*- coding: utf-8 -*-
"""app/inicio.py

Arranque del servicio: deja todo listo antes de levantar la aplicacion.

Pasos:
  1. crea la carpeta del volumen de archivos si no existe,
  2. aplica la migracion inicial (solo si la base esta vacia),
  3. crea el primer usuario (administrador) desde las variables de
     entorno (ADMIN_EMAIL y ADMIN_CLAVE), solo la primera vez,
  4. reintenta la propagacion de bloques que hayan quedado pendientes.

Se ejecuta con:  python -m app.inicio
"""
from app import cadena, db, config


def main():
    import os
    os.makedirs(os.path.join(config.dir_datos(), "archivos"), exist_ok=True)
    print("Volumen de archivos listo en %s" % config.dir_datos())

    if db.aplicar_migracion():
        print("Migracion inicial aplicada.")
    else:
        print("La base ya tenia el esquema; no se aplica migracion.")

    if db.asegurar_admin():
        print("Usuario administrador creado desde ADMIN_EMAIL.")
    else:
        print("Usuarios existentes; no se crea administrador.")

    cadena.reintentar_envios()
    print("Arranque completo.")


if __name__ == "__main__":
    main()
