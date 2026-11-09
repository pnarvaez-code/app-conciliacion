# -*- coding: utf-8 -*-
"""app/main.py

Aplicacion del servicio CONCILIADOR (FastAPI): la herramienta del auditor.

Pantallas (todas requieren sesion, salvo el ingreso):
  /                 Panel: estado general y accesos
  /recepciones      Subir los archivos de la empresa y del banco, verificar sellos
  /conciliacion     Ejecutar la conciliacion y ver el informe con las diferencias
  /cadena           Copia local de la cadena y sincronizacion con los pares
  /visor            Panel en vivo (se actualiza solo)
  /usuarios         Administracion de usuarios (un solo rol)
  /alertas          Alertas de integridad y de diferencias
  /auditoria        Registro de acciones con su responsable

API interna para los otros servicios: ver app/internos.py.
"""
import asyncio
import logging
import os
from pathlib import Path
import hashlib

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import (alertas, auditoria, cadena, conciliacion, config, db, internos,
                 recepciones, reporte, reset)

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Servicio CONCILIADOR - herramienta del auditor")
app.mount("/estaticos", StaticFiles(directory=str(BASE / "estaticos")),
          name="estaticos")
plantillas = Jinja2Templates(directory=str(BASE / "plantillas"))
app.include_router(internos.router)

from app import seguridad  # se importa despues para evitar ciclos en pruebas

_tarea_sincronizacion = None
_log = logging.getLogger(__name__)


async def _sincronizar_periodicamente():
    while True:
        await asyncio.sleep(30)
        try:
            await asyncio.to_thread(cadena.sincronizar_con_pares)
        except Exception:
            _log.exception("Error en la sincronizacion periodica de la cadena")


@app.on_event("startup")
async def iniciar_sincronizacion_periodica():
    global _tarea_sincronizacion
    _tarea_sincronizacion = asyncio.create_task(_sincronizar_periodicamente())


@app.on_event("shutdown")
async def detener_sincronizacion_periodica():
    if _tarea_sincronizacion:
        _tarea_sincronizacion.cancel()
        await asyncio.gather(_tarea_sincronizacion, return_exceptions=True)


def _contexto(request, usuario, **extra):
    datos = {"request": request, "usuario": usuario,
             "servicio": config.NOMBRE_SERVICIO,
             "alertas_nuevas": alertas.contar_nuevas()}
    datos.update(extra)
    return datos


class _IngresoRequerido(Exception):
    """Se lanza cuando no hay sesion; la maneja el manejador de abajo."""


def _exigir_usuario(request):
    usuario = seguridad.usuario_actual(request)
    if not usuario:
        raise _IngresoRequerido()
    return usuario


@app.exception_handler(_IngresoRequerido)
def _redirigir_ingreso(request, _excepcion):
    return RedirectResponse("/login", status_code=303)


# --------------------------------------------------------------- ingreso

@app.get("/login", response_class=HTMLResponse)
def mostrar_login(request: Request):
    return plantillas.TemplateResponse(request, "login.html",
                                       {"error": None,
                                        "servicio": config.NOMBRE_SERVICIO})


@app.post("/login")
def ingresar(request: Request, email: str = Form(...), clave: str = Form(...)):
    usuario = db.consultar_uno(
        "SELECT * FROM usuarios WHERE email = %s AND activo",
        (email.strip().lower(),))
    if not usuario or not seguridad.verificar_clave(clave, usuario["clave_hash"]):
        auditoria.registrar(None, "ingreso_fallido", "usuarios", None,
                            {"email": email}, seguridad.ip_de(request))
        return plantillas.TemplateResponse(
            request, "login.html",
            {"error": "Correo o clave incorrectos.",
             "servicio": config.NOMBRE_SERVICIO}, status_code=401)
    valor = seguridad.iniciar_sesion(usuario["id"], seguridad.ip_de(request),
                                     request.headers.get("user-agent", ""))
    auditoria.registrar(usuario["id"], "ingreso", "usuarios", usuario["id"],
                        {}, seguridad.ip_de(request))
    respuesta = RedirectResponse("/", status_code=303)
    respuesta.set_cookie(seguridad.CLAVE_COOKIE, valor, httponly=True, secure=os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
                         samesite="lax", max_age=8 * 3600)
    return respuesta


@app.get("/salir")
def salir(request: Request):
    seguridad.cerrar_sesion(request.cookies.get(seguridad.CLAVE_COOKIE))
    respuesta = RedirectResponse("/login", status_code=303)
    respuesta.delete_cookie(seguridad.CLAVE_COOKIE)
    return respuesta


# ---------------------------------------------------------------- panel

@app.get("/", response_class=HTMLResponse)
def panel(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "panel.html", _contexto(
        request, usuario,
        problemas_cadena=cadena.verificar_cadena_local(),
        recepciones=recepciones.listar(limite=5),
        conciliaciones=conciliacion.listar(limite=5)))


# ----------------------------------------------------------- recepciones

@app.get("/recepciones", response_class=HTMLResponse)
def ver_recepciones(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "recepciones.html", _contexto(
        request, usuario, recepciones=recepciones.listar()))


@app.post("/recepciones")
async def subir_recepcion(request: Request, origen: str = Form(...),
                          archivo: UploadFile = File(...)):
    usuario = _exigir_usuario(request)
    contenido = await archivo.read()
    try:
        recepcion = recepciones.recibir(origen, archivo.filename, contenido,
                                        usuario["id"], seguridad.ip_de(request))
        aviso = "Recepcion %s: %s" % (recepcion["estado_integridad"],
                                      recepcion["detalle"] or "")
    except ValueError as error:
        nombre_archivo = (archivo.filename or "sin-nombre").replace("\\", "/").rsplit("/", 1)[-1]
        detalle = "Archivo %s rechazado: %s" % (nombre_archivo, error)
        alertas.crear(
            "integridad", "alta",
            "Archivo %s de %s rechazado por formato"
            % (nombre_archivo, origen.upper()),
            detalle, referencia=archivo.filename,
            usuario_id=usuario["id"])
        auditoria.registrar(
            usuario["id"], "recepcion_rechazada", "archivos", None,
            {"origen": origen.upper(), "archivo": nombre_archivo,
             "ruta_reportada": archivo.filename or "",
             "sha256": hashlib.sha256(contenido).hexdigest(),
             "bytes": len(contenido), "motivo": str(error)},
            seguridad.ip_de(request))
        aviso = "No se pudo recibir el archivo: %s" % error
    return RedirectResponse("/recepciones?aviso=%s" % aviso.replace(" ", "+"),
                            status_code=303)


@app.post("/recepciones/{recepcion_id}/eliminar")
def eliminar_recepcion(request: Request, recepcion_id: int):
    usuario = _exigir_usuario(request)
    try:
        recepcion = recepciones.eliminar(
            recepcion_id, usuario["id"], seguridad.ip_de(request))
        aviso = "Recepcion duplicada eliminada: %s" % recepcion["nombre"]
    except (ValueError, RuntimeError) as error:
        aviso = "No se pudo eliminar la recepcion: %s" % error
    return RedirectResponse("/recepciones?aviso=%s" % aviso.replace(" ", "+"),
                            status_code=303)


# ---------------------------------------------------------- conciliacion

@app.get("/conciliacion", response_class=HTMLResponse)
def ver_conciliacion(request: Request):
    usuario = _exigir_usuario(request)
    filtro = request.query_params.get("filtro", "todos")
    lista = conciliacion.listar(limite=20)
    pares = pendientes = por_tipo = None
    ultima = lista[0] if lista else None
    if ultima:
        pares, pendientes, por_tipo = conciliacion.detalle(ultima["id"])
    lotes = {}
    fuentes = {}
    for origen in ("EMPRESA", "BANCO"):
        recepcion = recepciones.ultima_intacta(origen)
        if recepcion:
            fuentes[origen] = {
                "archivo": recepcion["archivo"],
                "ruta": recepcion["ruta"],
                "lote_codigo": recepcion.get("lote_codigo"),
                "sha256": recepcion.get("sha256"),
            }
            sello = cadena.sello_de_lote(recepcion["lote_codigo"])
            if sello:
                lotes[origen] = sello
    recepciones_recientes = recepciones.listar(limite=20)
    rechazos = auditoria.listar_rechazos_carga(limite=20)
    if filtro == "errores":
        recepciones_recientes = [
            r for r in recepciones_recientes
            if r["estado_integridad"] != "intacto"]
    elif filtro == "intactos":
        recepciones_recientes = [
            r for r in recepciones_recientes
            if r["estado_integridad"] == "intacto"]
        rechazos = []
    elif filtro == "alterados":
        recepciones_recientes = [
            r for r in recepciones_recientes
            if r["estado_integridad"] == "alterado"]
        rechazos = []
    else:
        filtro = "todos"
    return plantillas.TemplateResponse(request, "conciliacion.html", _contexto(
        request, usuario, conciliaciones=lista, ultima=ultima, pares=pares,
        pendientes=pendientes, por_tipo=por_tipo,
        recepciones=recepciones_recientes[:8], rechazos=rechazos,
        lotes=lotes, fuentes=fuentes, filtro=filtro))


@app.post("/conciliacion")
def ejecutar_conciliacion(request: Request):
    usuario = _exigir_usuario(request)
    try:
        fila = conciliacion.ejecutar(usuario["id"], seguridad.ip_de(request))
        aviso = ("Conciliacion completada: %d de %d movimientos (%d %%)"
                 % (fila["conciliados"], fila["total_empresa"],
                    fila["porcentaje"]))
    except ValueError as error:
        aviso = str(error)
    return RedirectResponse("/conciliacion?aviso=%s" % aviso.replace(" ", "+"),
                            status_code=303)


# ---------------------------------------------------------------- cadena

@app.get("/cadena", response_class=HTMLResponse)
def ver_cadena(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "cadena.html", _contexto(
        request, usuario, bloques=cadena.bloques_completos(),
        problemas_cadena=cadena.verificar_cadena_local()))


@app.get("/conexion", response_class=HTMLResponse)
def ver_conexion(request: Request):
    usuario = _exigir_usuario(request)
    resultados = [{"servicio": config.NOMBRE_SERVICIO,
                   "estado": "conectado" if not cadena.verificar_cadena_local()
                   else "advertencia",
                   "detalle": "La copia local de la cadena está verificada."
                   if not cadena.verificar_cadena_local()
                   else "La copia local tiene problemas de integridad.",
                   "indice": len(cadena.bloques_completos(limite=100000))}]
    for nombre, url in config.pares():
        servicio = "PYME" if nombre == "pyme" else "BANCO"
        resultado = {"servicio": servicio, "estado": "error",
                     "detalle": "No se pudo conectar.", "indice": "-"}
        if not url:
            resultado["detalle"] = "Falta configurar la URL pública del servicio."
        else:
            try:
                respuesta = httpx.get(
                    "%s/interno/salud" % url,
                    headers={"X-Servicio-Token": config.token_servicio()},
                    timeout=10)
                datos = respuesta.json()
                if respuesta.is_success and datos.get("estado") == "ok":
                    resultado.update(estado="conectado",
                                     detalle="API interna disponible.",
                                     indice=datos.get("ultimo_indice", 0))
                else:
                    resultado["detalle"] = "HTTP %s: %s" % (
                        respuesta.status_code,
                        datos.get("detail", "respuesta no válida"))
            except Exception as error:
                resultado["detalle"] = "No se pudo conectar: %s" % str(error)[:180]
        resultados.append(resultado)
    return plantillas.TemplateResponse(request, "conexion.html",
                                       _contexto(request, usuario,
                                                 resultados=resultados))


@app.post("/conexion/verificar")
def verificar_conexion(request: Request):
    usuario = _exigir_usuario(request)
    resultados = cadena.sincronizar_con_pares()
    auditoria.registrar(usuario["id"], "verificar_conexion", "servicios",
                        None, {"resultados": resultados},
                        seguridad.ip_de(request))
    return RedirectResponse("/conexion?aviso=Verificacion+de+conexion+ejecutada",
                            status_code=303)


@app.post("/cadena/sincronizar")
def sincronizar(request: Request):
    usuario = _exigir_usuario(request)
    resultados = cadena.sincronizar_con_pares()
    auditoria.registrar(usuario["id"], "sincronizar_cadena", "bloques", None,
                        {"resultados": resultados}, seguridad.ip_de(request))
    aviso = "; ".join("%s: %s" % (r.get("par"), r.get("nuevos", r.get("error")))
                      for r in resultados) or "sin pares configurados"
    return RedirectResponse("/cadena?aviso=%s" % aviso.replace(" ", "+"),
                            status_code=303)


# ----------------------------------------------------------------- visor

@app.get("/visor", response_class=HTMLResponse)
def ver_visor(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "visor.html",
                                       _contexto(request, usuario))


@app.get("/visor/estado")
def visor_estado(request: Request):
    """Estado para el panel en vivo (se consulta cada pocos segundos)."""
    _exigir_usuario(request)
    pares, pendientes, por_tipo = (None, None, None)
    lista = conciliacion.listar(limite=1)
    if lista:
        pares, pendientes, por_tipo = conciliacion.detalle(lista[0]["id"])
    recepciones_recientes = recepciones.listar(limite=20)
    errores_carga = []
    for r in recepciones_recientes:
        if r["estado_integridad"] != "intacto":
            errores_carga.append({
                "origen": r["origen"], "archivo": r["archivo"],
                "ruta": r["ruta"], "estado": r["estado_integridad"],
                "sha256": r["sha256"], "bytes": r["bytes"],
                "motivo": r["detalle"] or "",
                "usuario": r["subido_por_email"] or "sistema",
                "fecha": r["created_at"].isoformat(),
            })
    for r in auditoria.listar_rechazos_carga(limite=20):
        errores_carga.append({
            "origen": r["origen"], "archivo": r["archivo"],
            "ruta": r["ruta_reportada"] or r["archivo"],
            "estado": "rechazado", "sha256": r["sha256"],
            "bytes": int(r["bytes"] or 0), "motivo": r["motivo"] or "",
            "usuario": r["usuario"] or "sistema",
            "fecha": r["created_at"].isoformat(),
        })
    fuentes = {}
    for r in recepciones_recientes:
        if r["estado_integridad"] == "intacto" and r["origen"] not in fuentes:
            fuentes[r["origen"]] = {
                "archivo": r["archivo"], "ruta": r["ruta"],
                "lote": r.get("lote_codigo"),
            }
    movimientos_cadena = sum(b["n_movimientos"]
                             for b in cadena.bloques_completos(limite=12))
    intactas = sum(r["estado_integridad"] == "intacto"
                   for r in recepciones_recientes)
    total_cargas = len(recepciones_recientes) + len(
        auditoria.listar_rechazos_carga(limite=20))
    return JSONResponse({
        "cadena": [{"indice": b["indice"], "origen": b["origen"],
                    "lote": b["lote_codigo"], "movimientos": b["n_movimientos"]}
                   for b in cadena.bloques_completos(limite=12)],
        "problemas_cadena": cadena.verificar_cadena_local(),
        "recepciones": [{"origen": r["origen"], "archivo": r["archivo"],
                         "ruta": r["ruta"],
                         "estado": r["estado_integridad"],
                         "detalle": r["detalle"] or "",
                         "sha256": r["sha256"], "bytes": r["bytes"],
                         "usuario": r["subido_por_email"] or "sistema"}
                        for r in recepciones.listar(limite=6)],
        "errores_carga": errores_carga[:12],
        "conciliacion": ({"conciliados": lista[0]["conciliados"],
                          "porcentaje": lista[0]["porcentaje"],
                          "total": lista[0]["total_empresa"]} if lista else None),
        "diferencias": por_tipo or {},
        "diferencias_detalle": [{
            "tipo": p["tipo_diferencia"], "origen": p["origen"],
            "movimiento": p["movimiento"], "motivo": p["motivo"],
            "fuente": fuentes.get(p["origen"]),
        } for p in (pendientes or [])],
        "estadisticas": {
            "cargas": total_cargas,
            "cargas_intactas": intactas,
            "cargas_con_error": len(errores_carga),
            "movimientos_cadena": movimientos_cadena,
            "pares": len(pares or []),
            "diferencias": len(pendientes or []),
            "avance": (round(100 * len(pares or []) /
                             lista[0]["total_empresa"])
                       if lista and lista[0]["total_empresa"] else 0),
        },
        "alertas_nuevas": alertas.contar_nuevas(),
    })


# -------------------------------------------------------------- usuarios

@app.get("/usuarios", response_class=HTMLResponse)
def ver_usuarios(request: Request):
    usuario = _exigir_usuario(request)
    usuarios = db.consultar(
        "SELECT id, email, nombre, activo, created_at FROM usuarios ORDER BY id")
    return plantillas.TemplateResponse(request, "usuarios.html",
                                       _contexto(request, usuario,
                                                 usuarios=usuarios))


@app.post("/usuarios")
def alta_usuario(request: Request, email: str = Form(...), nombre: str = Form(...),
                 clave: str = Form(...)):
    usuario = _exigir_usuario(request)
    if len(clave) < 8:
        return RedirectResponse("/usuarios?aviso=La+clave+debe+tener+8+caracteres",
                                status_code=303)
    if db.consultar_uno("SELECT id FROM usuarios WHERE email = %s",
                        (email.strip().lower(),)):
        return RedirectResponse("/usuarios?aviso=El+correo+ya+esta+registrado",
                                status_code=303)
    fila = db.ejecutar(
        "INSERT INTO usuarios (email, nombre, clave_hash, creado_por)"
        " VALUES (%s, %s, %s, %s) RETURNING id",
        (email.strip().lower(), nombre.strip(),
         seguridad.hash_clave(clave), usuario["id"]))
    auditoria.registrar(usuario["id"], "alta_usuario", "usuarios", fila["id"],
                        {"email": email}, seguridad.ip_de(request))
    return RedirectResponse("/usuarios?aviso=Usuario+creado", status_code=303)


@app.post("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(request: Request, usuario_id: int,
                           activo: int = Form(...)):
    usuario = _exigir_usuario(request)
    db.ejecutar("UPDATE usuarios SET activo = %s, updated_at = now() WHERE id = %s",
                (bool(activo), usuario_id))
    auditoria.registrar(usuario["id"],
                        "activar_usuario" if activo else "desactivar_usuario",
                        "usuarios", usuario_id, {}, seguridad.ip_de(request))
    return RedirectResponse("/usuarios?aviso=Estado+actualizado", status_code=303)


# -------------------------------------------------------------- alertas

@app.get("/alertas", response_class=HTMLResponse)
def ver_alertas(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "alertas.html",
                                       _contexto(request, usuario,
                                                 alertas=alertas.listar()))


@app.post("/alertas/{alerta_id}/estado")
def estado_alerta(request: Request, alerta_id: int, estado: str = Form(...)):
    usuario = _exigir_usuario(request)
    if estado in ("leida", "resuelta"):
        alertas.cambiar_estado(alerta_id, estado)
        auditoria.registrar(usuario["id"], "alerta_%s" % estado, "alertas",
                            alerta_id, {}, seguridad.ip_de(request))
    return RedirectResponse("/alertas", status_code=303)


# ------------------------------------------------------------- auditoria

@app.get("/auditoria", response_class=HTMLResponse)
def ver_auditoria(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "auditoria.html",
                                       _contexto(request, usuario,
                                                 registros=auditoria.listar()))


@app.get("/reporte")
def descargar_reporte(request: Request):
    usuario = _exigir_usuario(request)
    auditoria.registrar(usuario["id"], "generar_reporte", "reportes", None,
                        {"formato": "pdf"}, seguridad.ip_de(request))
    contenido = reporte.generar(usuario)
    return Response(
        content=contenido, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte-conciliador.pdf"})


@app.get("/reset", response_class=HTMLResponse)
def ver_reset(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "reset.html",
                                       _contexto(request, usuario))


@app.post("/auditoria/reset")
def reset_datos(request: Request, email: str = Form(...),
                clave: str = Form(...)):
    usuario = _exigir_usuario(request)
    if not reset.ejecutar(email, clave, usuario["id"], seguridad.ip_de(request)):
        auditoria.registrar(usuario["id"], "reset_rechazado", "aplicacion",
                            None, {"email": email}, seguridad.ip_de(request))
        return RedirectResponse(
            "/auditoria?aviso=Credenciales+incorrectas%3A+no+se+realizo+el+reset",
            status_code=303)
    return RedirectResponse(
        "/auditoria?aviso=Datos+operativos+restablecidos", status_code=303)
