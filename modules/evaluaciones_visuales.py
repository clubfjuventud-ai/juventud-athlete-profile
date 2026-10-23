"""Pruebas deportivas con unidades reales y comparación respecto al historial personal."""
import math
from datetime import date
from html import escape

PUNTUACIONES = (
    ('pase_efectividad', 'Efectividad de pases', 'Pases'),
    ('tiros_efectividad', 'Efectividad de tiros al arco', 'Tiros'),
)
TIEMPOS = (
    ('conduccion', 'Conducción', 's', True),
    ('illinois', 'Illinois', 's', True),
    ('velocidad_10m', 'Velocidad 10 m', 's', True),
    ('velocidad_20m', 'Velocidad 20 m', 's', True),
)
FISICAS = TIEMPOS + (('course_navette', 'Course Navette', 'nivel', False),)
METRICAS = tuple((c,n,a) for c,n,a in PUNTUACIONES) + (
    ('conduccion', 'Conducción', 'Conducción'),
    ('illinois', 'Illinois', 'Illinois'),
    ('velocidad_10m', 'Velocidad 10 m', '10 m'),
    ('velocidad_20m', 'Velocidad 20 m', '20 m'),
    ('course_navette', 'Course Navette', 'Navette'),
)
CAMPOS_ACIERTOS = {c for c,_,_ in PUNTUACIONES}
CAMPOS_TIEMPO = {c for c,_,_,_ in TIEMPOS}
FUENTE_VO2 = 'https://pubmed.ncbi.nlm.nih.gov/3184250/'
NOTA_RADAR = 'Radar: 5 aciertos = 100%; en tiempos y Navette, 100% es el mejor registro personal del historial. No es una nota global ni un baremo por edad.'


def numero(valor):
    try:
        valor = float(valor)
        return valor if math.isfinite(valor) else None
    except (TypeError, ValueError):
        return None


def resultado(registro, campo):
    valor = numero((registro or {}).get(campo))
    if valor is None:
        return None
    if campo in CAMPOS_ACIERTOS:
        return valor if 0 <= valor <= 5 and valor.is_integer() else None
    if campo == 'course_navette':
        return valor if 1 <= valor <= 21 and valor.is_integer() else None
    return valor if valor > 0 else None


def variacion(actual, anterior, campo):
    a, b = resultado(actual, campo), resultado(anterior, campo)
    return a-b if a is not None and b is not None else None


def validar_resultados(registro):
    for campo,nombre,_ in METRICAS:
        if registro.get(campo) is not None and resultado(registro,campo) is None:
            return f'Revisa {nombre}: utiliza aciertos enteros de 0 a 5, tiempos positivos o un nivel entero de 1 a 21, según la prueba.'
    if not any(resultado(registro,c) is not None for c,_,_ in METRICAS):
        return 'Registra al menos un resultado antes de guardar.'
    return None


def ordenar_evaluaciones(registros):
    return sorted(registros,key=lambda r:(str(r.get('fecha_evaluacion') or ''),str(r.get('id') or '')),reverse=True)


def fecha_evaluacion(registro):
    from modules.utilidades import fecha_legible
    return fecha_legible((registro or {}).get('fecha_evaluacion'))


def edad_en_evaluacion(jugador, registro):
    try:
        nacimiento = date.fromisoformat(str(jugador.get('fecha_nacimiento'))[:10])
        evaluacion = date.fromisoformat(str(registro.get('fecha_evaluacion'))[:10])
        if nacimiento > evaluacion:
            return None
        return evaluacion.year-nacimiento.year-((evaluacion.month,evaluacion.day)<(nacimiento.month,nacimiento.day))
    except (TypeError,ValueError):
        return None


def estimar_vo2max(jugador, registro):
    """Léger 1988, 20 m: v=8+0.5*nivel. Validación 8–19 y adultos hasta 50.

    Para adultos se utiliza A=18, conforme al artículo original. La edad siempre
    corresponde a la fecha de evaluación. No se extrapola a edades no validadas.
    """
    nivel = resultado(registro,'course_navette')
    edad = edad_en_evaluacion(jugador or {},registro or {})
    if nivel is None or edad is None or not 8 <= edad <= 50:
        return None
    velocidad = 8+0.5*nivel
    edad_formula = min(edad,18)
    return 31.025+3.238*velocidad-3.248*edad_formula+0.1536*edad_formula*velocidad


def referencias_personales(registros):
    referencias = {campo:5.0 for campo in CAMPOS_ACIERTOS}
    for campo,_,_ in METRICAS:
        if campo in CAMPOS_ACIERTOS:
            continue
        valores=[resultado(r,campo) for r in registros]
        valores=[v for v in valores if v is not None]
        referencias[campo]=(min(valores) if campo in CAMPOS_TIEMPO else max(valores)) if valores else None
    return referencias


def porcentaje_radar(registro, campo, referencias):
    valor=resultado(registro,campo)
    referencia=referencias.get(campo)
    if valor is None or referencia is None or referencia <= 0:
        return None
    return min(100.0,100*referencia/valor if campo in CAMPOS_TIEMPO else 100*valor/referencia)


def puntos_radar(registro,cx=200,cy=200,radio=125,referencias=None):
    referencias=referencias if referencias is not None else referencias_personales([registro or {}])
    puntos=[]
    for i,(campo,_,_) in enumerate(METRICAS):
        valor=porcentaje_radar(registro,campo,referencias)
        if valor is None:
            puntos.append(None)
        else:
            a=-math.pi/2+i*2*math.pi/len(METRICAS)
            puntos.append((cx+radio*valor/100*math.cos(a),cy+radio*valor/100*math.sin(a)))
    return puntos


def texto_resultado(registro,campo):
    valor=resultado(registro,campo)
    if valor is None:
        return 'Sin registrar'
    if campo in CAMPOS_ACIERTOS:
        return f'{valor:g}/5'
    return f'{valor:.3f} s' if campo in CAMPOS_TIEMPO else f'Nivel {valor:g}'


def radar_svg(actual,anterior=None,color='#D4AF37',comparacion='#40C9CF',referencias=None):
    referencias=referencias if referencias is not None else referencias_personales([actual or {},anterior or {}])
    cantidad=len(METRICAS)
    partes=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" aria-label="Pruebas deportivas: comparación respecto al historial personal">',
            '<rect x="1" y="1" width="398" height="398" rx="22" fill="#111820" stroke="#33404C"/>']
    for escala in (20,40,60,80,100):
        puntos=[(200+125*escala/100*math.cos(-math.pi/2+i*2*math.pi/cantidad),200+125*escala/100*math.sin(-math.pi/2+i*2*math.pi/cantidad)) for i in range(cantidad)]
        partes.append('<polygon points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in puntos)+'" fill="none" stroke="#33404C"/>')
        partes.append(f'<text x="205" y="{200-125*escala/100+11}" fill="#A7B3BF" font-size="9">{escala}%</text>')
    for i,(_,_,etiqueta) in enumerate(METRICAS):
        a=-math.pi/2+i*2*math.pi/cantidad
        x,y=200+125*math.cos(a),200+125*math.sin(a)
        lx,ly=200+154*math.cos(a),200+151*math.sin(a)
        partes.append(f'<line x1="200" y1="200" x2="{x:.2f}" y2="{y:.2f}" stroke="#33404C"/>')
        partes.append(f'<text x="{lx:.2f}" y="{ly+4:.2f}" fill="#E7EDF2" font-family="sans-serif" font-size="11" text-anchor="middle">{escape(etiqueta)}</text>')
    for registro,tono,etiqueta in [(anterior,comparacion,'Comparación'),(actual,color,'Seleccionada')]:
        if not registro:
            continue
        puntos=puntos_radar(registro,referencias=referencias)
        if all(p is not None for p in puntos):
            partes.append('<polygon points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in puntos)+f'" fill="{tono}" fill-opacity="0.16" stroke="{tono}" stroke-width="2.5"/>')
        else:
            for i,p in enumerate(puntos):
                q=puntos[(i+1)%cantidad]
                if p is not None and q is not None:
                    partes.append(f'<line x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="{tono}" stroke-width="2.5"/>')
        for (campo,nombre,_),p in zip(METRICAS,puntos):
            if p is not None:
                partes.append(f'<circle cx="{p[0]:.2f}" cy="{p[1]:.2f}" r="4" fill="{tono}"><title>{escape(etiqueta)} · {escape(nombre)}: {escape(texto_resultado(registro,campo))}</title></circle>')
    partes.append(f'<circle cx="55" cy="372" r="4" fill="{color}"/><text x="65" y="376" fill="#E7EDF2" font-family="sans-serif" font-size="10">Seleccionada</text>')
    if anterior:
        partes.append(f'<circle cx="235" cy="372" r="4" fill="{comparacion}"/><text x="245" y="376" fill="#E7EDF2" font-family="sans-serif" font-size="10">Comparación</text>')
    return ''.join(partes)+'</svg>'


def mostrar_panel_evaluaciones(registros,jugador):
    import streamlit as st
    from modules.utilidades import nombre_jugador,grafico_evolucion
    from modules.configuracion import INSTITUCION_SURCOS
    ordenadas=ordenar_evaluaciones(registros)
    clave=str(jugador['id'])
    def etiqueta(i):
        return 'Sin comparación' if i is None else f'{fecha_evaluacion(ordenadas[i])} · Registro {len(ordenadas)-i}'
    st.markdown('#### Comparar evaluaciones')
    st.caption(f"{jugador.get('codigo_jugador') or 'Código pendiente'} · {nombre_jugador(jugador)}")
    fechas,referencia=st.columns(2)
    seleccion=fechas.selectbox('Evaluación que quieres ver',list(range(len(ordenadas))),format_func=etiqueta,key=f'perfil_fecha_{clave}')
    opciones=[None]+[i for i in range(len(ordenadas)) if i!=seleccion]
    predeterminada=seleccion+1 if seleccion+1<len(ordenadas) else None
    comparada=referencia.selectbox('Comparar con',opciones,index=opciones.index(predeterminada),format_func=etiqueta,disabled=len(ordenadas)==1,key=f'perfil_comparacion_{clave}_{seleccion}')
    actual=ordenadas[seleccion]
    anterior=ordenadas[comparada] if comparada is not None else None
    referencias=referencias_personales(ordenadas)
    color='#70A808' if jugador.get('institucion')==INSTITUCION_SURCOS else '#D4AF37'
    grafico,atributos=st.columns([1.1,1.4])
    with grafico:
        st.image(radar_svg(actual,anterior,color=color,referencias=referencias),width=480)
        st.caption(NOTA_RADAR+' Un dato vacío no equivale a cero.')
    with atributos:
        st.markdown('##### Efectividad · aciertos de 5 intentos')
        for columna,(campo,nombre,_) in zip(st.columns(2),PUNTUACIONES):
            valor=resultado(actual,campo);delta=variacion(actual,anterior,campo)
            columna.metric(nombre,f'{valor:g} / 5' if valor is not None else '—',delta=f'{delta:+g} aciertos' if delta is not None else None)
        st.markdown('##### Course Navette · 20 m')
        nivel=resultado(actual,'course_navette');delta=variacion(actual,anterior,'course_navette')
        columnas=st.columns(2)
        columnas[0].metric('Nivel alcanzado',f'{nivel:g}' if nivel is not None else '—',delta=f'{delta:+g} niveles' if delta is not None else None)
        vo2=estimar_vo2max(jugador,actual);previo=estimar_vo2max(jugador,anterior) if anterior else None
        columnas[1].metric('VO₂máx estimado',f'{vo2:.1f} ml/kg/min' if vo2 is not None else '—',delta=f'{vo2-previo:+.1f} ml/kg/min' if vo2 is not None and previo is not None else None)
        st.caption('Estimación Léger (1988), protocolo de 20 m: inicio a 8,5 km/h y aumento de 0,5 km/h por nivel. Usa la edad en la fecha de evaluación; para adultos, A=18. No se estima sin fecha de nacimiento o fuera de 8–50 años.')
    st.markdown('##### Pruebas cronometradas · segundos')
    for columna,(campo,nombre,_,_) in zip(st.columns(4),TIEMPOS):
        valor=resultado(actual,campo);delta=variacion(actual,anterior,campo)
        columna.metric(nombre,f'{valor:.3f} s' if valor is not None else '—',delta=f'{delta:+.3f} s' if delta is not None else None,delta_color='inverse')
    st.caption('En conducción, Illinois y velocidades de 10 y 20 m, menos segundos es mejor.')
    if len(ordenadas)==1:
        st.info('Primera evaluación registrada. Cuando haya otra fecha podrás comparar la evolución.')
    with st.expander('Observaciones del evaluador'):
        for campo,titulo in [('fortalezas','Fortalezas'),('aspectos_mejora','Aspectos por mejorar'),('recomendaciones','Recomendaciones')]:
            st.markdown(f'**{titulo}**');st.text(str(actual.get(campo) or 'Sin observaciones registradas.'))
    with st.expander('Ver evolución por fechas'):
        grafico_evolucion(ordenadas,[(c,n) for c,n,_ in PUNTUACIONES],'Efectividad · aciertos sobre 5')
        grafico_evolucion(ordenadas,[(c,n) for c,n,_,_ in TIEMPOS],'Pruebas cronometradas · segundos')
        grafico_evolucion(ordenadas,[('course_navette','Nivel alcanzado')],'Course Navette · nivel alcanzado')
        derivados=[dict(fecha_evaluacion=r.get('fecha_evaluacion'),vo2max=estimar_vo2max(jugador,r)) for r in ordenadas]
        grafico_evolucion(derivados,[('vo2max','VO₂máx estimado (ml/kg/min)')],'VO₂máx estimado')


def cuadro_evaluacion_pdf(actual,anterior,paleta,jugador=None,referencias=None):
    from reportlab.graphics.shapes import Drawing,Polygon,Line,Circle,String,Rect
    from reportlab.lib.colors import HexColor,Color
    referencias=referencias if referencias is not None else referencias_personales([actual or {},anterior or {}])
    dibujo=Drawing(465,350)
    tinta=HexColor(paleta['principal']);acento=HexColor(paleta['acento']);comparacion=HexColor('#637B8E')
    dibujo.add(Rect(0,0,465,350,rx=9,ry=9,fillColor=HexColor('#FAFBFC'),strokeColor=HexColor(paleta['borde'])))
    cx,cy,radio=119,220,76
    cantidad=len(METRICAS)
    for escala in (20,40,60,80,100):
        puntos=[]
        for i in range(cantidad):
            a=math.pi/2-i*2*math.pi/cantidad
            puntos.extend([cx+radio*escala/100*math.cos(a),cy+radio*escala/100*math.sin(a)])
        dibujo.add(Polygon(puntos,fillColor=None,strokeColor=HexColor('#DDE3E8'),strokeWidth=0.5))
    for i,(_,_,nombre) in enumerate(METRICAS):
        a=math.pi/2-i*2*math.pi/cantidad
        dibujo.add(Line(cx,cy,cx+radio*math.cos(a),cy+radio*math.sin(a),strokeColor=HexColor('#DDE3E8'),strokeWidth=0.5))
        dibujo.add(String(cx+99*math.cos(a),cy+96*math.sin(a)-3,nombre,fontName='Helvetica',fontSize=6.5,textAnchor='middle',fillColor=tinta))
    for registro,tono in [(anterior,comparacion),(actual,acento)]:
        if not registro:continue
        puntos=puntos_radar(registro,cx,cy,radio,referencias)
        puntos=[(p[0],2*cy-p[1]) if p is not None else None for p in puntos]
        if all(p is not None for p in puntos):
            dibujo.add(Polygon([v for p in puntos for v in p],fillColor=Color(tono.red,tono.green,tono.blue,alpha=0.15),strokeColor=tono,strokeWidth=1.4))
        else:
            for i,p in enumerate(puntos):
                q=puntos[(i+1)%cantidad]
                if p is not None and q is not None:dibujo.add(Line(*p,*q,strokeColor=tono,strokeWidth=1.4))
        for p in puntos:
            if p is not None:dibujo.add(Circle(*p,2.2,fillColor=tono,strokeColor=None))
    dibujo.add(String(18,332,'PERFIL DE PRUEBAS',fontName='Helvetica-Bold',fontSize=9,fillColor=tinta))
    dibujo.add(String(18,112,'Seleccionada: '+fecha_evaluacion(actual),fontSize=7,fillColor=tinta))
    dibujo.add(String(18,100,'Comparación: '+fecha_evaluacion(anterior) if anterior else 'Primera evaluación · sin comparación',fontSize=7,fillColor=comparacion))
    for i,(campo,nombre,_) in enumerate(METRICAS):
        x,y=243,306-i*25
        dibujo.add(Rect(x,y-12,207,23,rx=3,ry=3,fillColor=HexColor(paleta['fondo']),strokeColor=None))
        dibujo.add(String(x+6,y+1,nombre,fontSize=6.8,fillColor=tinta))
        delta=variacion(actual,anterior,campo);texto=texto_resultado(actual,campo)
        if delta is not None:texto+=f' ({delta:+.3f})' if campo in CAMPOS_TIEMPO else f' ({delta:+g})'
        dibujo.add(String(x+200,y-7,texto,fontName='Helvetica-Bold',fontSize=7,textAnchor='end',fillColor=tinta))
    dibujo.add(String(243,126,'Tiempos: menor es mejor. Pases y tiros: sobre 5.',fontSize=6.2,fillColor=comparacion))
    dibujo.add(String(18,83,'Radar: 5 aciertos = 100%; tiempos y Navette respecto al mejor registro del historial.',fontSize=6,fillColor=comparacion))
    for x,titulo,texto in [
        (12,'Course Navette · nivel alcanzado',texto_resultado(actual,'course_navette')),
        (237,'VO2max estimado · ml/kg/min',f'{estimar_vo2max(jugador or {},actual):.1f}' if estimar_vo2max(jugador or {},actual) is not None else 'No estimable con los datos disponibles'),
    ]:
        dibujo.add(Rect(x,24,216,46,rx=4,ry=4,fillColor=HexColor(paleta['fondo']),strokeColor=None))
        dibujo.add(String(x+7,54,titulo,fontSize=7,fillColor=tinta))
        dibujo.add(String(x+7,37,texto,fontName='Helvetica-Bold',fontSize=8,fillColor=tinta))
    dibujo.add(String(12,10,'VO2max: estimación Léger 1988, 20 m, edad en la evaluación (8–50 años); adultos A=18.',fontSize=6,fillColor=comparacion))
    return dibujo
