import copy
from contextlib import ExitStack
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from modules import autenticacion
from modules.informes_pdf import generar_pdf
from modules.utilidades import categoria_por_fecha, obtener_jugadores, opciones_expediente


class Estado(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class Consulta:
    """API en memoria; limita cada respuesta a dos filas, incluso si se piden más."""
    def __init__(self, cliente, tabla):
        self.cliente, self.tabla = cliente, tabla
        self.inicio, self.fin = 0, None
        self.filtros = {}

    def select(self, *args):
        return self

    def eq(self, campo, valor):
        self.filtros[campo] = valor
        return self

    def order(self, *args, **kwargs):
        return self

    def maybe_single(self):
        return self

    def range(self, inicio, fin):
        self.inicio, self.fin = inicio, fin
        return self

    def execute(self):
        self.cliente.consultas.append((self.tabla, self.inicio))
        if self.tabla in self.cliente.errores:
            raise ConnectionError('fallo sintético')
        if self.tabla == 'perfiles':
            return SimpleNamespace(data={'activo': True, 'rol': self.cliente.rol, 'nombre_completo': 'Prueba'})
        filas = self.cliente.datos.get(self.tabla, [])
        filas = [r for r in filas if all(r.get(k) == v for k, v in self.filtros.items())]
        fin = self.inicio + 2 if self.fin is None else min(self.fin + 1, self.inicio + 2)
        return SimpleNamespace(data=filas[self.inicio:fin])


class Cliente:
    def __init__(self, errores=(), rol='autoridad'):
        self.errores, self.rol = errores, rol
        self.consultas = []
        self.datos = {
            'jugadores': [
                {'id': i, 'codigo_jugador': f'JUV-{i:03}', 'nombres': 'Juan', 'apellidos': 'Pérez',
                 'institucion': 'Club Juventud', 'categorias': {'nombre': 'Sub 12'}}
                for i in range(1, 6)
            ],
            'categorias': [{'id': 1, 'nombre': 'Sub 12', 'edad_minima': 10, 'edad_maxima': 12, 'activa': True}],
        }

    def table(self, tabla):
        return Consulta(self, tabla)


class RegresionesDatos(unittest.TestCase):
    def test_selector_por_codigo_conserva_homonimos(self):
        opciones = opciones_expediente(Cliente().datos['jugadores'])
        self.assertEqual(opciones, {i: f'JUV-{i:03}' for i in range(1, 6)})

    def test_codigos_duplicados_o_ausentes_no_ocultan_registros(self):
        opciones = opciones_expediente([
            {'id': 1, 'codigo_jugador': 'JUV-1'}, {'id': 2, 'codigo_jugador': 'JUV-1'},
            {'id': 3}, {'id': 4},
        ])
        self.assertEqual(len(set(opciones.values())), 4)

    def test_paginacion_supera_el_limite_del_servidor(self):
        cliente = Cliente()
        self.assertEqual([j['id'] for j in obtener_jugadores(cliente)], [1, 2, 3, 4, 5])
        self.assertEqual(cliente.consultas, [('jugadores', 0), ('jugadores', 2), ('jugadores', 4), ('jugadores', 5)])

    def test_error_de_pagina_no_devuelve_lista_parcial(self):
        cliente = Cliente()
        original = cliente.table
        def table(tabla):
            consulta = original(tabla)
            execute = consulta.execute
            def falla():
                if consulta.inicio >= 2:
                    raise ConnectionError('fallo en segunda página')
                return execute()
            consulta.execute = falla
            return consulta
        cliente.table = table
        with self.assertRaises(ConnectionError):
            obtener_jugadores(cliente)

    def test_rango_explicito_no_se_reemplaza_por_nombre(self):
        categorias = Cliente().datos['categorias']
        self.assertIsNone(categoria_por_fecha(date(date.today().year - 5, 1, 1), categorias))
        self.assertEqual(categoria_por_fecha(date(date.today().year - 10, 1, 1), categorias)['id'], 1)
        self.assertEqual(categoria_por_fecha(date(date.today().year - 12, 1, 1), categorias)['id'], 1)
        self.assertIsNone(categoria_por_fecha(date(date.today().year - 13, 1, 1), categorias))

    def test_rangos_parciales_y_solapados(self):
        nacimiento = date(date.today().year - 5, 1, 1)
        self.assertIsNone(categoria_por_fecha(nacimiento, [{'nombre': 'Sub 12', 'edad_minima': 10}]))
        self.assertIsNone(categoria_por_fecha(nacimiento, [
            {'id': 1, 'edad_minima': 4, 'edad_maxima': 6},
            {'id': 2, 'edad_minima': 5, 'edad_maxima': 7},
        ]))

    def test_alternativa_sin_rangos_elige_limite_mas_cercano(self):
        categoria = categoria_por_fecha(date(date.today().year - 9, 1, 1), [
            {'nombre': 'Sub 12'}, {'nombre': 'Sub 8'}, {'nombre': 'Sub 10'},
        ])
        self.assertEqual(categoria['nombre'], 'Sub 10')

    def test_pdf_escapa_todos_los_bloques_sin_modificar_datos(self):
        texto = 'Ana & Luis <b>sin cerrar <img src="/archivo/inexistente"/>'
        datos = [
            {'nombres': texto, 'apellidos': texto, 'categorias': {'nombre': texto}},
            [{'periodo_academico': texto, 'observaciones': texto}],
            [{'temporada': texto, 'club_equipo': texto, 'logros': texto}],
            [{'fortalezas': texto, 'fecha_evaluacion': texto, 'pase_efectividad': 8}],
            [{'titulo': texto, 'url': texto, 'descripcion': texto}],
        ]
        antes = copy.deepcopy(datos)
        pdf = generar_pdf(*datos, True, True)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(datos, antes)


class RegresionesSesion(unittest.TestCase):
    def setUp(self):
        self.sesion = SimpleNamespace(access_token='anterior', refresh_token='renovacion', expires_at=2000)
        self.nueva = SimpleNamespace(access_token='nuevo', refresh_token='rotado', expires_at=4000)
        self.estado = Estado(sesion=self.sesion)
        self.cliente = Mock()
        self.cliente.auth.set_session.return_value = SimpleNamespace(session=self.nueva)
        self.cliente.auth.refresh_session.return_value = SimpleNamespace(session=self.nueva)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(autenticacion, 'st', SimpleNamespace(
            secrets={'SUPABASE_URL': 'https://example.invalid', 'SUPABASE_KEY': 'prueba'}, session_state=self.estado)))
        self.crear = self.stack.enter_context(patch.object(autenticacion, 'create_client', return_value=self.cliente))
        self.stack.enter_context(patch.object(autenticacion.time, 'time', return_value=1000))

    def test_sesion_vigente_se_restaura_y_guarda_tokens(self):
        autenticacion.conectar_supabase()
        self.cliente.auth.set_session.assert_called_once_with('anterior', 'renovacion')
        self.cliente.auth.refresh_session.assert_not_called()
        self.assertIs(self.estado.sesion, self.nueva)
        self.cliente.postgrest.auth.assert_called_once_with('nuevo')
        opciones = self.crear.call_args.kwargs['options']
        self.assertFalse(opciones.auto_refresh_token)
        self.assertFalse(opciones.persist_session)

    def test_token_caducado_o_proximo_a_caducar_se_renueva(self):
        for caducidad in [900, 1050, None]:
            with self.subTest(caducidad=caducidad):
                self.estado.sesion = self.sesion
                self.sesion.expires_at = caducidad
                autenticacion.conectar_supabase()
                self.assertIs(self.estado.sesion, self.nueva)
        self.assertEqual(self.cliente.auth.refresh_session.call_count, 3)
        self.cliente.auth.set_session.assert_not_called()

    def test_renovacion_rechazada_limpia_sesion(self):
        self.sesion.expires_at = 900
        error = Exception('rechazado')
        error.status = 400
        self.cliente.auth.refresh_session.side_effect = error
        with self.assertRaises(autenticacion.SesionCaducada):
            autenticacion.conectar_supabase()
        self.assertIsNone(self.estado.sesion)

    def test_error_de_red_conserva_sesion_para_reintento(self):
        self.sesion.expires_at = 900
        self.cliente.auth.refresh_session.side_effect = ConnectionError('sin conexión')
        with self.assertRaises(ConnectionError):
            autenticacion.conectar_supabase()
        self.assertIs(self.estado.sesion, self.sesion)


class RegresionesInterfaz(unittest.TestCase):
    def ejecutar(self, cliente, seccion='Jugadores Juventud'):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
        app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='usuario-prueba', email='prueba@example.invalid'))
        app.session_state.menu_principal = seccion
        with patch.object(autenticacion, 'conectar_supabase', return_value=cliente):
            app.run()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        return app

    def test_selector_presenta_codigos_en_interfaz(self):
        app = self.ejecutar(Cliente())
        selector = next(s for s in app.selectbox if s.label == 'Selecciona el código del deportista')
        self.assertEqual(selector.options, [f'JUV-{i:03}' for i in range(1, 6)])
        self.assertEqual(selector.value, 1)
        self.assertEqual(len(app.error), 0)

    def test_cambiar_codigo_selecciona_otro_expediente(self):
        cliente = Cliente()
        app = self.ejecutar(cliente)
        selector = next(s for s in app.selectbox if s.label == 'Selecciona el código del deportista')
        with patch.object(autenticacion, 'conectar_supabase', return_value=cliente):
            selector.select(2).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('**Código:** JUV-002' in item.value for item in app.markdown))

    def test_error_academico_bloquea_solo_pdf_que_lo_incluye(self):
        cliente = Cliente(errores=['historial_academico'])
        app = self.ejecutar(cliente)
        self.assertFalse(any('No se puede exportar' in e.value for e in app.error))
        incluir = next(c for c in app.checkbox if c.label.startswith('Incluir historial académico'))
        with patch.object(autenticacion, 'conectar_supabase', return_value=cliente):
            incluir.check().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('No se puede exportar' in e.value for e in app.error))

    def test_error_de_jugadores_no_muestra_cero_deportistas(self):
        app = self.ejecutar(Cliente(errores=['jugadores']), 'Inicio')
        self.assertTrue(any('No se pudieron cargar los deportistas' in e.value for e in app.error))
        self.assertEqual(len(app.metric), 0)

    def test_error_de_historial_bloquea_exportacion(self):
        app = self.ejecutar(Cliente(errores=['historial_deportivo']))
        errores = [e.value for e in app.error]
        self.assertTrue(any('No se pudo cargar el historial deportivo' in e for e in errores))
        self.assertTrue(any('No se puede exportar' in e for e in errores))
        self.assertFalse(any('Todavía no hay temporadas' in i.value for i in app.info))

    def test_error_de_categorias_se_informa(self):
        app = self.ejecutar(Cliente(errores=['categorias']))
        self.assertTrue(any('No se pudieron cargar las categorías' in e.value for e in app.error))

    def test_padre_no_consulta_historial_academico(self):
        cliente = Cliente(rol='padre')
        self.ejecutar(cliente)
        self.assertNotIn('historial_academico', [tabla for tabla, inicio in cliente.consultas])


if __name__ == '__main__':
    unittest.main()
