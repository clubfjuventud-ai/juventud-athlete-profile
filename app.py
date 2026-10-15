
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide"
)


# Crear un cliente independiente para esta sesión
def conectar_supabase():
    cliente = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    # Si existe una sesión, utilizar su token de acceso
    sesion = st.session_state.get("sesion")

    if sesion is not None:
        cliente.postgrest.auth(sesion.access_token)

    return cliente


# Inicializar el estado de la sesión
if "sesion" not in st.session_state:
    st.session_state.sesion = None


st.title("⚽ Juventud Athlete Profile")
st.subheader(
    "Sistema de gestión y desarrollo del estudiante-atleta"
)

st.write(
    "Plataforma deportiva de Club Juventud "
    "y Unidad Educativa Bilingüe Surcos."
)

st.divider()


# Pantalla de inicio de sesión
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
            st.error(
                "No se pudo iniciar sesión. "
                "Verifica tus credenciales."
            )
            st.code(str(e))


# Pantalla después del inicio de sesión
else:

    sesion = st.session_state.sesion
    usuario = sesion.user

    st.success("Sesión iniciada correctamente.")
    st.write(f"Correo: {usuario.email}")

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

    except Exception as e:
        st.error("No se pudo consultar tu perfil.")
        st.code(str(e))

    st.divider()

    if st.button("Cerrar sesión"):
        try:
            cliente_salida = create_client(
                st.secrets["SUPABASE_URL"],
                st.secrets["SUPABASE_KEY"]
            )

            cliente_salida.auth.set_session(
                st.session_state.sesion.access_token,
                st.session_state.sesion.refresh_token
            )

            cliente_salida.auth.sign_out()

        except Exception:
            pass

        finally:
            st.session_state.sesion = None
            st.rerun()
