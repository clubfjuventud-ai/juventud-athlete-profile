import re
from collections import Counter
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

def obtener_paginas(crear_consulta, tamano=500):
    """Recorre también respuestas limitadas por el máximo configurado de la API."""
    registros = []
    while True:
        pagina = crear_consulta().range(len(registros), len(registros) + tamano - 1).execute().data
        if not pagina:
            return registros
        registros.extend(pagina)


def obtener_jugadores(supabase):
    return obtener_paginas(lambda: (
        supabase.table("jugadores")
        .select(
            "id, codigo_jugador, cedula, nombres, apellidos, fecha_nacimiento, fecha_ingreso, curso, "
            "posicion_principal, posicion_secundaria, pie_dominante, estatura, peso, fotografia_url, "
            "nivel_competitivo, estado, categoria_id, institucion, categorias(nombre, edad_minima, edad_maxima)"
        )
        .order("apellidos").order("id")
    ))


def opciones_expediente(jugadores):
    """Mantiene cada ID independiente y presenta el código como etiqueta."""
    codigos = [str(j.get("codigo_jugador") or "").strip() for j in jugadores]
    repetidos = {codigo for codigo, cantidad in Counter(codigos).items() if cantidad > 1}
    return {
        j["id"]: (f"{codigo or 'Sin código'} · ID: {j['id']}"
                  if not codigo or codigo in repetidos else codigo)
        for j, codigo in zip(jugadores, codigos)
    }


def ruta_logo(institucion):
    """Resuelve el logo institucional; None conserva la institución predeterminada."""
    nombre = str(institucion or INSTITUCION_JUVENTUD).strip().casefold()
    rutas = {
        INSTITUCION_JUVENTUD.casefold(): LOGO_JUVENTUD,
        INSTITUCION_SURCOS.casefold(): LOGO_SURCOS,
    }
    ruta = rutas.get(nombre)
    return ruta if ruta is not None and ruta.is_file() else None


def mostrar_marca(institucion=INSTITUCION_JUVENTUD, ancho=120):
    """Muestra la imagen con su proporción original o el nombre si falta."""
    nombre = str(institucion or INSTITUCION_JUVENTUD).strip()
    ruta = ruta_logo(nombre)
    if ruta:
        try:
            # Solo se fija el ancho: Streamlit calcula la altura original.
            st.image(str(ruta), width=ancho)
            return
        except (OSError, ValueError):
            pass
    st.text(nombre)


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
    if edad < 0:
        return None
    coincidencias = []
    alternativas = []
    for categoria in categorias:
        minimo = categoria.get("edad_minima")
        maximo = categoria.get("edad_maxima")
        if minimo is not None or maximo is not None:
            # Un rango parcial también es explícito y no usa la alternativa por nombre.
            if ((minimo is None or edad >= int(minimo))
                    and (maximo is None or edad <= int(maximo))):
                coincidencias.append(categoria)
        else:
            match = re.fullmatch(r"sub\s*[- ]?\s*(\d+)", str(categoria.get("nombre", "")).strip(), re.IGNORECASE)
            if match and edad <= int(match.group(1)):
                alternativas.append((int(match.group(1)), categoria))
    if coincidencias:
        # Rangos superpuestos requieren corregir la configuración, no elegir al azar.
        return coincidencias[0] if len(coincidencias) == 1 else None
    if alternativas:
        limite = min(item[0] for item in alternativas)
        candidatas = [categoria for valor, categoria in alternativas if valor == limite]
        return candidatas[0] if len(candidatas) == 1 else None
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
