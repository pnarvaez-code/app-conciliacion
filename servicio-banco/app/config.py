# -*- coding: utf-8 -*-
"""app/config.py

Configuracion del servicio, tomada de variables de entorno (archivo .env
en desarrollo; variables del panel en el VPS con Coolify).

Todas las claves se leen al usarse, no al importar: asi el proyecto puede
importarse sin base ni entorno configurado (pruebas de arranque).
"""
import os

NOMBRE_SERVICIO = "BANCO"
ETIQUETA_SERVICIO = "BANCO"         # como figura en los bloques de la cadena


def base_datos():
    """Cadena de conexion a PostgreSQL (base propia de este servicio)."""
    return _obligatoria("DATABASE_URL")


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


def url_pyme():
    """URL del servicio de la PYME (para propagar bloques). Vacio = no hay."""
    return os.environ.get("URL_PYME", "").rstrip("/")


def url_conciliador():
    """URL del servicio conciliador. Vacio = no hay (modo aislado)."""
    return os.environ.get("URL_CONCILIADOR", "").rstrip("/")


def pares():
    """Destinos de propagacion: nombre interno y URL."""
    return [(nombre, url) for nombre, url in
            (("pyme", url_pyme()), ("conciliador", url_conciliador())) if url]


def dir_datos():
    """Carpeta del volumen donde se guardan los archivos."""
    return os.environ.get("DIR_DATOS", os.path.join(os.getcwd(), "datos"))


def puerto():
    return int(os.environ.get("PORT", "8002"))


def _obligatoria(nombre):
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError("Falta la variable de entorno %s" % nombre)
    return valor
