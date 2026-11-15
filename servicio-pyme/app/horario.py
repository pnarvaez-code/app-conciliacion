"""Presentación de fecha y hora de Paraguay sin alterar sellos ni fechas contables."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from importlib.resources import files

# Usar tzdata actualizado incluso si el sistema operativo conserva reglas viejas.
with files("tzdata.zoneinfo").joinpath("America", "Asuncion").open("rb") as archivo:
    ZONA_PARAGUAY = ZoneInfo.from_file(archivo, key="America/Asuncion")

def ahora():
    return datetime.now(ZONA_PARAGUAY)

def hoy():
    return ahora().date()

def presentar(valor):
    if isinstance(valor, datetime):
        # Los timestamps históricos sin zona se interpretan como UTC.
        instante = valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)
        local = instante.astimezone(ZONA_PARAGUAY)
        desplazamiento = local.strftime("%z")
        return local.strftime("%d/%m/%Y %H:%M:%S") + " GMT" + desplazamiento[:3] + ":" + desplazamiento[3:]
    return valor
