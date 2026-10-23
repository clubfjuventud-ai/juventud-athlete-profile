import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from modules import autenticacion, interfaz
from test_regresiones import Cliente, Consulta
from test_evaluaciones_visuales import evaluacion


class InterfazRenovada(unittest.TestCase):
    def iniciar(self, rol='administrador', vista='Mi cuenta', seccion='Colegio Surcos', errores=()):
        cliente = Cliente(rol=rol, errores=errores)
        for j in cliente.datos['jugadores']:
            j['institucion'] = 'Colegio Surcos'
        cliente.datos['evaluaciones_integrales'] = [evaluacion('a', '2026-09-01', 3, 3.1), evaluacion('b', '2026-10-01', 4, 2.9)]
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20)
        app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='prueba-vista', email='prueba@example.invalid'))
        app.session_state.menu_principal = seccion
        app.session_state['vista_rol_prueba-vista'] = vista
        self.ejecutar(app, cliente)
        return app, cliente

    def ejecutar(self, app, cliente, accion=None):
        with patch.object(autenticacion, 'conectar_supabase', return_value=cliente):
            (accion or app).run()
        self.assertEqual(len(app.exception), 0, str(app.exception))

    def etiquetas(self, app):
        return [t.label for t in app.tabs]

    def test_surcos_es_identidad_principal(self):
        app, _ = self.iniciar()
        self.assertEqual([t.value for t in app.title], ['Surcos'])
        texto = '\n'.join(t.value for t in app.markdown)
        self.assertNotIn('Juventud Athlete Profile', texto)
        self.assertNotIn('JUVENTUD CON PROPÓSITO', texto)
        self.assertIn('#94C93D', texto)
        self.assertIn('#123346', texto)
        self.assertEqual(len(app.get('image')), 2)  # Logo Surcos + radar de evaluación.

    def test_expediente_y_evolucion_son_primeras_pestanas(self):
        app, _ = self.iniciar()
        self.assertLess(self.etiquetas(app).index('Directorio'), self.etiquetas(app).index('Registrar deportista'))
        self.assertEqual(self.etiquetas(app)[:2], ['Expediente individual', 'Evolución'])
        self.assertEqual(next(m.value for m in app.metric if m.label == 'Última evaluación'), '01/10/2026')

    def test_vistas_previas_son_solo_lectura_sin_cambiar_cuenta(self):
        for vista in ['Entrenador', 'Autoridad', 'Representante']:
            with self.subTest(vista=vista):
                app, cliente = self.iniciar(vista=vista)
                self.assertEqual(cliente.rol, 'administrador')
                if vista == 'Entrenador':
                    self.assertIn('Registrar deportista', self.etiquetas(app))
                    self.assertTrue(all(b.disabled for b in app.button if b.label.startswith('Guardar')))
                else:
                    self.assertNotIn('Registrar deportista', self.etiquetas(app))
                    self.assertFalse(any(b.label.startswith('Guardar') for b in app.button))
                menu = next(r for r in app.radio if r.label == 'MENÚ PRINCIPAL')
                self.assertNotIn('Usuarios y representantes', menu.options)
                self.assertTrue(any('Solo lectura' in i.value for i in app.info))
                self.assertTrue(any(b.label == 'Análisis de rendimiento inteligente' for b in app.button))
                if vista == 'Representante':
                    self.assertNotIn('Académico', self.etiquetas(app))
                    self.assertNotIn('historial_academico', [t for t, _ in cliente.consultas])
                    self.assertEqual(len(app.checkbox), 0)

    def test_salir_de_vista_recupera_formularios_administrativos(self):
        app, cliente = self.iniciar(vista='Entrenador')
        selector = next(s for s in app.radio if s.label == 'Ver la interfaz como')
        self.ejecutar(app, cliente, selector.set_value('Mi cuenta'))
        self.assertIn('Registrar deportista', self.etiquetas(app))
        self.assertTrue(any(b.label == 'Guardar deportista' for b in app.button))
        self.assertTrue(any(b.label == 'Guardar periodo' for b in app.button))

    def test_vista_previa_rechaza_envio_de_formulario(self):
        app, cliente = self.iniciar(vista='Entrenador')
        import streamlit as st
        boton_real, enviar_real = st.button, st.form_submit_button
        def forzar(funcion):
            def pulsado(etiqueta, *args, **kwargs):
                valor = funcion(etiqueta, *args, **kwargs)
                return True if etiqueta.startswith('Guardar') else valor
            return pulsado
        with patch.object(Consulta, 'insert', create=True) as insertar, \
                patch.object(st, 'button', side_effect=forzar(boton_real)), \
                patch.object(st, 'form_submit_button', side_effect=forzar(enviar_real)):
            # Simula envíos que la interfaz deshabilitada no permitiría realizar.
            self.ejecutar(app, cliente)
            insertar.assert_not_called()

    def test_otro_rol_no_puede_activar_vista_admin_por_estado(self):
        for rol in ['padre', 'entrenador', 'autoridad']:
            with self.subTest(rol=rol):
                app, _ = self.iniciar(rol=rol, vista='Mi cuenta', seccion='Usuarios y representantes')
                self.assertFalse(any(s.label == 'Ver la interfaz como' for s in app.radio))
                menu = next(r for r in app.radio if r.label == 'MENÚ PRINCIPAL')
                self.assertEqual(menu.value, 'Inicio')
                self.assertNotIn('Usuarios y representantes', menu.options)

    def test_entrenador_real_conserva_edicion_y_padre_no(self):
        entrenador, _ = self.iniciar(rol='entrenador')
        self.assertTrue(any(b.label == 'Guardar evaluación' for b in entrenador.button))
        self.assertFalse(any(b.label == 'Guardar periodo' for b in entrenador.button))
        padre, _ = self.iniciar(rol='padre')
        self.assertFalse(any(b.label.startswith('Guardar') for b in padre.button))

    def test_acceso_inicio_abre_surcos(self):
        app, cliente = self.iniciar(seccion='Inicio')
        boton = next(b for b in app.button if b.label == 'Abrir Colegio Surcos')
        self.ejecutar(app, cliente, boton.click())
        self.assertEqual(app.session_state.menu_principal, 'Colegio Surcos')
        self.assertEqual(app.title[0].value, 'Surcos')

    def test_directorio_busca_por_codigo(self):
        app, cliente = self.iniciar()
        campo = next(t for t in app.text_input if t.label == 'Buscar por código, nombre o apellido')
        self.ejecutar(app, cliente, campo.input('JUV-003'))
        self.assertTrue(any(c.value == 'Deportistas visibles: 1' for c in app.caption))

    def test_pdf_se_genera_solo_a_peticion_y_se_invalida_por_datos_opciones_y_rol(self):
        with patch.object(interfaz, 'generar_pdf', return_value=b'%PDF-prueba') as generar:
            app, cliente = self.iniciar()
            generar.assert_not_called()
            boton = next(b for b in app.button if b.label == 'Preparar expediente PDF')
            self.ejecutar(app, cliente, boton.click())
            generar.assert_called_once()
            self.assertIn('expediente_pdf_preparado', app.session_state)
            self.ejecutar(app, cliente)
            generar.assert_called_once()
            cliente.datos['jugadores'][0]['peso'] = 41
            self.ejecutar(app, cliente)
            self.assertNotIn('expediente_pdf_preparado', app.session_state)
            self.ejecutar(app, cliente, next(b for b in app.button if b.label == 'Preparar expediente PDF').click())
            incluir = next(c for c in app.checkbox if c.label.startswith('Incluir evaluaciones'))
            self.ejecutar(app, cliente, incluir.check())
            self.assertNotIn('expediente_pdf_preparado', app.session_state)
            self.ejecutar(app, cliente, next(b for b in app.button if b.label == 'Preparar expediente PDF').click())
            vista = next(s for s in app.radio if s.label == 'Ver la interfaz como')
            self.ejecutar(app, cliente, vista.set_value('Representante'))
            self.assertNotIn('expediente_pdf_preparado', app.session_state)
            self.ejecutar(app, cliente, next(b for b in app.button if b.label == 'Preparar expediente PDF').click())
            self.assertEqual(generar.call_args.args[-2:], (False, False))

    def test_pdf_no_se_ofrece_si_falla_fuente_requerida(self):
        with patch.object(interfaz, 'generar_pdf') as generar:
            app, _ = self.iniciar(errores=['historial_deportivo'])
            self.assertFalse(any(b.label == 'Preparar expediente PDF' for b in app.button))
            generar.assert_not_called()

    def test_pulso_une_pruebas_de_misma_fecha_sin_contar_fechas_invalidas(self):
        from unittest.mock import Mock
        interfaz_falsa = Mock()
        columnas = [Mock(), Mock(), Mock()]
        interfaz_falsa.columns.return_value = columnas
        with patch.object(interfaz, 'st', interfaz_falsa):
            interfaz.mostrar_pulso([
                {'id': '1', 'fecha_evaluacion': '2026-10-01', 'pase_efectividad': 0},
                {'id': '2', 'fecha_evaluacion': '2026-10-01', 'tiros_efectividad': 5},
                {'id': '3', 'fecha_evaluacion': 'fecha incorrecta', 'conduccion': 2},
                {'id': '4', 'fecha_evaluacion': '2026-09-01', 'conduccion': 2},
            ])
        columnas[0].metric.assert_called_once_with('Fechas evaluadas', 2)
        columnas[2].metric.assert_called_once_with('Pruebas en la última fecha', '2/7')


if __name__ == '__main__':
    unittest.main()
