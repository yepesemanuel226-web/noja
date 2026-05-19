"""
Generador de Reportes PDF con ReportLab
Sistema de Gestión de Horarios Académicos
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                 Spacer, HRFlowable, KeepTogether)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session

# ── Colores institucionales ──────────────────────────────────────
AZUL       = colors.HexColor("#bfcbdc")
AZUL_MED   = colors.HexColor("#2563eb")
AZUL_LIGHT = colors.HexColor("#4078c2")
GRIS       = colors.HexColor("#f1f5f9")
GRIS_MED   = colors.HexColor("#94a3b8")
VERDE      = colors.HexColor("#059669")
ROJO       = colors.HexColor("#dc2626")
AMARILLO   = colors.HexColor("#d97706")
BLANCO     = colors.white
NEGRO      = colors.HexColor("#0f172a")

DIAS_ORDEN = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]


def _header_footer(canvas, doc, titulo, subtitulo=""):
    """Encabezado y pie de página en cada hoja."""
    canvas.saveState()
    w, h = doc.pagesize

    # Franja superior
    canvas.setFillColor(AZUL)
    canvas.rect(0, h - 72, w, 72, fill=1, stroke=0)

    # Título
    canvas.setFillColor(BLANCO)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(0.6 * inch, h - 32, "🎓 Sistema de Gestión de Horarios")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(0.6 * inch, h - 52, titulo)
    if subtitulo:
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(AZUL_LIGHT)
        canvas.drawString(0.6 * inch, h - 66, subtitulo)

    # Fecha en esquina
    canvas.setFillColor(AZUL_LIGHT)
    canvas.setFont("Helvetica", 8)
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    canvas.drawRightString(w - 0.5 * inch, h - 45, fecha)

    # Línea inferior de encabezado
    canvas.setStrokeColor(AZUL_MED)
    canvas.setLineWidth(2)
    canvas.line(0, h - 74, w, h - 74)

    # Pie de página
    canvas.setStrokeColor(GRIS_MED)
    canvas.setLineWidth(0.5)
    canvas.line(0.5 * inch, 0.55 * inch, w - 0.5 * inch, 0.55 * inch)
    canvas.setFillColor(GRIS_MED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.6 * inch, 0.35 * inch, "Generado automáticamente por el Sistema de Gestión de Horarios")
    canvas.drawRightString(w - 0.5 * inch, 0.35 * inch, f"Página {doc.page}")
    canvas.restoreState()


def _tabla_estilo_base(header_bg=AZUL):
    """Retorna el TableStyle base para todas las tablas."""
    return TableStyle([
        # Encabezado
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0), BLANCO),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 10),
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        # Filas alternas
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, GRIS]),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        # Bordes
        ("GRID",          (0, 0), (-1, -1), 0.4, GRIS_MED),
        ("BOX",           (0, 0), (-1, -1), 1,   AZUL),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.5, AZUL_MED),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])


# ═══════════════════════════════════════════════════════════════
# 1. Reporte: Horario por Docente
# ═══════════════════════════════════════════════════════════════
def generar_horario_docente(db: Session, docente_id: str, periodo: str) -> bytes:
    from backend.models import Docente, Asignacion, Salon, Grupo, Materia

    docente = db.query(Docente).filter(Docente.id == docente_id).first()
    if not docente:
        raise ValueError("Docente no encontrado")

    asigs = db.query(Asignacion).filter(
        Asignacion.docente_id == docente_id,
        Asignacion.periodo == periodo
    ).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=1.1*inch, bottomMargin=0.8*inch)

    styles = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle("t", fontSize=13, fontName="Helvetica-Bold",
                                    textColor=AZUL, spaceAfter=4)
    sub_estilo = ParagraphStyle("s", fontSize=10, fontName="Helvetica",
                                 textColor=GRIS_MED, spaceAfter=12)

    elements = []

    # Info del docente
    elements.append(Paragraph(f"Docente: {docente.nombre}", titulo_estilo))
    elements.append(Paragraph(f"Email: {docente.email}   |   Periodo: {periodo}", sub_estilo))
    elements.append(HRFlowable(width="100%", thickness=1, color=AZUL_MED, spaceAfter=10))

    # Tabla por día
    asigs_por_dia = {d: [] for d in DIAS_ORDEN}
    for a in asigs:
        dia = a.dia.lower()
        if dia in asigs_por_dia:
            salon_nom = a.salon.nombre if a.salon else a.salon_id[:8]
            grupo_nom = a.grupo.nombre if a.grupo else a.grupo_id[:8]
            materia_nom = a.materia.nombre if a.materia else "—"
            asigs_por_dia[dia].append((a.hora_inicio, a.hora_fin, materia_nom, salon_nom, grupo_nom))

    # Tabla visual completa (grilla semanal)
    horas_unicas = sorted(set(
        (a.hora_inicio, a.hora_fin) for a in asigs
    ))

    if horas_unicas:
        headers = ["Hora"] + [d.capitalize() for d in DIAS_ORDEN]
        col_w = [1.2*inch] + [1.5*inch] * 6
        tabla_data = [headers]
        for hi, hf in horas_unicas:
            row = [f"{hi}\n{hf}"]
            for dia in DIAS_ORDEN:
                clases_en_hora = [x for x in asigs_por_dia[dia] if x[0] == hi and x[1] == hf]
                if clases_en_hora:
                    c = clases_en_hora[0]
                    row.append(f"{c[2]}\n{c[3]}\nGrupo: {c[4]}")
                else:
                    row.append("—")
            tabla_data.append(row)

        estilo = _tabla_estilo_base()
        # Colorear celdas con clase
        for ri, row in enumerate(tabla_data[1:], 1):
            for ci, cell in enumerate(row[1:], 1):
                if cell != "—":
                    estilo.add("BACKGROUND", (ci, ri), (ci, ri), AZUL_LIGHT)
                    estilo.add("TEXTCOLOR",  (ci, ri), (ci, ri), AZUL)
                    estilo.add("FONTNAME",   (ci, ri), (ci, ri), "Helvetica-Bold")

        tabla = Table(tabla_data, colWidths=col_w, repeatRows=1)
        tabla.setStyle(estilo)
        elements.append(tabla)
    else:
        elements.append(Paragraph("No hay asignaciones para este docente en el periodo indicado.",
                                   styles["Normal"]))

    # Resumen
    elements.append(Spacer(1, 16))
    total_horas = sum(
        (int(a.hora_fin.split(":")[0]) * 60 + int(a.hora_fin.split(":")[1]) -
         int(a.hora_inicio.split(":")[0]) * 60 - int(a.hora_inicio.split(":")[1]))
        for a in asigs
    ) // 60
    resumen = [
        ["Total de clases", str(len(asigs))],
        ["Horas semanales", str(total_horas)],
        ["Periodo", periodo],
    ]
    t_res = Table(resumen, colWidths=[2.5*inch, 2*inch])
    t_res.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), AZUL),
        ("TEXTCOLOR",  (0, 0), (0, -1), BLANCO),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("GRID",       (0, 0), (-1, -1), 0.5, GRIS_MED),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    elements.append(KeepTogether([
        Paragraph("Resumen de carga académica", titulo_estilo),
        Spacer(1, 6),
        t_res
    ]))

    doc.build(elements,
              onFirstPage=lambda c, d: _header_footer(c, d, f"Horario Docente — {docente.nombre}", f"Periodo {periodo}"),
              onLaterPages=lambda c, d: _header_footer(c, d, f"Horario Docente — {docente.nombre}", f"Periodo {periodo}"))
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# 2. Reporte: Carga Académica General
# ═══════════════════════════════════════════════════════════════
def generar_carga_academica(db: Session, periodo: str) -> bytes:
    from backend.models import Docente, Asignacion

    docentes = db.query(Docente).filter(Docente.activo == True).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=1.1*inch, bottomMargin=0.8*inch)

    styles = getSampleStyleSheet()
    titulo_estilo = ParagraphStyle("t", fontSize=13, fontName="Helvetica-Bold",
                                    textColor=AZUL, spaceAfter=8)
    elements = []
    elements.append(Paragraph(f"Carga Académica por Docente — Periodo {periodo}", titulo_estilo))
    elements.append(HRFlowable(width="100%", thickness=1, color=AZUL_MED, spaceAfter=12))

    headers = ["#", "Docente", "Email", "Nº Clases", "Horas/Semana", "Estado"]
    col_w = [0.4*inch, 2.2*inch, 2.2*inch, 1*inch, 1.1*inch, 0.9*inch]
    rows = [headers]

    total_clases_all = 0
    for i, d in enumerate(docentes, 1):
        asigs = db.query(Asignacion).filter(
            Asignacion.docente_id == d.id, Asignacion.periodo == periodo
        ).all()
        n = len(asigs)
        horas = sum(
            (int(a.hora_fin.split(":")[0]) * 60 + int(a.hora_fin.split(":")[1]) -
             int(a.hora_inicio.split(":")[0]) * 60 - int(a.hora_inicio.split(":")[1]))
            for a in asigs
        ) // 60
        total_clases_all += n
        estado = "Normal"
        if horas > 20: estado = "⚠ Sobrecarga"
        elif horas < 4 and n > 0: estado = "↓ Baja"
        rows.append([str(i), d.nombre, d.email, str(n), str(horas), estado])

    estilo = _tabla_estilo_base()
    # Color de alerta en columna estado
    for ri, row in enumerate(rows[1:], 1):
        est = row[5]
        if "Sobrecarga" in est:
            estilo.add("TEXTCOLOR", (5, ri), (5, ri), ROJO)
            estilo.add("FONTNAME",  (5, ri), (5, ri), "Helvetica-Bold")
        elif "Baja" in est:
            estilo.add("TEXTCOLOR", (5, ri), (5, ri), AMARILLO)

    tabla = Table(rows, colWidths=col_w, repeatRows=1)
    tabla.setStyle(estilo)
    elements.append(tabla)

    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        f"Total docentes activos: {len(docentes)}   |   Total clases en el periodo: {total_clases_all}",
        ParagraphStyle("inf", fontSize=10, fontName="Helvetica-Oblique", textColor=GRIS_MED)
    ))

    doc.build(elements,
              onFirstPage=lambda c, d: _header_footer(c, d, "Reporte de Carga Académica", f"Periodo {periodo}"),
              onLaterPages=lambda c, d: _header_footer(c, d, "Reporte de Carga Académica", f"Periodo {periodo}"))
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# 3. Reporte: Conflictos
# ═══════════════════════════════════════════════════════════════
def generar_reporte_conflictos(db: Session) -> bytes:
    from backend.models import Conflicto

    conflictos = db.query(Conflicto).order_by(Conflicto.resuelto).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=1.1*inch, bottomMargin=0.8*inch)

    titulo_estilo = ParagraphStyle("t", fontSize=13, fontName="Helvetica-Bold",
                                    textColor=AZUL, spaceAfter=8)
    elements = []
    elements.append(Paragraph("Reporte de Conflictos Detectados", titulo_estilo))
    elements.append(HRFlowable(width="100%", thickness=1, color=AZUL_MED, spaceAfter=12))

    pendientes = [c for c in conflictos if not c.resuelto]
    resueltos  = [c for c in conflictos if c.resuelto]

    # Resumen visual
    resumen_data = [
        ["Total conflictos", str(len(conflictos))],
        ["Pendientes", str(len(pendientes))],
        ["Resueltos",  str(len(resueltos))],
    ]
    t_res = Table(resumen_data, colWidths=[2.5*inch, 1.5*inch])
    t_res.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), AZUL),
        ("BACKGROUND", (0, 1), (0, 1), ROJO),
        ("BACKGROUND", (0, 2), (0, 2), VERDE),
        ("TEXTCOLOR",  (0, 0), (0, -1), BLANCO),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 11),
        ("GRID",       (0, 0), (-1, -1), 0.5, GRIS_MED),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    elements.append(t_res)
    elements.append(Spacer(1, 18))

    # Detalle
    for seccion, lista, color_hdr in [
        ("⚠ Conflictos Pendientes", pendientes, ROJO),
        ("✔ Conflictos Resueltos",  resueltos,  VERDE)
    ]:
        if not lista:
            continue
        elements.append(Paragraph(seccion,
                                   ParagraphStyle("h2", fontSize=11, fontName="Helvetica-Bold",
                                                  textColor=color_hdr, spaceAfter=6)))
        hdr = ["#", "Tipo", "Descripción", "Asignación ID", "Estado"]
        col_w = [0.3*inch, 1.5*inch, 3.5*inch, 1.8*inch, 0.8*inch]
        rows = [hdr]
        for i, c in enumerate(lista, 1):
            rows.append([
                str(i),
                c.tipo,
                (c.descripcion or "")[:70],
                (c.asignacion_id or "")[:18] + "...",
                "Resuelto" if c.resuelto else "Pendiente"
            ])
        estilo = _tabla_estilo_base(header_bg=color_hdr)
        tabla = Table(rows, colWidths=col_w, repeatRows=1)
        tabla.setStyle(estilo)
        elements.append(tabla)
        elements.append(Spacer(1, 14))

    doc.build(elements,
              onFirstPage=lambda c, d: _header_footer(c, d, "Reporte de Conflictos"),
              onLaterPages=lambda c, d: _header_footer(c, d, "Reporte de Conflictos"))
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# 4. Reporte: Horario por Programa
# ═══════════════════════════════════════════════════════════════
def generar_horario_programa(db: Session, programa_id: str, periodo: str) -> bytes:
    from backend.models import Programa, Grupo, Asignacion, Docente, Salon

    programa = db.query(Programa).filter(Programa.id == programa_id).first()
    if not programa:
        raise ValueError("Programa no encontrado")

    grupos = db.query(Grupo).filter(Grupo.programa_id == programa_id).all()
    grupo_ids = [g.id for g in grupos]

    asigs = db.query(Asignacion).filter(
        Asignacion.grupo_id.in_(grupo_ids),
        Asignacion.periodo == periodo
    ).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=1.1*inch, bottomMargin=0.8*inch)

    titulo_estilo = ParagraphStyle("t", fontSize=13, fontName="Helvetica-Bold",
                                    textColor=AZUL, spaceAfter=8)
    elements = []
    elements.append(Paragraph(f"Horario del Programa: {programa.nombre} ({programa.codigo})", titulo_estilo))
    elements.append(HRFlowable(width="100%", thickness=1, color=AZUL_MED, spaceAfter=12))

    hdr = ["Día", "Hora Inicio", "Hora Fin", "Grupo", "Docente", "Salón", "Materia"]
    col_w = [1*inch, 1*inch, 1*inch, 1.5*inch, 2*inch, 1.2*inch, 2*inch]
    rows = [hdr]

    asigs_ord = sorted(asigs, key=lambda a: (DIAS_ORDEN.index(a.dia.lower()) if a.dia.lower() in DIAS_ORDEN else 9, a.hora_inicio))
    for a in asigs_ord:
        docente = db.query(Docente).filter(Docente.id == a.docente_id).first()
        salon = db.query(Salon).filter(Salon.id == a.salon_id).first()
        grupo = db.query(Grupo).filter(Grupo.id == a.grupo_id).first()
        rows.append([
            a.dia.capitalize(),
            a.hora_inicio,
            a.hora_fin,
            grupo.nombre if grupo else "—",
            docente.nombre if docente else "—",
            salon.nombre if salon else "—",
            a.materia.nombre if a.materia else "—"
        ])

    tabla = Table(rows, colWidths=col_w, repeatRows=1)
    tabla.setStyle(_tabla_estilo_base())
    elements.append(tabla)

    doc.build(elements,
              onFirstPage=lambda c, d: _header_footer(c, d, f"Horario Programa — {programa.nombre}", f"Periodo {periodo}"),
              onLaterPages=lambda c, d: _header_footer(c, d, f"Horario Programa — {programa.nombre}", f"Periodo {periodo}"))
    return buf.getvalue()
