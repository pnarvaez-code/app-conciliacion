# -*- coding: utf-8 -*-
"""app/config.py

Configuracion del servicio conciliador, tomada de variables de entorno.

Todas las claves se leen al usarse, no al importar: el proyecto puede
importarse sin base ni entorno configurado (pruebas de arranque).
"""
import os

NOMBRE_SERVICIO = "CONCILIADOR"
ETIQUETA_SERVICIO = "CONCILIADOR"

# Etiqueta de la cadena que corresponde a cada parte: los bloques los firma el
# servicio que los emite (PYME o BANCO), mientras que en las pantallas del
# conciliador las partes son EMPRESA y BANCO.
ETIQUETAS_POR_ORIGEN = {"EMPRESA": "PYME", "BANCO": "BANCO"}


def etiqueta_de_origen(origen):
    """Etiqueta de la cadena que corresponde a una parte (EMPRESA o BANCO)."""
    nombre = (origen or "").strip().upper()
    return ETIQUETAS_POR_ORIGEN.get(nombre, nombre)


def base_datos():
    """Cadena de conexion a PostgreSQL (base propia del conciliador)."""
    return _obligatoria("DATABASE_URL")


def clave_sesion():
    return _obligatoria("CLAVE_SESION")


def token_servicio():
    """Token compartido para las llamadas internas entre servicios."""
    return _obligatoria("TOKEN_SERVICIO")


def token_servicio_configurado():
    """Token interno configurado, o vacio si no hay (API interna cerrada)."""
    return os.environ.get("TOKEN_SERVICIO", "").strip()


def admin_inicial():
    return _obligatoria("ADMIN_EMAIL"), _obligatoria("ADMIN_CLAVE")


def url_pyme():
    """URL del servicio de la PYME (para sincronizar su cadena)."""
    return os.environ.get("URL_PYME", "").rstrip("/")


def url_banco():
    """URL del servicio del banco (para sincronizar su cadena)."""
    return os.environ.get("URL_BANCO", "").rstrip("/")


def pares():
    """Servicios desde los cuales sincronizar la cadena."""
    return [(nombre, url) for nombre, url in
            (("pyme", url_pyme()), ("banco", url_banco())) if url]


def dir_datos():
    """Carpeta del volumen: archivos recibidos de ambas partes."""
    return os.environ.get("DIR_DATOS", os.path.join(os.getcwd(), "datos"))


def puerto():
    return int(os.environ.get("PORT", "8000"))


def _obligatoria(nombre):
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError("Falta la variable de entorno %s" % nombre)
    return valor
