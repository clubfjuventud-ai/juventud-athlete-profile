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
    PUNTUACIONES, resultado, variacion, ordenar_evaluaciones, puntos_radar, radar_svg,
)
from test_regresiones import Cliente


def evaluacion(identificador, fecha, puntuacion, tiempo):
    return dict(id=identificador, jugador_id=1, fecha_evaluacion=fecha,
                velocidad_10m=tiempo, velocidad_20m=tiempo*2, illinois=tiempo*5,
                course_navette=6+puntuacion/10,
                **{campo:puntuacion for campo,_,_ in PUNTUACIONES})


class DatosVisuales(unittest.TestCase):
    def setUp(self):
        self.anterior = evaluacion('a', '2026-09-01', 6, 3.1)
        self.actual = evaluacion('b', '2026-10-01', 8, 2.9)

    def test_orden_cronologico_sin_modificar_originales(self):
        datos=[self.anterior,self.actual]
        antes=copy.deepcopy(datos)
        self.assertEqual([e['id'] for e in ordenar_evaluaciones(datos)],['b','a'])
        self.assertEqual(datos,antes)

    def test_variaciones_conservan_unidades_y_signo(self):
        self.assertAlmostEqual(variacion(self.actual,self.anterior,'velocidad_10m'),-0.2)
        self.assertEqual(variacion(self.actual,self.anterior,'pase_efectividad'),2)
        self.assertIsNone(variacion(self.actual,None,'pase_efectividad'))

    def test_datos_faltantes_y_no_finitos_no_equivalen_a_cero(self):
        for valor in [None,0,'', 'abc',float('nan'),float('inf')]:
            with self.subTest(valor=valor):
                self.assertIsNone(resultado({'pase_efectividad':valor},'pase_efectividad'))
        self.assertEqual(resultado({'pase_efectividad':'7.5'},'pase_efectividad'),7.5)

    def test_radio_respeta_escala_real_y_ausencia(self):
        puntos=puntos_radar({'pase_efectividad':10,'conduccion':5})
        self.assertAlmostEqual(math.dist((200,200),puntos[0]),125)
        self.assertAlmostEqual(math.dist((200,200),puntos[1]),62.5)
        self.assertTrue(all(p is None for p in puntos[2:]))

    def test_radar_incompleto_no_inventa_poligono_ni_puntos(self):
        raiz=ET.fromstring(radar_svg({'pase_efectividad':8,'conduccion':6}))
        ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(raiz.findall('.//s:circle/s:title',ns)),2)
        self.assertFalse(any(p.get('fill-opacity') for p in raiz.findall('.//s:polygon',ns)))

    def test_superposicion_de_dos_perfiles(self):
        raiz=ET.fromstring(radar_svg(self.actual,self.anterior))
        ns={'s':'http://www.w3.org/2000/svg'}
        self.assertEqual(len(raiz.findall('.//s:circle/s:title',ns)),16)
        self.assertEqual(sum(p.get('fill-opacity')=='0.16' for p in raiz.findall('.//s:polygon',ns)),2)

    def test_pdf_usa_cuadros_vectoriales_en_lugar_de_tablas_de_resultados(self):
        capturado=[]
        def capturar(doc,elementos,**kwargs):
            capturado.extend(elementos)
        with patch.object(informes_pdf.SimpleDocTemplate,'build',autospec=True,side_effect=capturar), \
                patch.object(informes_pdf,'ruta_logo',return_value=None):
            informes_pdf.generar_pdf({'institucion':'Colegio Surcos'},[],[],[self.actual,self.anterior],[],False,True)
        def expandir(elementos):
            for e in elementos:
                yield e
                if hasattr(e,'_content'):
                    yield from expandir(e._content)
        todos=list(expandir(capturado))
        # Solo permanece la tabla de datos personales; las evaluaciones son vectoriales.
        self.assertEqual(sum(isinstance(e,Table) for e in todos),1)
        self.assertEqual(sum(isinstance(e,Drawing) for e in todos),2)


class PanelInterfaz(unittest.TestCase):
    def iniciar(self, registros):
        cliente=Cliente(rol='autoridad')
        cliente.datos['evaluaciones_integrales']=registros
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20)
        app.session_state.sesion=SimpleNamespace(user=SimpleNamespace(id='prueba',email='prueba@example.invalid'))
        app.session_state.menu_principal='Jugadores Juventud'
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):
            app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.error),0)
        return app,cliente

    def test_dos_fechas_radar_delta_y_sin_tablas_de_evaluacion(self):
        app,_=self.iniciar([evaluacion('a','2026-09-01',6,3.1),evaluacion('b','2026-10-01',8,2.9)])
        self.assertTrue(any(s.label=='Evaluación que quieres ver' for s in app.selectbox))
        metricas={m.label:m for m in app.metric}
        self.assertEqual(metricas['Pase'].value,'8 / 10')
        self.assertEqual(metricas['Pase'].delta,'+2.0 puntos')
        self.assertEqual(metricas['Velocidad 10 m'].delta,'-0.200 s')
        radares=[i.proto.imgs[0].url for i in app.get('image') if i.proto.imgs[0].url.startswith('data:image/svg+xml;base64,')]
        self.assertEqual(len(radares),1)
        self.assertIn(b'<svg',base64.b64decode(radares[0].split(',',1)[1]))
        # El listado de jugadores existente es la única tabla de esta pantalla.
        self.assertEqual(len(app.dataframe),1)

    def test_selector_permite_ver_evaluacion_anterior(self):
        app,cliente=self.iniciar([evaluacion('a','2026-09-01',6,3.1),evaluacion('b','2026-10-01',8,2.9)])
        selector=next(s for s in app.selectbox if s.label=='Evaluación que quieres ver')
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):
            selector.select(1).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(next(m.value for m in app.metric if m.label=='Pase'),'6 / 10')

    def test_primera_evaluacion_sin_comparacion(self):
        app,_=self.iniciar([evaluacion('a','2026-09-01',6,3.1)])
        comparacion=next(s for s in app.selectbox if s.label=='Comparar con')
        self.assertTrue(comparacion.disabled)
        self.assertTrue(any('Primera evaluación' in i.value for i in app.info))
        self.assertEqual(next(m.value for m in app.metric if m.label=='Pase'),'6 / 10')

    def test_evaluacion_parcial_se_muestra_sin_ceros_ficticios(self):
        app,_=self.iniciar([{'id':'a','jugador_id':1,'fecha_evaluacion':'2026-09-01','pase_efectividad':7}])
        metricas={m.label:m.value for m in app.metric}
        self.assertEqual(metricas['Pase'],'7 / 10')
        self.assertEqual(metricas['Conducción'],'—')
        self.assertEqual(metricas['Velocidad 10 m'],'—')


if __name__=='__main__':
    unittest.main()
