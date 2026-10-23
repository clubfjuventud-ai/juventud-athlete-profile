import io
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image as PDFImage

from modules.evaluaciones_visuales import ordenar_evaluaciones, cuadro_evaluacion_pdf
from modules.configuracion import INSTITUCION_JUVENTUD, INSTITUCION_SURCOS
from modules.utilidades import nombre_jugador, categoria_jugador, fecha_legible, ruta_logo

# Tonos institucionales sobre fondo blanco para conservar legibilidad al imprimir.
PALETAS_PDF = {
    INSTITUCION_JUVENTUD: {
        "principal": "#17170F", "acento": "#D8A830", "marca": "#8A6A0A",
        "seccion": "#8A6A0A", "fondo": "#F8F1D9", "borde": "#DECEA0",
        "lema": "Juventud con Propósito y Futuro",
    },
    INSTITUCION_SURCOS: {
        "principal": "#0868A0", "acento": "#70A808", "marca": "#4C7300",
        "seccion": "#0868A0", "fondo": "#EFF6DF", "borde": "#BCD6E4",
        "lema": "Unidad Educativa Bilingüe",
    },
}


def paleta_pdf(institucion):
    nombre = str(institucion or INSTITUCION_JUVENTUD).strip().casefold()
    for institucion_conocida, paleta in PALETAS_PDF.items():
        if institucion_conocida.casefold() == nombre:
            return paleta
    return {
        "principal": "#222222", "acento": "#666666", "marca": "#333333",
        "seccion": "#333333", "fondo": "#F2F2F2", "borde": "#D8D8D8",
        "lema": str(institucion),
    }


def _escapar_datos(valor):
    """Copia los datos y neutraliza marcado antes de pasarlos a Paragraph."""
    if isinstance(valor, str):
        return escape(valor)
    if isinstance(valor, dict):
        return {clave: _escapar_datos(dato) for clave, dato in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_escapar_datos(dato) for dato in valor]
    return valor


def generar_pdf(jugador, academico, deportivo, evaluaciones, evidencias, incluir_academico, incluir_evaluaciones):
    """Genera un PDF interno. El usuario debe verificar autorizaciones antes de compartirlo."""
    institucion = str(jugador.get("institucion") or INSTITUCION_JUVENTUD).strip()
    paleta = paleta_pdf(institucion)
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.65 * cm, leftMargin=1.65 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Expediente deportivo - {nombre_jugador(jugador)}",
        author=institucion,
    )
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle(
        name="Marca", parent=estilos["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=colors.HexColor(paleta["marca"]), alignment=TA_CENTER,
    ))
    estilos.add(ParagraphStyle(
        name="TituloClub", parent=estilos["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, textColor=colors.HexColor(paleta["principal"]), alignment=TA_CENTER,
        spaceAfter=4,
    ))
    estilos.add(ParagraphStyle(
        name="SubtituloClub", parent=estilos["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
        spaceAfter=12,
    ))
    estilos.add(ParagraphStyle(
        name="SeccionClub", parent=estilos["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=colors.HexColor(paleta["seccion"]),
        spaceBefore=12, spaceAfter=6,
    ))
    estilos.add(ParagraphStyle(
        name="TextoPequeno", parent=estilos["BodyText"], fontName="Helvetica",
        fontSize=8.5, leading=11, textColor=colors.HexColor("#333333"),
    ))
    nombre_marca = escape(institucion.upper())
    logo = ruta_logo(institucion)
    jugador, academico, deportivo, evaluaciones, evidencias = _escapar_datos(
        [jugador, academico, deportivo, evaluaciones, evidencias]
    )
    elementos = []
    if logo:
        try:
            # kind="bound" ajusta dentro de la caja sin alterar la relación ancho/alto.
            imagen_logo = PDFImage(
                str(logo), width=4.5 * cm, height=3.0 * cm,
                kind="bound", hAlign="CENTER", lazy=0,
            )
            elementos.append(imagen_logo)
            elementos.append(Spacer(1, 4))
        except (OSError, ValueError):
            # El nombre institucional permanece visible aunque la imagen no se pueda leer.
            pass
    elementos.extend([
        Paragraph(nombre_marca, estilos["Marca"]),
        Paragraph("EXPEDIENTE DEL ESTUDIANTE-ATLETA", estilos["TituloClub"]),
        Paragraph(f"{escape(institucion.upper())} · DOCUMENTO DE USO INTERNO", estilos["SubtituloClub"]),
    ])

    def tabla_datos(filas, anchos=None):
        datos = [[Paragraph(f"<b>{a}</b>", estilos["TextoPequeno"]), Paragraph(str(b or "No registrado"), estilos["TextoPequeno"])] for a, b in filas]
        tabla = Table(datos, colWidths=anchos or [4.3 * cm, 12.1 * cm], hAlign="LEFT")
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(paleta["fondo"])),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(paleta["borde"])),
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
            ordenadas = ordenar_evaluaciones(evaluaciones)
            for indice, ev in enumerate(ordenadas):
                anterior = ordenadas[indice + 1] if indice + 1 < len(ordenadas) else None
                elementos.append(KeepTogether([
                    Paragraph(f"<b>Fecha:</b> {fecha_legible(ev.get('fecha_evaluacion'))}", estilos["TextoPequeno"]),
                    cuadro_evaluacion_pdf(ev, anterior, paleta),
                    Spacer(1, 6),
                ]))
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
        Paragraph(escape(paleta["lema"]), estilos["Marca"]),
        Paragraph("Documento interno. Antes de compartirlo, verifica la autorización del representante legal y elimina la información que no sea necesaria para el destinatario.", estilos["TextoPequeno"]),
    ])

    def pie_pagina(canvas, doc):
        canvas.saveState()
        canvas.setLineWidth(2)
        inicio, fin = 1.65 * cm, A4[0] - 1.65 * cm
        division = inicio + (fin - inicio) * 0.7
        canvas.setStrokeColor(colors.HexColor(paleta["principal"]))
        canvas.line(inicio, 1.15 * cm, division, 1.15 * cm)
        canvas.setStrokeColor(colors.HexColor(paleta["acento"]))
        canvas.line(division, 1.15 * cm, fin, 1.15 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.65 * cm, 0.75 * cm, f"{institucion.upper()} · EXPEDIENTE CONFIDENCIAL")
        canvas.drawRightString(A4[0] - 1.65 * cm, 0.75 * cm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    buffer.seek(0)
    return buffer.getvalue()
