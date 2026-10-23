import copy
import io
import unittest
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image
from reportlab.pdfgen import canvas
from streamlit.testing.v1 import AppTest

from modules import autenticacion
from modules.entrenamientos import (
    Contexto, validar_archivo, crear_sesion, subir_adjunto, publicar_sesion,
    guardar_asistencia, grupos_visibles, asistencia_sesion, csv_asistencia,
    paquete_sesion, BUCKET, nombre_seguro,
    mostrar_documento,
)


class Consulta:
    def __init__(self, cliente, tabla):
        self.cliente, self.tabla = cliente, tabla
        self.filtros = {}; self.inicio = 0; self.fin = None; self.accion = 'select'; self.payload = None; self.singular = False
    def select(self, *args): return self
    def eq(self, campo, valor): self.filtros[campo] = valor; return self
    def order(self, *args, **kwargs): return self
    def range(self, inicio, fin): self.inicio, self.fin = inicio, fin; return self
    def maybe_single(self): self.singular = True; return self
    def insert(self, payload): self.accion, self.payload = 'insert', payload; return self
    def update(self, payload): self.accion, self.payload = 'update', payload; return self
    def delete(self): self.accion = 'delete'; return self
    def execute(self):
        c = self.cliente
        c.operaciones.append((self.tabla, self.accion, dict(self.filtros), copy.deepcopy(self.payload)))
        if self.tabla in c.errores:
            raise ConnectionError('fallo simulado')
        if self.singular:
            return SimpleNamespace(data={'id': c.usuario, 'rol': c.rol, 'activo': True, 'nombre_completo': 'Prueba'})
        filas = c.datos.setdefault(self.tabla, [])
        seleccionadas = [r for r in filas if all(str(r.get(k)) == str(v) for k, v in self.filtros.items())]
        if self.accion == 'insert':
            fila = copy.deepcopy(self.payload)
            fila.setdefault('id', 'nuevo')
            if self.tabla == 'ent_sesiones':
                fila.update(creado_por=c.usuario, estado='borrador', autor_nombre='Entrenador')
            if self.tabla == 'ent_archivos': fila.setdefault('confirmado', False)
            filas.append(fila)
            return SimpleNamespace(data=[fila])
        if self.accion == 'update':
            for fila in seleccionadas: fila.update(self.payload)
            return SimpleNamespace(data=seleccionadas)
        if self.accion == 'delete':
            for fila in seleccionadas: filas.remove(fila)
            return SimpleNamespace(data=seleccionadas)
        fin = self.inicio + 2 if self.fin is None else min(self.fin + 1, self.inicio + 2)
        return SimpleNamespace(data=seleccionadas[self.inicio:fin])


class Storage:
    def __init__(self): self.archivos = {}; self.operaciones = []; self.falla = False
    def from_(self, bucket):
        assert bucket == BUCKET
        return self
    def upload(self, ruta, contenido, opciones):
        self.operaciones.append(('upload', ruta))
        if self.falla: raise ConnectionError('carga fallida')
        self.archivos[ruta] = contenido
    def download(self, ruta): self.operaciones.append(('download', ruta)); return self.archivos[ruta]
    def remove(self, rutas):
        self.operaciones.append(('remove', list(rutas)))
        for ruta in rutas: self.archivos.pop(ruta, None)


class Cliente:
    def __init__(self, rol='entrenador'):
        self.rol = rol; self.usuario = 'usuario'; self.operaciones = []; self.errores = []
        self.storage = Storage()
        self.datos = {
            'ent_grupos': [{'id': 'grupo', 'categoria_id': 10, 'institucion': 'Colegio Surcos', 'categorias': {'nombre': 'Sub 12'}}],
            'ent_sesiones': [{'id': 'sesion', 'grupo_id': 'grupo', 'creado_por': 'usuario', 'fecha': '2026-10-20', 'titulo': 'Sesión publicada', 'objetivos': 'Mejorar pases', 'contenido': 'Rondos y conducción', 'estado': 'publicada'}],
            'jugadores': [{'id': 101, 'categoria_id': 10, 'institucion': 'Colegio Surcos', 'codigo_jugador': 'SUR-101', 'nombres': 'Mateo', 'apellidos': 'Andrade'},
                          {'id': 102, 'categoria_id': 10, 'institucion': 'Colegio Surcos', 'nombres': 'Otro', 'apellidos': 'Deportista'}],
            'ent_asistencias': [{'sesion_id': 'sesion', 'jugador_id': 101, 'estado': 'presente'}, {'sesion_id': 'sesion', 'jugador_id': 102, 'estado': 'ausente'}],
            'categorias': [{'id': 10, 'nombre': 'Sub 12', 'activa': True}],
        }
    def table(self, tabla): return Consulta(self, tabla)
    def rpc(self, nombre, parametros):
        def execute():
            self.operaciones.append((nombre, 'rpc', {}, copy.deepcopy(parametros)))
            if nombre == 'ent_confirmar_archivo':
                next(a for a in self.datos['ent_archivos'] if a['id'] == parametros['p_archivo'])['confirmado'] = True
            return SimpleNamespace(data=None)
        return SimpleNamespace(execute=execute)


class ArchivosEntrenamiento(unittest.TestCase):
    def test_pdf_valido_y_limite_de_paginas(self):
        salida = io.BytesIO(); pdf = canvas.Canvas(salida)
        for _ in range(21): pdf.drawString(40, 700, 'Sesión'); pdf.showPage()
        pdf.save()
        with self.assertRaises(ValueError): validar_archivo('plan.pdf', salida.getvalue(), 'plan')
        salida = io.BytesIO(); pdf = canvas.Canvas(salida); pdf.drawString(40, 700, 'Sesión'); pdf.save()
        archivo = validar_archivo('plan.pdf', salida.getvalue(), 'plan')
        self.assertEqual(archivo['mime'], 'application/pdf')
        self.assertEqual(archivo['contenido'], salida.getvalue())

    def test_rechaza_extension_falsa_archivos_vacios_y_tipo_desconocido(self):
        for nombre, datos, tipo in [('falso.pdf', b'No es PDF', 'plan'), ('foto.jpg', b'No es foto', 'foto'), ('vacio', b'', 'foto'), ('x', b'abc', 'otro')]:
            with self.subTest(nombre=nombre), self.assertRaises(ValueError): validar_archivo(nombre, datos, tipo)

    def test_fotos_no_se_deforman_y_no_conservan_metadatos(self):
        salida = io.BytesIO(); imagen = Image.new('RGB', (240, 120), '#70A808')
        exif = Image.Exif(); exif[270] = 'Información privada'
        imagen.save(salida, format='JPEG', exif=exif)
        archivo = validar_archivo('foto.jpg', salida.getvalue(), 'foto')
        with Image.open(io.BytesIO(archivo['contenido'])) as resultado:
            self.assertEqual(resultado.size, (240, 120)); self.assertEqual(dict(resultado.getexif()), {})

    def test_nombre_no_puede_crear_rutas_en_zip(self):
        self.assertEqual(nombre_seguro('../../secreto.pdf'), 'secreto.pdf')
        self.assertEqual(nombre_seguro('..\\..\\foto.jpg'), 'foto.jpg')

    def test_foto_con_orientacion_exif_se_gira_sin_recortar(self):
        salida = io.BytesIO(); imagen = Image.new('RGB', (240, 120), '#70A808')
        exif = Image.Exif(); exif[274] = 6
        imagen.save(salida, format='JPEG', exif=exif)
        archivo = validar_archivo('foto.jpg', salida.getvalue(), 'foto')
        with Image.open(io.BytesIO(archivo['contenido'])) as resultado:
            self.assertEqual(resultado.size, (120, 240))
            self.assertEqual(dict(resultado.getexif()), {})

    def test_pdf_de_pagina_enorme_se_muestra_con_resolucion_acotada(self):
        salida = io.BytesIO()
        pdf = canvas.Canvas(salida, pagesize=(20000, 30000))
        pdf.drawString(40, 700, 'Contenido de prueba'); pdf.save()
        dimensiones = []
        with patch('streamlit.checkbox', return_value=True), \
                patch('streamlit.number_input', return_value=1), \
                patch('modules.entrenamientos.leer_archivo', return_value=salida.getvalue()), \
                patch('streamlit.image', side_effect=lambda imagen, **kwargs: dimensiones.append(imagen.size)), \
                patch('streamlit.error') as error:
            mostrar_documento(None, {'id': 'pdf', 'nombre': 'plan.pdf', 'tipo': 'plan'}, Contexto('padre', 'usuario'))
        error.assert_not_called()
        self.assertEqual(len(dimensiones), 1)
        self.assertLessEqual(max(dimensiones[0]), 1801)


class OperacionesEntrenamiento(unittest.TestCase):
    def setUp(self):
        self.cliente = Cliente(); self.ctx = Contexto('entrenador', 'usuario')
        self.sesion = self.cliente.datos['ent_sesiones'][0]; self.grupo = self.cliente.datos['ent_grupos'][0]

    def test_lectores_y_vista_previa_no_escriben_ni_suben(self):
        for ctx in [Contexto('padre', 'usuario'), Contexto('autoridad', 'usuario'), Contexto('entrenador', 'otro'), Contexto('entrenador', 'usuario', True), Contexto('administrador', 'usuario', True)]:
            with self.subTest(ctx=ctx):
                for llamada in [lambda: publicar_sesion(self.cliente, ctx, self.sesion),
                                lambda: guardar_asistencia(self.cliente, ctx, self.sesion, []),
                                lambda: subir_adjunto(self.cliente, ctx, self.sesion, {})]:
                    with self.assertRaises(PermissionError): llamada()
        self.assertEqual(self.cliente.operaciones, [])
        self.assertEqual(self.cliente.storage.operaciones, [])

    def test_crea_borrador_y_confirma_cada_carga_antes_de_publicar(self):
        foto = {'tipo': 'foto', 'mime': 'image/png', 'extension': 'png', 'nombre': 'foto.png', 'contenido': b'foto'}
        identificador = crear_sesion(self.cliente, self.ctx, self.grupo, 'Nueva', 'Objetivo', 'Contenido', date(2026,10,20), [foto])
        creada = next(s for s in self.cliente.datos['ent_sesiones'] if s['id'] == identificador)
        self.assertEqual(creada['estado'], 'publicada')
        self.assertTrue(self.cliente.datos['ent_archivos'][0]['confirmado'])
        nombres = [(tabla, accion) for tabla, accion, _, _ in self.cliente.operaciones]
        self.assertLess(nombres.index(('ent_confirmar_archivo', 'rpc')), nombres.index(('ent_sesiones', 'update')))

    def test_fallo_de_carga_no_publica_y_limpia_solo_el_objeto_nuevo(self):
        self.cliente.storage.falla = True
        self.cliente.storage.archivos['ajeno'] = b'Conservar'
        archivo = {'tipo': 'foto', 'mime': 'image/png', 'extension': 'png', 'nombre': 'foto.png', 'contenido': b'foto'}
        with self.assertRaises(RuntimeError): crear_sesion(self.cliente, self.ctx, self.grupo, 'Nueva', 'Objetivo', 'Contenido', date.today(), [archivo])
        self.assertEqual(self.cliente.datos['ent_sesiones'][-1]['estado'], 'borrador')
        self.assertEqual(self.cliente.storage.archivos['ajeno'], b'Conservar')
        self.assertEqual(self.cliente.datos['ent_archivos'], [])

    def test_grupo_y_asistencia_de_representante_se_filtran_en_la_consulta(self):
        jugador = self.cliente.datos['jugadores'][0]
        grupos_visibles(self.cliente, Contexto('padre', 'usuario'), jugador)
        asistencia = asistencia_sesion(self.cliente, self.sesion, jugador)
        consultas = [o for o in self.cliente.operaciones if o[0] == 'ent_grupos']
        self.assertEqual(consultas[0][2], {'categoria_id': 10, 'institucion': 'Colegio Surcos'})
        self.assertEqual([a['jugador_id'] for a in asistencia], [101])

    def test_autoridad_no_muestra_grupos_de_club(self):
        self.cliente.datos['ent_grupos'].append(dict(self.grupo, id='club', institucion='Club Juventud'))
        self.assertEqual([g['id'] for g in grupos_visibles(self.cliente, Contexto('autoridad', 'usuario'))], ['grupo'])

    def test_ficha_deportiva_limita_espacio_a_su_institucion_y_categoria_tambien_para_staff(self):
        self.cliente.datos['ent_grupos'].append(dict(self.grupo, id='club', institucion='Club Juventud'))
        jugador = self.cliente.datos['jugadores'][0]
        self.assertEqual([g['id'] for g in grupos_visibles(self.cliente, self.ctx, jugador)], ['grupo'])

    def test_estado_asistencia_invalido_no_envia_rpc(self):
        with self.assertRaises(ValueError): guardar_asistencia(self.cliente, self.ctx, self.sesion, [{'jugador_id':101,'estado':'inventado'}])
        self.assertEqual(self.cliente.operaciones, [])

    def test_csv_contiene_estados_reales_y_neutraliza_formulas(self):
        jugadores = [{'id': 101, 'apellidos': '=FORMULA', 'nombres': 'Prueba'}]
        datos = csv_asistencia([{'jugador_id':101,'estado':'justificado'}], jugadores).decode('utf-8-sig')
        self.assertIn("'=FORMULA", datos); self.assertIn('Justificado', datos)

    def test_csv_incluye_a_quien_aun_no_tiene_asistencia_sin_suponer_ausencia(self):
        datos = csv_asistencia([{'jugador_id':101, 'estado':'presente'}], self.cliente.datos['jugadores']).decode('utf-8-sig')
        self.assertIn('Deportista, Otro,Sin registrar', datos.replace('"', ''))
        self.assertNotIn('Ausente', datos)

    def test_zip_incluye_sesion_asistencia_y_archivos_sin_pendientes(self):
        self.cliente.storage.archivos['ruta'] = b'PDF'
        adjuntos = [{'id':'archivo','confirmado':True,'ruta':'ruta','nombre':'../../plan.pdf'}, {'id':'pendiente','confirmado':False}]
        datos = paquete_sesion(self.cliente, self.ctx, self.sesion, adjuntos, self.cliente.datos['ent_asistencias'], self.cliente.datos['jugadores'])
        with zipfile.ZipFile(io.BytesIO(datos)) as archivo:
            self.assertEqual(set(archivo.namelist()), {'sesion.txt','asistencia.csv','archivo_plan.pdf'})
        with self.assertRaises(PermissionError): paquete_sesion(self.cliente, Contexto('padre','usuario'),self.sesion,adjuntos,[],[])


class InterfazEntrenamientos(unittest.TestCase):
    def ejecutar(self, rol, errores=(), previa=None):
        cliente = Cliente(rol)
        cliente.errores = errores
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=20)
        app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='usuario',email='prueba@example.invalid'))
        app.session_state.menu_principal = 'Entrenamientos'
        if previa: app.session_state['vista_rol_usuario'] = previa
        with patch.object(autenticacion,'conectar_supabase',return_value=cliente): app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app, cliente

    def test_entrenador_tiene_cargas_y_asistencia(self):
        app, _ = self.ejecutar('entrenador')
        self.assertTrue(any(b.label == 'Publicar entrenamiento' for b in app.button))
        self.assertTrue(any(b.label == 'Guardar asistencia' for b in app.button))
        self.assertTrue(any(e.label == 'Registrar asistencia de la categoría' for e in app.expander))

    def test_autoridad_ve_y_descarga_sin_cargas_ni_guardado(self):
        app, _ = self.ejecutar('autoridad')
        self.assertTrue(any(m.value == '#### Sesión publicada' for m in app.markdown))
        self.assertFalse(any(b.label in ('Publicar entrenamiento','Guardar asistencia','Añadir archivo') for b in app.button))
        self.assertTrue(any(c.label == 'Preparar descarga completa de esta sesión' for c in app.checkbox))

    def test_representante_sin_descargas_ni_asistencia_ajena(self):
        app, cliente = self.ejecutar('padre')
        self.assertIn('Entrenamientos', [t.label for t in app.tabs])
        self.assertFalse(any(c.label == 'Preparar descarga completa de esta sesión' for c in app.checkbox))
        self.assertFalse(any(b.label == 'Guardar asistencia' for b in app.button))
        self.assertFalse(any(d.type == 'download_button' and 'ent_' in str(d.proto) for d in app.get('download_button')))
        consultas = [o for o in cliente.operaciones if o[0] == 'ent_asistencias']
        self.assertTrue(consultas)
        self.assertTrue(all(o[2].get('jugador_id') == 101 for o in consultas))
        self.assertTrue(any(m.value == 'Presente' for m in app.markdown))

    def test_administrador_tiene_gestion_de_categorias_y_descargas(self):
        app, _ = self.ejecutar('administrador')
        self.assertTrue(any(e.label == 'Administrar categorías de entrenamiento y entrenadores' for e in app.expander))
        self.assertTrue(any(c.label == 'Preparar descarga completa de esta sesión' for c in app.checkbox))

    def test_falta_de_tablas_no_rompe_ficha(self):
        app, _ = self.ejecutar('padre', errores=['ent_grupos'])
        self.assertTrue(any('aún no está disponible' in i.value for i in app.info))
        self.assertTrue(any(b.label == 'Análisis de rendimiento inteligente' for b in app.button))

    def test_vista_previa_bloquea_publicacion(self):
        app, _ = self.ejecutar('administrador', previa='Entrenador')
        self.assertTrue(next(b for b in app.button if b.label == 'Publicar entrenamiento').disabled)


if __name__ == '__main__': unittest.main()
