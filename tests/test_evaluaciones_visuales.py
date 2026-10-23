import base64
import copy
import math
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Table

from modules import autenticacion, informes_pdf
from modules.evaluaciones_visuales import (
    PUNTUACIONES, METRICAS, resultado, variacion, ordenar_evaluaciones, puntos_radar,
    radar_svg, referencias_personales, porcentaje_radar, estimar_vo2max,
    edad_en_evaluacion, validar_resultados,
)
from test_regresiones import Cliente


def evaluacion(identificador,fecha,puntuacion,tiempo):
    return dict(id=identificador,jugador_id=1,fecha_evaluacion=fecha,
                conduccion=tiempo*4,velocidad_10m=tiempo,velocidad_20m=tiempo*2,
                illinois=tiempo*5,course_navette=3+puntuacion,
                **{campo:puntuacion for campo,_,_ in PUNTUACIONES})


class DatosVisuales(unittest.TestCase):
    def setUp(self):
        self.anterior=evaluacion('a','2026-09-01',3,3.1)
        self.actual=evaluacion('b','2026-10-01',4,2.9)

    def test_orden_cronologico_sin_modificar_originales(self):
        datos=[self.anterior,self.actual];antes=copy.deepcopy(datos)
        self.assertEqual([e['id'] for e in ordenar_evaluaciones(datos)],['b','a'])
        self.assertEqual(datos,antes)

    def test_variaciones_conservan_unidades_y_signo(self):
        self.assertAlmostEqual(variacion(self.actual,self.anterior,'velocidad_10m'),-0.2)
        self.assertEqual(variacion(self.actual,self.anterior,'pase_efectividad'),1)
        self.assertIsNone(variacion(self.actual,None,'pase_efectividad'))

    def test_datos_faltantes_y_no_finitos_no_equivalen_a_cero(self):
        for valor in [None,'','abc',float('nan'),float('inf')]:
            with self.subTest(valor=valor):self.assertIsNone(resultado({'pase_efectividad':valor},'pase_efectividad'))
        self.assertEqual(resultado({'pase_efectividad':0},'pase_efectividad'),0)
        self.assertIsNone(resultado({'velocidad_10m':0},'velocidad_10m'))

    def test_aciertos_solo_enteros_de_cero_a_cinco(self):
        for v in range(6):self.assertEqual(resultado({'tiros_efectividad':v},'tiros_efectividad'),v)
        for v in [-1,5.5,6,10]:self.assertIsNone(resultado({'tiros_efectividad':v},'tiros_efectividad'))

    def test_validacion_admite_cero_aciertos_y_rechaza_eval_vacia(self):
        self.assertIsNone(validar_resultados({'pase_efectividad':0}))
        self.assertIsNotNone(validar_resultados({}))
        self.assertIsNotNone(validar_resultados({'conduccion':0}))
        self.assertIsNotNone(validar_resultados({'course_navette':6.5}))

    def test_radio_respeta_efectividad_sobre_cinco(self):
        puntos=puntos_radar({'pase_efectividad':5,'tiros_efectividad':0})
        self.assertAlmostEqual(math.dist((200,200),puntos[0]),125)
        self.assertEqual(puntos[1],(200.0,200.0))
        self.assertTrue(all(p is None for p in puntos[2:]))

    def test_mejor_tiempo_extiende_radar_con_referencias_compartidas(self):
        ref=referencias_personales([self.actual,self.anterior])
        self.assertEqual(porcentaje_radar(self.actual,'conduccion',ref),100)
        self.assertLess(porcentaje_radar(self.anterior,'conduccion',ref),100)
        self.assertEqual(porcentaje_radar(self.actual,'pase_efectividad',ref),80)

    def test_radar_incompleto_no_inventa_poligono_ni_puntos(self):
        raiz=ET.fromstring(radar_svg({'pase_efectividad':0,'conduccion':12.3}))
        ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(raiz.findall('.//s:circle/s:title',ns)),2)
        self.assertFalse(any(p.get('fill-opacity') for p in raiz.findall('.//s:polygon',ns)))

    def test_superposicion_de_dos_perfiles_sin_actitudinal(self):
        raiz=ET.fromstring(radar_svg(self.actual,self.anterior));ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(raiz.findall('.//s:circle/s:title',ns)),2*len(METRICAS))
        self.assertEqual(sum(p.get('fill-opacity')=='0.16' for p in raiz.findall('.//s:polygon',ns)),2)
        texto=ET.tostring(raiz).decode()
        for campo in ['Disciplina','Compromiso','Responsab.','Esfuerzo','Equipo']:self.assertNotIn(campo,texto)

    def test_pdf_usa_cuadros_vectoriales_en_lugar_de_tablas_de_resultados(self):
        capturado=[]
        def capturar(doc,elementos,**kwargs):capturado.extend(elementos)
        with patch.object(informes_pdf.SimpleDocTemplate,'build',autospec=True,side_effect=capturar),patch.object(informes_pdf,'ruta_logo',return_value=None):
            informes_pdf.generar_pdf({'institucion':'Colegio Surcos','fecha_nacimiento':'2014-06-15'},[],[],[self.actual,self.anterior],[],False,True)
        def expandir(elementos):
            for e in elementos:
                yield e
                if hasattr(e,'_content'):yield from expandir(e._content)
        todos=list(expandir(capturado))
        self.assertEqual(sum(isinstance(e,Table) for e in todos),1)
        cuadros=[e for e in todos if isinstance(e,Drawing)]
        self.assertEqual(len(cuadros),2)
        textos=[e.text for d in cuadros for e in d.contents if hasattr(e,'text')]
        self.assertTrue(any('VO2max estimado' in t for t in textos))
        self.assertTrue(any('12.400 s' in t for t in textos))
        self.assertFalse(any('Disciplina' in t for t in textos))


class CourseNavette(unittest.TestCase):
    def test_ecuacion_leguer_con_ejemplo_calculado(self):
        valor=estimar_vo2max({'fecha_nacimiento':'2014-06-15'},{'fecha_evaluacion':'2026-10-01','course_navette':8})
        self.assertAlmostEqual(valor,53.0234,places=4)

    def test_edad_es_la_de_la_evaluacion_no_la_actual(self):
        j={'fecha_nacimiento':'2014-06-15'}
        self.assertEqual(edad_en_evaluacion(j,{'fecha_evaluacion':'2026-06-14'}),11)
        self.assertEqual(edad_en_evaluacion(j,{'fecha_evaluacion':'2026-06-15'}),12)
        self.assertEqual(edad_en_evaluacion(j,{'fecha_evaluacion':'2024-06-15'}),10)

    def test_para_adultos_se_aplica_edad_dieciocho(self):
        v=estimar_vo2max({'fecha_nacimiento':'1986-01-01'},{'fecha_evaluacion':'2026-10-01','course_navette':8})
        self.assertAlmostEqual(v,44.5946,places=4)

    def test_no_estima_sin_datos_o_fuera_del_rango_validado(self):
        r={'fecha_evaluacion':'2026-10-01','course_navette':8}
        for j in [{},{'fecha_nacimiento':'2020-01-01'},{'fecha_nacimiento':'1960-01-01'},{'fecha_nacimiento':'2030-01-01'}]:
            self.assertIsNone(estimar_vo2max(j,r))
        for nivel in [None,0,6.5,22]:
            self.assertIsNone(estimar_vo2max({'fecha_nacimiento':'2014-06-15'},dict(r,course_navette=nivel)))


class PanelInterfaz(unittest.TestCase):
    def iniciar(self,registros,rol='autoridad'):
        cliente=Cliente(rol=rol)
        for j in cliente.datos['jugadores']:j['fecha_nacimiento']='2014-06-15'
        cliente.datos['evaluaciones_integrales']=registros
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20)
        app.session_state.sesion=SimpleNamespace(user=SimpleNamespace(id='prueba',email='prueba@example.invalid'))
        app.session_state.menu_principal='Jugadores Juventud'
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):app.run()
        self.assertEqual(len(app.exception),0,str(app.exception));self.assertEqual(len(app.error),0)
        return app,cliente

    def test_dos_fechas_radar_delta_y_sin_tablas_de_evaluacion(self):
        app,_=self.iniciar([evaluacion('a','2026-09-01',3,3.1),evaluacion('b','2026-10-01',4,2.9)])
        metricas={m.label:m for m in app.metric}
        self.assertEqual(metricas['Efectividad de pases'].value,'4 / 5')
        self.assertEqual(metricas['Efectividad de pases'].delta,'+1 aciertos')
        self.assertEqual(metricas['Velocidad 10 m'].delta,'-0.200 s')
        self.assertEqual(metricas['Conducción'].value,'11.600 s')
        self.assertEqual(metricas['Nivel alcanzado'].value,'7')
        self.assertIn('ml/kg/min',metricas['VO₂máx estimado'].value)
        self.assertNotIn('Disciplina',metricas)
        radares=[i.proto.imgs[0].url for i in app.get('image') if i.proto.imgs[0].url.startswith('data:image/svg+xml;base64,')]
        self.assertEqual(len(radares),1);self.assertIn(b'<svg',base64.b64decode(radares[0].split(',',1)[1]))
        self.assertEqual(len(app.dataframe),1)

    def test_selector_permite_ver_evaluacion_anterior(self):
        app,cliente=self.iniciar([evaluacion('a','2026-09-01',3,3.1),evaluacion('b','2026-10-01',4,2.9)])
        selector=next(s for s in app.selectbox if s.label=='Evaluación que quieres ver')
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):selector.select(1).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(next(m.value for m in app.metric if m.label=='Efectividad de pases'),'3 / 5')

    def test_primera_evaluacion_sin_comparacion(self):
        app,_=self.iniciar([evaluacion('a','2026-09-01',3,3.1)])
        self.assertTrue(next(s for s in app.selectbox if s.label=='Comparar con').disabled)
        self.assertTrue(any('Primera evaluación' in i.value for i in app.info))

    def test_evaluacion_parcial_con_cero_aciertos_real(self):
        app,_=self.iniciar([{'id':'a','jugador_id':1,'fecha_evaluacion':'2026-09-01','pase_efectividad':0}])
        metricas={m.label:m.value for m in app.metric}
        self.assertEqual(metricas['Efectividad de pases'],'0 / 5')
        self.assertEqual(metricas['Conducción'],'—')
        self.assertEqual(metricas['Velocidad 10 m'],'—')

    def test_formulario_tiene_escalas_correctas_y_no_actitudinal(self):
        app,_=self.iniciar([],rol='entrenador')
        entradas={n.label:n for n in app.number_input}
        self.assertEqual(entradas['Efectividad de pases (aciertos / 5)'].max,5)
        self.assertIsNone(entradas['Efectividad de pases (aciertos / 5)'].value)
        self.assertIn('Conducción (s)',entradas);self.assertIn('Illinois (s)',entradas)
        self.assertIn('Velocidad 10 m (s)',entradas);self.assertIn('Velocidad 20 m (s)',entradas)
        self.assertEqual(entradas['Nivel alcanzado en Course Navette'].step,1)
        for nombre in ['Disciplina','Compromiso','Responsabilidad','Trabajo en equipo','Capacidad de esfuerzo']:self.assertNotIn(nombre,entradas)

    def test_guardar_preserva_cero_y_segundos_sin_escribir_vo2_ni_actitud(self):
        app,cliente=self.iniciar([],rol='entrenador')
        capturados=[];original=cliente.table
        def tabla(nombre):
            consulta=original(nombre)
            if nombre=='evaluaciones_integrales':
                def insertar(payload):
                    capturados.append(payload)
                    return SimpleNamespace(execute=lambda:SimpleNamespace(data=[]))
                consulta.insert=insertar
            return consulta
        cliente.table=tabla
        entradas={n.label:n for n in app.number_input}
        entradas['Efectividad de pases (aciertos / 5)'].set_value(0)
        entradas['Efectividad de tiros al arco (aciertos / 5)'].set_value(5)
        entradas['Conducción (s)'].set_value(14.25)
        entradas['Nivel alcanzado en Course Navette'].set_value(8)
        guardar=next(b for b in app.button if b.label=='Guardar evaluación')
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):guardar.click().run()
        self.assertEqual(len(app.exception),0,str(app.exception));self.assertEqual(len(capturados),1)
        p=capturados[0]
        self.assertEqual(p['pase_efectividad'],0);self.assertEqual(p['tiros_efectividad'],5)
        self.assertEqual(p['conduccion'],14.25);self.assertEqual(p['course_navette'],8)
        for campo in ['disciplina','compromiso','responsabilidad','trabajo_equipo','capacidad_esfuerzo','vo2max']:self.assertNotIn(campo,p)


if __name__=='__main__':unittest.main()
