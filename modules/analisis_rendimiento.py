"""Interpretación local y verificable. No usa IA generativa ni servicios externos."""
import hashlib
import json
import math
import re
from collections import Counter
from datetime import date

from modules.evaluaciones_visuales import (
    METRICAS, CAMPOS_ACIERTOS, CAMPOS_TIEMPO, resultado, numero,
    estimar_vo2max, edad_en_evaluacion,
)

SIGNIFICADOS = {
    'pase_efectividad': 'Cuenta aciertos de 5 intentos: 1 acierto equivale a 20 puntos porcentuales. Describe esa prueba, no el porcentaje de pases de un partido.',
    'tiros_efectividad': 'Cuenta aciertos de 5 intentos. Más aciertos es mejor; para comparar deben mantenerse la distancia, el objetivo y las condiciones.',
    'conduccion': 'Mide el tiempo del recorrido con balón. Menos segundos es mejor si se conserva el mismo recorrido. El tiempo no describe por sí solo todos los aspectos de la técnica.',
    'illinois': 'Mide el tiempo de un circuito de cambios de dirección. Menos segundos es mejor; utiliza el mismo circuito, superficie y sistema de cronometraje.',
    'velocidad_10m': 'Describe el tiempo de aceleración en 10 metros. Menos segundos es mejor. Mantener la salida y el método de cronometraje permite una comparación útil.',
    'velocidad_20m': 'Describe el tiempo para recorrer 20 metros. Menos segundos es mejor; este dato no equivale directamente a la velocidad máxima del deportista.',
    'course_navette': 'Es el último nivel completo alcanzado en el protocolo de 20 m. Más niveles es mejor. La velocidad asociada es 8 + 0,5 × nivel, en km/h.',
}


def n(valor, decimales=1):
    return f'{valor:.{decimales}f}'.replace('.', ',')


def fecha_iso(valor):
    try:
        return date.fromisoformat(str(valor)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def fecha_texto(valor):
    return date.fromisoformat(valor).strftime('%d/%m/%Y') if valor else 'sin fecha válida'


def valor_texto(valor, campo):
    if campo in CAMPOS_ACIERTOS:
        return f'{valor:g}/5 ({valor*20:g}%)'
    if campo in CAMPOS_TIEMPO:
        return f'{n(valor,3)} s'
    return f'nivel {valor:g}'


def comparar(inicio, fin, campo):
    delta=fin-inicio
    igual=math.isclose(delta,0,abs_tol=0.0005 if campo in CAMPOS_TIEMPO else 1e-9)
    estado='estable' if igual else ('mejora' if (delta<0 if campo in CAMPOS_TIEMPO else delta>0) else 'retroceso')
    if igual:
        return estado,f'Se mantiene en {valor_texto(fin,campo)} a la precisión registrada.'
    if campo in CAMPOS_ACIERTOS:
        detalle=f'{abs(delta):g} acierto{"" if abs(delta)==1 else "s"} {"más" if delta>0 else "menos"}, lo que equivale a {abs(delta)*20:g} puntos porcentuales de efectividad'
    elif campo in CAMPOS_TIEMPO:
        relativo=abs(delta)/inicio*100
        detalle=f'{"redujo" if delta<0 else "aumentó"} {n(abs(delta),3)} s ({n(relativo)}% {"menos" if delta<0 else "más"} tiempo)'
    else:
        detalle=f'{abs(delta):g} nivel{"" if abs(delta)==1 else "es"} {"más" if delta>0 else "menos"}; la velocidad asociada pasa de {n(8+0.5*inicio)} a {n(8+0.5*fin)} km/h'
    return estado,f'Pasó de {valor_texto(inicio,campo)} a {valor_texto(fin,campo)}: {detalle}. El resultado muestra {"una mejora" if estado=="mejora" else "un retroceso"} en esta comparación.'


def analizar_prueba(registros,campo,nombre,inicio_periodo,fin_periodo):
    por_fecha={}
    invalidos=0
    for registro in registros:
        fecha=fecha_iso(registro.get('fecha_evaluacion'))
        valor=resultado(registro,campo)
        if registro.get(campo) is not None and valor is None:
            invalidos+=1
        if fecha and valor is not None:
            por_fecha.setdefault(fecha,[]).append(valor)
    conflictos=[f for f,valores in por_fecha.items() if len(set(valores))>1]
    mediciones=sorted((f,valores[0]) for f,valores in por_fecha.items() if len(set(valores))==1)
    salida={'campo':campo,'nombre':nombre,'significado':SIGNIFICADOS[campo],
            'estado':'sin_datos','comparable_periodo':False,'texto':'','avisos':[],
            'mediciones':mediciones}
    if invalidos:
        salida['avisos'].append(f'{invalidos} valor(es) no cumplen la escala o unidad y se excluyeron de la comparación.')
    if conflictos:
        salida['estado']='revisar'
        salida['texto']='Hay resultados distintos para una misma fecha ('+', '.join(fecha_texto(f) for f in sorted(conflictos))+'). Revisa esos registros: sin hora u orden de intentos no es posible decidir cuál representa la evolución.'
        return salida
    if not mediciones:
        salida['texto']='No hay un resultado válido con fecha para esta prueba. No se interpreta como cero ni como bajo rendimiento.'
        return salida
    primera,ultimo=mediciones[0],mediciones[-1]
    salida.update(primera=primera,ultima=ultimo)
    if len(mediciones)==1:
        salida['estado']='primera_medicion'
        salida['texto']=f'Única medición válida: {valor_texto(ultimo[1],campo)}, el {fecha_texto(ultimo[0])}. Hace falta una medición en otra fecha para valorar cambios.'
    else:
        estado,texto=comparar(primera[1],ultimo[1],campo)
        salida['estado']=estado
        salida['comparable_periodo']=primera[0]==inicio_periodo and ultimo[0]==fin_periodo
        salida['texto']=f'Del {fecha_texto(primera[0])} al {fecha_texto(ultimo[0])}: {texto}'
        if len(mediciones)>2:
            previo=mediciones[-2]
            estado_ultimo,texto_ultimo=comparar(previo[1],ultimo[1],campo)
            salida['texto']+=f' Respecto a la medición inmediatamente anterior ({fecha_texto(previo[0])}): {texto_ultimo}'
            if estado=='mejora' and estado_ultimo=='retroceso':
                salida['avisos'].append('El balance desde el inicio es positivo, pero el último intervalo retrocede; la evolución no ha sido continua.')
        else:
            salida['avisos'].append('Dos mediciones describen un cambio; todavía no demuestran una tendencia sostenida.')
    if ultimo[0]!=fin_periodo:
        salida['avisos'].append(f'Esta prueba no tiene un resultado válido en la última fecha del expediente ({fecha_texto(fin_periodo)}); no se presenta como rendimiento actualizado.')
    if primera[0]!=inicio_periodo:
        salida['avisos'].append('Esta prueba empezó a medirse después del primer registro del expediente. Su comparación utiliza sus propias fechas, no todo el periodo.')
    return salida


def analisis_vo2(jugador, prueba):
    if prueba['estado']=='revisar':
        return 'Primero hay que resolver los resultados de Navette con fechas duplicadas. No se calcula una evolución del VO₂máx sobre datos ambiguos.'
    mediciones=prueba['mediciones']
    if not mediciones:
        return 'Sin un nivel completo de Course Navette y una fecha válidos, no se puede estimar el VO₂máx.'
    valores=[]
    for fecha,nivel in mediciones:
        registro={'fecha_evaluacion':fecha,'course_navette':nivel}
        vo2=estimar_vo2max(jugador,registro)
        if vo2 is not None:
            valores.append((fecha,nivel,vo2,edad_en_evaluacion(jugador,registro)))
    if not valores:
        return 'No hay datos suficientes para una estimación aplicable: se necesita la fecha de nacimiento, la fecha de evaluación y una edad entre 8 y 50 años. El nivel de Navette conserva su valor aunque el VO₂máx no sea estimable.'
    primero,ultimo=valores[0],valores[-1]
    texto=f'El último VO₂máx estimable es {n(ultimo[2])} ml/kg/min, para el nivel {ultimo[1]:g} del {fecha_texto(ultimo[0])}, con {ultimo[3]} años en esa evaluación.'
    if len(valores)>1:
        texto+=f' En la primera fecha estimable ({fecha_texto(primero[0])}) era {n(primero[2])} ml/kg/min: diferencia de {n(ultimo[2]-primero[2])} ml/kg/min.'
        if primero[1]==ultimo[1] and primero[3]!=ultimo[3] and not math.isclose(primero[2],ultimo[2]):
            texto+=' El nivel alcanzado no cambió; esta diferencia del VO₂máx estimado procede del término de edad de la ecuación, no de una mejora o pérdida demostrada en el test.'
        elif min(primero[3],18)!=min(ultimo[3],18):
            texto+=' La edad utilizada también cambió entre fechas, por lo que no toda la diferencia estimada debe atribuirse al rendimiento.'
    if ultimo[0]!=mediciones[-1][0]:
        texto+=' No corresponde al último Navette registrado: para esa fecha faltan datos o la edad queda fuera del rango aplicable.'
    return texto+' Se calcula con Léger (1988) para el protocolo de 20 m. Es una estimación derivada del Navette, no una prueba independiente ni una medición de laboratorio.'


def contexto_perfil(jugador,historial_deportivo,academico,evidencias,incluir_academico):
    textos=[]
    medidas=[]
    for campo,unidad in [('estatura','cm'),('peso','kg')]:
        valor=numero(jugador.get(campo))
        if valor is not None and valor>0:medidas.append(f'{campo}: {n(valor)} {unidad}')
    if medidas:
        textos.append('Datos físicos actuales: '+', '.join(medidas)+'. Sin mediciones históricas fechadas no se puede deducir crecimiento, cambios de composición corporal ni el motivo de un resultado.')
    if jugador.get('posicion_principal'):
        textos.append('Posición registrada: '+str(jugador['posicion_principal'])+'. Las pruebas describen capacidades concretas; estos datos no bastan para calificar el desempeño táctico ni todo el rendimiento en partido.')
    if historial_deportivo is None:
        textos.append('El historial deportivo no está disponible en esta consulta; no se interpreta como ausencia de trayectoria.')
    elif not historial_deportivo:
        textos.append('No hay temporadas deportivas visibles registradas para complementar el análisis de las pruebas.')
    else:
        partes=[]
        for campo,nombre in [('partidos_disputados','partidos'),('minutos_jugados','minutos'),('goles','goles'),('asistencias','asistencias')]:
            valores=[numero(r.get(campo)) for r in historial_deportivo]
            disponibles=[v for v in valores if v is not None and v>=0]
            if disponibles:
                partes.append(f'{sum(disponibles):g} {nombre}'+(' (total parcial: hay registros sin ese dato)' if len(disponibles)!=len(valores) else ''))
        textos.append(f'En {len(historial_deportivo)} registro(s) de trayectoria: '+('; '.join(partes) or 'faltan estadísticas cuantificadas')+'. Estos totales describen participación; sin fechas y condiciones comparables no demuestran por sí solos una mejora entre temporadas.')
    if incluir_academico:
        if academico is None:
            textos.append('Los datos académicos no están disponibles en esta consulta.')
        elif academico:
            notas=[numero(r.get('promedio')) for r in academico]
            notas=[v for v in notas if v is not None and 0<=v<=10]
            textos.append(f'Hay {len(academico)} periodo(s) académico(s) visible(s). '+(f'Las notas registradas van de {n(min(notas))} a {n(max(notas))} sobre 10. ' if notas else 'Faltan promedios válidos. ')+'No se utilizan las notas escolares para explicar causas del rendimiento físico.')
        else:
            textos.append('No hay periodos académicos visibles registrados. No se infiere un nivel académico a partir de esa ausencia.')
    if evidencias is None:
        textos.append('Las evidencias no están disponibles en esta consulta.')
    elif evidencias:
        tipos=Counter(str(r.get('tipo') or 'sin tipo') for r in evidencias)
        textos.append('Evidencias registradas: '+', '.join(f'{cantidad} de tipo {tipo}' for tipo,cantidad in sorted(tipos.items()))+'. Este informe contabiliza los registros; no ha analizado el contenido de vídeos, fotografías o documentos.')
    return textos


def generar_analisis(jugador,evaluaciones,historial_deportivo=None,academico=None,evidencias=None,incluir_academico=False):
    if evaluaciones is None:
        raise ValueError('No se pudieron cargar las evaluaciones. Reintenta antes de generar el análisis.')
    validos=[r for r in evaluaciones if fecha_iso(r.get('fecha_evaluacion')) and any(resultado(r,c) is not None for c,_,_ in METRICAS)]
    fechas=sorted({fecha_iso(r.get('fecha_evaluacion')) for r in validos})
    inicio,fin=(fechas[0],fechas[-1]) if fechas else (None,None)
    pruebas=[analizar_prueba(evaluaciones,c,nombre,inicio,fin) for c,nombre,_ in METRICAS]
    conteos=Counter(p['estado'] for p in pruebas if p['comparable_periodo'])
    comparables=sum(conteos.values())
    if not fechas:
        resumen='Aún no hay evaluaciones con fecha y resultados válidos. El primer paso es registrar una medición inicial; no se puede concluir si ha mejorado ni si tiene bajo rendimiento.'
    elif len(fechas)==1:
        resumen=f'Solo hay resultados de una fecha ({fecha_texto(inicio)}). Sirven como punto de partida, pero hace falta otra fecha para comparar la evolución.'
    elif not comparables:
        resumen='Hay varias fechas, pero ninguna prueba tiene mediciones no ambiguas tanto al inicio como al final del periodo. Hace falta completar o revisar los registros para describir un progreso global.'
    else:
        resumen=(f'Del {fecha_texto(inicio)} al {fecha_texto(fin)}, de {comparables} prueba{"" if comparables==1 else "s"} comparable{"" if comparables==1 else "s"} en ambas fechas: '
                 f'{conteos["mejora"]} {"mejoró" if conteos["mejora"]==1 else "mejoraron"}, '
                 f'{conteos["estable"]} {"se mantuvo" if conteos["estable"]==1 else "se mantuvieron"} y '
                 f'{conteos["retroceso"]} {"retrocedió" if conteos["retroceso"]==1 else "retrocedieron"}.')
        if conteos['mejora'] and not conteos['retroceso']:
            resumen+=' El balance de esos resultados es positivo.'
        elif conteos['mejora'] and conteos['retroceso']:
            resumen+=' La evolución es mixta: conviene revisar cada prueba por separado.'
        elif conteos['retroceso']:
            resumen+=' Hay resultados que necesitan revisión con el entrenador; los registros no identifican la causa.'
        else:
            resumen+=' Las mediciones iniciales y finales no muestran cambios a la precisión registrada.'
    prioridades=[]
    revisar=[p['nombre'] for p in pruebas if p['estado']=='revisar']
    if revisar:prioridades.append('Resolver resultados distintos de una misma fecha en: '+', '.join(revisar)+'.')
    bajas=[p['nombre'] for p in pruebas if p['comparable_periodo'] and p['estado']=='retroceso']
    if bajas:prioridades.append('Revisar con el entrenador '+', '.join(bajas)+': confirmar que se repitió el mismo protocolo y contrastar con otra medición antes de atribuir causas.')
    faltantes=[p['nombre'] for p in pruebas if not p['comparable_periodo']]
    if faltantes:prioridades.append('Completar mediciones comparables en '+', '.join(faltantes)+'. No sustituir datos ausentes por cero.')
    prioridades.append('Mantener recorrido, distancias, material, salida y cronometraje comparables; registrar fecha y resultados reales. Con cinco intentos, cada acierto modifica la efectividad en 20 puntos porcentuales.')
    prioridades.append('Este informe describe cambios del propio deportista. No asigna un baremo por edad, una nota global ni causas como falta de entrenamiento, cansancio o lesión que los datos no permiten verificar.')
    comentarios=[]
    if fin:
        for registro in validos:
            if fecha_iso(registro.get('fecha_evaluacion'))==fin:
                for campo,titulo in [('fortalezas','Fortalezas'),('aspectos_mejora','Aspectos por mejorar'),('recomendaciones','Recomendaciones')]:
                    if registro.get(campo):comentarios.append(f'{titulo} ({fecha_texto(fin)}): {registro[campo]}')
    return {'inicio':inicio,'fin':fin,'fechas':len(fechas),'registros':len(evaluaciones),
            'excluidos':len(evaluaciones)-len(validos),'comparables':comparables,
            'conteos':dict(conteos),'resumen':resumen,'pruebas':pruebas,
            'vo2':analisis_vo2(jugador,next(p for p in pruebas if p['campo']=='course_navette')),
            'prioridades':prioridades,'comentarios':comentarios,
            'contexto':contexto_perfil(jugador,historial_deportivo,academico,evidencias,incluir_academico)}


def texto_informe(informe):
    lineas=['ANÁLISIS DE RENDIMIENTO',informe['resumen']]
    if informe['excluidos']:lineas.append(f"Registros sin fecha o resultados válidos excluidos del periodo: {informe['excluidos']}.")
    for p in informe['pruebas']:
        lineas.extend(['',p['nombre'],p['texto'],*p['avisos'],'Qué significa: '+p['significado']])
    lineas.extend(['','VO₂máx estimado',informe['vo2'],'','Qué revisar',*informe['prioridades'],'','Contexto',*informe['contexto']])
    if informe['comentarios']:lineas.extend(['','Comentarios del personal registrados; no son conclusiones del cálculo',*informe['comentarios']])
    return '\n'.join(lineas)


def mostrar_analisis_rendimiento(jugador,evaluaciones,historial_deportivo,academico,evidencias,usuario_id,incluir_academico=False):
    import streamlit as st
    st.markdown('#### Análisis de rendimiento')
    st.caption('Informe automático basado en los registros de este expediente visibles para tu cuenta.')
    clave=f"analisis_rendimiento_{usuario_id}_{jugador['id']}"
    datos=[jugador,evaluaciones,historial_deportivo,academico if incluir_academico else None,evidencias,incluir_academico]
    huella=hashlib.sha256(json.dumps(datos,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
    if st.button('Análisis de rendimiento inteligente',key=clave+'_boton',disabled=evaluaciones is None,use_container_width=True):
        informe=generar_analisis(jugador,evaluaciones,historial_deportivo,academico,evidencias,incluir_academico)
        st.session_state[clave]={'huella':huella,'informe':informe}
    if evaluaciones is None:
        st.info('Primero hay que cargar correctamente las evaluaciones para poder analizarlas.')
        return
    guardado=st.session_state.get(clave)
    if not guardado:return
    if guardado['huella']!=huella:
        st.info('Los datos del expediente han cambiado. Pulsa el botón para actualizar el análisis.')
        return
    informe=guardado['informe']
    with st.container(border=True):
        st.markdown('##### ¿Ha mejorado desde que empezó?')
        st.write(informe['resumen'])
        if informe['comparables']:
            for columna,(estado,titulo) in zip(st.columns(3),[('mejora','Mejoraron'),('estable','Se mantuvieron'),('retroceso','Retrocedieron')]):
                columna.metric(titulo,informe['conteos'].get(estado,0))
        if informe['excluidos']:st.caption(f"{informe['excluidos']} registro(s) sin fecha o resultados válidos no se utilizan para describir el periodo.")
    with st.expander('¿Qué cambió y qué significa cada prueba?',expanded=True):
        for p in informe['pruebas']:
            st.markdown('**'+p['nombre']+'**')
            st.write(p['texto'])
            for aviso in p['avisos']:st.caption(aviso)
            st.caption('Qué mide: '+p['significado'])
    with st.expander('¿Cómo se interpreta el VO₂máx estimado?',expanded=True):st.write(informe['vo2'])
    with st.expander('¿Qué conviene revisar con el entrenador?',expanded=True):
        for prioridad in informe['prioridades']:st.write('• '+prioridad)
    with st.expander('Contexto de los demás datos del expediente'):
        for texto in informe['contexto']:st.text(texto)
    if informe['comentarios']:
        with st.expander('Comentarios registrados por el personal'):
            st.caption('Estos comentarios se reproducen como contexto; no se presentan como conclusiones del cálculo.')
            for texto in informe['comentarios']:st.text(texto)
    codigo=re.sub(r'[^\w-]','_',str(jugador.get('codigo_jugador') or 'deportista'))
    st.download_button('Descargar análisis de rendimiento (.txt)',texto_informe(informe),file_name=f'analisis_rendimiento_{codigo}.txt',mime='text/plain',key=clave+'_descarga')
