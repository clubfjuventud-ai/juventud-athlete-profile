import tempfile
import base64
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image
from streamlit.testing.v1 import AppTest

from modules import autenticacion, informes_pdf, utilidades
from modules.configuracion import INSTITUCION_JUVENTUD, INSTITUCION_SURCOS
from test_regresiones import Cliente


class LogosInstitucionales(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        carpeta = Path(self.temporal.name)
        # Imágenes de prueba deliberadamente distintas en proporciones.
        self.juventud = carpeta / 'logo_juventud.png'
        self.surcos = carpeta / 'logo_surcos.png'
        Image.new('RGB', (200, 300), '#101114').save(self.juventud)
        Image.new('RGB', (500, 150), 'white').save(self.surcos)
        for nombre, ruta in [('LOGO_JUVENTUD', self.juventud), ('LOGO_SURCOS', self.surcos)]:
            parche = patch.object(utilidades, nombre, ruta)
            parche.start()
            self.addCleanup(parche.stop)

    def test_resuelve_por_institucion_y_no_inventa_logo_para_otras(self):
        self.assertEqual(utilidades.ruta_logo(INSTITUCION_JUVENTUD), self.juventud)
        self.assertEqual(utilidades.ruta_logo(' Colegio Surcos '), self.surcos)
        self.assertEqual(utilidades.ruta_logo(None), self.juventud)
        self.assertIsNone(utilidades.ruta_logo('Otra institución'))

    def test_archivos_ausentes_o_directorios_devuelven_none(self):
        self.juventud.unlink()
        self.surcos.unlink()
        self.surcos.mkdir()
        self.assertIsNone(utilidades.ruta_logo(INSTITUCION_JUVENTUD))
        self.assertIsNone(utilidades.ruta_logo(INSTITUCION_SURCOS))

    def test_streamlit_fija_solo_ancho_y_selecciona_logo_correcto(self):
        with patch.object(utilidades, 'st') as interfaz:
            utilidades.mostrar_marca(INSTITUCION_SURCOS, ancho=180)
            interfaz.image.assert_called_once()
            llamada = interfaz.image.call_args
            self.assertEqual(llamada.kwargs, {"width": 180})
            self.assertTrue(llamada.args[0].startswith("data:image/png;base64,"))
            interfaz.text.assert_not_called()

    def test_nombre_visible_si_falta_o_no_se_puede_leer_imagen(self):
        self.surcos.unlink()
        with patch.object(utilidades, 'st') as interfaz:
            utilidades.mostrar_marca(INSTITUCION_SURCOS)
            interfaz.text.assert_called_once_with(INSTITUCION_SURCOS)
            interfaz.image.assert_not_called()
        with patch.object(utilidades, 'st') as interfaz:
            interfaz.image.side_effect = OSError('imagen ilegible')
            utilidades.mostrar_marca(INSTITUCION_JUVENTUD)
            interfaz.text.assert_called_once_with(INSTITUCION_JUVENTUD)

    def test_pdf_conserva_proporciones_de_ambos_logos(self):
        original = informes_pdf.PDFImage
        for institucion, proporcion in [(INSTITUCION_JUVENTUD, 2/3), (INSTITUCION_SURCOS, 10/3)]:
            with self.subTest(institucion=institucion):
                imagenes = []
                def capturar(*args, **kwargs):
                    imagen = original(*args, **kwargs)
                    imagenes.append(imagen)
                    return imagen
                with patch.object(informes_pdf, 'PDFImage', side_effect=capturar):
                    pdf = informes_pdf.generar_pdf({'institucion': institucion}, [], [], [], [], False, False)
                self.assertTrue(pdf.startswith(b'%PDF'))
                self.assertEqual(len(imagenes), 1)
                self.assertAlmostEqual(imagenes[0].drawWidth / imagenes[0].drawHeight, proporcion)

    def test_pdf_sin_logos_o_con_archivo_invalido_sigue_funcionando(self):
        for institucion, ruta in [(INSTITUCION_JUVENTUD, self.juventud), (INSTITUCION_SURCOS, self.surcos)]:
            ruta.unlink()
            pdf = informes_pdf.generar_pdf({'institucion': institucion}, [], [], [], [], False, False)
            self.assertTrue(pdf.startswith(b'%PDF'))
            ruta.write_text('archivo inválido')
            pdf = informes_pdf.generar_pdf({'institucion': institucion}, [], [], [], [], False, False)
            self.assertTrue(pdf.startswith(b'%PDF'))

    def app(self):
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)

    def test_acceso_no_muestra_logos_sin_conectar_supabase(self):
        app = self.app().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('image')), 0)
        self.assertTrue(any(b.label == 'Iniciar sesión' for b in app.button))

    def test_menu_ficha_y_administracion(self):
        for seccion, imagenes in [('Inicio', 0), ('Jugadores Juventud', 2), ('Colegio Surcos', 2), ('Usuarios y representantes', 0)]:
            with self.subTest(seccion=seccion):
                cliente = Cliente(rol='administrador')
                if seccion == 'Colegio Surcos':
                    for jugador in cliente.datos['jugadores']:
                        jugador['institucion'] = INSTITUCION_SURCOS
                app = self.app()
                app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='prueba', email='prueba@example.invalid'))
                app.session_state.menu_principal = seccion
                with patch.object(autenticacion, 'conectar_supabase', return_value=cliente), \
                        patch.object(utilidades, 'mostrar_marca', wraps=utilidades.mostrar_marca) as marcas:
                    app.run()
                self.assertEqual(len(app.exception), 0, str(app.exception))
                self.assertEqual(len(app.get('image')), imagenes)
                self.assertEqual(len(app.sidebar.get('image')), 0)

    def test_acceso_sin_archivos_no_muestra_logos(self):
        self.juventud.unlink()
        self.surcos.unlink()
        app = self.app().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('image')), 0)
        self.assertEqual(len(app.text), 0)


class LogosOriginales(unittest.TestCase):
    def test_png_originales_resuelven_y_se_decodifican(self):
        for institucion in (INSTITUCION_JUVENTUD, INSTITUCION_SURCOS):
            with self.subTest(institucion=institucion):
                ruta = utilidades.ruta_logo(institucion)
                self.assertIsNotNone(ruta)
                with Image.open(ruta) as imagen:
                    self.assertEqual(imagen.format, 'PNG')
                    self.assertEqual(max(imagen.size), 3840)
                    imagen.verify()

    def test_acceso_con_png_originales(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.get('image')), 0)

    def test_menu_fichas_y_administracion_con_png_originales(self):
        for seccion in ('Inicio', 'Jugadores Juventud', 'Colegio Surcos', 'Usuarios y representantes'):
            with self.subTest(seccion=seccion):
                cliente = Cliente(rol='administrador')
                if seccion == 'Colegio Surcos':
                    for jugador in cliente.datos['jugadores']:
                        jugador['institucion'] = INSTITUCION_SURCOS
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15)
                app.session_state.sesion = SimpleNamespace(user=SimpleNamespace(id='prueba', email='prueba@example.invalid'))
                app.session_state.menu_principal = seccion
                with patch.object(autenticacion, 'conectar_supabase', return_value=cliente), \
                        patch.object(utilidades, 'mostrar_marca', wraps=utilidades.mostrar_marca) as marcas:
                    app.run()
                self.assertEqual(len(app.exception), 0, str(app.exception))
                cantidad = 2 if seccion in ('Jugadores Juventud', 'Colegio Surcos') else 0
                self.assertEqual(len(app.get('image')), cantidad)
                self.assertEqual(marcas.call_count, cantidad)
                if cantidad:
                    institucion = INSTITUCION_SURCOS if seccion == 'Colegio Surcos' else INSTITUCION_JUVENTUD
                    self.assertTrue(all(llamada.args[0] == institucion for llamada in marcas.call_args_list))
                    for imagen_web in app.get('image'):
                        uri = imagen_web.proto.imgs[0].url
                        self.assertTrue(uri.startswith('data:image/png;base64,'))
                        with Image.open(io.BytesIO(base64.b64decode(uri.split(',', 1)[1]))) as enviada:
                            self.assertGreaterEqual(enviada.width, 420)

                self.assertEqual(len(app.sidebar.get('image')), 0)
                self.assertEqual(len(app.error), 0)

    def test_logo_web_retiene_tres_pixeles_por_pixel_css(self):
        for institucion in (INSTITUCION_JUVENTUD, INSTITUCION_SURCOS):
            with self.subTest(institucion=institucion), patch.object(utilidades, 'st') as interfaz:
                utilidades.mostrar_marca(institucion, ancho=150)
                uri = interfaz.image.call_args.args[0]
                with Image.open(io.BytesIO(base64.b64decode(uri.split(',', 1)[1]))) as enviada:
                    self.assertEqual(enviada.width, 450)
                    with Image.open(utilidades.ruta_logo(institucion)) as original:
                        self.assertLessEqual(abs(enviada.height - 450 * original.height / original.width), 0.5)
                self.assertEqual(interfaz.image.call_args.kwargs['width'], 150)

    def test_pdf_incrusta_original_correcto_sin_deformarlo(self):
        constructor = informes_pdf.PDFImage
        for institucion in (INSTITUCION_JUVENTUD, INSTITUCION_SURCOS):
            with self.subTest(institucion=institucion):
                ruta = utilidades.ruta_logo(institucion)
                with Image.open(ruta) as original:
                    proporcion = original.width / original.height
                imagenes = []
                def capturar(*args, **kwargs):
                    self.assertEqual(Path(args[0]), ruta)
                    imagen = constructor(*args, **kwargs)
                    imagenes.append(imagen)
                    return imagen
                with patch.object(informes_pdf, 'PDFImage', side_effect=capturar):
                    pdf = informes_pdf.generar_pdf({'institucion': institucion}, [], [], [], [], False, False)
                self.assertEqual(len(imagenes), 1)
                self.assertAlmostEqual(imagenes[0].drawWidth / imagenes[0].drawHeight, proporcion)
                self.assertTrue(pdf.startswith(b'%PDF'))
                self.assertIn(b'/Subtype /Image', pdf)


class ColoresPdf(unittest.TestCase):
    def test_paleta_encabezados_tablas_y_pie_por_institucion(self):
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Table
        from unittest.mock import Mock
        for institucion, principal, acento, fondo in [
            (INSTITUCION_JUVENTUD, '#17170F', '#D8A830', '#F8F1D9'),
            (INSTITUCION_SURCOS, '#0868A0', '#70A808', '#EFF6DF'),
        ]:
            with self.subTest(institucion=institucion):
                documentos = []
                def capturar(doc, elementos, **callbacks):
                    documentos.append((doc, elementos))
                    canvas = Mock()
                    callbacks['onFirstPage'](canvas, SimpleNamespace(page=1))
                    trazos = [llamada.args[0] for llamada in canvas.setStrokeColor.call_args_list]
                    self.assertEqual(trazos, [HexColor(principal), HexColor(acento)])
                    self.assertTrue(any(institucion.upper() in llamada.args[-1]
                                        for llamada in canvas.drawString.call_args_list))
                with patch.object(informes_pdf.SimpleDocTemplate, 'build', autospec=True, side_effect=capturar), \
                        patch.object(informes_pdf, 'ruta_logo', return_value=None):
                    informes_pdf.generar_pdf({'institucion': institucion}, [], [], [], [], False, False)
                doc, elementos = documentos[0]
                self.assertEqual(doc.author, institucion)
                titulo = next(e for e in elementos if isinstance(e, Paragraph) and e.style.name == 'TituloClub')
                self.assertEqual(titulo.style.textColor, HexColor(principal))
                tablas = [e for e in elementos if isinstance(e, Table)]
                self.assertTrue(tablas)
                self.assertTrue(all(t._bkgrndcmds[0][-1] == HexColor(fondo) for t in tablas))
                textos = [e.getPlainText() for e in elementos if isinstance(e, Paragraph)]
                if institucion == INSTITUCION_SURCOS:
                    self.assertIn('Unidad Educativa Bilingüe', textos)
                    self.assertNotIn('Juventud con Propósito y Futuro', textos)



if __name__ == '__main__':
    unittest.main()
