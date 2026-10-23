import io
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image as PDFImage

from modules.configuracion import INSTITUCION_JUVENTUD, INSTITUCION_SURCOS
from modules.utilidades import nombre_jugador, categoria_jugador, fecha_legible, ruta_logo

def generar_pdf(jugador, academico, deportivo, evaluaciones, evidencias, incluir_academico, incluir_evaluaciones):
    """Genera un PDF interno. El usuario debe verificar autorizaciones antes de compartirlo."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.65 * cm, leftMargin=1.65 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Expediente deportivo - {nombre_jugador(jugador)}",
        author="Club Juventud",
    )
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name="Marca", parent=estilos["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor("#B18C20"), alignment=TA_CENTER,
    ))
    estilos.add(ParagraphStyle(
        name="TituloClub", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, textColor=colors.HexColor("#151515"), alignment=TA_CENTER,
        spaceAfter=4,
    ))
    estilos.add(ParagraphStyle(
        name="SubtituloClub", parent=estilos["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
        spaceAfter=12,
    ))
    estilos.add(ParagraphStyle(
        name="SeccionClub", parent=estilos["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=colors.HexColor("#8A6A0A"),
        spaceBefore=12, spaceAfter=6,
    ))
    estilos.add(ParagraphStyle(
        name="TextoPequeno", parent=estilos["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"),
    ))
    institucion = jugador.get("institucion") or INSTITUCION_JUVENTUD
    nombre_marca = "COLEGIO SURCOS" if institucion == INSTITUCION_SURCOS else "CLUB JUVENTUD"
    logo = ruta_logo(institucion)
    elementos = []
    if logo:
        imagen_logo = PDFImage(str(logo), width=3.0 * cm, height=3.0 * cm, kind="bound", hAlign="CENTER")
        elementos.append(imagen_logo)
        elementos.append(Spacer(1, 4))
    elementos.extend([
        Paragraph(nombre_marca, estilos["Marca"]),
        Paragraph("EXPEDIENTE DEL ESTUDIANTE-ATLETA", estilos["TituloClub"]),
        Paragraph(f"{institucion.upper()} · DOCUMENTO DE USO INTERNO", estilos["SubtituloClub"]),
    ])

    def tabla_datos(filas, anchos=None):
        datos = [[Paragraph(f"<b>{a}</b>", estilos["TextoPequeno"]), Paragraph(str(b or "No registrado"), estilos["TextoPequeno"])] for a, b in filas]
        tabla = Table(datos, colWidths=anchos or [4.3 * cm, 12.1 * cm], hAlign="LEFT")
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2EBD5")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8D8D8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return tabla

    elementos.append(Paragraph("1. DATOS DEL DEPORTISTA", estilos["SeccionClub"]))
    elementos.append(tabla_datos([
        ("Código del jugador", jugador.get("codigo_jugador")),
        ("Cédula", jugador.get("cedula")),
        ("Nombre completo", nombre_jugador(jugador)),
        ("Fecha de nacimiento", fecha_legible(jugador.get("fecha_nacimiento"))),
        ("Fecha de ingreso", fecha_legible(jugador.get("fecha_ingreso"))),
        ("Categoría", categoria_jugador(jugador)),
        ("Curso escolar", jugador.get("curso")),
        ("Posición principal", jugador.get("posicion_principal")),
        ("Posición secundaria", jugador.get("posicion_secundaria")),
        ("Pie dominante", jugador.get("pie_dominante")),
        ("Estatura (cm)", jugador.get("estatura")),
        ("Peso (kg)", jugador.get("peso")),
        ("Nivel competitivo", jugador.get("nivel_competitivo")),
        ("Estado", jugador.get("estado")),
    ]))

    elementos.append(Paragraph("2. HISTORIAL DEPORTIVO", estilos["SeccionClub"]))
    if deportivo:
        for registro in deportivo:
            elementos.append(KeepTogether([
                Paragraph(f"<b>Temporada:</b> {registro.get('temporada') or 'No registrada'} · <b>Equipo:</b> {registro.get('club_equipo') or 'No registrado'}", estilos["TextoPequeno"]),
                Paragraph(
                    f"Categoría: {registro.get('categoria') or '—'} · Posición: {registro.get('posicion') or '—'} · "
                    f"Camiseta: {registro.get('numero_camiseta') or '—'}", estilos["TextoPequeno"]
                ),
                Paragraph(
                    f"Partidos: {registro.get('partidos_disputados') or 0} · Minutos: {registro.get('minutos_jugados') or 0} · "
                    f"Goles: {registro.get('goles') or 0} · Asistencias: {registro.get('asistencias') or 0}", estilos["TextoPequeno"]
                ),
                Paragraph(f"Competiciones: {registro.get('competiciones') or '—'} · Logros: {registro.get('logros') or '—'}", estilos["TextoPequeno"]),
                Spacer(1, 6),
            ]))
    else:
        elementos.append(Paragraph("Todavía no hay temporadas deportivas registradas.", estilos["TextoPequeno"]))

    if incluir_academico:
        elementos.append(Paragraph("3. HISTORIAL ACADÉMICO · INFORMACIÓN CONFIDENCIAL", estilos["SeccionClub"]))
        if academico:
            for registro in academico:
                elementos.append(KeepTogether([
                    Paragraph(f"<b>Periodo:</b> {registro.get('periodo_academico') or '—'} · <b>Curso:</b> {registro.get('curso') or '—'} · <b>Promedio:</b> {registro.get('promedio') or '—'}", estilos["TextoPequeno"]),
                    Paragraph(f"Materias destacadas: {registro.get('materias_destacadas') or '—'}", estilos["TextoPequeno"]),
                    Paragraph(f"Reconocimientos: {registro.get('reconocimientos') or '—'} · Inglés: {registro.get('ingles') or '—'} · Comportamiento: {registro.get('comportamiento') if registro.get('comportamiento') is not None else '—'} · Otros idiomas: {registro.get('idiomas') or '—'}", estilos["TextoPequeno"]),
                    Spacer(1, 6),
                ]))
        else:
            elementos.append(Paragraph("No hay registros académicos disponibles o visibles para esta cuenta.", estilos["TextoPequeno"]))

    if incluir_evaluaciones:
        elementos.append(Paragraph("4. EVALUACIONES INTEGRALES · CONFIDENCIAL", estilos["SeccionClub"]))
        if evaluaciones:
            for ev in evaluaciones:
                elementos.append(Paragraph(f"<b>Fecha:</b> {fecha_legible(ev.get('fecha_evaluacion'))}", estilos["TextoPequeno"]))
                metricas = [
                    ("Efectividad de pase (1-10)", ev.get("pase_efectividad")),
                    ("Conducción (1-10)", ev.get("conduccion")),
                    ("Efectividad de tiros al arco (1-10)", ev.get("tiros_efectividad")),
                    ("Velocidad 10 m (segundos)", ev.get("velocidad_10m")),
                    ("Velocidad 20 m (segundos)", ev.get("velocidad_20m")),
                    ("Illinois (segundos)", ev.get("illinois")),
                    ("Course Navette (nivel/etapa)", ev.get("course_navette")),
                    ("Disciplina (1-10)", ev.get("disciplina")),
                    ("Compromiso (1-10)", ev.get("compromiso")),
                    ("Responsabilidad (1-10)", ev.get("responsabilidad")),
                    ("Trabajo en equipo (1-10)", ev.get("trabajo_equipo")),
                    ("Capacidad de esfuerzo (1-10)", ev.get("capacidad_esfuerzo")),
                ]
                elementos.append(tabla_datos([(a, b if b is not None else "—") for a, b in metricas]))
                elementos.append(Paragraph(f"Fortalezas: {ev.get('fortalezas') or '—'}", estilos["TextoPequeno"]))
                elementos.append(Paragraph(f"Aspectos por mejorar: {ev.get('aspectos_mejora') or '—'}", estilos["TextoPequeno"]))
                elementos.append(Paragraph(f"Recomendaciones: {ev.get('recomendaciones') or '—'}", estilos["TextoPequeno"]))
                elementos.append(Spacer(1, 8))
        else:
            elementos.append(Paragraph("No hay evaluaciones visibles para esta cuenta.", estilos["TextoPequeno"]))

    elementos.append(Paragraph("5. EVIDENCIAS REGISTRADAS", estilos["SeccionClub"]))
    if evidencias:
        for ev in evidencias:
            linea = f"{ev.get('titulo') or 'Evidencia'} · {ev.get('tipo') or 'otro'} · {fecha_legible(ev.get('fecha_evidencia'))}"
            elementos.append(Paragraph(linea, estilos["TextoPequeno"]))
            if ev.get("url"):
                elementos.append(Paragraph(f"Enlace: {ev.get('url')}", estilos["TextoPequeno"]))
            if ev.get("descripcion"):
                elementos.append(Paragraph(f"Descripción: {ev.get('descripcion')}", estilos["TextoPequeno"]))
            elementos.append(Spacer(1, 4))
    else:
        elementos.append(Paragraph("Todavía no hay evidencias registradas.", estilos["TextoPequeno"]))

    elementos.extend([
        Spacer(1, 14),
        Paragraph("Juventud con Propósito y Futuro", estilos["Marca"]),
        Paragraph("Documento interno. Antes de compartirlo, verifica la autorización del representante legal y elimina la información que no sea necesaria para el destinatario.", estilos["TextoPequeno"]),
    ])

    def pie_pagina(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#B18C20"))
        canvas.setLineWidth(2)
        canvas.line(1.65 * cm, 1.15 * cm, A4[0] - 1.65 * cm, 1.15 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.65 * cm, 0.75 * cm, "CLUB JUVENTUD · EXPEDIENTE CONFIDENCIAL")
        canvas.drawRightString(A4[0] - 1.65 * cm, 0.75 * cm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    buffer.seek(0)
    return buffer.getvalue()
