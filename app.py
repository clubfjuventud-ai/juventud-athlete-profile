import logging
from html import escape
from datetime import date

import streamlit as st
from supabase import create_client

from modules.configuracion import INSTITUCION_JUVENTUD, INSTITUCION_SURCOS
from modules.autenticacion import conectar_supabase, cerrar_sesion, SesionCaducada
from modules.utilidades import (
    encabezado_seccion, obtener_jugadores, ruta_logo, mostrar_marca,
    nombre_jugador, categoria_jugador, categoria_por_fecha,
    fecha_legible, puede_editar, opciones_expediente, obtener_paginas,
)
from modules.interfaz import aplicar_estilo, mostrar_cabecera_jugador, mostrar_pulso, preparar_pdf, seleccionar_representado
from modules.entrenamientos import Contexto, mostrar_espacio
from modules.analisis_rendimiento import mostrar_analisis_rendimiento
from modules.evaluaciones_visuales import mostrar_panel_evaluaciones, validar_resultados


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="Surcos · Desarrollo deportivo" if st.session_state.get("menu_principal") == "Colegio Surcos" else "Perfil deportivo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="auto",
)


# La identidad institucional se aplica después de resolver la navegación.
if "sesion" not in st.session_state:
    st.session_state.sesion = None

# ============================================================
# LOGIN
# ============================================================
if st.session_state.sesion is None:
    aplicar_estilo()
    st.title("Desarrollo del estudiante-atleta")
    st.caption("Accede a tu espacio de seguimiento deportivo y formativo.")
    izquierda, centro, derecha = st.columns([1, 1.25, 1])
    with centro:
        st.markdown(
            '<div class="hero"><div class="eyebrow">Deporte · Formación · Evolución</div>'
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
try:
    supabase = conectar_supabase()
    usuario = st.session_state.sesion.user
    resultado_perfil = (
        supabase.table("perfiles")
        .select("*")
        .eq("id", str(usuario.id))
        .maybe_single()
        .execute()
    )
    perfil = resultado_perfil.data
except SesionCaducada:
    st.warning("Tu sesión ha caducado. Vuelve a iniciar sesión.")
    if st.button("Volver al inicio de sesión"):
        st.rerun()
    st.stop()
except Exception as error:
    logging.getLogger(__name__).warning("Consulta de perfil fallida (%s)", type(error).__name__)
    st.error("No se pudo consultar tu perfil. Comprueba la conexión y vuelve a iniciar sesión.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
    st.stop()

if not perfil or not perfil.get("activo"):
    st.warning("Tu cuenta no tiene un perfil activo. Contacta al administrador.")
    if st.button("Cerrar sesión"):
        cerrar_sesion()
    st.stop()

rol_real = perfil.get("rol", "sin rol")
nombre = perfil.get("nombre_completo") or usuario.email
clave_vista = f"vista_rol_{usuario.id}"
vista = "Mi cuenta"
if rol_real == "administrador":
    with st.sidebar.expander("Vista previa de roles"):
        vista = st.radio("Ver la interfaz como", ["Mi cuenta", "Entrenador", "Autoridad", "Representante"], key=clave_vista)
        st.caption("La vista previa es de solo lectura. Usa los datos visibles para tu cuenta; no simula los filtros RLS ni los vínculos de otra persona.")
roles_vista = {"Entrenador": "entrenador", "Autoridad": "autoridad", "Representante": "padre"}
modo_previa = rol_real == "administrador" and vista in roles_vista
rol = roles_vista[vista] if modo_previa else rol_real
rol_admin = rol == "administrador"
rol_entrenador = rol == "entrenador"
rol_autoridad = rol == "autoridad"
rol_padre = rol == "padre"
muestra_formularios = puede_editar(rol)
permite_edicion = muestra_formularios and not modo_previa

# Cargar deportistas una vez por ejecución; las políticas RLS de Supabase filtran resultados.
error_jugadores = False
try:
    jugadores = obtener_jugadores(supabase)
except Exception as error:
    logging.getLogger(__name__).warning("Consulta de jugadores fallida (%s)", type(error).__name__)
    jugadores = []
    error_jugadores = True


# ============================================================
# NAVEGACIÓN
# ============================================================
st.sidebar.markdown("### Mi espacio deportivo")
st.sidebar.write(f"**{nombre}**")
st.sidebar.caption(f"Rol: {rol.capitalize()}" + (" · vista previa" if modo_previa else ""))
st.sidebar.divider()
jugador_representado = None
if rol_padre:
    jugador_representado = seleccionar_representado(jugadores, str(usuario.id), modo_previa)
    institucion_representado = (jugador_representado or {}).get("institucion") or INSTITUCION_JUVENTUD
    seccion = "Colegio Surcos" if institucion_representado == INSTITUCION_SURCOS else "Jugadores Juventud"
    st.sidebar.caption("Mi representado · Seguimiento individual")
else:
    opciones_menu = ["Inicio", "Jugadores Juventud", "Colegio Surcos", "Entrenamientos"]
    if rol_admin:
        opciones_menu.append("Usuarios y representantes")
    if st.session_state.get("menu_principal") not in opciones_menu:
        st.session_state.menu_principal = "Inicio"
    seccion = st.sidebar.radio("MENÚ PRINCIPAL", opciones_menu, key="menu_principal")
st.sidebar.divider()
if st.sidebar.button("Cerrar sesión", use_container_width=True):
    cerrar_sesion()

es_surcos = seccion == "Colegio Surcos"
aplicar_estilo(es_surcos)
if seccion not in ("Jugadores Juventud", "Colegio Surcos"):
    st.title("Mi espacio deportivo")
    st.caption("Seguimiento del estudiante-atleta")
if modo_previa:
    st.info(f"Vista previa: {vista}. Solo lectura con los datos de tu cuenta administradora. Para salir, selecciona «Mi cuenta» en el menú lateral.")

if error_jugadores:
    st.error("No se pudieron cargar los deportistas. Reintenta recargando la página.")
    st.stop()
if rol_padre and jugador_representado is None:
    st.title("Mi representado")
    st.info("No hay un deportista disponible para esta cuenta. Solicita al administrador que revise el vínculo con tu representado.")
    st.stop()
if rol_padre:
    # El título del navegador también corresponde al expediente abierto sin menú.
    st.set_page_config(page_title="Surcos · Desarrollo deportivo" if es_surcos else "Club Juventud · Mi representado")

# ============================================================
# INICIO
# ============================================================
if seccion == "Inicio":
    st.markdown(
        f'<div class="hero"><div class="eyebrow">Panel de gestión</div>'
        f'<h2>Bienvenido/a, {escape(str(nombre))}</h2>'
        '<p>Una visión organizada del proceso deportivo y formativo de nuestros atletas.</p></div>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Deportistas visibles", len(jugadores))
    activos = sum(1 for j in jugadores if j.get("estado") == "activo")
    col2.metric("Deportistas activos", activos)
    categorias = set(categoria_jugador(j) for j in jugadores)
    col3.metric("Categorías", len(categorias))
    st.subheader("¿Qué espacio quieres consultar?")
    def ir_a(destino):
        st.session_state.menu_principal = destino
    for columna, destino, titulo, descripcion in zip(
        st.columns(2), ["Jugadores Juventud", "Colegio Surcos"],
        ["Club Juventud", "Colegio Surcos"],
        ["Expedientes y evolución deportiva del club.", "Seguimiento deportivo y formativo de Surcos."],
    ):
        with columna, st.container(border=True):
            st.markdown(f"#### {titulo}")
            st.write(descripcion)
            st.button("Abrir " + titulo, key="abrir_" + destino, on_click=ir_a, args=(destino,), use_container_width=True)
    st.caption("La información disponible depende de tu cuenta y de sus permisos de acceso.")

# ============================================================
# DEPORTISTAS
# ============================================================
elif seccion in ("Jugadores Juventud", "Colegio Surcos"):
    institucion_actual = INSTITUCION_SURCOS if seccion == "Colegio Surcos" else INSTITUCION_JUVENTUD
    jugadores = [jugador_representado] if rol_padre else [j for j in jugadores if (j.get("institucion") or INSTITUCION_JUVENTUD) == institucion_actual]
    with st.container(key="cabecera_institucion"):
        marca_col, titulo_col = st.columns([1, 4])
        with marca_col:
            mostrar_marca(institucion_actual, ancho=150)
        with titulo_col:
            st.markdown('<div class="eyebrow">Desarrollo deportivo y formativo</div>', unsafe_allow_html=True)
            st.title("Surcos" if es_surcos else "Club Juventud")
            st.caption("Cada evaluación cuenta una parte de su evolución.")
    if rol_padre:
        tab_expediente = st.container()
        categorias_lista = []
    else:
        nombres_tabs = ["Expediente individual", "Directorio"]
        if muestra_formularios:
            nombres_tabs.append("Registrar deportista")
        tabs_institucion = st.tabs(nombres_tabs)
        tab_expediente, tab_consulta = tabs_institucion[:2]

        # Categorías activas
        try:
            categorias_resultado = supabase.table("categorias").select("id, nombre, edad_minima, edad_maxima").eq("activa", True).order("nombre").execute()
            categorias_lista = categorias_resultado.data or []
        except Exception as error:
            logging.getLogger(__name__).warning("Consulta de categorías fallida (%s)", type(error).__name__)
            st.error("No se pudieron cargar las categorías. Reintenta recargando la página.")
            st.stop()

    if muestra_formularios:
        with tabs_institucion[2]:
            if not categorias_lista:
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
                guardar = st.button("Guardar deportista", use_container_width=True, key=f"guardar_jugador_{prefijo_key}", disabled=not permite_edicion)
                if guardar and permite_edicion:
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

    if not rol_padre:
        with tab_consulta:
            if jugadores:
                busqueda = st.text_input("Buscar por código, nombre o apellido", key="buscar_jugador", placeholder="Escribe un código o un apellido")
                filtrados = [j for j in jugadores if busqueda.strip().casefold() in (str(j.get("codigo_jugador") or "") + " " + nombre_jugador(j)).casefold()] if busqueda.strip() else jugadores
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
            if rol_padre:
                jugador = jugador_representado
                jugador_id = jugador["id"]
            else:
                opciones_jugadores = opciones_expediente(jugadores)
                jugador_id = st.selectbox(
                    "Selecciona el código del deportista", list(opciones_jugadores),
                    format_func=opciones_jugadores.get, key=f"expediente_jugador_{institucion_actual}",
                )
                jugador = next(j for j in jugadores if j["id"] == jugador_id)
            mostrar_cabecera_jugador(jugador)

            # Un resultado fallido se conserva como None para distinguirlo de una lista vacía.
            def cargar_historial(tabla, orden):
                try:
                    return obtener_paginas(lambda: (
                        supabase.table(tabla).select("*").eq("jugador_id", jugador_id)
                        .order(orden, desc=True).order("id")
                    ))
                except Exception as error:
                    logging.getLogger(__name__).warning("Consulta de %s fallida (%s)", tabla, type(error).__name__)
                    return None

            hist_dep = cargar_historial("historial_deportivo", "temporada")
            hist_acad = [] if rol_padre else cargar_historial("historial_academico", "periodo_academico")
            evals = cargar_historial("evaluaciones_integrales", "fecha_evaluacion")
            evidencias = cargar_historial("evidencias_deportivas", "created_at")

            mostrar_pulso(evals)
            etiquetas = ["Evolución", "Trayectoria"]
            if not rol_padre:
                etiquetas.append("Académico")
            etiquetas.extend(["Entrenamientos", "Evidencias", "Datos personales", "Informe PDF"])
            tabs_ficha = dict(zip(etiquetas, st.tabs(etiquetas)))
            tab_eval, tab_deportivo = tabs_ficha["Evolución"], tabs_ficha["Trayectoria"]
            tab_resumen, tab_evidencias, tab_pdf = tabs_ficha["Datos personales"], tabs_ficha["Evidencias"], tabs_ficha["Informe PDF"]

            with tabs_ficha["Entrenamientos"]:
                mostrar_espacio(supabase, Contexto(rol, str(usuario.id), modo_previa), [jugador] if rol_padre else jugadores, jugador)

            with tab_resumen:
                st.markdown("#### Datos del deportista")
                st.write(f"**Fecha de nacimiento:** {fecha_legible(jugador.get('fecha_nacimiento'))}")
                st.write(f"**Curso escolar:** {jugador.get('curso') or 'No registrado'}")
                st.write(f"**Posición secundaria:** {jugador.get('posicion_secundaria') or 'No registrada'}")
                st.write(f"**Peso:** {str(jugador.get('peso')) + ' kg' if jugador.get('peso') else 'No registrado'}")
                st.write(f"**Estado:** {jugador.get('estado') or 'No registrado'}")
                st.caption("El historial conserva registros por periodo; evita sobrescribir evaluaciones o temporadas anteriores.")
                st.write(f"**Código:** {jugador.get('codigo_jugador') or 'Pendiente'}")
                st.write(f"**Cédula:** {jugador.get('cedula') or 'No registrada'}")
                st.write(f"**Fecha de ingreso:** {fecha_legible(jugador.get('fecha_ingreso'))}")
                st.write(f"**Nivel competitivo:** {jugador.get('nivel_competitivo') or 'No definido'}")
                st.write(f"**Estatura:** {str(jugador.get('estatura')) + ' cm' if jugador.get('estatura') else 'No registrada'}")
                st.write(f"**Pie dominante:** {jugador.get('pie_dominante') or 'No definido'}")

            with tab_deportivo:
                st.markdown("#### Temporadas y trayectoria")
                if hist_dep is None:
                    st.error("No se pudo cargar el historial deportivo. Reintenta recargando la página.")
                elif hist_dep:
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
                if hist_dep is not None and muestra_formularios:
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
                            guardar_dep = st.form_submit_button("Guardar temporada", use_container_width=True, disabled=not permite_edicion)
                        if guardar_dep and permite_edicion:
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

            if not rol_padre:
                with tabs_ficha["Académico"]:
                    st.markdown("#### Evolución académica")
                    if hist_acad is None:
                        st.error("No se pudo cargar el historial académico. Reintenta recargando la página.")
                    elif hist_acad:
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
                    if hist_acad is not None and rol_admin and not modo_previa:
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
                st.caption("Pases y tiros: aciertos de 5 intentos. Conducción, Illinois y velocidades de 10 y 20 m: segundos. Course Navette: nivel alcanzado y VO₂máx estimado.")
                mostrar_analisis_rendimiento(
                    jugador, evals, hist_dep, hist_acad, evidencias,
                    usuario_id=f"{usuario.id}_{rol}_{modo_previa}", incluir_academico=not rol_padre,
                )
                st.divider()
                if evals is None:
                    st.error("No se pudieron cargar las evaluaciones. Reintenta recargando la página.")
                elif evals:
                    mostrar_panel_evaluaciones(evals, jugador)
                else:
                    st.info("No hay evaluaciones registradas. Cuando guardes la primera, aparecerá aquí; con dos o más fechas podrás observar la evolución.")
                st.divider()
                if evals is not None and muestra_formularios:
                    with st.expander("➕ Registrar nueva evaluación"):
                        with st.form(f"form_eval_detallada_{jugador_id}"):
                            fecha_eval = st.date_input("Fecha de evaluación", value=date.today(), format="DD/MM/YYYY")
                            st.markdown("##### Efectividad · aciertos de 5 intentos")
                            c1, c2 = st.columns(2)
                            pase = c1.number_input("Efectividad de pases (aciertos / 5)", min_value=0, max_value=5, value=None, step=1, help="Deja vacío si no se realizó. Cero significa 0 aciertos de 5 intentos.")
                            tiros = c2.number_input("Efectividad de tiros al arco (aciertos / 5)", min_value=0, max_value=5, value=None, step=1)
                            st.markdown("##### Pruebas cronometradas · segundos")
                            f1, f2, f3, f4 = st.columns(4)
                            conduccion = f1.number_input("Conducción (s)", min_value=0.001, max_value=600.0, value=None, step=0.01, format="%.3f")
                            illinois = f2.number_input("Illinois (s)", min_value=0.001, max_value=300.0, value=None, step=0.01, format="%.3f")
                            vel10 = f3.number_input("Velocidad 10 m (s)", min_value=0.001, max_value=120.0, value=None, step=0.01, format="%.3f")
                            vel20 = f4.number_input("Velocidad 20 m (s)", min_value=0.001, max_value=120.0, value=None, step=0.01, format="%.3f")
                            st.markdown("##### Course Navette · protocolo de 20 m")
                            st.caption("Inicio a 8,5 km/h; incremento de 0,5 km/h por nivel. Registra el último nivel completado, sin mezclarlo con el número de recorridos.")
                            navette = st.number_input("Nivel alcanzado en Course Navette", min_value=1, max_value=21, value=None, step=1)
                            st.caption("El VO₂máx estimado se calcula al consultar el resultado con la edad del deportista en la fecha de evaluación. No es un campo que debas introducir manualmente.")
                            fortalezas = st.text_area("Fortalezas")
                            aspectos_mejora = st.text_area("Aspectos por mejorar")
                            recomendaciones = st.text_area("Recomendaciones")
                            guardar_eval = st.form_submit_button("Guardar evaluación", use_container_width=True, disabled=not permite_edicion)
                        if guardar_eval and permite_edicion:
                            payload = {
                                "jugador_id": jugador_id,
                                "fecha_evaluacion": fecha_eval.isoformat(),
                                "evaluador_id": str(usuario.id),
                                "pase_efectividad": pase,
                                "conduccion": conduccion,
                                "tiros_efectividad": tiros,
                                "velocidad_10m": vel10,
                                "velocidad_20m": vel20,
                                "illinois": illinois,
                                "course_navette": navette,
                                "fortalezas": fortalezas.strip() or None,
                                "aspectos_mejora": aspectos_mejora.strip() or None,
                                "recomendaciones": recomendaciones.strip() or None,
                            }
                            error_validacion = validar_resultados(payload)
                            if error_validacion:
                                st.error(error_validacion)
                            else:
                                try:
                                    supabase.table("evaluaciones_integrales").insert(payload).execute()
                                    st.success("Evaluación guardada. Se incorporará al gráfico de evolución.")
                                    st.rerun()
                                except Exception:
                                    st.error("No se pudo guardar la evaluación. Ejecuta primero migracion_ficha_evaluaciones.sql y revisa los permisos de Supabase.")

            with tab_evidencias:
                st.markdown("#### Material de seguimiento")
                if evidencias is None:
                    st.error("No se pudieron cargar las evidencias. Reintenta recargando la página.")
                elif evidencias:
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
                if evidencias is not None and muestra_formularios:
                    with st.expander("➕ Añadir evidencia"):
                        with st.form(f"form_evidencia_{jugador_id}"):
                            titulo_ev = st.text_input("Título *")
                            tipo_ev = st.selectbox("Tipo", ["fotografia", "video", "partido_completo", "certificado", "reconocimiento", "convocatoria", "informe", "otro"])
                            url_ev = st.text_input("Enlace (URL)")
                            fecha_ev = st.date_input("Fecha de la evidencia", value=date.today(), format="DD/MM/YYYY")
                            desc_ev = st.text_area("Descripción")
                            compartir_ev = st.checkbox("Marcar para posible perfil compartible (no publica automáticamente)", value=False)
                            guardar_ev = st.form_submit_button("Guardar evidencia", use_container_width=True, disabled=not permite_edicion)
                        if guardar_ev and permite_edicion:
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
                st.caption("Este expediente contiene datos personales. Compártelo solo con destinatarios autorizados.")
                incluir_academico_pdf = False if rol_padre else st.checkbox("Incluir historial académico (información confidencial)", value=False)
                incluir_eval_pdf = False if rol_padre else st.checkbox("Incluir evaluaciones integrales (información confidencial)", value=False)
                fuentes_pdf = [hist_dep, evidencias]
                if incluir_academico_pdf:
                    fuentes_pdf.append(hist_acad)
                if incluir_eval_pdf:
                    fuentes_pdf.append(evals)
                if any(datos is None for datos in fuentes_pdf):
                    st.error("No se puede exportar: faltan datos que no pudieron cargarse. Reintenta recargando la página.")
                else:
                    preparar_pdf(
                        jugador, hist_acad, hist_dep, evals, evidencias,
                        incluir_academico_pdf, incluir_eval_pdf,
                        alcance=f"{usuario.id}_{rol}_{modo_previa}",
                    )

# ============================================================
# ENTRENAMIENTOS
# ============================================================
elif seccion == "Entrenamientos":
    mostrar_espacio(supabase, Contexto(rol, str(usuario.id), modo_previa), jugadores)

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
