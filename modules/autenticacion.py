import time

import streamlit as st
from supabase import ClientOptions, create_client


class SesionCaducada(Exception):
    """El servidor rechazó la renovación de la sesión."""


def conectar_supabase():
    """Restaura una sesión aislada y conserva cualquier token renovado."""
    cliente = create_client(
        st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"],
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )
    sesion = st.session_state.get("sesion")
    if sesion is not None:
        try:
            if not sesion.expires_at or sesion.expires_at <= time.time() + 60:
                respuesta = cliente.auth.refresh_session(sesion.refresh_token)
            else:
                respuesta = cliente.auth.set_session(sesion.access_token, sesion.refresh_token)
        except Exception as error:
            if getattr(error, "status", None) in (400, 401, 403):
                st.session_state.sesion = None
                raise SesionCaducada() from error
            raise
        if respuesta.session is None:
            st.session_state.sesion = None
            raise SesionCaducada()
        st.session_state.sesion = respuesta.session
        cliente.postgrest.auth(respuesta.session.access_token)
    return cliente


def cerrar_sesion():
    try:
        if st.session_state.get("sesion") is not None:
            cliente = conectar_supabase()
            cliente.auth.sign_out({"scope": "local"})
    except Exception:
        # El cierre local debe completarse incluso sin conexión.
        pass
    st.session_state.sesion = None
    st.rerun()
