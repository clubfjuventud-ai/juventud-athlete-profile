import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from modules import autenticacion
from test_regresiones import Cliente, Consulta


class AccesoRepresentantes(unittest.TestCase):
    def iniciar(self, jugadores, rol='padre', previa=False, estado=None):
        cliente = Cliente(rol=rol)
        # Simula las filas que devuelve el servidor después de aplicar sus RLS.
        cliente.datos['jugadores'] = jugadores
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
        app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='familia', email='familia@example.invalid'))
        app.session_state.menu_principal = 'Jugadores Juventud'
        if previa:
            app.session_state['vista_rol_familia'] = 'Representante'
        for clave, valor in (estado or {}).items():
            app.session_state[clave] = valor
        self.ejecutar(app, cliente)
        return app, cliente

    def ejecutar(self, app, cliente, accion=None):
        with patch.object(autenticacion, 'conectar_supabase', return_value=cliente):
            (accion or app).run()
        self.assertEqual(len(app.exception), 0, str(app.exception))

    def jugador(self, id=7, institucion='Colegio Surcos'):
        return {'id': id, 'institucion': institucion, 'nombres': 'Mateo', 'apellidos': 'Andrade', 'codigo_jugador': f'SUR-{id:03}'}

    def test_un_representado_abre_directamente_sin_menu_directorio_o_codigo(self):
        for institucion, titulo in [('Colegio Surcos', 'Surcos'), ('Club Juventud', 'Club Juventud')]:
            with self.subTest(institucion=institucion):
                app, cliente = self.iniciar([self.jugador(institucion=institucion)])
                self.assertEqual(app.title[0].value, titulo)
                self.assertFalse(any(r.label == 'MENÚ PRINCIPAL' for r in app.radio))
                self.assertEqual(len(app.selectbox), 0)
                self.assertNotIn('Directorio', [t.label for t in app.tabs])
                self.assertNotIn('Académico', [t.label for t in app.tabs])
                self.assertFalse(any(b.label.startswith('Guardar') for b in app.button))
                self.assertNotIn('categorias', [tabla for tabla, _ in cliente.consultas])
                self.assertNotIn('historial_academico', [tabla for tabla, _ in cliente.consultas])

    def test_estado_antiguo_no_abre_otro_deportista(self):
        consultas = []
        original = Consulta.execute
        def registrar(consulta):
            if 'jugador_id' in consulta.filtros:
                consultas.append(consulta.filtros['jugador_id'])
            return original(consulta)
        with patch.object(Consulta, 'execute', registrar):
            app, _ = self.iniciar([self.jugador()], estado={
                'expediente_jugador_Club Juventud': 1,
                'mis_representados_familia': 999,
                'ejemplo_representante_familia': 999,
            })
        self.assertTrue(consultas)
        self.assertEqual(set(consultas), {7})
        self.assertTrue(any('SUR-007' in m.value for m in app.markdown))

    def test_sin_vinculos_no_muestra_expediente_ni_consulta_historiales(self):
        app, cliente = self.iniciar([])
        self.assertTrue(any('No hay un deportista disponible' in i.value for i in app.info))
        self.assertFalse(any(b.label == 'Análisis de rendimiento inteligente' for b in app.button))
        self.assertEqual(set(tabla for tabla, _ in cliente.consultas), {'perfiles', 'jugadores'})
        self.assertEqual(len(app.selectbox), 0)

    def test_varios_representados_autorizados_se_eligen_por_nombre(self):
        app, cliente = self.iniciar([self.jugador(), dict(self.jugador(id=8, institucion='Club Juventud'), nombres='Lucía')])
        selector = next(s for s in app.selectbox if s.label == 'Mis representados')
        self.assertEqual(selector.options, ['Andrade, Mateo', 'Andrade, Lucía'])
        self.ejecutar(app, cliente, selector.select(8))
        self.assertEqual(app.title[0].value, 'Club Juventud')
        self.assertFalse(any(s.label == 'Selecciona el código del deportista' for s in app.selectbox))

    def test_selector_no_conserva_id_que_dejo_de_ser_visible(self):
        app, _ = self.iniciar([self.jugador(), self.jugador(id=8)], estado={'mis_representados_familia': 999})
        selector = next(s for s in app.selectbox if s.label == 'Mis representados')
        self.assertEqual(selector.value, 7)
        self.assertEqual(len(set(selector.options)), 2)

    def test_previa_admin_elige_ejemplo_fuera_de_la_pantalla_del_representante(self):
        app, cliente = self.iniciar([self.jugador(), self.jugador(id=8, institucion='Club Juventud')], rol='administrador', previa=True)
        self.assertFalse(any(r.label == 'MENÚ PRINCIPAL' for r in app.radio))
        self.assertFalse(any(s.label == 'Selecciona el código del deportista' for s in app.selectbox))
        self.assertTrue(any(e.label == 'Ejemplo de expediente · Solo administrador' for e in app.sidebar.expander))
        selector = next(s for s in app.selectbox if s.label == 'Deportista para la vista previa')
        self.ejecutar(app, cliente, selector.select(8))
        self.assertEqual(app.title[0].value, 'Club Juventud')
        self.assertEqual(cliente.rol, 'administrador')

    def test_selector_de_ejemplo_no_aparece_a_cuenta_real(self):
        app, _ = self.iniciar([self.jugador(), self.jugador(id=8)], estado={'vista_rol_familia': 'Representante'})
        self.assertFalse(any(s.label == 'Deportista para la vista previa' for s in app.selectbox))
        self.assertFalse(any(r.label == 'Ver la interfaz como' for r in app.radio))


if __name__ == '__main__':
    unittest.main()
