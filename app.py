
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide"
)


def conectar_supabase():
    cliente = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    sesion = st.session_state.get("sesion")

    if sesion is not None:
        cliente.postgrest.auth(sesion.access_token)

    return cliente


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


st.title("⚽ Juventud Athlete Profile")
st.caption(
    "Sistema de gestión y desarrollo del estudiante-atleta"
)

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

    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        cerrar_sesion()

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

    elif seccion == "Deportistas":
        st.header("👥 Deportistas")
        st.info(
            "Aquí construiremos el registro y las fichas "
            "individuales de los jugadores."
        )

    elif seccion == "Evaluaciones":
        st.header("📋 Evaluaciones deportivas")
        st.info(
            "Aquí construiremos el seguimiento técnico, "
            "táctico, físico y deportivo."
        )

    elif seccion == "Asistencia":
        st.header("📅 Control de asistencia")
        st.info(
            "Aquí construiremos el registro de asistencia "
            "a los entrenamientos."
        )

    elif seccion == "Competencias":
        st.header("🏆 Competencias")
        st.info(
            "Aquí gestionaremos partidos, torneos "
            "y estadísticas."
        )

    elif seccion == "Usuarios y representantes":
        st.header("🔐 Usuarios y representantes")
        st.info(
            "Aquí construiremos la administración de cuentas, "
            "entrenadores y representantes."
        )
