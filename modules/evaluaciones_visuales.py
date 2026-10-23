"""Perfil visual de evaluaciones. Conserva las escalas y los resultados originales."""
import math
from html import escape

PUNTUACIONES = (
    ('pase_efectividad', 'Pase', 'Pase'),
    ('conduccion', 'Conducción', 'Conducción'),
    ('tiros_efectividad', 'Tiros al arco', 'Tiros'),
    ('disciplina', 'Disciplina', 'Disciplina'),
    ('compromiso', 'Compromiso', 'Compromiso'),
    ('responsabilidad', 'Responsabilidad', 'Responsab.'),
    ('trabajo_equipo', 'Trabajo en equipo', 'Equipo'),
    ('capacidad_esfuerzo', 'Capacidad de esfuerzo', 'Esfuerzo'),
)
FISICAS = (
    ('velocidad_10m', 'Velocidad 10 m', 's', True),
    ('velocidad_20m', 'Velocidad 20 m', 's', True),
    ('illinois', 'Agilidad Illinois', 's', True),
    ('course_navette', 'Course Navette', 'nivel/etapa', False),
)


def numero(valor):
    try:
        resultado = float(valor)
        return resultado if math.isfinite(resultado) else None
    except (TypeError, ValueError):
        return None


def resultado(registro, campo):
    valor = numero((registro or {}).get(campo))
    # Los formularios existentes utilizan cero para indicar un resultado sin registrar.
    return valor if valor is not None and valor > 0 else None


def variacion(actual, anterior, campo):
    a, b = resultado(actual, campo), resultado(anterior, campo)
    return a - b if a is not None and b is not None else None


def ordenar_evaluaciones(registros):
    return sorted(registros, key=lambda r: (str(r.get('fecha_evaluacion') or ''), str(r.get('id') or '')), reverse=True)


def fecha_evaluacion(registro):
    from modules.utilidades import fecha_legible
    return fecha_legible((registro or {}).get('fecha_evaluacion'))


def puntos_radar(registro, cx=200, cy=200, radio=125):
    puntos = []
    for i, (campo, _, _) in enumerate(PUNTUACIONES):
        valor = resultado(registro, campo)
        if valor is None or valor > 10:
            puntos.append(None)
            continue
        angulo = -math.pi / 2 + i * 2 * math.pi / len(PUNTUACIONES)
        puntos.append((cx + radio * valor / 10 * math.cos(angulo), cy + radio * valor / 10 * math.sin(angulo)))
    return puntos


def radar_svg(actual, anterior=None, color='#D4AF37', comparacion='#40C9CF'):
    """SVG real, sin rasterización. Los datos ausentes interrumpen el contorno."""
    partes = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" aria-label="Perfil de evaluación y comparación por fecha">',
              '<rect x="1" y="1" width="398" height="398" rx="22" fill="#111820" stroke="#33404C"/>']
    for escala in (2, 4, 6, 8, 10):
        puntos = [(200 + 125 * escala / 10 * math.cos(-math.pi/2 + i*math.pi/4),
                   200 + 125 * escala / 10 * math.sin(-math.pi/2 + i*math.pi/4)) for i in range(8)]
        partes.append('<polygon points="' + ' '.join(f'{x:.2f},{y:.2f}' for x,y in puntos) + '" fill="none" stroke="#33404C"/>')
        partes.append(f'<text x="205" y="{200-125*escala/10+11}" fill="#A7B3BF" font-size="9">{escala}</text>')
    for i, (_, _, etiqueta) in enumerate(PUNTUACIONES):
        angulo = -math.pi/2 + i*math.pi/4
        x, y = 200 + 125*math.cos(angulo), 200 + 125*math.sin(angulo)
        lx, ly = 200 + 156*math.cos(angulo), 200 + 151*math.sin(angulo)
        partes.append(f'<line x1="200" y1="200" x2="{x:.2f}" y2="{y:.2f}" stroke="#33404C"/>')
        partes.append(f'<text x="{lx:.2f}" y="{ly+4:.2f}" fill="#E7EDF2" font-family="sans-serif" font-size="11" text-anchor="middle">{escape(etiqueta)}</text>')
    for registro, tono, etiqueta in [(anterior, comparacion, 'Comparación'), (actual, color, 'Seleccionada')]:
        if not registro:
            continue
        puntos = puntos_radar(registro)
        if all(p is not None for p in puntos):
            partes.append('<polygon points="' + ' '.join(f'{x:.2f},{y:.2f}' for x,y in puntos) + f'" fill="{tono}" fill-opacity="0.16" stroke="{tono}" stroke-width="2.5"/>')
        else:
            for i, punto in enumerate(puntos):
                siguiente = puntos[(i+1) % len(puntos)]
                if punto is not None and siguiente is not None:
                    partes.append(f'<line x1="{punto[0]:.2f}" y1="{punto[1]:.2f}" x2="{siguiente[0]:.2f}" y2="{siguiente[1]:.2f}" stroke="{tono}" stroke-width="2.5"/>')
        for (campo, nombre, _), punto in zip(PUNTUACIONES, puntos):
            if punto is not None:
                partes.append(f'<circle cx="{punto[0]:.2f}" cy="{punto[1]:.2f}" r="4" fill="{tono}"><title>{escape(etiqueta)} · {escape(nombre)}: {resultado(registro,campo):g}/10</title></circle>')
    partes.append(f'<circle cx="55" cy="372" r="4" fill="{color}"/><text x="65" y="376" fill="#E7EDF2" font-family="sans-serif" font-size="10">Seleccionada</text>')
    if anterior:
        partes.append(f'<circle cx="235" cy="372" r="4" fill="{comparacion}"/><text x="245" y="376" fill="#E7EDF2" font-family="sans-serif" font-size="10">Comparación</text>')
    partes.append('</svg>')
    return ''.join(partes)


def mostrar_panel_evaluaciones(registros, jugador):
    import streamlit as st
    from modules.utilidades import nombre_jugador, grafico_evolucion
    from modules.configuracion import INSTITUCION_SURCOS

    ordenadas = ordenar_evaluaciones(registros)
    clave = str(jugador['id'])
    def etiqueta(i):
        if i is None:
            return 'Sin comparación'
        return f'{fecha_evaluacion(ordenadas[i])} · Registro {len(ordenadas)-i}'
    st.markdown('#### Perfil del deportista')
    st.caption(f"{jugador.get('codigo_jugador') or 'Código pendiente'} · {nombre_jugador(jugador)}")
    fechas, referencia = st.columns(2)
    seleccion = fechas.selectbox('Evaluación que quieres ver', list(range(len(ordenadas))), format_func=etiqueta, key=f'perfil_fecha_{clave}')
    opciones = [None] + [i for i in range(len(ordenadas)) if i != seleccion]
    predeterminada = seleccion + 1 if seleccion + 1 < len(ordenadas) else None
    comparada = referencia.selectbox('Comparar con', opciones, index=opciones.index(predeterminada), format_func=etiqueta,
                                    disabled=len(ordenadas) == 1, key=f'perfil_comparacion_{clave}_{seleccion}')
    actual = ordenadas[seleccion]
    anterior = ordenadas[comparada] if comparada is not None else None
    color = '#70A808' if jugador.get('institucion') == INSTITUCION_SURCOS else '#D4AF37'
    grafico, atributos = st.columns([1.1, 1.4])
    with grafico:
        st.image(radar_svg(actual, anterior, color=color), width=480)
        st.caption('Puntuaciones sobre 10. Los datos sin registrar quedan vacíos; no equivalen a cero. No se calcula una nota global.')
    with atributos:
        st.markdown('##### Técnica y actitud')
        for i in range(0, len(PUNTUACIONES), 2):
            for columna, (campo, nombre, _) in zip(st.columns(2), PUNTUACIONES[i:i+2]):
                valor = resultado(actual, campo)
                delta = variacion(actual, anterior, campo)
                columna.metric(nombre, f'{valor:g} / 10' if valor is not None else '—',
                               delta=f'{delta:+.1f} puntos' if delta is not None else None)
    st.markdown('##### Pruebas físicas')
    for columna, (campo, nombre, unidad, menor_mejor) in zip(st.columns(4), FISICAS):
        valor = resultado(actual, campo)
        delta = variacion(actual, anterior, campo)
        texto = f'{valor:.3f} s' if unidad == 's' and valor is not None else (f'{valor:g}' if valor is not None else '—')
        columna.metric(nombre, texto, delta=f'{delta:+.3f} {unidad}' if delta is not None else None,
                       delta_color='inverse' if menor_mejor else 'normal')
    st.caption('Velocidad e Illinois: menos segundos es mejor. Course Navette: mayor nivel/etapa es mejor. Las pruebas físicas conservan sus unidades; no se convierten en puntuaciones del radar.')
    if len(ordenadas) == 1:
        st.info('Primera evaluación registrada. Cuando haya otra fecha podrás comparar la evolución.')
    for campo, titulo in [('fortalezas', 'Fortalezas'), ('aspectos_mejora', 'Aspectos por mejorar'), ('recomendaciones', 'Recomendaciones')]:
        st.markdown(f'**{titulo}**')
        st.text(str(actual.get(campo) or 'Sin observaciones registradas.'))
    with st.expander('Ver evolución por fechas'):
        grafico_evolucion(ordenadas, [(c,n) for c,n,_ in PUNTUACIONES[:3]], 'Evolución técnica · escala de 1 a 10')
        grafico_evolucion(ordenadas, [(c,n) for c,n,_ in PUNTUACIONES[3:]], 'Evolución actitudinal · escala de 1 a 10')
        grafico_evolucion(ordenadas, [(c,n) for c,n,u,_ in FISICAS if u == 's'], 'Velocidad y agilidad · segundos')
        grafico_evolucion(ordenadas, [('course_navette','Nivel/etapa')], 'Course Navette')


def cuadro_evaluacion_pdf(actual, anterior, paleta):
    """Cuadro vectorial imprimible: radar, tarjetas de atributos y pruebas físicas."""
    from reportlab.graphics.shapes import Drawing, Polygon, Line, Circle, String, Rect
    from reportlab.lib.colors import HexColor, Color

    dibujo = Drawing(465, 306)
    tinta = HexColor(paleta['principal'])
    acento = HexColor(paleta['acento'])
    comparacion = HexColor('#637B8E')
    dibujo.add(Rect(0, 0, 465, 306, rx=9, ry=9, fillColor=HexColor('#FAFBFC'), strokeColor=HexColor(paleta['borde'])))
    cx, cy, radio = 119, 177, 76
    for escala in (2,4,6,8,10):
        puntos = []
        for i in range(8):
            a = math.pi/2-i*math.pi/4
            puntos.extend([cx+radio*escala/10*math.cos(a),cy+radio*escala/10*math.sin(a)])
        dibujo.add(Polygon(puntos, fillColor=None, strokeColor=HexColor('#DDE3E8'), strokeWidth=0.5))
    for i, (_,_,nombre) in enumerate(PUNTUACIONES):
        a=math.pi/2-i*math.pi/4
        dibujo.add(Line(cx,cy,cx+radio*math.cos(a),cy+radio*math.sin(a),strokeColor=HexColor('#DDE3E8'),strokeWidth=0.5))
        dibujo.add(String(cx+99*math.cos(a),cy+96*math.sin(a)-3,nombre,fontName='Helvetica',fontSize=6.5,textAnchor='middle',fillColor=tinta))
    for registro, tono in [(anterior,comparacion),(actual,acento)]:
        if not registro:
            continue
        puntos = puntos_radar(registro,cx,cy,radio)
        # El PDF tiene el origen vertical invertido respecto a SVG.
        puntos = [(p[0],2*cy-p[1]) if p is not None else None for p in puntos]
        if all(p is not None for p in puntos):
            dibujo.add(Polygon([v for p in puntos for v in p],fillColor=Color(tono.red,tono.green,tono.blue,alpha=0.15),strokeColor=tono,strokeWidth=1.4))
        else:
            for i,p in enumerate(puntos):
                q=puntos[(i+1)%8]
                if p is not None and q is not None:
                    dibujo.add(Line(*p,*q,strokeColor=tono,strokeWidth=1.4))
        for p in puntos:
            if p is not None:
                dibujo.add(Circle(*p,2.2,fillColor=tono,strokeColor=None))
    dibujo.add(String(243,60,'Escala sobre 10 · vacíos: sin registrar',fontSize=6.5,fillColor=comparacion))
    dibujo.add(String(18,289,'PERFIL DEL DEPORTISTA',fontName='Helvetica-Bold',fontSize=9,fillColor=tinta))
    dibujo.add(String(18,68,'Seleccionada: '+fecha_evaluacion(actual),fontSize=7,fillColor=tinta))
    dibujo.add(String(18,56,'Comparación: '+fecha_evaluacion(anterior) if anterior else 'Primera evaluación · sin comparación',fontSize=7,fillColor=comparacion))
    for i,(campo,nombre,_) in enumerate(PUNTUACIONES):
        x,y=243,265-i*24
        valor=resultado(actual,campo);delta=variacion(actual,anterior,campo)
        dibujo.add(Rect(x,y-12,207,22,rx=3,ry=3,fillColor=HexColor(paleta['fondo']),strokeColor=None))
        dibujo.add(String(x+6,y-3,nombre,fontSize=7,fillColor=tinta))
        texto=f'{valor:g}/10' if valor is not None else 'Sin registrar'
        if delta is not None: texto+=f' ({delta:+.1f})'
        dibujo.add(String(x+200,y-3,texto,fontName='Helvetica-Bold',fontSize=7,textAnchor='end',fillColor=tinta))
    for i,(campo,nombre,unidad,menor_mejor) in enumerate(FISICAS):
        x=12+i*113
        dibujo.add(Rect(x,8,106,40,rx=4,ry=4,fillColor=HexColor(paleta['fondo']),strokeColor=None))
        dibujo.add(String(x+5,37,nombre,fontSize=6.5,fillColor=tinta))
        valor=resultado(actual,campo);delta=variacion(actual,anterior,campo)
        texto=f'{valor:.3f} s' if valor is not None and unidad=='s' else (f'{valor:g} nivel/etapa' if valor is not None else 'Sin registrar')
        dibujo.add(String(x+5,24,texto,fontName='Helvetica-Bold',fontSize=8,fillColor=tinta))
        detalle='Sin comparación'
        if delta is not None:
            mejora = delta < 0 if menor_mejor else delta > 0
            estado = 'Sin cambio' if delta == 0 else ('Mejora' if mejora else 'Descenso')
            detalle=f'{delta:+.3f} · {estado}'
        dibujo.add(String(x+5,13,detalle,fontSize=6.5,fillColor=tinta))
    return dibujo
