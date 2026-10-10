# -*- coding: utf-8 -*-
"""app/nucleo/conciliacion.py

Motor de conciliacion (funciones puras, sin base de datos).

Cruza los movimientos de la empresa con los del banco en tres niveles:

  Nivel 1: la referencia (comprobante) coincide en ambos lados.
  Nivel 2: mismo monto y fechas a no mas de 3 dias.
  Nivel 3: la descripcion comparte palabras y el monto difiere menos del 5 %.

Lo que no cruza no se fuerza: se clasifica por tipo de diferencia, que es
lo que el informe del auditor muestra:

  en_empresa_no_banco: la empresa vendio y el banco no acredito.
  en_banco_no_empresa: el banco registro algo que la empresa no tiene.
  monto_distinto:      existe contrapartida parecida pero el monto difiere.
  fuera_de_ventana:    mismo monto con fechas demasiado lejanas.
  referencia_distinta: misma referencia con datos que no cuadran.

Cada movimiento se cruza como maximo una vez, con el primer candidato y en
el mejor nivel posible: el sistema nunca inventa coincidencias.
"""
from datetime import date

NIVELES = {1: "Referencia exacta", 2: "Monto y fecha cercana",
           3: "Descripcion y monto aproximado"}

TIPOS_DIFERENCIA = {
    "en_empresa_no_banco": "En la empresa, no en el banco",
    "en_banco_no_empresa": "En el banco, no en la empresa",
    "monto_distinto": "Monto distinto",
    "fuera_de_ventana": "Fuera de la ventana de fechas",
    "referencia_distinta": "Referencia con datos que no cuadran",
}


def _dias(a, b):
    return abs((date(*[int(x) for x in a.split("-")]) -
                date(*[int(x) for x in b.split("-")])).days)


def _tokens(texto):
    return set((texto or "").upper().split())


def _nivel3(empresa, banco):
    if not empresa["descripcion"] or not banco["descripcion"]:
        return False
    if not (_tokens(empresa["descripcion"]) & _tokens(banco["descripcion"])):
        return False
    return abs(empresa["monto"] - banco["monto"]) <= empresa["monto"] * 0.05


def conciliar(empresa, banco):
    """Devuelve (pares, pendientes_empresa, pendientes_banco)."""
    usados = set()
    pares = []
    con_par = [False] * len(empresa)
    for i, movimiento_empresa in enumerate(empresa):
        for j, movimiento_banco in enumerate(banco):
            if j in usados:
                continue
            if (movimiento_empresa["referencia"] and
                    movimiento_empresa["referencia"].upper() ==
                    movimiento_banco["referencia"].upper()):
                pares.append((movimiento_empresa, movimiento_banco, 1))
                usados.add(j); con_par[i] = True
                break
        else:
            for j, movimiento_banco in enumerate(banco):
                if j in usados:
                    continue
                if (movimiento_empresa["monto"] == movimiento_banco["monto"] and
                        _dias(movimiento_empresa["fecha"], movimiento_banco["fecha"]) <= 3):
                    pares.append((movimiento_empresa, movimiento_banco, 2))
                    usados.add(j); con_par[i] = True
                    break
            else:
                for j, movimiento_banco in enumerate(banco):
                    if j in usados:
                        continue
                    if _nivel3(movimiento_empresa, movimiento_banco):
                        pares.append((movimiento_empresa, movimiento_banco, 3))
                        usados.add(j); con_par[i] = True
                        break
    pendientes_empresa = [m for i, m in enumerate(empresa) if not con_par[i]]
    pendientes_banco = [m for j, m in enumerate(banco) if j not in usados]
    return pares, pendientes_empresa, pendientes_banco


def formatear_monto(monto):
    return "{:,}".format(monto).replace(",", ".")


def clasificar_pendiente(movimiento, otros):
    """Devuelve (tipo_diferencia, motivo) para un movimiento sin contrapartida.

    Recorre las contrapartidas posibles y describe el caso mas cercano a un
    cruce; si no hay nada parecido, la diferencia es de existencia (esta en
    un lado y no en el otro).
    """
    if not otros:
        return "en_banco_no_empresa", "no se recibieron movimientos del otro lado"

    mismo_monto_lejano = None
    mismo_dia = None
    descripcion_cercana = None
    for otro in otros:
        igual = movimiento["monto"] == otro["monto"]
        dias = _dias(movimiento["fecha"], otro["fecha"])
        diferencia = abs(movimiento["monto"] - otro["monto"])
        comunes = _tokens(movimiento["descripcion"]) & _tokens(otro["descripcion"])
        dentro_pct = diferencia <= movimiento["monto"] * 0.05
        if igual and dias <= 3:
            return ("referencia_distinta",
                    "hay una contrapartida con el mismo monto y fecha cercana "
                    "(%s el %s) pero no se cruzo" % (formatear_monto(otro["monto"]),
                                                     otro["fecha"]))
        if igual and (mismo_monto_lejano is None or dias < mismo_monto_lejano[0]):
            mismo_monto_lejano = (dias, otro)
            continue
        if dias == 0 and (mismo_dia is None or diferencia < mismo_dia[0]):
            mismo_dia = (diferencia, otro)
            continue
        if comunes and not dentro_pct and (
                descripcion_cercana is None or diferencia < descripcion_cercana[0]):
            descripcion_cercana = (diferencia, otro)

    if mismo_monto_lejano:
        dias, otro = mismo_monto_lejano
        return ("fuera_de_ventana",
                "existe una operacion con el mismo monto (%s) pero su fecha esta "
                "a %d dias (maximo permitido: 3)"
                % (formatear_monto(movimiento["monto"]), dias))
    if descripcion_cercana or mismo_dia:
        _, otro = descripcion_cercana or mismo_dia
        return ("monto_distinto",
                "existe una operacion parecida pero el monto difiere (%s vs %s)"
                % (formatear_monto(movimiento["monto"]), formatear_monto(otro["monto"])))
    return (None, "no se encontro contrapartida parecida en el otro lado")
