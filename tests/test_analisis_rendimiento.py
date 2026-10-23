import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from modules import autenticacion
from modules.analisis_rendimiento import generar_analisis, texto_informe, comparar
from test_regresiones import Cliente
from test_evaluaciones_visuales import evaluacion


class Interpretacion(unittest.TestCase):
    def setUp(self):
        self.jugador={'id':1,'fecha_nacimiento':'2014-06-15','posicion_principal':'Portero/a'}
        self.primera=evaluacion('a','2026-09-01',3,3.1)
        self.ultima=evaluacion('b','2026-10-01',4,2.9)

    def prueba(self,informe,campo):return next(p for p in informe['pruebas'] if p['campo']==campo)

    def test_seis_cambios_de_signo_y_aciertos(self):
        estado,texto=comparar(3.1,2.9,'velocidad_10m')
        self.assertEqual(estado,'mejora');self.assertIn('0,200 s',texto);self.assertIn('6,5%',texto)
        self.assertEqual(comparar(2.9,3.1,'velocidad_10m')[0],'retroceso')
        self.assertEqual(comparar(3.1,3.1,'velocidad_10m')[0],'estable')
        self.assertEqual(comparar(3,4,'pase_efectividad')[0],'mejora')
        self.assertIn('20 puntos porcentuales',comparar(3,4,'pase_efectividad')[1])
        self.assertEqual(comparar(8,6,'course_navette')[0],'retroceso')

    def test_cero_aciertos_es_medicion_real_no_divide_por_cero(self):
        a=dict(self.primera,pase_efectividad=0);b=dict(self.ultima,pase_efectividad=3)
        r=self.prueba(generar_analisis(self.jugador,[a,b]),'pase_efectividad')
        self.assertEqual(r['estado'],'mejora');self.assertIn('0/5 (0%)',r['texto'])
        self.assertIn('60 puntos porcentuales',r['texto'])

    def test_informe_completo_sin_modificar_entradas(self):
        datos=[self.ultima,self.primera];antes=copy.deepcopy(datos)
        r=generar_analisis(self.jugador,datos)
        self.assertEqual(r['comparables'],7)
        self.assertEqual(r['conteos']['mejora'],7)
        self.assertIn('balance de esos resultados es positivo',r['resumen'])
        self.assertEqual(datos,antes)

    def test_distingue_avance_inicial_de_retroceso_reciente(self):
        medio=evaluacion('c','2026-09-15',5,2.8)
        p=self.prueba(generar_analisis(self.jugador,[self.primera,medio,self.ultima]),'velocidad_10m')
        self.assertEqual(p['estado'],'mejora')
        self.assertTrue(any('último intervalo retrocede' in a for a in p['avisos']))
        self.assertIn('medición inmediatamente anterior',p['texto'])

    def test_ausencia_no_se_interpreta_como_cero_ni_bajo_rendimiento(self):
        datos=[{'fecha_evaluacion':'2026-09-01','pase_efectividad':2},
               {'fecha_evaluacion':'2026-10-01','tiros_efectividad':4}]
        r=generar_analisis(self.jugador,datos)
        self.assertEqual(r['comparables'],0)
        self.assertIn('ninguna prueba',r['resumen'])
        p=self.prueba(r,'pase_efectividad')
        self.assertFalse(p['comparable_periodo']);self.assertTrue(any('no tiene un resultado' in a for a in p['avisos']))
        self.assertIn('No hay un resultado válido',self.prueba(r,'conduccion')['texto'])

    def test_resultados_contradictorios_misma_fecha_no_se_ordenan_al_azar(self):
        r=generar_analisis(self.jugador,[self.primera,dict(self.primera,id='otra',pase_efectividad=5),self.ultima])
        p=self.prueba(r,'pase_efectividad')
        self.assertEqual(p['estado'],'revisar');self.assertFalse(p['comparable_periodo'])
        self.assertIn('resultados distintos',p['texto'])

    def test_datos_identicos_misma_fecha_no_crean_evolucion_temporal(self):
        r=generar_analisis(self.jugador,[self.primera,dict(self.primera,id='otra')])
        self.assertEqual(r['fechas'],1);self.assertEqual(r['comparables'],0)
        self.assertIn('otra fecha',r['resumen'])

    def test_no_hay_pruebas_o_fechas_validas(self):
        r=generar_analisis(self.jugador,[])
        self.assertEqual(r['fechas'],0);self.assertIn('primer paso',r['resumen'])
        r=generar_analisis(self.jugador,[dict(self.primera,fecha_evaluacion='incorrecta')])
        self.assertEqual(r['fechas'],0);self.assertEqual(r['excluidos'],1)
        with self.assertRaises(ValueError):generar_analisis(self.jugador,None)

    def test_valores_invalidos_se_identifican(self):
        r=generar_analisis(self.jugador,[self.primera,dict(self.ultima,pase_efectividad=10)])
        p=self.prueba(r,'pase_efectividad')
        self.assertFalse(p['comparable_periodo'])
        self.assertTrue(any('no cumplen la escala' in a for a in p['avisos']))

    def test_vo2_no_atribuye_a_rendimiento_un_cambio_solo_por_edad(self):
        datos=[dict(self.primera,fecha_evaluacion='2026-06-14',course_navette=8),
               dict(self.ultima,fecha_evaluacion='2026-06-15',course_navette=8)]
        r=generar_analisis(self.jugador,datos)
        self.assertIn('procede del término de edad',r['vo2'])
        self.assertEqual(r['conteos']['estable'],1)
        self.assertEqual(r['comparables'],7)

    def test_vo2_adulto_no_afirma_que_cambia_edad_de_formula(self):
        j={'id':1,'fecha_nacimiento':'1990-06-15'}
        datos=[dict(self.primera,fecha_evaluacion='2025-10-01',course_navette=8),
               dict(self.ultima,fecha_evaluacion='2026-10-01',course_navette=8)]
        r=generar_analisis(j,datos)
        self.assertNotIn('edad utilizada también cambió',r['vo2'])
        self.assertNotIn('procede del término de edad',r['vo2'])

    def test_vo2_no_inventa_valor_sin_fecha_de_nacimiento(self):
        r=generar_analisis({'id':1},[self.primera,self.ultima])
        self.assertIn('No hay datos suficientes',r['vo2'])

    def test_notas_academicas_no_salen_sin_permiso(self):
        notas=[{'promedio':9.8}]
        oculto=generar_analisis(self.jugador,[self.primera],academico=notas,incluir_academico=False)
        self.assertNotIn('9,8',texto_informe(oculto))
        visible=generar_analisis(self.jugador,[self.primera],academico=notas,incluir_academico=True)
        self.assertIn('9,8',texto_informe(visible))

    def test_no_confunde_error_de_carga_con_historial_vacio(self):
        r=generar_analisis(self.jugador,[self.primera],historial_deportivo=None)
        self.assertTrue(any('no está disponible' in t for t in r['contexto']))
        r=generar_analisis(self.jugador,[self.primera],historial_deportivo=[])
        self.assertTrue(any('No hay temporadas' in t for t in r['contexto']))

    def test_comentarios_se_atribuyen_y_evidencias_no_se_dan_por_vistas(self):
        r=generar_analisis(self.jugador,[dict(self.ultima,recomendaciones='Comentario del entrenador')],evidencias=[{'tipo':'video','url':'https://privado.invalid'}])
        texto=texto_informe(r)
        self.assertIn('no son conclusiones del cálculo',texto)
        self.assertIn('no ha analizado el contenido',texto)
        self.assertNotIn('https://privado.invalid',texto)


class InterfazAnalisis(unittest.TestCase):
    def iniciar(self,rol='autoridad',errores=()):
        cliente=Cliente(rol=rol,errores=errores)
        cliente.datos['evaluaciones_integrales']=[evaluacion('a','2026-09-01',3,3.1),evaluacion('b','2026-10-01',4,2.9)]
        cliente.datos['historial_academico']=[{'id':'nota','jugador_id':1,'promedio':9.8}]
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=20)
        app.session_state.sesion=SimpleNamespace(user=SimpleNamespace(id='usuario-'+rol,email='prueba@example.invalid'))
        app.session_state.menu_principal='Jugadores Juventud'
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app,cliente

    def ejecutar(self,app,cliente):
        boton=next(b for b in app.button if b.label=='Análisis de rendimiento inteligente')
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):boton.click().run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        return next(v['informe'] for k,v in app.session_state.items() if k.startswith('analisis_rendimiento_') and isinstance(v,dict))

    def test_boton_funciona_para_todos_los_roles(self):
        for rol in ['padre','administrador','entrenador','autoridad']:
            with self.subTest(rol=rol):
                app,cliente=self.iniciar(rol)
                informe=self.ejecutar(app,cliente)
                self.assertEqual(informe['conteos']['mejora'],7)
                if rol=='padre':self.assertNotIn('9,8',texto_informe(informe))
                else:self.assertIn('9,8',texto_informe(informe))
                self.assertTrue(any('balance de esos resultados es positivo' in t.value for t in app.markdown))

    def test_error_de_carga_deshabilita_boton(self):
        app,_=self.iniciar(errores=['evaluaciones_integrales'])
        self.assertTrue(next(b for b in app.button if b.label=='Análisis de rendimiento inteligente').disabled)

    def test_resultados_no_se_generan_sin_pulsar_boton(self):
        app,_=self.iniciar()
        self.assertFalse(any(isinstance(v,dict) and 'informe' in v for v in app.session_state.values()))

    def test_cambio_de_datos_invalida_informe_anterior(self):
        app,cliente=self.iniciar();self.ejecutar(app,cliente)
        cliente.datos['evaluaciones_integrales'][1]['pase_efectividad']=2
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):app.run()
        self.assertTrue(any('datos del expediente han cambiado' in e.value for e in app.info))
        self.assertFalse(any('balance de esos resultados es positivo' in t.value for t in app.markdown))

    def test_cambiar_de_jugador_no_muestra_otro_informe(self):
        app,cliente=self.iniciar();self.ejecutar(app,cliente)
        selector=next(s for s in app.selectbox if s.label=='Selecciona el código del deportista')
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente):selector.select(2).run()
        self.assertEqual(len(app.exception),0)
        self.assertFalse(any('balance de esos resultados es positivo' in t.value for t in app.markdown))


if __name__=='__main__':unittest.main()
