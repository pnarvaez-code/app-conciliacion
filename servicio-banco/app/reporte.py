"""Generación del reporte operativo PDF en español."""
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import alertas, auditoria, config, db


def _texto(valor):
    return escape("" if valor is None else str(valor))


def _pie(canvas, documento):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(22 * mm, 16 * mm, 188 * mm, 16 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(22 * mm, 11 * mm, "Sistema de Conciliación Financiera")
    canvas.drawRightString(188 * mm, 11 * mm, "Página %d" % documento.page)
    canvas.restoreState()


def generar(usuario):
    buffer = BytesIO()
    documento = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm,
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
    metricas = [
        ("Usuarios registrados", db.consultar_uno("SELECT COUNT(*) AS n FROM usuarios")["n"]),
        ("Operaciones auditadas", db.consultar_uno("SELECT COUNT(*) AS n FROM auditoria")["n"]),
        ("Alertas acumuladas", db.consultar_uno("SELECT COUNT(*) AS n FROM alertas")["n"]),
        ("Bloques sellados", db.consultar_uno("SELECT COUNT(*) AS n FROM bloques")["n"]),
    ]
    elementos = [
        Spacer(1, 8 * mm), Paragraph("REPORTE OPERATIVO", estilos["Portada"]),
        Paragraph(_texto(config.NOMBRE_SERVICIO), estilos["Portada"]),
        Paragraph("Documento de seguimiento y control del servicio.", estilos["Cuerpo"]),
        Paragraph("Generado para: %s" % _texto(usuario["email"]), estilos["Cuerpo"]),
        Paragraph("Fecha de generación: %s" % datetime.now().strftime("%d/%m/%Y %H:%M"), estilos["Cuerpo"]),
        Paragraph("Este informe resume los movimientos y extractos gestionados, "
                  "los sellos criptográficos, las alertas y las acciones "
                  "auditadas por el servicio bancario.", estilos["Cuerpo"]),
        Paragraph("Resumen ejecutivo", estilos["Seccion"]),
        _tabla(["Indicador", "Valor"], [[_texto(k), _texto(v)] for k, v in metricas],
               [125 * mm, 35 * mm], "#123b5d"),
        Paragraph("Interpretación del estado", estilos["Seccion"]),
        Paragraph("Los bloques sellados identifican los extractos emitidos y "
                  "permiten comprobar que su contenido no fue alterado. La "
                  "auditoría conserva el historial de emisiones, reemisiones "
                  "y verificaciones para facilitar la revisión financiera.", estilos["Cuerpo"]),
        Paragraph("Últimas operaciones auditadas", estilos["Seccion"]),
        _tabla(["Fecha", "Usuario", "Acción", "Entidad"],
               [[_texto(r["created_at"]), _texto(r["usuario"] or "sistema"),
                 _texto(r["accion"]), _texto("%s %s" % (r["entidad"] or "", r["entidad_id"] or ""))]
                for r in auditorias] or [["-", "-", "Sin operaciones", "-"]],
               [35 * mm, 40 * mm, 50 * mm, 35 * mm], "#256d85"),
        Paragraph("Alertas recientes", estilos["Seccion"]),
        _tabla(["Fecha", "Tipo", "Severidad", "Estado", "Detalle"],
               [[_texto(a["created_at"]), _texto(a["tipo"]), _texto(a["severidad"]),
                 _texto(a["estado"]), _texto(a["titulo"])] for a in alertas_recientes]
               or [["-", "-", "-", "-", "No se registran alertas recientes."]],
               [30 * mm, 25 * mm, 25 * mm, 25 * mm, 55 * mm], "#9a3412"),
        Paragraph("Conclusión operativa: este informe respalda el control del "
                  "servicio, pero no sustituye la revisión contable ni la "
                  "consulta del extracto bancario original.", estilos["Cuerpo"]),
    ]
    documento.build(elementos, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()


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
