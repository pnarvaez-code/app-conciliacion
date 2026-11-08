# -*- coding: utf-8 -*-
"""app/main.py

Aplicacion del servicio PYME (FastAPI).

Pantallas (todas requieren sesion, salvo el ingreso):
  /            Panel: ventas del dia, alta rapida y resumen
  /lotes       Cierres del dia: cerrar, re-emitir y descargar el archivo
  /usuarios    Administracion de usuarios (un solo rol)
  /alertas     Alertas del servicio (integridad y operativas)
  /auditoria   Registro de acciones con su responsable

API interna para los otros servicios: ver app/internos.py.
Cada accion relevante queda auditada con el usuario y la IP de origen.
"""
import os

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import (alertas, auditoria, cadena, cierre, config, db, importar,
                 internos, movimientos, reporte, reset, seguridad, verificacion)

BASE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="Servicio PYME - sistema de ventas")
app.mount("/estaticos", StaticFiles(directory=os.path.join(BASE, "estaticos")),
          name="estaticos")
plantillas = Jinja2Templates(directory=os.path.join(BASE, "plantillas"))
app.include_router(internos.router)


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
            "login.html", {"request": request, "error": "Correo o clave incorrectos.",
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
        request, usuario, movimientos=movimientos.listar(),
        resumen=movimientos.resumen(),
        proxima_referencia=movimientos.proxima_referencia()))


@app.post("/movimientos")
def alta_movimiento(request: Request, fecha: str = Form(""), monto: int = Form(...),
                    referencia: str = Form(""), descripcion: str = Form("")):
    usuario = _exigir_usuario(request)
    if monto <= 0:
        return RedirectResponse("/?aviso=El+monto+debe+ser+positivo", status_code=303)
    fila = movimientos.alta(fecha, monto, referencia, descripcion, usuario["id"])
    auditoria.registrar(usuario["id"], "alta_movimiento", "movimientos", fila["id"],
                        {"monto": monto, "referencia": fila["referencia"]},
                        seguridad.ip_de(request))
    return RedirectResponse("/?aviso=Venta+registrada", status_code=303)


@app.post("/movimientos/importar")
async def importar_movimientos(request: Request, texto: str = Form(""),
                               archivo: UploadFile = File(None)):
    usuario = _exigir_usuario(request)
    if texto.strip() and archivo and archivo.filename:
        return RedirectResponse(
            "/?aviso=Use+texto+o+archivo%2C+no+ambos", status_code=303)
    try:
        if archivo and archivo.filename:
            contenido = await archivo.read()
            if len(contenido) > 5 * 1024 * 1024:
                raise ValueError("el archivo supera el maximo de 5 MB")
            filas = importar.leer_archivo(
                archivo.filename, contenido.decode("utf-8-sig"))
            origen = archivo.filename
        elif texto.strip():
            filas = importar.leer_texto(texto)
            origen = "texto pegado"
        else:
            raise ValueError("ingrese texto o seleccione un archivo CSV/XML")
        creados, omitidos = importar.importar_filas(filas, usuario["id"], origen)
    except (UnicodeDecodeError, ValueError) as error:
        from urllib.parse import quote_plus
        return RedirectResponse("/?aviso=%s" % quote_plus(str(error)), status_code=303)
    return RedirectResponse(
        "/?aviso=Importados+%d+movimientos%2C+%d+omitidos+por+referencia"
        % (creados, omitidos), status_code=303)


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
    movimientos.actualizar(movimiento_id, fecha, monto, referencia, descripcion)
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
def cerrar(request: Request):
    usuario = _exigir_usuario(request)
    try:
        lote, bloque = cierre.cerrar_dia(usuario["id"], seguridad.ip_de(request))
    except ValueError as error:
        return RedirectResponse("/lotes?aviso=%s" % str(error).replace(" ", "+"),
                                status_code=303)
    return RedirectResponse("/lotes?aviso=Lote+%s+sellado+en+el+bloque+%s"
                            % (lote["codigo"], bloque["indice"]), status_code=303)


@app.post("/lotes/reemitir")
def reemitir(request: Request):
    usuario = _exigir_usuario(request)
    try:
        lote, bloque = cierre.reemitir_ultimo(usuario["id"], seguridad.ip_de(request))
    except ValueError as error:
        return RedirectResponse("/lotes?aviso=%s" % str(error).replace(" ", "+"),
                                status_code=303)
    return RedirectResponse("/lotes?aviso=Lote+%s+re-emitido+(bloque+%s)"
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
        "SELECT l.codigo, a.nombre, a.ruta FROM lotes l"
        " JOIN archivos a ON a.id = l.archivo_id WHERE l.id = %s", (lote_id,))
    if not lote:
        return RedirectResponse("/lotes?aviso=Lote+sin+archivo", status_code=303)
    auditoria.registrar(usuario["id"], "descargar_lote", "lotes", lote_id,
                        {"archivo": lote["nombre"]}, seguridad.ip_de(request))
    return FileResponse(lote["ruta"], media_type="text/csv",
                        filename=lote["nombre"])


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
        headers={"Content-Disposition": "attachment; filename=reporte-pyme.pdf"})


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
