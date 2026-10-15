import io
import re
from pathlib import Path
from datetime import date, datetime

import pandas as pd

import streamlit as st
from supabase import create_client

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image as PDFImage


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
LOGO_JUVENTUD = ASSETS_DIR / "logo_juventud.png"
LOGO_SURCOS = ASSETS_DIR / "logo_surcos.png"
INSTITUCION_JUVENTUD = "Club Juventud"
INSTITUCION_SURCOS = "Colegio Surcos"

NEGRO = "#101114"
NEGRO_CARD = "#191B20"
DORADO = "#D4AF37"
BLANCO = "#F5F5F5"
GRIS = "#A8ABB3"

st.markdown(
    f"""
    <style>
      .stApp {{ background: {NEGRO}; color: {BLANCO}; }}
      [data-testid="stSidebar"] {{ background: #0B0C0E; border-right: 1px solid #292A2F; }}
      h1, h2, h3 {{ color: {BLANCO} !important; }}
      p, label, [data-testid="stMarkdownContainer"] {{ color: {BLANCO}; }}
      .brand-line {{ height: 4px; background: {DORADO}; border-radius: 8px; margin: 0 0 1rem 0; }}
      .eyebrow {{ color: {DORADO}; font-size: .78rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }}
      .hero {{ background: linear-gradient(135deg, #202126, #131417); border: 1px solid #34353B; border-left: 5px solid {DORADO}; padding: 1.3rem 1.5rem; border-radius: 14px; margin-bottom: 1rem; }}
      .hero h2 {{ margin: .25rem 0 .3rem 0; }}
      .hero p {{ color: #C5C6CC; margin-bottom: 0; }}
      div[data-testid="stMetric"] {{ background: {NEGRO_CARD}; border: 1px solid #303137; padding: 1rem; border-radius: 12px; }}
      div[data-testid="stMetricLabel"] {{ color: {GRIS}; }}
      div[data-testid="stMetricValue"] {{ color: {DORADO}; }}
      .section-card {{ background: {NEGRO_CARD}; border: 1px solid #303137; padding: 1rem; border-radius: 12px; }}
      div.stButton > button, div.stFormSubmitButton > button {{ background: {DORADO}; color: #111111; border: 0; border-radius: 8px; font-weight: 700; }}
      div.stButton > button:hover, div.stFormSubmitButton > button:hover {{ background: #E5C85C; color: #111111; border: 0; }}
      div[data-baseweb="tab-list"] {{ gap: .4rem; }}
      button[data-baseweb="tab"] {{ background: #1B1C21; border-radius: 8px 8px 0 0; }}
      button[data-baseweb="tab"] p {{ color: #E7E7E7; }}
      hr {{ border-color: #33343A; }}
      .small-muted {{ color: {GRIS}; font-size: .86rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def encabezado_seccion(titulo, descripcion=None):
    st.markdown('<div class="brand-line"></div>', unsafe_allow_html=True)
    st.header(titulo)
    if descripcion:
        st.caption(descripcion)


def conectar_supabase():
    """Crea un cliente por ejecución para evitar compartir sesiones entre usuarios."""
    cliente = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    sesion = st.session_state.get("sesion")
    if sesion is not None:
        cliente.postgrest.auth(sesion.access_token)
    return cliente


def cerrar_sesion():
    try:
        if st.session_state.get("sesion") is not None:
            cliente = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
            cliente.auth.set_session(
                st.session_state.sesion.access_token,
                st.session_state.sesion.refresh_token,
            )
            cliente.auth.sign_out()
    except Exception:
        pass
    st.session_state.sesion = None
    st.rerun()


def obtener_jugadores(supabase):
    respuesta = (
        supabase.table("jugadores")
        .select(
            "id, codigo_jugador, cedula, nombres, apellidos, fecha_nacimiento, fecha_ingreso, curso, "
            "posicion_principal, posicion_secundaria, pie_dominante, estatura, peso, fotografia_url, "
            "nivel_competitivo, estado, categoria_id, institucion, categorias(nombre, edad_minima, edad_maxima)"
        )
        .order("apellidos")
        .execute()
    )
    return respuesta.data or []


def ruta_logo(institucion):
    """Devuelve el archivo de logo correspondiente si está instalado en assets/."""
    ruta = LOGO_SURCOS if institucion == INSTITUCION_SURCOS else LOGO_JUVENTUD
    return ruta if ruta.exists() else None


def mostrar_marca(institucion=INSTITUCION_JUVENTUD, ancho=120):
    ruta = ruta_logo(institucion)
    if ruta:
        st.image(str(ruta), width=ancho)
    else:
        st.markdown(f"**{institucion.upper()}**")


def nombre_jugador(jugador):
    return f"{jugador.get('apellidos', '')}, {jugador.get('nombres', '')}".strip(", ")


def categoria_jugador(jugador):
    categoria = jugador.get("categorias")
    if isinstance(categoria, list):
        categoria = categoria[0] if categoria else None
    return (categoria or {}).get("nombre", "Sin categoría")

def obtener_edad(fecha_nacimiento, fecha_referencia=None):
    # Categoría por año de nacimiento: criterio de temporada deportiva.
    fecha_referencia = fecha_referencia or date.today()
    return fecha_referencia.year - fecha_nacimiento.year


def categoria_por_fecha(fecha_nacimiento, categorias):
    """Busca por rangos de edad y, si no están configurados, usa nombres como Sub-8/Sub-10."""
    edad = obtener_edad(fecha_nacimiento)
    for categoria in categorias:
        minimo = categoria.get("edad_minima")
        maximo = categoria.get("edad_maxima")
        if minimo is not None and maximo is not None and int(minimo) <= edad <= int(maximo):
            return categoria
    # Alternativa para categorías típicas Sub-8, Sub-10, Sub-12, Sub-14 y Sub-16.
    categorias_con_limite = []
    for categoria in categorias:
        match = re.search(r"sub\s*[- ]?\s*(\d+)", str(categoria.get("nombre", "")), re.IGNORECASE)
        if match:
            categorias_con_limite.append((int(match.group(1)), categoria))
    for limite, categoria in sorted(categorias_con_limite, key=lambda item: item[0]):
        if edad <= limite:
            return categoria
    return None


def grafico_evolucion(registros, campos, titulo, ylabel=None):
    """Dibuja evolución cronológica solo cuando existen datos para esas métricas."""
    puntos = []
    for registro in sorted(registros, key=lambda x: str(x.get("fecha_evaluacion") or "")):
        fila = {"Fecha": str(registro.get("fecha_evaluacion") or "")}
        for campo, etiqueta in campos:
            valor = registro.get(campo)
            if valor is not None:
                try:
                    fila[etiqueta] = float(valor)
                except (TypeError, ValueError):
                    pass
        if len(fila) > 1:
            puntos.append(fila)
    if puntos:
        df = pd.DataFrame(puntos).set_index("Fecha")
        st.markdown(f"**{titulo}**")
        st.line_chart(df, height=260)
        if ylabel:
            st.caption(ylabel)
    else:
        st.caption(f"El gráfico de {titulo.lower()} aparecerá cuando haya resultados registrados en más de una fecha.")


def fecha_legible(valor):
    if not valor:
        return "No registrada"
    try:
        return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return str(valor)


def puede_editar(rol):
    return rol in ("administrador", "entrenador")


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


# ============================================================
# ESTADO DE SESIÓN Y CABECERA
# ============================================================
if "sesion" not in st.session_state:
    st.session_state.sesion = None

cab_logo, cab_texto = st.columns([1, 5])
with cab_logo:
    mostrar_marca(INSTITUCION_JUVENTUD, ancho=110)
with cab_texto:
    st.markdown('<div class="eyebrow">Club Formativo Deportivo Especializado</div>', unsafe_allow_html=True)
    st.title("Juventud Athlete Profile")
    st.caption("Sistema de gestión y desarrollo del estudiante-atleta")

# ============================================================
# LOGIN
# ============================================================
if st.session_state.sesion is None:
    izquierda, centro, derecha = st.columns([1, 1.25, 1])
    with centro:
        st.markdown(
            '<div class="hero"><div class="eyebrow">Juventud con propósito y futuro</div>'
            '<h2>Tu desarrollo, en un solo lugar.</h2>'
            '<p>Plataforma de gestión deportiva y seguimiento del estudiante-atleta.</p></div>',
            unsafe_allow_html=True,
        )
        with st.form("formulario_login"):
            correo = st.text_input("Correo electrónico")
            contrasena = st.text_input("Contraseña", type="password")
            ingresar = st.form_submit_button("Iniciar sesión", use_container_width=True)
        if ingresar:
            if not correo.strip() or not contrasena:
                st.warning("Escribe tu correo y contraseña.")
            else:
                try:
                    cliente_login = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                    respuesta = cliente_login.auth.sign_in_with_password({
                        "email": correo.strip(),
                        "password": contrasena,
                    })
                    if respuesta.session is None:
                        st.error("No se pudo crear una sesión. Revisa tus credenciales.")
                    else:
                        st.session_state.sesion = respuesta.session
                        st.rerun()
                except Exception:
                    st.error("No se pudo iniciar sesión. Revisa las credenciales o intenta nuevamente.")
    st.stop()

# ============================================================
# VALIDACIÓN DE PERFIL
# ============================================================
usuario = st.session_state.sesion.user
try:
    supabase = conectar_supabase()
    resultado_perfil = (
        supabase.table("perfiles")
        .select("*")
        .eq("id", str(usuario.id))
        .maybe_single()
        .execute()
    )
    perfil = resultado_perfil.data
except Exception:
    st.error("No se pudo consultar tu perfil. Comprueba la conexión y vuelve a iniciar sesión.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
    st.stop()

if not perfil or not perfil.get("activo"):
    st.warning("Tu cuenta no tiene un perfil activo. Contacta al administrador.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
    st.stop()

rol = perfil.get("rol", "sin rol")
nombre = perfil.get("nombre_completo") or usuario.email
rol_admin = rol == "administrador"
rol_entrenador = rol == "entrenador"
rol_autoridad = rol == "autoridad"
rol_padre = rol == "padre"

# ============================================================
# NAVEGACIÓN
# ============================================================
mostrar_marca(INSTITUCION_JUVENTUD, ancho=145)
st.sidebar.caption("JUVENTUD CON PROPÓSITO Y FUTURO")
st.sidebar.write(f"**{nombre}**")
st.sidebar.caption(f"Rol: {rol.capitalize()}")
st.sidebar.divider()
seccion = st.sidebar.radio(
    "MENÚ PRINCIPAL",
    ["Inicio", "Jugadores Juventud", "Colegio Surcos", "Usuarios y representantes"],
    key="menu_principal",
)
st.sidebar.divider()
if st.sidebar.button("Cerrar sesión", use_container_width=True):
    cerrar_sesion()

# Cargar deportistas una vez por ejecución; las políticas RLS de Supabase filtran resultados.
try:
    jugadores = obtener_jugadores(supabase)
except Exception:
    jugadores = []

# ============================================================
# INICIO
# ============================================================
if seccion == "Inicio":
    st.markdown(
        f'<div class="hero"><div class="eyebrow">Panel de gestión</div>'
        f'<h2>Bienvenido/a, {nombre}</h2>'
        '<p>Una visión organizada del proceso deportivo y formativo de nuestros atletas.</p></div>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Deportistas visibles", len(jugadores))
    activos = sum(1 for j in jugadores if j.get("estado") == "activo")
    col2.metric("Deportistas activos", activos)
    categorias = set(categoria_jugador(j) for j in jugadores)
    col3.metric("Categorías", len(categorias))
    st.subheader("Accesos principales")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 👥 Deportistas")
        st.write("Consulta expedientes y seguimiento individual.")
    with c2:
        st.markdown("#### 📊 Evaluaciones")
        st.write("Registra y revisa la evolución integral.")
    with c3:
        st.markdown("#### 🏆 Competencias")
        st.write("Organiza temporadas, partidos y logros.")
    st.info("La información que ves depende de tu cuenta y de los permisos configurados en Supabase.")

# ============================================================
# DEPORTISTAS
# ============================================================
elif seccion in ("Jugadores Juventud", "Colegio Surcos"):
    institucion_actual = INSTITUCION_SURCOS if seccion == "Colegio Surcos" else INSTITUCION_JUVENTUD
    jugadores = [j for j in jugadores if (j.get("institucion") or INSTITUCION_JUVENTUD) == institucion_actual]
    mostrar_marca(institucion_actual, ancho=150)
    encabezado_seccion(f"👥 {seccion}", f"Registro, consulta y expedientes individuales de {institucion_actual}.")
    tab_registro, tab_consulta, tab_expediente = st.tabs(["➕ Registrar", "📋 Consultar", "🗂️ Expediente individual"])

    # Categorías activas
    try:
        categorias_resultado = supabase.table("categorias").select("id, nombre, edad_minima, edad_maxima").eq("activa", True).order("nombre").execute()
        categorias_lista = categorias_resultado.data or []
    except Exception:
        categorias_lista = []
    mapa_categorias = {c["nombre"]: c["id"] for c in categorias_lista}

    with tab_registro:
        if not puede_editar(rol) and not rol_admin:
            st.info("Tu rol tiene acceso de consulta. Para registrar deportistas, solicita apoyo al administrador o entrenador autorizado.")
        elif not categorias_lista:
            st.warning("No hay categorías activas disponibles. Revisa la tabla categorias en Supabase.")
        else:
            st.markdown(f"#### Registro para: {institucion_actual}")
            st.caption("El código se asigna automáticamente al guardar. La categoría se actualiza automáticamente según el año de nacimiento y los rangos configurados en Supabase.")
            prefijo_key = "surcos" if institucion_actual == INSTITUCION_SURCOS else "juventud"
            st.markdown("#### Identificación")
            c1, c2 = st.columns(2)
            nombres = c1.text_input("Nombres *", key=f"nombres_{prefijo_key}")
            apellidos = c2.text_input("Apellidos *", key=f"apellidos_{prefijo_key}")
            cedula = st.text_input("Número de cédula", max_chars=10, help="Opcional. Se guarda como texto para conservar ceros iniciales.", key=f"cedula_{prefijo_key}")
            c3, c4 = st.columns(2)
            fecha_nacimiento = c3.date_input("Fecha de nacimiento *", value=date(2015, 1, 1), min_value=date(1990, 1, 1), max_value=date.today(), format="DD/MM/YYYY", key=f"nacimiento_{prefijo_key}")
            curso = c4.text_input("Curso escolar", key=f"curso_{prefijo_key}")
            fotografia_url = st.text_input("URL de fotografía tamaño carnet (opcional)", key=f"foto_{prefijo_key}")
            categoria_auto = categoria_por_fecha(fecha_nacimiento, categorias_lista)
            if categoria_auto:
                st.success(f"Categoría asignada automáticamente: **{categoria_auto['nombre']}** · Año de nacimiento: {fecha_nacimiento.year}")
            else:
                st.warning("No se encontró una categoría para este año de nacimiento. Revisa los rangos edad_minima y edad_maxima de la tabla categorias.")
            if fotografia_url.strip():
                st.image(fotografia_url.strip(), width=120, caption="Vista previa · tamaño carnet")
            st.markdown("#### Información deportiva")
            posiciones = ["Portero/a", "Defensa central", "Lateral derecho", "Lateral izquierdo", "Mediocentro defensivo", "Mediocentro", "Mediocentro ofensivo", "Extremo derecho", "Extremo izquierdo", "Delantero/a"]
            c5, c6, c7 = st.columns(3)
            posicion_principal = c5.selectbox("Posición principal", ["No definida"] + posiciones, key=f"pos_principal_{prefijo_key}")
            posicion_secundaria = c6.selectbox("Posición secundaria", ["No definida"] + posiciones, key=f"pos_secundaria_{prefijo_key}")
            pie_dominante = c7.selectbox("Pie dominante", ["No definido", "Derecho", "Izquierdo", "Ambidiestro"], key=f"pie_{prefijo_key}")
            c8, c9, c10 = st.columns(3)
            estatura = c8.number_input("Estatura (cm)", min_value=0, max_value=250, value=0, key=f"estatura_{prefijo_key}")
            peso = c9.number_input("Peso (kg)", min_value=0.0, max_value=200.0, value=0.0, step=0.5, key=f"peso_{prefijo_key}")
            fecha_ingreso = c10.date_input("Fecha de ingreso", value=date.today(), format="DD/MM/YYYY", key=f"ingreso_{prefijo_key}")
            nivel_competitivo = st.selectbox("Nivel competitivo", ["No definido", "Formativo", "Recreativo", "Intercolegial", "Provincial", "Nacional", "Selección"], key=f"nivel_{prefijo_key}")
            guardar = st.button("Guardar deportista", use_container_width=True, key=f"guardar_jugador_{prefijo_key}")
            if guardar:
                if not nombres.strip() or not apellidos.strip():
                    st.error("Completa los nombres y apellidos.")
                elif not categoria_auto:
                    st.error("No se puede asignar la categoría automáticamente. Ajusta los rangos de edad en Supabase antes de registrar.")
                elif cedula.strip() and (not cedula.strip().isdigit() or len(cedula.strip()) != 10):
                    st.error("La cédula ecuatoriana debe contener 10 dígitos. Déjala vacía si todavía no la vas a registrar.")
                else:
                    payload = {
                        "institucion": institucion_actual,
                        "cedula": cedula.strip() or None,
                        "nombres": nombres.strip(), "apellidos": apellidos.strip(),
                        "fecha_nacimiento": fecha_nacimiento.isoformat(),
                        "categoria_id": categoria_auto["id"],
                        "curso": curso.strip() or None,
                        "posicion_principal": None if posicion_principal == "No definida" else posicion_principal,
                        "posicion_secundaria": None if posicion_secundaria == "No definida" else posicion_secundaria,
                        "pie_dominante": None if pie_dominante == "No definido" else pie_dominante,
                        "estatura": estatura if estatura > 0 else None,
                        "peso": peso if peso > 0 else None,
                        "fecha_ingreso": fecha_ingreso.isoformat(),
                        "nivel_competitivo": None if nivel_competitivo == "No definido" else nivel_competitivo,
                        "fotografia_url": fotografia_url.strip() or None,
                        "estado": "activo",
                    }
                    try:
                        supabase.table("jugadores").insert(payload).execute()
                        st.success("Deportista registrado correctamente. Su código se asignó automáticamente.")
                        st.rerun()
                    except Exception:
                        st.error("No se pudo guardar el deportista. Revisa si la cédula ya está registrada y confirma que ejecutaste la migración SQL.")

    with tab_consulta:
        if jugadores:
            busqueda = st.text_input("Buscar por nombre o apellido", key="buscar_jugador")
            filtrados = [j for j in jugadores if busqueda.lower() in nombre_jugador(j).lower()] if busqueda.strip() else jugadores
            filas = [{
                "Código": j.get("codigo_jugador") or "Pendiente",
                "Deportista": nombre_jugador(j),
                "Categoría": categoria_jugador(j),
                "Fecha de nacimiento": fecha_legible(j.get("fecha_nacimiento")),
                "Curso": j.get("curso") or "",
                "Posición": j.get("posicion_principal") or "",
                "Estado": j.get("estado") or "",
            } for j in filtrados]
            st.dataframe(filas, use_container_width=True, hide_index=True)
            st.caption(f"Deportistas visibles: {len(filtrados)}")
        else:
            st.info("No hay deportistas visibles para tu cuenta.")

    with tab_expediente:
        if not jugadores:
            st.info("No hay deportistas disponibles para consultar.")
        else:
            opciones_jugadores = {f"{nombre_jugador(j)} · {categoria_jugador(j)}": j["id"] for j in jugadores}
            elegido = st.selectbox("Selecciona un deportista", list(opciones_jugadores.keys()), key="expediente_jugador")
            jugador_id = opciones_jugadores[elegido]
            jugador = next(j for j in jugadores if j["id"] == jugador_id)
            st.markdown(f'<div class="hero"><div class="eyebrow">Expediente individual</div><h2>{nombre_jugador(jugador)}</h2><p>{jugador.get("codigo_jugador") or "Código pendiente"} · {categoria_jugador(jugador)} · {jugador.get("posicion_principal") or "Posición por definir"}</p></div>', unsafe_allow_html=True)
            foto_col, datos_col = st.columns([1, 4])
            with foto_col:
                if jugador.get("fotografia_url"):
                    try:
                        st.image(jugador["fotografia_url"], width=125, caption="Fotografía tamaño carnet")
                    except Exception:
                        st.caption("Fotografía no disponible")
                else:
                    st.caption("Sin fotografía")
            with datos_col:
                st.write(f"**Código:** {jugador.get('codigo_jugador') or 'Pendiente'}")
                st.write(f"**Cédula:** {jugador.get('cedula') or 'No registrada'}")
                st.write(f"**Fecha de nacimiento:** {fecha_legible(jugador.get('fecha_nacimiento'))} · **Fecha de ingreso:** {fecha_legible(jugador.get('fecha_ingreso'))}")
                st.write(f"**Curso:** {jugador.get('curso') or 'No registrado'} · **Nivel competitivo:** {jugador.get('nivel_competitivo') or 'No definido'}")
            a, b, c, d = st.columns(4)
            a.metric("Categoría", categoria_jugador(jugador))
            b.metric("Posición", jugador.get("posicion_principal") or "—")
            c.metric("Estatura", f"{jugador.get('estatura')} cm" if jugador.get("estatura") else "—")
            d.metric("Pie dominante", jugador.get("pie_dominante") or "—")

            # Leer registros asociados al jugador; Supabase RLS determina lo permitido.
            try:
                hist_dep = (supabase.table("historial_deportivo").select("*").eq("jugador_id", jugador_id).order("temporada", desc=True).execute().data or [])
            except Exception:
                hist_dep = []
            try:
                hist_acad = (supabase.table("historial_academico").select("*").eq("jugador_id", jugador_id).order("periodo_academico", desc=True).execute().data or [])
            except Exception:
                hist_acad = []
            try:
                evals = (supabase.table("evaluaciones_integrales").select("*").eq("jugador_id", jugador_id).order("fecha_evaluacion", desc=True).execute().data or [])
            except Exception:
                evals = []
            try:
                evidencias = (supabase.table("evidencias_deportivas").select("*").eq("jugador_id", jugador_id).order("created_at", desc=True).execute().data or [])
            except Exception:
                evidencias = []

            st.divider()
            tab_resumen, tab_deportivo, tab_academico, tab_eval, tab_evidencias, tab_pdf = st.tabs(["Resumen", "Historial deportivo", "Historial académico", "Evaluaciones", "Evidencias", "Exportar PDF"])

            with tab_resumen:
                st.markdown("#### Datos del deportista")
                st.write(f"**Fecha de nacimiento:** {fecha_legible(jugador.get('fecha_nacimiento'))}")
                st.write(f"**Curso escolar:** {jugador.get('curso') or 'No registrado'}")
                st.write(f"**Posición secundaria:** {jugador.get('posicion_secundaria') or 'No registrada'}")
                st.write(f"**Peso:** {str(jugador.get('peso')) + ' kg' if jugador.get('peso') else 'No registrado'}")
                st.write(f"**Estado:** {jugador.get('estado') or 'No registrado'}")
                st.caption("El historial conserva registros por periodo; evita sobrescribir evaluaciones o temporadas anteriores.")

            with tab_deportivo:
                st.markdown("#### Temporadas y trayectoria")
                if hist_dep:
                    for reg in hist_dep:
                        with st.expander(f"{reg.get('temporada', 'Temporada')} · {reg.get('club_equipo') or 'Equipo no indicado'}"):
                            st.write(f"Categoría: {reg.get('categoria') or '—'} · Posición: {reg.get('posicion') or '—'} · Camiseta: {reg.get('numero_camiseta') or '—'}")
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("Partidos", reg.get("partidos_disputados") or 0)
                            m2.metric("Minutos", reg.get("minutos_jugados") or 0)
                            m3.metric("Goles", reg.get("goles") or 0)
                            m4.metric("Asistencias", reg.get("asistencias") or 0)
                            st.write(f"**Torneos/competiciones:** {reg.get('competiciones') or '—'}")
                            st.write(f"**Premios:** {reg.get('premios') or '—'}")
                            st.write(f"**Convocatorias/selecciones:** {reg.get('convocatorias') or '—'}")
                            st.write(f"**Logros:** {reg.get('logros') or '—'}")
                            if reg.get("observaciones"):
                                st.write(f"**Observaciones:** {reg['observaciones']}")
                else:
                    st.info("Todavía no hay temporadas deportivas registradas.")
                if puede_editar(rol):
                    with st.expander("➕ Añadir temporada deportiva"):
                        with st.form(f"form_histdep_{jugador_id}"):
                            t1, t2 = st.columns(2)
                            temporada = t1.text_input("Temporada *", placeholder="2026-2027")
                            club_equipo = t2.text_input("Club o equipo")
                            t3, t4, t5 = st.columns(3)
                            categoria_hist = t3.text_input("Categoría")
                            posicion_hist = t4.text_input("Posición")
                            camiseta = t5.number_input("Número de camiseta", min_value=0, max_value=99, value=0)
                            t6, t7, t8, t9 = st.columns(4)
                            partidos = t6.number_input("Partidos", min_value=0, value=0)
                            minutos = t7.number_input("Minutos", min_value=0, value=0)
                            goles = t8.number_input("Goles", min_value=0, value=0)
                            asistencias = t9.number_input("Asistencias", min_value=0, value=0)
                            competiciones = st.text_area("Torneos y competiciones")
                            premios = st.text_area("Premios")
                            convocatorias = st.text_area("Convocatorias y selecciones")
                            logros = st.text_area("Otros logros y reconocimientos")
                            obs_dep = st.text_area("Observaciones")
                            guardar_dep = st.form_submit_button("Guardar temporada", use_container_width=True)
                        if guardar_dep:
                            if not temporada.strip():
                                st.error("La temporada es obligatoria.")
                            else:
                                payload = {
                                    "jugador_id": jugador_id, "temporada": temporada.strip(),
                                    "club_equipo": club_equipo.strip() or None,
                                    "categoria": categoria_hist.strip() or None,
                                    "posicion": posicion_hist.strip() or None,
                                    "numero_camiseta": camiseta or None,
                                    "partidos_disputados": partidos, "minutos_jugados": minutos,
                                    "goles": goles, "asistencias": asistencias,
                                    "competiciones": competiciones.strip() or None,
                                    "premios": premios.strip() or None,
                                    "convocatorias": convocatorias.strip() or None,
                                    "logros": logros.strip() or None,
                                    "observaciones": obs_dep.strip() or None,
                                    "registrado_por": str(usuario.id),
                                }
                                try:
                                    supabase.table("historial_deportivo").insert(payload).execute()
                                    st.success("Temporada guardada.")
                                    st.rerun()
                                except Exception:
                                    st.error("No se pudo guardar la temporada. Verifica las políticas de acceso en Supabase.")

            with tab_academico:
                if rol_padre:
                    st.warning("El historial académico no está habilitado para representantes en esta versión.")
                else:
                    st.markdown("#### Evolución académica")
                    if hist_acad:
                        st.dataframe([{
                            "Periodo": r.get("periodo_academico"), "Curso": r.get("curso") or "",
                            "Promedio": r.get("promedio") if r.get("promedio") is not None else "",
                            "Materias destacadas": r.get("materias_destacadas") or "",
                            "Reconocimientos": r.get("reconocimientos") or "",
                            "Inglés": r.get("ingles") or "",
                            "Comportamiento": r.get("comportamiento") if r.get("comportamiento") is not None else "",
                            "Idiomas": r.get("idiomas") or "",
                        } for r in hist_acad], use_container_width=True, hide_index=True)
                    else:
                        st.info("No hay historial académico visible para esta cuenta.")
                    if rol_admin:
                        with st.expander("➕ Añadir periodo académico"):
                            with st.form(f"form_academico_{jugador_id}"):
                                periodo = st.text_input("Periodo académico *", placeholder="2026-2027")
                                curso_acad = st.text_input("Curso")
                                promedio = st.number_input("Promedio", min_value=0.0, max_value=10.0, value=0.0, step=0.1)
                                materias = st.text_area("Materias destacadas")
                                reconocimientos = st.text_area("Reconocimientos académicos")
                                idiomas = st.text_input("Otros idiomas")
                                ingles = st.selectbox("Nivel de inglés", ["No evaluado", "Básico", "Intermedio", "Avanzado", "Bilingüe"])
                                comportamiento = st.number_input("Comportamiento (escala 1 a 10)", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                                extracurriculares = st.text_area("Actividades extracurriculares")
                                obs_acad = st.text_area("Observaciones")
                                guardar_acad = st.form_submit_button("Guardar periodo", use_container_width=True)
                            if guardar_acad:
                                if not periodo.strip():
                                    st.error("El periodo académico es obligatorio.")
                                else:
                                    payload = {
                                        "jugador_id": jugador_id, "periodo_academico": periodo.strip(),
                                        "curso": curso_acad.strip() or None,
                                        "promedio": promedio if promedio > 0 else None,
                                        "materias_destacadas": materias.strip() or None,
                                        "reconocimientos": reconocimientos.strip() or None,
                                        "idiomas": idiomas.strip() or None,
                                        "ingles": None if ingles == "No evaluado" else ingles,
                                        "comportamiento": comportamiento if comportamiento > 0 else None,
                                        "actividades_extracurriculares": extracurriculares.strip() or None,
                                        "observaciones": obs_acad.strip() or None,
                                        "registrado_por": str(usuario.id),
                                    }
                                    try:
                                        supabase.table("historial_academico").insert(payload).execute()
                                        st.success("Periodo académico guardado.")
                                        st.rerun()
                                    except Exception:
                                        st.error("No se pudo guardar el periodo. Esta tabla está configurada para administración.")

            with tab_eval:
                st.markdown("#### Evolución del deportista")
                st.caption("Técnica y actitudinal se califican de 1 a 10. En pruebas físicas registra los segundos obtenidos; un tiempo menor es mejor. Course Navette se registra como nivel/etapa alcanzada; un valor mayor es mejor.")
                if evals:
                    grafico_evolucion(evals, [("pase_efectividad", "Pase"), ("conduccion", "Conducción"), ("tiros_efectividad", "Tiros al arco")], "Evolución técnica · escala 1 a 10")
                    grafico_evolucion(evals, [("disciplina", "Disciplina"), ("compromiso", "Compromiso"), ("responsabilidad", "Responsabilidad"), ("trabajo_equipo", "Trabajo en equipo"), ("capacidad_esfuerzo", "Capacidad de esfuerzo")], "Evolución actitudinal · escala 1 a 10")
                    grafico_evolucion(evals, [("velocidad_10m", "10 m (s)"), ("velocidad_20m", "20 m (s)"), ("illinois", "Illinois (s)")], "Pruebas de velocidad y agilidad", "En estas pruebas, la mejora normalmente se observa cuando disminuye el tiempo.")
                    grafico_evolucion(evals, [("course_navette", "Nivel/etapa")], "Course Navette")
                    st.markdown("#### Evaluaciones registradas")
                    for ev in sorted(evals, key=lambda x: str(x.get("fecha_evaluacion") or ""), reverse=True):
                        with st.expander(f"Evaluación · {fecha_legible(ev.get('fecha_evaluacion'))}"):
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Efectividad de pase", ev.get("pase_efectividad") if ev.get("pase_efectividad") is not None else "—")
                            c2.metric("Conducción", ev.get("conduccion") if ev.get("conduccion") is not None else "—")
                            c3.metric("Efectividad de tiros", ev.get("tiros_efectividad") if ev.get("tiros_efectividad") is not None else "—")
                            st.write(f"**Físicas:** 10 m: {ev.get('velocidad_10m') if ev.get('velocidad_10m') is not None else '—'} s · 20 m: {ev.get('velocidad_20m') if ev.get('velocidad_20m') is not None else '—'} s · Illinois: {ev.get('illinois') if ev.get('illinois') is not None else '—'} s · Course Navette: {ev.get('course_navette') if ev.get('course_navette') is not None else '—'}")
                            st.write(f"**Actitudinal:** Disciplina {ev.get('disciplina') if ev.get('disciplina') is not None else '—'} · Compromiso {ev.get('compromiso') if ev.get('compromiso') is not None else '—'} · Responsabilidad {ev.get('responsabilidad') if ev.get('responsabilidad') is not None else '—'} · Trabajo en equipo {ev.get('trabajo_equipo') if ev.get('trabajo_equipo') is not None else '—'} · Esfuerzo {ev.get('capacidad_esfuerzo') if ev.get('capacidad_esfuerzo') is not None else '—'}")
                            st.write(f"**Fortalezas:** {ev.get('fortalezas') or '—'}")
                            st.write(f"**Aspectos por mejorar:** {ev.get('aspectos_mejora') or '—'}")
                            st.write(f"**Recomendaciones:** {ev.get('recomendaciones') or '—'}")
                else:
                    st.info("No hay evaluaciones registradas. Cuando guardes la primera, aparecerá aquí; con dos o más fechas podrás observar la evolución.")
                if puede_editar(rol):
                    with st.expander("➕ Registrar nueva evaluación"):
                        with st.form(f"form_eval_detallada_{jugador_id}"):
                            fecha_eval = st.date_input("Fecha de evaluación", value=date.today(), format="DD/MM/YYYY")
                            st.markdown("##### Técnica · escala 1 a 10")
                            c1, c2, c3 = st.columns(3)
                            pase = c1.number_input("Efectividad de pase", min_value=0.0, max_value=10.0, value=0.0, step=0.5, help="0 = sin registrar; de 1 a 10 = puntuación")
                            conduccion = c2.number_input("Conducción", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            tiros = c3.number_input("Efectividad de tiros al arco", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            st.markdown("##### Física · registra tiempos reales en segundos")
                            f1, f2, f3, f4 = st.columns(4)
                            vel10 = f1.number_input("Velocidad 10 m (s)", min_value=0.0, max_value=120.0, value=0.0, step=0.01, format="%.3f")
                            vel20 = f2.number_input("Velocidad 20 m (s)", min_value=0.0, max_value=120.0, value=0.0, step=0.01, format="%.3f")
                            illinois = f3.number_input("Illinois (s)", min_value=0.0, max_value=300.0, value=0.0, step=0.01, format="%.3f")
                            navette = f4.number_input("Course Navette (nivel/etapa)", min_value=0.0, max_value=30.0, value=0.0, step=0.5)
                            st.markdown("##### Actitudinal · escala 1 a 10")
                            att = st.columns(5)
                            disciplina = att[0].number_input("Disciplina", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            compromiso = att[1].number_input("Compromiso", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            responsabilidad = att[2].number_input("Responsabilidad", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            trabajo_equipo = att[3].number_input("Trabajo en equipo", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            esfuerzo = att[4].number_input("Capacidad de esfuerzo", min_value=0.0, max_value=10.0, value=0.0, step=0.5)
                            fortalezas = st.text_area("Fortalezas")
                            aspectos_mejora = st.text_area("Aspectos por mejorar")
                            recomendaciones = st.text_area("Recomendaciones")
                            guardar_eval = st.form_submit_button("Guardar evaluación", use_container_width=True)
                        if guardar_eval:
                            payload = {
                                "jugador_id": jugador_id,
                                "fecha_evaluacion": fecha_eval.isoformat(),
                                "evaluador_id": str(usuario.id),
                                "pase_efectividad": pase if pase > 0 else None,
                                "conduccion": conduccion if conduccion > 0 else None,
                                "tiros_efectividad": tiros if tiros > 0 else None,
                                "velocidad_10m": vel10 if vel10 > 0 else None,
                                "velocidad_20m": vel20 if vel20 > 0 else None,
                                "illinois": illinois if illinois > 0 else None,
                                "course_navette": navette if navette > 0 else None,
                                "disciplina": disciplina if disciplina > 0 else None,
                                "compromiso": compromiso if compromiso > 0 else None,
                                "responsabilidad": responsabilidad if responsabilidad > 0 else None,
                                "trabajo_equipo": trabajo_equipo if trabajo_equipo > 0 else None,
                                "capacidad_esfuerzo": esfuerzo if esfuerzo > 0 else None,
                                "fortalezas": fortalezas.strip() or None,
                                "aspectos_mejora": aspectos_mejora.strip() or None,
                                "recomendaciones": recomendaciones.strip() or None,
                            }
                            if not any(payload[k] is not None for k in ["pase_efectividad", "conduccion", "tiros_efectividad", "velocidad_10m", "velocidad_20m", "illinois", "course_navette", "disciplina", "compromiso", "responsabilidad", "trabajo_equipo", "capacidad_esfuerzo"]):
                                st.error("Registra al menos un resultado antes de guardar.")
                            else:
                                try:
                                    supabase.table("evaluaciones_integrales").insert(payload).execute()
                                    st.success("Evaluación guardada. Se incorporará al gráfico de evolución.")
                                    st.rerun()
                                except Exception:
                                    st.error("No se pudo guardar la evaluación. Ejecuta primero migracion_ficha_evaluaciones.sql y revisa los permisos de Supabase.")

            with tab_evidencias:
                st.markdown("#### Material de seguimiento")
                if evidencias:
                    for ev in evidencias:
                        with st.expander(f"{ev.get('titulo', 'Evidencia')} · {ev.get('tipo', 'otro')}"):
                            st.write(f"**Fecha:** {fecha_legible(ev.get('fecha_evidencia'))}")
                            st.write(ev.get("descripcion") or "Sin descripción.")
                            if ev.get("url"):
                                st.link_button("Abrir evidencia", ev["url"])
                            if ev.get("incluir_perfil_publico"):
                                st.caption("Marcada para posible perfil compartible; confirma autorización antes de divulgarla.")
                else:
                    st.info("No hay evidencias registradas.")
                if puede_editar(rol):
                    with st.expander("➕ Añadir evidencia"):
                        with st.form(f"form_evidencia_{jugador_id}"):
                            titulo_ev = st.text_input("Título *")
                            tipo_ev = st.selectbox("Tipo", ["fotografia", "video", "partido_completo", "certificado", "reconocimiento", "convocatoria", "informe", "otro"])
                            url_ev = st.text_input("Enlace (URL)")
                            fecha_ev = st.date_input("Fecha de la evidencia", value=date.today(), format="DD/MM/YYYY")
                            desc_ev = st.text_area("Descripción")
                            compartir_ev = st.checkbox("Marcar para posible perfil compartible (no publica automáticamente)", value=False)
                            guardar_ev = st.form_submit_button("Guardar evidencia", use_container_width=True)
                        if guardar_ev:
                            if not titulo_ev.strip():
                                st.error("El título es obligatorio.")
                            else:
                                payload = {"jugador_id": jugador_id, "titulo": titulo_ev.strip(), "tipo": tipo_ev, "url": url_ev.strip() or None, "fecha_evidencia": fecha_ev.isoformat(), "descripcion": desc_ev.strip() or None, "incluir_perfil_publico": compartir_ev, "registrado_por": str(usuario.id)}
                                try:
                                    supabase.table("evidencias_deportivas").insert(payload).execute()
                                    st.success("Evidencia guardada.")
                                    st.rerun()
                                except Exception:
                                    st.error("No se pudo guardar la evidencia. Verifica las políticas de acceso.")

            with tab_pdf:
                st.markdown(f"#### Generar expediente descargable · {jugador.get('institucion') or INSTITUCION_JUVENTUD}")
                logo_pdf = ruta_logo(jugador.get("institucion") or INSTITUCION_JUVENTUD)
                if logo_pdf:
                    st.caption("El PDF utilizará el logo de la institución correspondiente.")
                else:
                    st.warning("Aún falta subir el archivo del logo de esta institución a la carpeta assets del repositorio. El PDF se generará sin imagen de logo hasta entonces.")
                st.warning("El PDF puede contener datos personales de un menor. Guárdalo de forma segura y compártelo únicamente con autorización del representante legal y con destinatarios autorizados.")
                incluir_academico_pdf = st.checkbox("Incluir historial académico (información confidencial)", value=False)
                incluir_eval_pdf = st.checkbox("Incluir evaluaciones integrales (información confidencial)", value=False)
                if rol_padre:
                    incluir_academico_pdf = False
                    incluir_eval_pdf = False
                try:
                    pdf_bytes = generar_pdf(jugador, hist_acad, hist_dep, evals, evidencias, incluir_academico_pdf, incluir_eval_pdf)
                    prefijo_pdf = "surcos" if (jugador.get("institucion") or INSTITUCION_JUVENTUD) == INSTITUCION_SURCOS else "juventud"
                    nombre_archivo = f"expediente_{prefijo_pdf}_{jugador.get('apellidos','').replace(' ','_')}_{jugador.get('nombres','').replace(' ','_')}.pdf"
                    st.download_button("⬇️ Descargar expediente PDF", data=pdf_bytes, file_name=nombre_archivo, mime="application/pdf", use_container_width=True)
                except Exception:
                    st.error("No se pudo generar el PDF. Revisa que reportlab esté instalado en requirements.txt.")

# ============================================================
# USUARIOS Y REPRESENTANTES
# ============================================================
elif seccion == "Usuarios y representantes":
    encabezado_seccion("🔐 Usuarios y representantes", "Gestión de accesos y vínculos familiares.")
    if rol_admin:
        st.info("Por seguridad, la creación de usuarios y la asignación de representantes deben configurarse con un flujo administrativo controlado. Esta pantalla no modifica cuentas ni vínculos todavía.")
        st.write("Funciones previstas: activar/desactivar perfiles, asignar roles, vincular representantes con deportistas y asignar entrenadores a categorías.")
    else:
        st.info("Esta sección está reservada al administrador del sistema.")
