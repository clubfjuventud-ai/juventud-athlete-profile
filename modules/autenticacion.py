import streamlit as st
from supabase import create_client

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
