# -*- coding: utf-8 -*-
"""nucleo/sellos.py

Núcleo de la cadena de sellos (SHA-256), comun a los tres servicios.

Solo usa `hashlib` y `json` de la biblioteca estandar: no hay dependencias
externas ni cifrado de contenido. Los calculos son:

  * huella_movimiento: SHA-256 de la forma canonica del movimiento
    (fecha | monto | referencia en mayusculas | descripcion),
  * huella_raiz: SHA-256 de la concatenacion de las huellas del lote,
  * huella_archivo: SHA-256 del contenido exacto del archivo,
  * huella_bloque: SHA-256 de los campos sellados, ordenados por clave,
  * encadenamiento: cada bloque referencia `hash_anterior` = huella del
    bloque previo; el primer bloque usa 64 ceros.

La verificacion reproduce los calculos y compara: cadena, archivo y datos.
"""
import hashlib
import json


def huella(texto):
    """SHA-256 en hexadecimal (64 caracteres)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def huella_movimiento(movimiento):
    """Huella de un movimiento en su forma canonica."""
    linea = "|".join([
        str(movimiento["fecha"]),
        str(int(movimiento["monto"])),
        (movimiento.get("referencia") or "").strip().upper(),
        (movimiento.get("descripcion") or "").strip(),
    ])
    return huella(linea)


def huella_raiz(movimientos):
    """Huella del lote: concatenacion de las huellas, en orden."""
    return huella("".join(huella_movimiento(m) for m in movimientos))


def huella_archivo(contenido):
    """Huella del archivo; el contenido se lee sin modificarlo."""
    if isinstance(contenido, bytes):
        return hashlib.sha256(contenido).hexdigest()
    return huella(contenido)


CAMPOS_SELLADOS = ("indice", "origen", "lote_codigo", "archivo", "n_movimientos",
                   "hashes_movimientos", "hash_raiz", "hash_archivo",
                   "hash_anterior", "emitido_por", "sellado_en")

# Campos que viajan al propagar el bloque: los sellados mas la huella misma.
CAMPOS_BLOQUE = CAMPOS_SELLADOS + ("hash_bloque",)


def huella_bloque(bloque):
    """Huella del bloque: sus campos sellados, en JSON ordenado por clave.

    Se toman unicamente los campos de CAMPOS_SELLADOS. La fila guardada en la
    base trae ademas su id y otras columnas de control, que no son parte del
    sello y no deben entrar en el calculo.
    """
    contenido = {campo: bloque[campo] for campo in CAMPOS_SELLADOS}
    return huella(json.dumps(contenido, sort_keys=True))


def construir_bloque(indice, origen, lote_codigo, archivo, movimientos,
                     hash_archivo, hash_anterior, emitido_por, sellado_en):
    """Arma el bloque completo con su huella (sin tocar la base todavia)."""
    bloque = {
        "indice": indice,
        "origen": origen,
        "lote_codigo": lote_codigo,
        "archivo": archivo,
        "n_movimientos": len(movimientos),
        "hashes_movimientos": [huella_movimiento(m) for m in movimientos],
        "hash_raiz": huella_raiz(movimientos),
        "hash_archivo": hash_archivo,
        "hash_anterior": hash_anterior or ("0" * 64),
        "emitido_por": emitido_por,
        "sellado_en": sellado_en,
    }
    bloque["hash_bloque"] = huella_bloque(bloque)
    return bloque


def verificar_cadena(bloques):
    """Chequeo (a): cada bloque cuadra y encadena con el anterior."""
    problemas = []
    anterior = "0" * 64
    for bloque in sorted(bloques, key=lambda b: b["indice"]):
        if huella_bloque(bloque) != bloque["hash_bloque"]:
            problemas.append("bloque %s: contenido alterado" % bloque["indice"])
        if bloque["hash_anterior"] != anterior:
            problemas.append("bloque %s: rompe el encadenamiento" % bloque["indice"])
        anterior = bloque["hash_bloque"]
    return problemas


def verificar_archivo(bloque, contenido_actual):
    """Chequeo (b): el archivo actual conserva la huella de su emision."""
    if huella_archivo(contenido_actual) == bloque["hash_archivo"]:
        return None
    return ("el archivo %s fue modificado despues de su emision"
            % bloque["archivo"])


def verificar_movimientos(bloque, movimientos_actuales):
    """Chequeo (c): los movimientos actuales coinciden con el sello.

    Compara posicion por posicion para poder señalar el movimiento exacto.
    """
    actuales = [huella_movimiento(m) for m in movimientos_actuales]
    problemas = []
    if len(actuales) != len(bloque["hashes_movimientos"]):
        problemas.append("cantidad distinta: el sello esperaba %d y hay %d"
                         % (len(bloque["hashes_movimientos"]), len(actuales)))
    for posicion, (actual, esperado) in enumerate(
            zip(actuales, bloque["hashes_movimientos"]), start=1):
        if actual != esperado:
            problemas.append("movimiento #%d: su huella difiere del sello" % posicion)
    return problemas
