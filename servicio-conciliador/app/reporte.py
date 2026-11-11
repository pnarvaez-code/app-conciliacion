"""Generación del reporte operativo PDF en español."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import alertas, auditoria, conciliacion, config, db, recepciones


def _texto(valor):
    return escape("" if valor is None else str(valor))


def _pie(canvas, documento):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    inicio = documento.leftMargin
    fin = documento.pagesize[0] - documento.rightMargin
    canvas.line(inicio, 16 * mm, fin, 16 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(inicio, 11 * mm, "Sistema de Conciliación Financiera")
    canvas.drawRightString(fin, 11 * mm, "Página %d" % documento.page)
    canvas.restoreState()


def generar(usuario):
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=landscape(A4),
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
        bottomMargin=24 * mm, title="Reporte operativo %s" % config.NOMBRE_SERVICIO,
        author="Sistema de Conciliación Financiera")
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle("Portada", parent=estilos["Title"],
        alignment=TA_CENTER, fontSize=22, leading=27,
        textColor=colors.HexColor("#123b5d"), spaceAfter=8 * mm))
    estilos.add(ParagraphStyle("Seccion", parent=estilos["Heading2"],
        fontSize=14, leading=18, textColor=colors.HexColor("#123b5d"),
        spaceBefore=12, spaceAfter=6))
    estilos.add(ParagraphStyle("Cuerpo", parent=estilos["BodyText"],
        fontSize=9.5, leading=14, spaceAfter=5))
    auditorias = auditoria.listar(limite=25)
    alertas_recientes = alertas.listar(limite=10)
    operaciones = conciliacion.listar(limite=1)
    operacion = operaciones[0] if operaciones else None
    fuentes = _fuentes_certificadas(operacion["id"] if operacion else None)
    metricas = [
        ("Usuarios registrados", db.consultar_uno("SELECT COUNT(*) AS n FROM usuarios")["n"]),
        ("Operaciones auditadas", db.consultar_uno("SELECT COUNT(*) AS n FROM auditoria")["n"]),
        ("Alertas acumuladas", db.consultar_uno("SELECT COUNT(*) AS n FROM alertas")["n"]),
        ("Bloques sincronizados", db.consultar_uno("SELECT COUNT(*) AS n FROM bloques")["n"]),
    ]
    elementos = [
        Paragraph("REPORTE DE CONCILIACIÓN", estilos["Portada"]),
        Paragraph("%s · Sistema de conciliación con integridad verificable"
                  % _texto(config.NOMBRE_SERVICIO.title()), estilos["Cuerpo"]),
        Paragraph("Generado el %s · Responsable: %s"
                  % (datetime.now().strftime("%d/%m/%Y %H:%M"), _texto(usuario["email"])),
                  estilos["Cuerpo"]),
        Paragraph("1. Resultado de conciliación", estilos["Seccion"]),
        _resultado_conciliacion(operacion, estilos),
        Paragraph("2. Certificado de integridad de los datos fuente", estilos["Seccion"]),
        Paragraph("Cada archivo se verifica contra el sello SHA-256 de su emisor y "
                  "contra las huellas de sus movimientos. Un archivo Alterado, "
                  "Sin sello o Rechazado queda excluido de la conciliación.", estilos["Cuerpo"]),
        _tabla(["Origen", "Lote", "Archivo", "Sellado", "Mov.", "Hash raíz SHA-256", "Estado"],
               [[_texto(f["origen"]), _texto(f["lote"]), _texto(f["archivo"]),
                 _texto(f["sellado"]), _texto(f["movimientos"]),
                 _texto(f["hash_raiz"]), _texto(f["estado"])] for f in fuentes]
               or [["-", "-", "Sin fuentes verificadas", "-", "-", "-", "-"]],
               [22 * mm, 30 * mm, 42 * mm, 28 * mm, 13 * mm, 87 * mm, 25 * mm], "#123b5d"),
        Paragraph("3. Resumen ejecutivo", estilos["Seccion"]),
        _tabla(["Indicador", "Valor"], [[_texto(k), _texto(v)] for k, v in metricas],
               [145 * mm, 70 * mm], "#123b5d"),
        Paragraph("Alertas recientes", estilos["Seccion"]),
        _tabla(["Fecha", "Tipo", "Severidad", "Estado", "Detalle"],
               [[_texto(a["created_at"]), _texto(a["tipo"]), _texto(a["severidad"]),
                 _texto(a["estado"]), _texto(a["titulo"])] for a in alertas_recientes]
               or [["-", "-", "-", "-", "No se registran alertas recientes."]],
               [40 * mm, 35 * mm, 32 * mm, 30 * mm, 78 * mm], "#9a3412"),
        Paragraph("4. Firma", estilos["Seccion"]),
        Spacer(1, 10 * mm),
        HRFlowable(width=80 * mm, thickness=0.6, color=colors.HexColor("#334155"),
                   spaceBefore=0, spaceAfter=2),
        Paragraph("Contador / responsable financiero o auditor", estilos["Cuerpo"]),
        Paragraph("Últimas operaciones auditadas", estilos["Seccion"]),
        _tabla(["Fecha", "Usuario", "Acción", "Entidad"],
               [[_texto(r["created_at"]), _texto(r["usuario"] or "sistema"),
                 _texto(r["accion"]), _texto("%s %s" % (r["entidad"] or "", r["entidad_id"] or ""))]
                for r in auditorias] or [["-", "-", "Sin operaciones", "-"]],
               [45 * mm, 55 * mm, 65 * mm, 50 * mm], "#256d85"),
    ]
    documento.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()


def _resultado_conciliacion(operacion, estilos):
    if not operacion:
        return Paragraph("Todavía no se ejecutó una conciliación. Reciba dos "
                         "archivos íntegros y use la pestaña Conciliación.",
                         estilos["Cuerpo"])
    return Paragraph(
        "Operación #%s · %s pares conciliados de %s movimientos de Empresa y "
        "%s de Banco · <b>%s %% conciliado</b>."
        % (operacion["id"], operacion["conciliados"], operacion["total_empresa"],
           operacion["total_banco"], operacion["porcentaje"]), estilos["Cuerpo"])


def _fuentes_certificadas(conciliacion_id):
    if conciliacion_id:
        fuentes = conciliacion.fuentes(conciliacion_id)
    else:
        fuentes = [recepciones.ultima_intacta(origen)
                   for origen in ("EMPRESA", "BANCO")]
        fuentes = [fuente for fuente in fuentes if fuente]
    resultado = []
    for fuente in fuentes:
        etiqueta = "PYME" if fuente["origen"] == "EMPRESA" else "BANCO"
        sello = db.consultar_uno(
            "SELECT hash_raiz, n_movimientos, sellado_en FROM bloques "
            "WHERE origen = %s AND lote_codigo = %s ORDER BY indice DESC LIMIT 1",
            (etiqueta, fuente.get("lote_codigo")))
        resultado.append({
            "origen": fuente["origen"],
            "lote": fuente.get("lote_codigo") or "sin lote",
            "archivo": fuente.get("archivo") or "no disponible",
            "sellado": sello["sellado_en"] if sello else "sin sello",
            "movimientos": sello["n_movimientos"] if sello else "-",
            "hash_raiz": sello["hash_raiz"] if sello else "no disponible",
            "estado": (fuente.get("estado_integridad") or "intacto").title(),
        })
    return resultado


def _tabla(encabezado, filas, anchos, color):
    datos = [[Paragraph(_texto(c), getSampleStyleSheet()["BodyText"]) for c in encabezado]]
    datos += [[Paragraph(_texto(c), getSampleStyleSheet()["BodyText"]) for c in fila]
              for fila in filas]
    return Table(datos, repeatRows=1, colWidths=anchos, hAlign="LEFT",
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color)),
                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                     ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                     ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                     ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("LEFTPADDING", (0, 0), (-1, -1), 5),
                     ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                     ("TOPPADDING", (0, 0), (-1, -1), 5),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                 ]))
