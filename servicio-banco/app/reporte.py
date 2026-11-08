"""Reporte operativo PDF del servicio."""
import unicodedata
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import alertas, auditoria, config, db


def _texto(valor):
    texto = "" if valor is None else str(valor)
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def generar(usuario):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title="Reporte operativo %s" % config.NOMBRE_SERVICIO)
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle("Portada", parent=estilos["Title"],
                               alignment=TA_CENTER, fontSize=22, leading=27,
                               textColor=colors.HexColor("#123b5d")))
    estilos.add(ParagraphStyle("Seccion", parent=estilos["Heading2"],
                               textColor=colors.HexColor("#123b5d"),
                               spaceBefore=12, spaceAfter=6))
    auditorias = auditoria.listar(limite=25)
    alertas_recientes = alertas.listar(limite=10)
    metricas = [
        ("Usuarios registrados", db.consultar_uno("SELECT COUNT(*) AS n FROM usuarios")["n"]),
        ("Operaciones auditadas", db.consultar_uno("SELECT COUNT(*) AS n FROM auditoria")["n"]),
        ("Alertas acumuladas", db.consultar_uno("SELECT COUNT(*) AS n FROM alertas")["n"]),
        ("Bloques sellados", db.consultar_uno("SELECT COUNT(*) AS n FROM bloques")["n"]),
    ]
    elementos = [
        Spacer(1, 15 * mm),
        Paragraph("REPORTE OPERATIVO", estilos["Portada"]),
        Paragraph(_texto(config.NOMBRE_SERVICIO), estilos["Portada"]),
        Spacer(1, 8 * mm),
        Paragraph("Generado para: %s" % _texto(usuario["email"]), estilos["Normal"]),
        Paragraph("Fecha: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), estilos["Normal"]),
        Spacer(1, 10 * mm),
        Paragraph("Resumen de operaciones, integridad y alertas del servicio.", estilos["Normal"]),
        Paragraph("Fuente: registro append-only de Auditoria.", estilos["Normal"]),
        Paragraph("Resumen ejecutivo", estilos["Seccion"]),
        _tabla(["Indicador", "Valor"], [[_texto(k), _texto(v)] for k, v in metricas],
               [110 * mm, 45 * mm], "#123b5d"),
        Paragraph("Ultimas operaciones", estilos["Seccion"]),
        _tabla(["Fecha", "Usuario", "Accion", "Entidad"],
               [[_texto(r["created_at"]), _texto(r["usuario"] or "sistema"),
                 _texto(r["accion"]), _texto("%s %s" % (r["entidad"] or "", r["entidad_id"] or ""))]
                for r in auditorias], [32 * mm, 42 * mm, 48 * mm, 33 * mm], "#256d85"),
        Paragraph("Alertas recientes", estilos["Seccion"]),
        _tabla(["Fecha", "Tipo", "Severidad", "Estado", "Detalle"],
               [[_texto(a["created_at"]), _texto(a["tipo"]), _texto(a["severidad"]),
                 _texto(a["estado"]), _texto(a["titulo"])] for a in alertas_recientes]
               or [["-", "-", "-", "-", "Sin alertas"]],
               [29 * mm, 25 * mm, 25 * mm, 25 * mm, 51 * mm], "#9a3412"),
    ]
    documento.build(elementos)
    return buffer.getvalue()


def _tabla(encabezado, filas, anchos, color):
    return Table([encabezado] + filas, repeatRows=1, colWidths=anchos,
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color)),
                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                     ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                     ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                      [colors.white, colors.HexColor("#f8fafc")]),
                     ("FONTSIZE", (0, 0), (-1, -1), 7),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("PADDING", (0, 0), (-1, -1), 5),
                 ]))
