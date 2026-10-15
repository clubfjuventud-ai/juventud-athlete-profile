import io
from datetime import date

import streamlit as st
from supabase import create_client

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
            "id, nombres, apellidos, fecha_nacimiento, curso, posicion_principal, "
            "posicion_secundaria, pie_dominante, estatura, peso, fotografia_url, "
            "estado, categoria_id, categorias(nombre)"
        )
        .order("apellidos")
        .execute()
    )
    return respuesta.data or []


def nombre_jugador(jugador):
    return f"{jugador.get('apellidos', '')}, {jugador.get('nombres', '')}".strip(", ")


def categoria_jugador(jugador):
    categoria = jugador.get("categorias")
    if isinstance(categoria, list):
        categoria = categoria[0] if categoria else None
    return (categoria or {}).get("nombre", "Sin categoría")


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
    elementos = [
        Paragraph("CLUB FORMATIVO DEPORTIVO ESPECIALIZADO", estilos["Marca"]),
        Paragraph("JUVENTUD", estilos["TituloClub"]),
        Paragraph("EXPEDIENTE DEL ESTUDIANTE-ATLETA · USO INTERNO", estilos["SubtituloClub"]),
    ]

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
        ("Nombre completo", nombre_jugador(jugador)),
        ("Fecha de nacimiento", fecha_legible(jugador.get("fecha_nacimiento"))),
        ("Categoría", categoria_jugador(jugador)),
        ("Curso escolar", jugador.get("curso")),
        ("Posición principal", jugador.get("posicion_principal")),
        ("Posición secundaria", jugador.get("posicion_secundaria")),
        ("Pie dominante", jugador.get("pie_dominante")),
        ("Estatura (cm)", jugador.get("estatura")),
        ("Peso (kg)", jugador.get("peso")),
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
                    Paragraph(f"Reconocimientos: {registro.get('reconocimientos') or '—'} · Idiomas: {registro.get('idiomas') or '—'}", estilos["TextoPequeno"]),
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
                    ("Técnica", ev.get("tecnica")), ("Táctica", ev.get("tactica")),
                    ("Toma de decisiones", ev.get("toma_decisiones")), ("Condición física", ev.get("condicion_fisica")),
                    ("Actitud y mentalidad", ev.get("actitud_mentalidad")), ("Aprendizaje", ev.get("capacidad_aprendizaje")),
                    ("Adaptabilidad", ev.get("adaptabilidad")), ("Rendimiento competitivo", ev.get("rendimiento_competitivo")),
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

st.markdown('<div class="eyebrow">Club Formativo Deportivo Especializado</div>', unsafe_allow_html=True)
st.title("⚽ Juventud Athlete Profile")
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
st.sidebar.markdown("## ⚽ CLUB JUVENTUD")
st.sidebar.caption("JUVENTUD CON PROPÓSITO Y FUTURO")
st.sidebar.write(f"**{nombre}**")
st.sidebar.caption(f"Rol: {rol.capitalize()}")
st.sidebar.divider()
seccion = st.sidebar.radio(
    "MENÚ PRINCIPAL",
    ["Inicio", "Deportistas", "Evaluaciones", "Asistencia", "Competencias", "Usuarios y representantes"],
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
elif seccion == "Deportistas":
    encabezado_seccion("👥 Gestión de deportistas", "Registro, consulta y expediente individual.")
    tab_registro, tab_consulta, tab_expediente = st.tabs(["➕ Registrar", "📋 Consultar", "🗂️ Expediente individual"])

    # Categorías activas
    try:
        categorias_resultado = supabase.table("categorias").select("id, nombre").eq("activa", True).order("nombre").execute()
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
            with st.form("formulario_deportista", clear_on_submit=True):
                st.markdown("#### Datos personales")
                c1, c2 = st.columns(2)
                nombres = c1.text_input("Nombres *")
                apellidos = c2.text_input("Apellidos *")
                c3, c4 = st.columns(2)
                fecha_nacimiento = c3.date_input("Fecha de nacimiento", value=date(2015, 1, 1), min_value=date(1990, 1, 1), max_value=date.today(), format="DD/MM/YYYY")
                categoria_nombre = c4.selectbox("Categoría *", list(mapa_categorias.keys()), index=None, placeholder="Selecciona una categoría")
                curso = st.text_input("Curso escolar")
                st.markdown("#### Datos deportivos")
                posiciones = ["Portero/a", "Defensa central", "Lateral derecho", "Lateral izquierdo", "Mediocentro defensivo", "Mediocentro", "Mediocentro ofensivo", "Extremo derecho", "Extremo izquierdo", "Delantero/a"]
                c5, c6, c7 = st.columns(3)
                posicion_principal = c5.selectbox("Posición principal", ["No definida"] + posiciones)
                posicion_secundaria = c6.selectbox("Posición secundaria", ["No definida"] + posiciones)
                pie_dominante = c7.selectbox("Pie dominante", ["No definido", "Derecho", "Izquierdo", "Ambidiestro"])
                c8, c9, c10 = st.columns(3)
                estatura = c8.number_input("Estatura (cm)", min_value=0, max_value=250, value=0)
                peso = c9.number_input("Peso (kg)", min_value=0.0, max_value=200.0, value=0.0, step=0.5)
                fotografia_url = c10.text_input("URL de fotografía (opcional)")
                guardar = st.form_submit_button("Guardar deportista", use_container_width=True)
            if guardar:
                if not nombres.strip() or not apellidos.strip() or not categoria_nombre:
                    st.error("Completa los nombres, apellidos y categoría.")
                else:
                    payload = {
                        "nombres": nombres.strip(), "apellidos": apellidos.strip(),
                        "fecha_nacimiento": fecha_nacimiento.isoformat(),
                        "categoria_id": mapa_categorias[categoria_nombre],
                        "curso": curso.strip() or None,
                        "posicion_principal": None if posicion_principal == "No definida" else posicion_principal,
                        "posicion_secundaria": None if posicion_secundaria == "No definida" else posicion_secundaria,
                        "pie_dominante": None if pie_dominante == "No definido" else pie_dominante,
                        "estatura": estatura if estatura > 0 else None,
                        "peso": peso if peso > 0 else None,
                        "fotografia_url": fotografia_url.strip() or None,
                        "estado": "activo",
                    }
                    try:
                        supabase.table("jugadores").insert(payload).execute()
                        st.success("Deportista registrado correctamente.")
                        st.rerun()
                    except Exception:
                        st.error("No se pudo guardar el deportista. Verifica los permisos y los datos obligatorios de Supabase.")

    with tab_consulta:
        if jugadores:
            busqueda = st.text_input("Buscar por nombre o apellido", key="buscar_jugador")
            filtrados = [j for j in jugadores if busqueda.lower() in nombre_jugador(j).lower()] if busqueda.strip() else jugadores
            filas = [{
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
            st.markdown(f'<div class="hero"><div class="eyebrow">Expediente individual</div><h2>{nombre_jugador(jugador)}</h2><p>{categoria_jugador(jugador)} · {jugador.get("posicion_principal") or "Posición por definir"}</p></div>', unsafe_allow_html=True)
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
                            st.write(f"**Competiciones:** {reg.get('competiciones') or '—'}")
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
                            competiciones = st.text_area("Competiciones")
                            logros = st.text_area("Logros y reconocimientos")
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
                                idiomas = st.text_input("Idiomas")
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
                st.markdown("#### Seguimiento integral (escala 1 a 10)")
                if evals:
                    for ev in evals:
                        with st.expander(f"Evaluación · {fecha_legible(ev.get('fecha_evaluacion'))}"):
                            metricas = [
                                ("Técnica", "tecnica"), ("Táctica", "tactica"),
                                ("Toma de decisiones", "toma_decisiones"), ("Condición física", "condicion_fisica"),
                                ("Actitud y mentalidad", "actitud_mentalidad"), ("Capacidad de aprendizaje", "capacidad_aprendizaje"),
                                ("Adaptabilidad", "adaptabilidad"), ("Rendimiento competitivo", "rendimiento_competitivo"),
                            ]
                            cols = st.columns(4)
                            for idx, (etiqueta, campo) in enumerate(metricas):
                                valor = ev.get(campo)
                                cols[idx % 4].metric(etiqueta, valor if valor is not None else "—")
                            st.write(f"**Fortalezas:** {ev.get('fortalezas') or '—'}")
                            st.write(f"**Aspectos por mejorar:** {ev.get('aspectos_mejora') or '—'}")
                            st.write(f"**Recomendaciones:** {ev.get('recomendaciones') or '—'}")
                else:
                    st.info("No hay evaluaciones integrales registradas.")
                if puede_editar(rol):
                    with st.expander("➕ Registrar evaluación integral"):
                        with st.form(f"form_eval_{jugador_id}"):
                            fecha_eval = st.date_input("Fecha de evaluación", value=date.today(), format="DD/MM/YYYY")
                            etiquetas_metricas = [
                                ("Técnica", "tecnica"), ("Táctica", "tactica"),
                                ("Toma de decisiones", "toma_decisiones"), ("Condición física", "condicion_fisica"),
                                ("Actitud y mentalidad", "actitud_mentalidad"), ("Capacidad de aprendizaje", "capacidad_aprendizaje"),
                                ("Adaptabilidad", "adaptabilidad"), ("Rendimiento competitivo", "rendimiento_competitivo"),
                            ]
                            valores_metricas = {}
                            cols = st.columns(4)
                            for idx, (etiqueta, campo) in enumerate(etiquetas_metricas):
                                valores_metricas[campo] = cols[idx % 4].selectbox(etiqueta, ["Sin evaluar"] + list(range(1, 11)), key=f"{campo}_{jugador_id}")
                            fortalezas = st.text_area("Fortalezas")
                            aspectos_mejora = st.text_area("Aspectos por mejorar")
                            recomendaciones = st.text_area("Recomendaciones de trabajo")
                            guardar_eval = st.form_submit_button("Guardar evaluación", use_container_width=True)
                        if guardar_eval:
                            payload = {"jugador_id": jugador_id, "fecha_evaluacion": fecha_eval.isoformat(), "evaluador_id": str(usuario.id), "fortalezas": fortalezas.strip() or None, "aspectos_mejora": aspectos_mejora.strip() or None, "recomendaciones": recomendaciones.strip() or None}
                            payload.update({campo: (valor if isinstance(valor, int) else None) for campo, valor in valores_metricas.items()})
                            try:
                                supabase.table("evaluaciones_integrales").insert(payload).execute()
                                st.success("Evaluación guardada correctamente.")
                                st.rerun()
                            except Exception:
                                st.error("No se pudo guardar la evaluación. Verifica que el usuario tenga permisos de entrenador o administrador.")

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
                st.markdown("#### Generar expediente descargable")
                st.warning("El PDF puede contener datos personales de un menor. Guárdalo de forma segura y compártelo únicamente con autorización del representante legal y con destinatarios autorizados.")
                incluir_academico_pdf = st.checkbox("Incluir historial académico (información confidencial)", value=False)
                incluir_eval_pdf = st.checkbox("Incluir evaluaciones integrales (información confidencial)", value=False)
                if rol_padre:
                    incluir_academico_pdf = False
                    incluir_eval_pdf = False
                try:
                    pdf_bytes = generar_pdf(jugador, hist_acad, hist_dep, evals, evidencias, incluir_academico_pdf, incluir_eval_pdf)
                    nombre_archivo = f"expediente_juventud_{jugador.get('apellidos','').replace(' ','_')}_{jugador.get('nombres','').replace(' ','_')}.pdf"
                    st.download_button("⬇️ Descargar expediente PDF", data=pdf_bytes, file_name=nombre_archivo, mime="application/pdf", use_container_width=True)
                except Exception:
                    st.error("No se pudo generar el PDF. Revisa que reportlab esté instalado en requirements.txt.")

# ============================================================
# EVALUACIONES: ACCESO DIRECTO
# ============================================================
elif seccion == "Evaluaciones":
    encabezado_seccion("📊 Evaluaciones integrales", "Consulta evaluaciones y entra al expediente del deportista para registrar una nueva.")
    st.write("Las evaluaciones se guardan como registros históricos para observar la evolución, no para reemplazar la evaluación anterior.")
    if jugadores:
        lista_eval = []
        for j in jugadores:
            try:
                regs = supabase.table("evaluaciones_integrales").select("fecha_evaluacion, tecnica, tactica, toma_decisiones, condicion_fisica, actitud_mentalidad, capacidad_aprendizaje, adaptabilidad, rendimiento_competitivo").eq("jugador_id", j["id"]).order("fecha_evaluacion", desc=True).limit(1).execute().data or []
                if regs:
                    r = regs[0]
                    lista_eval.append({"Deportista": nombre_jugador(j), "Categoría": categoria_jugador(j), "Fecha": fecha_legible(r.get("fecha_evaluacion")), "Técnica": r.get("tecnica"), "Táctica": r.get("tactica"), "Decisiones": r.get("toma_decisiones"), "Físico": r.get("condicion_fisica"), "Mentalidad": r.get("actitud_mentalidad")})
            except Exception:
                pass
        if lista_eval:
            st.dataframe(lista_eval, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no existen evaluaciones integrales visibles.")
    else:
        st.info("No hay deportistas visibles para tu cuenta.")
    st.caption("Para registrar una evaluación, abre Deportistas → Expediente individual → Evaluaciones.")

# ============================================================
# ASISTENCIA
# ============================================================
elif seccion == "Asistencia":
    encabezado_seccion("📅 Control de asistencia", "Registro de participación en entrenamientos.")
    st.info("El módulo de asistencia aún no se ha ampliado en esta versión. Se mantiene pendiente para evitar modificar la estructura actual sin revisar las columnas de la tabla asistencia.")

# ============================================================
# COMPETENCIAS
# ============================================================
elif seccion == "Competencias":
    encabezado_seccion("🏆 Competencias", "Partidos, torneos, convocatorias y resultados.")
    st.info("El módulo de competencias se ampliará en una siguiente etapa, después de revisar las columnas actuales de competencias y estadisticas_competencia.")

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
