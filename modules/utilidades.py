import re
from datetime import date
import pandas as pd
import streamlit as st

from modules.configuracion import (
    LOGO_JUVENTUD, LOGO_SURCOS, INSTITUCION_JUVENTUD, INSTITUCION_SURCOS
)

def encabezado_seccion(titulo, descripcion=None):
    st.markdown('<div class="brand-line"></div>', unsafe_allow_html=True)
    st.header(titulo)
    if descripcion:
        st.caption(descripcion)

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
