
import streamlit as st
from supabase import create_client
from datetime import date

st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide"
)


# ==========================================
# CONEXIÓN CON SUPABASE
# ==========================================

def conectar_supabase():
    cliente = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    sesion = st.session_state.get("sesion")

    if sesion is not None:
        cliente.postgrest.auth(sesion.access_token)

    return cliente


# ==========================================
# SESIÓN
# ==========================================

if "sesion" not in st.session_state:
    st.session_state.sesion = None


def cerrar_sesion():
    try:
        cliente = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )

        cliente.auth.set_session(
            st.session_state.sesion.access_token,
            st.session_state.sesion.refresh_token
        )
        cliente.auth.sign_out()

    except Exception:
        pass

    finally:
        st.session_state.sesion = None
        st.rerun()


# ==========================================
# ENCABEZADO
# ==========================================

st.title("⚽ Juventud Athlete Profile")
st.caption(
    "Sistema de gestión y desarrollo del estudiante-atleta"
)


# ==========================================
# INICIO DE SESIÓN
# ==========================================

if st.session_state.sesion is None:

    st.write(
        "Plataforma deportiva de Club Juventud "
        "y Unidad Educativa Bilingüe Surcos."
    )

    with st.form("formulario_login"):
        correo = st.text_input("Correo electrónico")
        contrasena = st.text_input(
            "Contraseña",
            type="password"
        )

        ingresar = st.form_submit_button("Iniciar sesión")

    if ingresar:
        try:
            cliente_login = create_client(
                st.secrets["SUPABASE_URL"],
                st.secrets["SUPABASE_KEY"]
            )

            respuesta = cliente_login.auth.sign_in_with_password({
                "email": correo.strip(),
                "password": contrasena
            })

            if respuesta.session is None:
                st.error("No se pudo crear una sesión.")
            else:
                st.session_state.sesion = respuesta.session
                st.rerun()

        except Exception as e:
            st.error("No se pudo iniciar sesión.")
            st.code(str(e))


# ==========================================
# APLICACIÓN AUTENTICADA
# ==========================================

else:

    usuario = st.session_state.sesion.user

    try:
        supabase = conectar_supabase()

        resultado = (
            supabase.table("perfiles")
            .select("*")
            .eq("id", str(usuario.id))
            .maybe_single()
            .execute()
        )

        perfil = resultado.data

    except Exception as e:
        st.error("No se pudo consultar tu perfil.")
        st.code(str(e))
        st.stop()

    if not perfil or not perfil.get("activo"):

        st.warning(
            "Tu cuenta no tiene un perfil activo. "
            "Contacta al administrador."
        )

        if st.button("Cerrar sesión"):
            cerrar_sesion()

        st.stop()

    rol = perfil.get("rol", "sin rol")
    nombre = perfil.get("nombre_completo", usuario.email)

    # ======================================
    # MENÚ LATERAL
    # ======================================

    st.sidebar.title("⚽ Club Juventud")
    st.sidebar.write(f"**Usuario:** {nombre}")
    st.sidebar.caption(f"Rol: {rol.capitalize()}")
    st.sidebar.divider()

    opciones = [
        "Inicio",
        "Deportistas",
        "Evaluaciones",
        "Asistencia",
        "Competencias",
        "Usuarios y representantes"
    ]

    seccion = st.sidebar.radio(
        "MENÚ PRINCIPAL",
        opciones,
        key="menu_principal"
    )

    st.sidebar.divider()

    if st.sidebar.button(
        "Cerrar sesión",
        use_container_width=True
    ):
        cerrar_sesion()

    # ======================================
    # INICIO
    # ======================================

    if seccion == "Inicio":

        st.header("Panel principal")
        st.write(f"Bienvenido, {nombre}.")

        st.info(
            "Desde este panel podrás gestionar "
            "la información deportiva de los estudiantes."
        )

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Gestión deportiva")
            st.write("• Deportistas")
            st.write("• Evaluaciones")
            st.write("• Asistencia")

        with col2:
            st.subheader("Administración")
            st.write("• Competencias")
            st.write("• Usuarios y representantes")

        st.caption(
            "Las funciones se habilitarán progresivamente."
        )

    # ======================================
    # DEPORTISTAS
    # ======================================

    elif seccion == "Deportistas":

        st.header("👥 Gestión de deportistas")
        st.write(
            "Registra y consulta las fichas deportivas."
        )

        pesta_registro, pesta_consulta = st.tabs([
            "➕ Registrar deportista",
            "📋 Consultar deportistas"
        ])

        # Cargar categorías activas
        try:
            resultado_categorias = (
                supabase.table("categorias")
                .select("id, nombre")
                .eq("activa", True)
                .order("nombre")
                .execute()
            )

            categorias = resultado_categorias.data or []

        except Exception as e:
            st.error("No se pudieron cargar las categorías.")
            st.code(str(e))
            categorias = []

        # ----------------------------------
        # REGISTRAR DEPORTISTA
        # ----------------------------------

        with pesta_registro:

            if not categorias:
                st.warning(
                    "No hay categorías activas disponibles. "
                    "Verifica la tabla categorias en Supabase."
                )

            nombres_categorias = {
                categoria["nombre"]: categoria["id"]
                for categoria in categorias
            }

            with st.form("formulario_deportista"):

                st.subheader("Datos personales")

                nombres = st.text_input("Nombres *")
                apellidos = st.text_input("Apellidos *")

                fecha_nacimiento = st.date_input(
                    "Fecha de nacimiento",
                    value=date(2015, 1, 1),
                    min_value=date(1990, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY"
                )

                categoria_nombre = st.selectbox(
                    "Categoría *",
                    options=list(nombres_categorias.keys()),
                    index=None,
                    placeholder="Selecciona una categoría"
                )

                curso = st.text_input("Curso escolar")

                st.subheader("Datos deportivos")

                posiciones = [
                    "Portero/a",
                    "Defensa central",
                    "Lateral derecho",
                    "Lateral izquierdo",
                    "Mediocentro defensivo",
                    "Mediocentro",
                    "Mediocentro ofensivo",
                    "Extremo derecho",
                    "Extremo izquierdo",
                    "Delantero/a"
                ]

                posicion_principal = st.selectbox(
                    "Posición principal",
                    ["No definida"] + posiciones
                )

                posicion_secundaria = st.selectbox(
                    "Posición secundaria",
                    ["No definida"] + posiciones
                )

                pie_dominante = st.selectbox(
                    "Pie dominante",
                    [
                        "No definido",
                        "Derecho",
                        "Izquierdo",
                        "Ambidiestro"
                    ]
                )

                col1, col2 = st.columns(2)

                with col1:
                    estatura = st.number_input(
                        "Estatura en centímetros",
                        min_value=0,
                        max_value=250,
                        value=0
                    )

                with col2:
                    peso = st.number_input(
                        "Peso en kilogramos",
                        min_value=0.0,
                        max_value=200.0,
                        value=0.0,
                        step=0.5
                    )

                fotografia_url = st.text_input(
                    "URL de fotografía (opcional)"
                )

                guardar = st.form_submit_button(
                    "Guardar deportista",
                    disabled=not bool(categorias),
                    use_container_width=True
                )

            if guardar:

                if not nombres.strip() or not apellidos.strip():
                    st.error(
                        "Completa los nombres y apellidos."
                    )

                elif not categoria_nombre:
                    st.error("Selecciona una categoría.")

                else:

                    nuevo_deportista = {
                        "nombres": nombres.strip(),
                        "apellidos": apellidos.strip(),
                        "fecha_nacimiento": (
                            fecha_nacimiento.isoformat()
                        ),
                        "categoria_id": (
                            nombres_categorias[categoria_nombre]
                        ),
                        "curso": curso.strip() or None,
                        "posicion_principal": (
                            None
                            if posicion_principal == "No definida"
                            else posicion_principal
                        ),
                        "posicion_secundaria": (
                            None
                            if posicion_secundaria == "No definida"
                            else posicion_secundaria
                        ),
                        "pie_dominante": (
                            None
                            if pie_dominante == "No definido"
                            else pie_dominante
                        ),
                        "estatura": (
                            estatura if estatura > 0 else None
                        ),
                        "peso": peso if peso > 0 else None,
                        "fotografia_url": (
                            fotografia_url.strip() or None
                        ),
                        "estado": "activo"
                    }

                    try:
                        supabase.table("jugadores").insert(
                            nuevo_deportista
                        ).execute()

                        st.success(
                            "Deportista registrado correctamente."
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(
                            "No se pudo guardar el deportista."
                        )
                        st.code(str(e))

        # ----------------------------------
        # CONSULTAR DEPORTISTAS
        # ----------------------------------

        with pesta_consulta:

            try:
                resultado_jugadores = (
                    supabase.table("jugadores")
                    .select(
                        "id, nombres, apellidos, fecha_nacimiento, "
                        "curso, posicion_principal, estado, "
                        "categorias(nombre)"
                    )
                    .order("apellidos")
                    .execute()
                )

                jugadores = resultado_jugadores.data or []

                if jugadores:

                    filas = []

                    for jugador in jugadores:

                        categoria = jugador.get("categorias")

                        if isinstance(categoria, list):
                            categoria = (
                                categoria[0] if categoria else {}
                            )

                        filas.append({
                            "Nombres": jugador["nombres"],
                            "Apellidos": jugador["apellidos"],
                            "Fecha de nacimiento": (
                                jugador["fecha_nacimiento"]
                            ),
                            "Categoría": (
                                categoria.get("nombre", "")
                                if categoria else ""
                            ),
                            "Curso": jugador.get("curso") or "",
                            "Posición": (
                                jugador.get("posicion_principal") or ""
                            ),
                            "Estado": jugador.get("estado") or ""
                        })

                    st.dataframe(
                        filas,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.caption(
                        f"Total de deportistas visibles: {len(filas)}"
                    )

                else:
                    st.info(
                        "No hay deportistas visibles para tu cuenta."
                    )

            except Exception as e:
                st.error(
                    "No se pudieron consultar los deportistas."
                )
                st.code(str(e))

    # ======================================
    # EVALUACIONES
    # ======================================

    elif seccion == "Evaluaciones":

        st.header("📋 Evaluaciones deportivas")
        st.info(
            "Aquí construiremos el seguimiento técnico, "
            "táctico, físico y deportivo."
        )

    # ======================================
    # ASISTENCIA
    # ======================================

    elif seccion == "Asistencia":

        st.header("📅 Control de asistencia")
        st.info(
            "Aquí construiremos el registro de asistencia "
            "a los entrenamientos."
        )

    # ======================================
    # COMPETENCIAS
    # ======================================

    elif seccion == "Competencias":

        st.header("🏆 Competencias")
        st.info(
            "Aquí gestionaremos partidos, torneos "
            "y estadísticas."
        )

    # ======================================
    # USUARIOS Y REPRESENTANTES
    # ======================================

    elif seccion == "Usuarios y representantes":

        st.header("🔐 Usuarios y representantes")
        st.info(
            "Aquí construiremos la administración de cuentas, "
            "entrenadores y representantes."
        )
