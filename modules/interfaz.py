"""Presentación del expediente; no modifica datos ni permisos de acceso."""
import hashlib
import json
from datetime import date
from html import escape

import streamlit as st

from modules.evaluaciones_visuales import ordenar_evaluaciones, fecha_evaluacion, resultado, METRICAS
from modules.utilidades import nombre_jugador, categoria_jugador
from modules.informes_pdf import generar_pdf


def aplicar_estilo(surcos=False):
    acento, suave = ("#94C93D", "#123346") if surcos else ("#E4C365", "#302A1A")
    st.markdown(f"""
    <style>
    .stApp {{ background:#10151D; color:#F2F5FA; --acento:{acento}; }}
    [data-testid="stSidebar"] {{background:#0C1118;border-right:1px solid #283444;}}
    .block-container,[data-testid="stMainBlockContainer"] {{max-width:1280px;padding-top:4.5rem;padding-bottom:3rem;}}
    h1,h2,h3,h4,p,label,[data-testid="stMarkdownContainer"] {{color:#F2F5FA;}}
    h1 {{font-size:2.2rem;letter-spacing:-.04em;}}
    .eyebrow {{color:{acento};font-size:.76rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;}}
    .hero {{background:linear-gradient(120deg,{suave},#17202C);border:1px solid #344151;border-radius:18px;padding:1.5rem;margin-bottom:1.1rem;}}
    .hero h2 {{margin:.3rem 0;padding:0;font-size:1.8rem;line-height:1.2;overflow-wrap:anywhere;}}
    .hero p {{color:#C2CDDA;margin:.5rem 0 0;}}
    .profile-tag {{display:inline-block;background:#17202C;border:1px solid #465363;border-radius:30px;padding:.25rem .7rem;margin:.3rem .3rem 0 0;font-size:.83rem;}}
    .photo-placeholder {{height:138px;width:112px;border-radius:16px;display:flex;align-items:center;justify-content:center;background:{suave};color:{acento};font-size:2rem;font-weight:700;}}
    [data-testid="stMetric"] {{background:#18212D;border:1px solid #303D4D;padding:1rem;border-radius:14px;min-width:0;}}
    [data-testid="stMetricValue"],[data-testid="stMetricValue"] * {{color:{acento};font-size:1.6rem;}}
    [data-testid="stMetricLabel"] {{color:#BAC6D5;}}
    [data-testid="stVerticalBlockBorderWrapper"]>div {{border-color:#303D4D!important;border-radius:14px;}}
    div.stButton>button,div.stFormSubmitButton>button {{border-radius:10px;min-height:2.65rem;}}
    div.stButton>button[kind="primary"],div.stFormSubmitButton>button {{background:{acento};color:#10151D;border-color:{acento};font-weight:700;}}
    button[kind="primary"] p,div.stFormSubmitButton>button p {{color:#10151D;}}
    button:focus-visible {{outline:3px solid {acento};outline-offset:3px;}}
    [role="tablist"] {{gap:1rem;overflow-x:auto;flex-wrap:nowrap;border-bottom:1px solid #344151;}}
    [role="tab"] {{white-space:nowrap;padding:.7rem .2rem;}}
    [role="tab"][aria-selected="true"] p {{color:{acento};}}
    [data-baseweb="tab-highlight"],.react-aria-SelectionIndicator,.brand-line {{background:{acento}!important;}}
    [data-testid="stRadioOption"][data-selected="true"]>div>div:first-child {{background:{acento};border-color:{acento};}}
    .brand-line {{height:3px;border-radius:3px;margin:1rem 0;}}
    hr {{border-color:#303D4D;}}
    @media(max-width:640px) {{
      .block-container,[data-testid="stMainBlockContainer"] {{padding:4rem .85rem 2rem;}}
      h1 {{font-size:1.8rem;}}
      .hero {{padding:1rem;}}
      .hero h2 {{font-size:1.45rem;}}
      [data-testid="stHorizontalBlock"] {{flex-wrap:wrap;gap:.7rem;}}
      [data-testid="stHorizontalBlock"]>[data-testid="stColumn"] {{min-width:min(100%,155px);flex:1 1 155px;}}
      [data-testid="stMetricValue"] {{font-size:1.35rem;}}
      .st-key-cabecera_institucion [data-testid="stColumn"]:first-child {{flex:0 0 95px;min-width:95px;}}
      .st-key-cabecera_institucion [data-testid="stColumn"]:last-child {{flex:1 1 200px;min-width:200px;}}
      .st-key-cabecera_institucion img {{width:90px!important;height:auto!important;}}
      .st-key-cabecera_institucion .eyebrow {{display:none;}}
      .st-key-cabecera_deportista [data-testid="stColumn"]:first-child {{flex:0 0 70px;min-width:70px;}}
      .st-key-cabecera_deportista [data-testid="stColumn"]:last-child {{flex:1 1 240px;min-width:min(100%,240px);}}
      .st-key-cabecera_deportista img {{max-width:70px;height:auto;}}
      .st-key-cabecera_deportista .photo-placeholder {{width:70px;height:90px;font-size:1.4rem;}}
      .st-key-cabecera_deportista .hero h2 {{font-size:1.25rem;}}
      .st-key-cabecera_deportista .hero p {{display:none;}}
    }}
    </style>""", unsafe_allow_html=True)


def mostrar_cabecera_jugador(jugador):
    with st.container(key="cabecera_deportista"):
        foto, identidad = st.columns([1, 6])
        with foto:
            if jugador.get("fotografia_url"):
                try:
                    st.image(jugador["fotografia_url"], width=112)
                except (OSError, ValueError):
                    st.caption("Fotografía no disponible")
            else:
                iniciales = "".join(str(jugador.get(c) or "?")[:1] for c in ("nombres", "apellidos"))
                st.markdown(f'<div class="photo-placeholder" aria-label="Sin fotografía">{escape(iniciales)}</div>', unsafe_allow_html=True)
        with identidad:
            etiquetas = [jugador.get("codigo_jugador") or "Código pendiente", categoria_jugador(jugador), jugador.get("posicion_principal") or "Posición por definir"]
            chips = "".join(f'<span class="profile-tag">{escape(str(t))}</span>' for t in etiquetas)
            st.markdown(f'<div class="hero"><div class="eyebrow">Expediente individual</div><h2>{escape(nombre_jugador(jugador))}</h2>{chips}<p>Su progreso, evaluación a evaluación.</p></div>', unsafe_allow_html=True)


def mostrar_pulso(evaluaciones):
    if evaluaciones is None:
        st.caption("El resumen de evolución estará disponible cuando se carguen las evaluaciones.")
        return
    ordenadas = ordenar_evaluaciones(evaluaciones)
    con_datos = []
    for registro in ordenadas:
        try:
            date.fromisoformat(str(registro.get("fecha_evaluacion")))
        except ValueError:
            continue
        if any(resultado(registro, c) is not None for c, _, _ in METRICAS):
            con_datos.append(registro)
    ultima = con_datos[0] if con_datos else None
    fechas = {r.get("fecha_evaluacion") for r in con_datos if r.get("fecha_evaluacion")}
    a, b, c = st.columns(3)
    a.metric("Fechas evaluadas", len(fechas))
    b.metric("Última evaluación", fecha_evaluacion(ultima) if ultima else "Pendiente")
    ultimas = [r for r in con_datos if r["fecha_evaluacion"] == ultima["fecha_evaluacion"]] if ultima else []
    completas = sum(any(resultado(r, campo) is not None for r in ultimas) for campo, _, _ in METRICAS)
    c.metric("Pruebas en la última fecha", f"{completas}/7" if ultima else "—")
    st.caption("Compara los resultados en Evolución. El análisis explica los cambios y los datos que faltan.")


def preparar_pdf(jugador, academico, deportivo, evaluaciones, evidencias, incluir_academico, incluir_eval, alcance):
    """Genera únicamente a petición y retiene solo el último PDF de esta sesión."""
    datos = [alcance, jugador, academico if incluir_academico else [], deportivo,
             evaluaciones if incluir_eval else [], evidencias, incluir_academico, incluir_eval]
    huella = hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()
    clave = "expediente_pdf_preparado"
    guardado = st.session_state.get(clave)
    if guardado and guardado["huella"] != huella:
        del st.session_state[clave]
        guardado = None
    if st.button("Preparar expediente PDF", key="preparar_pdf", type="primary", use_container_width=True):
        try:
            with st.spinner("Preparando el expediente…"):
                contenido = generar_pdf(jugador, academico, deportivo, evaluaciones, evidencias, incluir_academico, incluir_eval)
            guardado = {"huella": huella, "contenido": contenido}
            st.session_state[clave] = guardado
        except Exception:
            st.error("No se pudo generar el PDF. Reintenta y, si el problema continúa, contacta al administrador.")
    if guardado:
        codigo = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(jugador.get("codigo_jugador") or jugador["id"]))
        st.download_button("⬇️ Descargar expediente PDF", guardado["contenido"], file_name=f"expediente_{codigo}.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.caption("El documento se prepara al pulsar el botón, con los datos y opciones actuales.")
