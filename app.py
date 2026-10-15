
import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Juventud Athlete Profile",
    page_icon="⚽",
    layout="wide"
)

@st.cache_resource
def conectar_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

st.title("⚽ Juventud Athlete Profile")
st.subheader("Sistema de gestión y desarrollo del estudiante-atleta")

st.write(
    "Plataforma deportiva de Club Juventud y Unidad Educativa Bilingüe Surcos."
)

st.divider()

try:
    supabase = conectar_supabase()
    st.success("Conexión con Supabase establecida correctamente.")
except Exception as e:
    st.error("No se pudo conectar con Supabase.")
    st.caption(
        "Revisa los Secrets de Streamlit y la configuración de la aplicación."
    )
    st.stop()

st.info("Sistema en desarrollo — Versión 1.0")
