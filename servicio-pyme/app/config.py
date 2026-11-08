# -*- coding: utf-8 -*-
"""app/config.py

Configuracion del servicio, tomada de variables de entorno (archivo .env
en desarrollo; variables del panel en el VPS con Coolify).

Todas las claves se leen al usarse, no al importar: asi el proyecto puede
importarse sin base ni entorno configurado (pruebas de arranque).
"""
import os
import re

NOMBRE_SERVICIO = "PYME"
ETIQUETA_SERVICIO = "PYME"          # como figura en los bloques de la cadena


def base_datos():
    """Cadena de conexion a PostgreSQL (base propia de este servicio)."""
    url = _obligatoria("DATABASE_URL")
    return ("postgresql://" + url[len("postgres://"):]
            if url.startswith("postgres://") else url)


def esquema():
    """Esquema PostgreSQL aislado para este servicio."""
    valor = os.environ.get("DB_SCHEMA", "public").strip() or "public"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", valor):
        raise RuntimeError("DB_SCHEMA contiene un nombre invalido")
    return valor


def clave_sesion():
    """Clave para firmar la cookie de sesion."""
    return _obligatoria("CLAVE_SESION")


def token_servicio():
    """Token compartido para las llamadas internas entre servicios."""
    return _obligatoria("TOKEN_SERVICIO")


def admin_inicial():
    """Correo y clave del primer usuario, usados solo al inicializar."""
    return _obligatoria("ADMIN_EMAIL"), _obligatoria("ADMIN_CLAVE")


def token_servicio_configurado():
    """Token interno configurado, o vacio si no hay (API interna cerrada)."""
    return os.environ.get("TOKEN_SERVICIO", "").strip()


def url_banco():
    """URL del servicio del banco (para propagar bloques). Vacio = no hay."""
    return os.environ.get("URL_BANCO", "").rstrip("/")


def url_conciliador():
    """URL del servicio conciliador. Vacio = no hay (modo aislado)."""
    return os.environ.get("URL_CONCILIADOR", "").rstrip("/")


def pares():
    """Destino de propagacion: el conciliador recibe la cadena de la PYME."""
    url = url_conciliador()
    return [("conciliador", url)] if url else []


def dir_datos():
    """Carpeta del volumen donde se guardan los archivos."""
    return os.environ.get("DIR_DATOS", os.path.join(os.getcwd(), "datos"))


def puerto():
    return int(os.environ.get("PORT", "8001"))


def _obligatoria(nombre):
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError("Falta la variable de entorno %s" % nombre)
    return valor
