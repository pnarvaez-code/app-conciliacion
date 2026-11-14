# -*- coding: utf-8 -*-
"""app/main.py

Aplicacion del servicio BANCO (FastAPI).

Pantallas (todas requieren sesion, salvo el ingreso):
  /            Panel: movimientos de la cuenta y alta rapida
  /lotes       Extractos: emitir (CSV o XML), re-emitir y descargar
  /usuarios    Administracion de usuarios (un solo rol)
  /alertas     Alertas del servicio (integridad y operativas)
  /auditoria   Registro de acciones con su responsable

API interna para los otros servicios: ver app/internos.py.
Cada accion relevante queda auditada con el usuario y la IP de origen.
"""
import logging
import os
from pathlib import Path

import httpx
import psycopg
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import (alertas, archivos, auditoria, cadena, cierre, config, db, importar,
                 internos, movimientos, reporte, reset, seguridad, verificacion)

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Servicio BANCO - portal de empresas")
app.mount("/estaticos", StaticFiles(directory=str(BASE / "estaticos")),
          name="estaticos")
plantillas = Jinja2Templates(directory=str(BASE / "plantillas"))
app.include_router(internos.router)

_log = logging.getLogger(__name__)


def _contexto(request, usuario, **extra):
    """Datos comunes de las plantillas (usuario, menu y alertas nuevas)."""
    datos = {"request": request, "usuario": usuario,
             "servicio": config.NOMBRE_SERVICIO,
             "alertas_nuevas": alertas.contar_nuevas()}
    datos.update(extra)
    return datos


def _exigir_usuario(request):
    """Devuelve el usuario o lanza redireccion al ingreso."""
    usuario = seguridad.usuario_actual(request)
    if not usuario:
        raise _IngresoRequerido()
    return usuario


class _IngresoRequerido(Exception):
    """Se lanza cuando no hay sesion; la maneja el manejador de abajo."""


@app.exception_handler(_IngresoRequerido)
def _redirigir_ingreso(request, _excepcion):
    return RedirectResponse("/login", status_code=303)


# --------------------------------------------------------------- ingreso

@app.get("/login", response_class=HTMLResponse)
def mostrar_login(request: Request):
    return plantillas.TemplateResponse(request, "login.html",
                                       {"request": request, "error": None,
                                        "servicio": config.NOMBRE_SERVICIO})


@app.post("/login")
def ingresar(request: Request, email: str = Form(...), clave: str = Form(...)):
    usuario = db.consultar_uno(
        "SELECT * FROM usuarios WHERE email = %s AND activo", (email.strip().lower(),))
    if not usuario or not seguridad.verificar_clave(clave, usuario["clave_hash"]):
        auditoria.registrar(None, "ingreso_fallido", "usuarios", None,
                            {"email": email}, seguridad.ip_de(request))
        return plantillas.TemplateResponse(
            request, "login.html", {"error": "Correo o clave incorrectos.",
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


@app.post("/sesion/actividad", status_code=204)
def actividad_sesion(request: Request):
    """Renueva la sesión mientras una pestaña de Banco sigue abierta."""
    _exigir_usuario(request)
    return Response(status_code=204)


# ---------------------------------------------------------------- panel

@app.get("/", response_class=HTMLResponse)
def panel(request: Request):
    usuario = _exigir_usuario(request)
    return plantillas.TemplateResponse(request, "panel.html", _contexto(
        request, usuario, movimientos=movimientos.listar(),
        resumen=movimientos.resumen(),
        proxima_referencia=movimientos.proxima_referencia()))


@app.post("/movimientos")
def alta_movimiento(request: Request, fecha: str = Form(""), monto: int = Form(...),
                    referencia: str = Form(""), descripcion: str = Form("")):
    usuario = _exigir_usuario(request)
    if monto <= 0:
        return RedirectResponse("/?aviso=El+monto+debe+ser+positivo", status_code=303)
    try:
        fila = movimientos.alta(fecha, monto, referencia, descripcion, usuario["id"])
    except ValueError as error:
        return RedirectResponse("/?aviso=%s" % str(error).replace(" ", "+"), status_code=303)
    auditoria.registrar(usuario["id"], "alta_movimiento", "movimientos", fila["id"],
                        {"monto": monto, "referencia": fila["referencia"]},
                        seguridad.ip_de(request))
    return RedirectResponse("/?aviso=Movimiento+registrado", status_code=303)


@app.post("/movimientos/importar")
async def importar_movimientos(request: Request, texto: str = Form(""),
                               archivo: UploadFile = File(None)):
    usuario = _exigir_usuario(request)
    if texto.strip() and archivo and archivo.filename:
        return RedirectResponse(
            "/?aviso=Use+texto+o+archivo%2C+no+ambos", status_code=303)
    try:
        if archivo and archivo.filename:
            contenido = await seguridad.leer_archivo_limitado(archivo)
            filas = importar.leer_archivo(
                archivo.filename, contenido.decode("utf-8-sig"))
            origen = archivo.filename
        elif texto.strip():
            filas = importar.leer_texto(texto)
            origen = "texto pegado"
        else:
            raise ValueError("ingrese texto o seleccione un archivo CSV/XML")
        sin_referencia = sum(not fila["referencia"] for fila in filas)
        creados, omitidos = importar.importar_filas(filas, usuario["id"], origen)
    except (UnicodeDecodeError, ValueError) as error:
        from urllib.parse import quote_plus
        return RedirectResponse("/?aviso=%s" % quote_plus(str(error)), status_code=303)
    except psycopg.Error:
        _log.exception("Error de PostgreSQL al importar movimientos de Banco")
        return RedirectResponse(
            "/?aviso=No+se+pudieron+guardar+los+movimientos.+Intente+nuevamente.",
            status_code=303)
    from urllib.parse import quote_plus
    aviso = "Importados %d movimientos, %d omitidos por referencia" % (creados, omitidos)
    if sin_referencia:
        alertas.crear(
            "operativa", "media", "Movimientos sin referencia detectados",
            "%d movimiento(s) de %s no incluyen referencia. La carga es válida, "
            "pero requerirá cruce seguro por monto y fecha o revisión manual."
            % (sin_referencia, origen), referencia=origen, usuario_id=usuario["id"])
        auditoria.registrar(
            usuario["id"], "importar_sin_referencia", "movimientos", None,
            {"archivo": origen, "sin_referencia": sin_referencia},
            seguridad.ip_de(request))
        aviso += ". Alerta: %d sin referencia" % sin_referencia
    return RedirectResponse("/?aviso=%s" % quote_plus(aviso), status_code=303)


@app.get("/movimientos/{movimiento_id}/editar", response_class=HTMLResponse)
def editar_movimiento(request: Request, movimiento_id: int):
    usuario = _exigir_usuario(request)
    fila = movimientos.obtener(movimiento_id)
    if not fila or fila["estado"] != "pendiente":
        return RedirectResponse("/?aviso=Solo+se+pueden+editar+movimientos+pendientes",
                                status_code=303)
    return plantillas.TemplateResponse(request, "movimiento_editar.html",
                                       _contexto(request, usuario, movimiento=fila))


@app.post("/movimientos/{movimiento_id}")
def guardar_movimiento(request: Request, movimiento_id: int, fecha: str = Form(...),
                       monto: int = Form(...), referencia: str = Form(""),
                       descripcion: str = Form("")):
    usuario = _exigir_usuario(request)
    fila = movimientos.obtener(movimiento_id)
    if not fila or fila["estado"] != "pendiente":
        return RedirectResponse("/?aviso=Solo+se+pueden+editar+movimientos+pendientes",
                                status_code=303)
    try:
        movimientos.actualizar(movimiento_id, fecha, monto, referencia, descripcion)
    except ValueError as error:
        return RedirectResponse("/?aviso=%s" % str(error).replace(" ", "+"), status_code=303)
    auditoria.registrar(usuario["id"], "editar_movimiento", "movimientos",
                        movimiento_id,
                        {"antes": {"monto": fila["monto"],
                                   "fecha": str(fila["fecha"])},
                         "despues": {"monto": monto, "fecha": fecha}},
                        seguridad.ip_de(request))
    return RedirectResponse("/?aviso=Movimiento+actualizado", status_code=303)


@app.post("/movimientos/{movimiento_id}/eliminar")
def eliminar_movimiento(request: Request, movimiento_id: int):
    usuario = _exigir_usuario(request)
    fila = movimientos.obtener(movimiento_id)
    if not fila or fila["estado"] != "pendiente":
        return RedirectResponse("/?aviso=Solo+se+pueden+eliminar+movimientos+pendientes",
                                status_code=303)
    movimientos.eliminar(movimiento_id)
    auditoria.registrar(usuario["id"], "eliminar_movimiento", "movimientos",
                        movimiento_id, {"referencia": fila["referencia"]},
                        seguridad.ip_de(request))
    return RedirectResponse("/?aviso=Movimiento+eliminado", status_code=303)


# ---------------------------------------------------------------- lotes

@app.get("/lotes", response_class=HTMLResponse)
def ver_lotes(request: Request):
    usuario = _exigir_usuario(request)
    problemas = cadena.verificar_cadena_local()
    return plantillas.TemplateResponse(request, "lotes.html", _contexto(
        request, usuario, lotes=cierre.listar_lotes(),
        problemas_cadena=problemas,
        bloques=cadena.bloques_desde(0),
        verificacion=verificacion.verificar_lotes_propios()))


@app.post("/lotes/cerrar")
def cerrar(request: Request, formato: str = Form("csv")):
    usuario = _exigir_usuario(request)
    try:
        lote, bloque = cierre.cerrar_dia(usuario["id"], seguridad.ip_de(request),
                                         formato=formato)
    except ValueError as error:
        return RedirectResponse("/lotes?aviso=%s" % str(error).replace(" ", "+"),
                                status_code=303)
    return RedirectResponse("/lotes?aviso=Extracto+%s+sellado+en+el+bloque+%s"
                            % (lote["codigo"], bloque["indice"]), status_code=303)


@app.post("/lotes/reemitir")
def reemitir(request: Request, formato: str = Form("csv")):
    usuario = _exigir_usuario(request)
    try:
        lote, bloque = cierre.reemitir_ultimo(usuario["id"],
                                              seguridad.ip_de(request),
                                              formato=formato)
    except ValueError as error:
        return RedirectResponse("/lotes?aviso=%s" % str(error).replace(" ", "+"),
                                status_code=303)
    return RedirectResponse("/lotes?aviso=Extracto+%s+re-emitido+(bloque+%s)"
                            % (lote["codigo"], bloque["indice"]), status_code=303)

@app.post("/lotes/verificar")
def verificar_lotes(request: Request):
    usuario = _exigir_usuario(request)
    resultados = verificacion.verificar_y_alertar(usuario["id"],
                                                  seguridad.ip_de(request))
    alterados = [r for r in resultados if r["estado"] != "intacto"]
    if alterados:
        aviso = "%d lote(s) con problemas de integridad" % len(alterados)
    else:
        aviso = "Todos los lotes emitidos coinciden con sus sellos"
    return RedirectResponse("/lotes?aviso=%s" % aviso.replace(" ", "+"),
                            status_code=303)



@app.get("/lotes/{lote_id}/descargar")
def descargar_lote(request: Request, lote_id: int):
    usuario = _exigir_usuario(request)
    lote = db.consultar_uno(
        "SELECT l.codigo, a.* FROM lotes l"
        " JOIN archivos a ON a.id = l.archivo_id WHERE l.id = %s", (lote_id,))
    if not lote:
        return RedirectResponse("/lotes?aviso=Lote+sin+archivo", status_code=303)
    auditoria.registrar(usuario["id"], "descargar_lote", "lotes", lote_id,
                        {"archivo": lote["nombre"]}, seguridad.ip_de(request))
    try:
        contenido = archivos.obtener_contenido(lote)
    except FileNotFoundError:
        return RedirectResponse("/lotes?aviso=Archivo+no+disponible%3B+reemita+el+extracto",
                                status_code=303)
    media_type = "application/xml" if lote["nombre"].lower().endswith(".xml") else "text/csv"
    return Response(content=contenido, media_type=media_type,
                    headers={"Content-Disposition": "attachment; filename=%s" % lote["nombre"]})


# -------------------------------------------------------------- usuarios

@app.get("/usuarios", response_class=HTMLResponse)
def ver_usuarios(request: Request):
    usuario = _exigir_usuario(request)
    usuarios = db.consultar(
        "SELECT id, email, nombre, activo, created_at FROM usuarios ORDER BY id")
    return plantillas.TemplateResponse(request, "usuarios.html",
                                       _contexto(request, usuario, usuarios=usuarios))


@app.post("/usuarios")
def alta_usuario(request: Request, email: str = Form(...), nombre: str = Form(...),
                 clave: str = Form(...)):
    usuario = _exigir_usuario(request)
    if len(clave) < 8:
        return RedirectResponse("/usuarios?aviso=La+clave+debe+tener+8+caracteres",
                                status_code=303)
    existente = db.consultar_uno("SELECT id FROM usuarios WHERE email = %s",
                                 (email.strip().lower(),))
    if existente:
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
    if usuario_id == usuario["id"] and not bool(activo):
        return RedirectResponse(
            "/usuarios?aviso=No+puede+desactivar+su+propio+usuario",
            status_code=303)
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


@app.get("/conexion", response_class=HTMLResponse)
def ver_conexion(request: Request):
    usuario = _exigir_usuario(request)
    resultados = [{"servicio": config.NOMBRE_SERVICIO, "estado": "conectado",
                   "detalle": "La aplicación está activa y responde correctamente.",
                   "indice": cadena.ultimo_bloque()["indice"]
                   if cadena.ultimo_bloque() else 0}]
    url = config.url_conciliador()
    if not url:
        resultados.append({"servicio": "CONCILIADOR", "estado": "error",
                           "detalle": "Falta configurar URL_CONCILIADOR.",
                           "indice": "-"})
    else:
        try:
            respuesta = httpx.get(
                "%s/interno/salud" % url,
                headers={"X-Servicio-Token": config.token_servicio()},
                timeout=10)
            datos = respuesta.json()
            if respuesta.is_success and datos.get("estado") == "ok":
                resultados.append({"servicio": "CONCILIADOR",
                                   "estado": "conectado",
                                   "detalle": "API interna disponible.",
                                   "indice": datos.get("ultimo_indice", 0)})
            else:
                resultados.append({"servicio": "CONCILIADOR", "estado": "error",
                                   "detalle": "HTTP %s: %s" %
                                   (respuesta.status_code, datos.get("detail", "respuesta no válida")),
                                   "indice": "-"})
        except Exception as error:
            resultados.append({"servicio": "CONCILIADOR", "estado": "error",
                               "detalle": "No se pudo conectar: %s" % str(error)[:180],
                               "indice": "-"})
    return plantillas.TemplateResponse(request, "conexion.html",
                                       _contexto(request, usuario,
                                                 resultados=resultados,
                                                 conexion_establecida=all(
                                                     item["estado"] == "conectado"
                                                     for item in resultados)))


@app.post("/conexion/verificar")
def verificar_conexion(request: Request):
    usuario = _exigir_usuario(request)
    cadena.reintentar_envios()
    auditoria.registrar(usuario["id"], "verificar_conexion", "servicios",
                        None, {}, seguridad.ip_de(request))
    return RedirectResponse("/conexion?aviso=Verificacion+de+conexion+ejecutada",
                            status_code=303)


@app.get("/reporte")
def descargar_reporte(request: Request):
    usuario = _exigir_usuario(request)
    auditoria.registrar(usuario["id"], "generar_reporte", "reportes", None,
                        {"formato": "pdf"}, seguridad.ip_de(request))
    contenido = reporte.generar(usuario)
    return Response(
        content=contenido, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reporte-banco.pdf"})


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
