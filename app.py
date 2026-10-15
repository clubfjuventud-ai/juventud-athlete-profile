
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide"
)


@st.cache_resource
def conectar_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


supabase = conectar_supabase()

if "sesion" not in st.session_state:
    st.session_state.sesion = None


st.title("⚽ Juventud Athlete Profile")
st.subheader("Sistema de gestión y desarrollo del estudiante-atleta")
st.write(
    "Plataforma deportiva de Club Juventud y Unidad Educativa Bilingüe Surcos."
)
st.divider()


if st.session_state.sesion is None:

    st.write("Ingresa con tu cuenta para continuar.")

    with st.form("formulario_login"):
        correo = st.text_input("Correo electrónico")
        contrasena = st.text_input(
            "Contraseña",
            type="password"
        )
        ingresar = st.form_submit_button("Iniciar sesión")

    if ingresar:
        try:
            respuesta = supabase.auth.sign_in_with_password({
                "email": correo.strip(),
                "password": contrasena
            })

            st.session_state.sesion = respuesta.session
            st.rerun()

        except Exception:
            st.error(
                "No se pudo iniciar sesión. "
                "Verifica tus credenciales."
            )

else:

    usuario = st.session_state.sesion.user

    st.success("Sesión iniciada correctamente.")
    st.write(f"Correo: {usuario.email}")

    try:
        resultado = (
            supabase.table("perfiles")
            .select("*")
            .eq("id", str(usuario.id))
            .maybe_single()
            .execute()
        )

        perfil = resultado.data

        if perfil and perfil.get("activo"):

            rol = perfil.get("rol", "sin rol")
            st.info(f"Rol: {rol.capitalize()}")

            nombre = perfil.get("nombre_completo")
            if nombre:
                st.write(f"Nombre: {nombre}")

        else:
            st.warning(
                "Tu cuenta no tiene un perfil activo. "
                "Contacta al administrador."
            )

    except Exception:
        st.error(
            "No se pudo consultar tu perfil. "
            "Verifica la tabla perfiles y sus permisos."
        )

    st.divider()

    if st.button("Cerrar sesión"):
        try:
            supabase.auth.sign_out()
        finally:
            st.session_state.sesion = None
            st.rerun()
