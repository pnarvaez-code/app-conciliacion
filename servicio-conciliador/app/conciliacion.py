# -*- coding: utf-8 -*-
"""app/conciliacion.py

Ejecucion de la conciliacion con los archivos recibidos.

Toma la ultima recepcion INTACTA de cada parte (la verificacion previa es
la que garantiza que los datos no fueron alterados despues de su
emision), corre el motor de tres niveles y guarda:

  * la conciliacion (totales y porcentaje),
  * los pares cruzados, con la fotografia de ambos movimientos,
  * los pendientes clasificados por tipo de diferencia (los escenarios
    que pide el tribunal): en la empresa y no en el banco, en el banco y
    no en la empresa, monto distinto, fuera de ventana, referencia que no
    cuadra.

Los pendientes tambien generan alerta, para que el auditor los vea.
"""
import json

from app import alertas, auditoria, carga, db, recepciones
from app.nucleo import conciliacion as motor


def ejecutar(usuario_id, ip=None):
    """Concilia las ultimas recepciones intactas. Devuelve la fila creada."""
    empresa = recepciones.ultima_intacta("EMPRESA")
    banco = recepciones.ultima_intacta("BANCO")
    if not empresa or not banco:
        falta = "la empresa" if not empresa else "el banco"
        raise ValueError("Falta un archivo recibido e intacto de %s "
                         "(suba el archivo en Recepciones)." % falta)

    movimientos_empresa, _ = carga.leer(empresa["archivo"],
                                        _contenido(empresa["ruta"]))
    movimientos_banco, _ = carga.leer(banco["archivo"], _contenido(banco["ruta"]))

    pares, pendientes_empresa, pendientes_banco = motor.conciliar(
        movimientos_empresa, movimientos_banco)
    total_empresa, total_banco = len(movimientos_empresa), len(movimientos_banco)

    fila = db.ejecutar(
        "INSERT INTO conciliaciones (desde, hasta, total_empresa, total_banco,"
        " conciliados, porcentaje, ejecutada_por)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (_fecha_min(movimientos_empresa + movimientos_banco),
         _fecha_max(movimientos_empresa + movimientos_banco),
         total_empresa, total_banco, len(pares),
         round(100.0 * len(pares) / total_empresa) if total_empresa else 0,
         usuario_id))
    conciliacion_id = fila["id"]

    for movimiento_empresa, movimiento_banco, nivel in pares:
        db.ejecutar(
            "INSERT INTO conciliacion_pares (conciliacion_id, nivel,"
            " movimiento_empresa, movimiento_banco) VALUES (%s, %s, %s::jsonb, %s::jsonb)",
            (conciliacion_id, nivel, _json(movimiento_empresa),
             _json(movimiento_banco)))

    resumen_diferencias = {}
    for movimiento in pendientes_empresa:
        tipo, motivo = motor.clasificar_pendiente(movimiento, movimientos_banco)
        tipo = tipo or "en_empresa_no_banco"
        _guardar_pendiente(conciliacion_id, "EMPRESA", tipo, movimiento, motivo)
        resumen_diferencias[tipo] = resumen_diferencias.get(tipo, 0) + 1
    for movimiento in pendientes_banco:
        tipo, motivo = motor.clasificar_pendiente(movimiento, movimientos_empresa)
        tipo = tipo or "en_banco_no_empresa"
        _guardar_pendiente(conciliacion_id, "BANCO", tipo, movimiento, motivo)
        resumen_diferencias[tipo] = resumen_diferencias.get(tipo, 0) + 1

    if resumen_diferencias:
        detalle = "; ".join("%s: %d" % (motor.TIPOS_DIFERENCIA.get(tipo, tipo), n)
                            for tipo, n in sorted(resumen_diferencias.items()))
        alertas.crear("diferencia", "alta" if "monto_distinto" in resumen_diferencias
                      else "media",
                      "La conciliacion encontro %d diferencias"
                      % sum(resumen_diferencias.values()),
                      detalle, referencia="conciliacion %d" % conciliacion_id,
                      usuario_id=usuario_id)

    auditoria.registrar(usuario_id, "conciliacion", "conciliaciones",
                        conciliacion_id,
                        {"conciliados": len(pares), "total_empresa": total_empresa,
                         "total_banco": total_banco,
                         "pendientes": len(pendientes_empresa) + len(pendientes_banco),
                         "detalle": resumen_diferencias}, ip)
    return fila


def listar(limite=50):
    return db.consultar(
        "SELECT c.*, u.email AS ejecutada_por_email FROM conciliaciones c "
        "LEFT JOIN usuarios u ON u.id = c.ejecutada_por "
        "ORDER BY c.id DESC LIMIT %s", (limite,))


def detalle(conciliacion_id):
    """Pares, pendientes y totales de una conciliacion."""
    pares = db.consultar(
        "SELECT * FROM conciliacion_pares WHERE conciliacion_id = %s"
        " ORDER BY nivel, id", (conciliacion_id,))
    pendientes = db.consultar(
        "SELECT * FROM conciliacion_pendientes WHERE conciliacion_id = %s"
        " ORDER BY tipo_diferencia, id", (conciliacion_id,))
    por_tipo = {}
    for pendiente in pendientes:
        por_tipo[pendiente["tipo_diferencia"]] = \
            por_tipo.get(pendiente["tipo_diferencia"], 0) + 1
    return pares, pendientes, por_tipo


def _guardar_pendiente(conciliacion_id, origen, tipo, movimiento, motivo):
    db.ejecutar(
        "INSERT INTO conciliacion_pendientes (conciliacion_id, origen,"
        " tipo_diferencia, movimiento, motivo) VALUES (%s, %s, %s, %s::jsonb, %s)",
        (conciliacion_id, origen, tipo, _json(movimiento), motivo))


def _contenido(ruta):
    with open(ruta, "rb") as archivo:
        return archivo.read().decode("utf-8", errors="replace")


def _fecha_min(movimientos):
    fechas = [m["fecha"] for m in movimientos if m.get("fecha")]
    return min(fechas) if fechas else None


def _fecha_max(movimientos):
    fechas = [m["fecha"] for m in movimientos if m.get("fecha")]
    return max(fechas) if fechas else None


def _json(dato):
    return json.dumps(dato, ensure_ascii=False)
