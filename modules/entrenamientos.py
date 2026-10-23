"""Sesiones por institución/categoría. Siempre usa el cliente autenticado y sus RLS."""
import csv
import io
import logging
import math
import re
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from PIL import Image, ImageOps
from modules.utilidades import obtener_paginas, nombre_jugador, fecha_legible

BUCKET = 'entrenamientos-privados'
MAX_ARCHIVO = 10 * 1024 * 1024
ESTADOS = {'sin_registrar': 'Sin registrar', 'presente': 'Presente', 'ausente': 'Ausente', 'justificado': 'Justificado'}


@dataclass(frozen=True)
class Contexto:
    rol: str
    usuario_id: str
    previa: bool = False

    @property
    def descarga(self):
        return self.rol in ('administrador', 'entrenador', 'autoridad')

    def edita(self, sesion=None):
        return not self.previa and (self.rol == 'administrador' or (
            self.rol == 'entrenador' and (sesion is None or str(sesion['creado_por']) == self.usuario_id)))


def exigir_edicion(ctx, sesion=None):
    if not ctx.edita(sesion):
        raise PermissionError('Esta cuenta no puede guardar cambios en esta sesión.')


def nombre_seguro(nombre):
    return re.sub(r'[^\w. -]', '_', str(nombre).replace('\\', '/').rsplit('/', 1)[-1])[:160] or 'archivo'


def validar_archivo(nombre, contenido, tipo):
    if not contenido or len(contenido) > MAX_ARCHIVO:
        raise ValueError('Cada archivo debe tener contenido y pesar como máximo 10 MB.')
    nombre = nombre_seguro(nombre)
    if tipo == 'plan':
        if not contenido.startswith(b'%PDF-'):
            raise ValueError('El documento debe ser un PDF válido.')
        import pypdfium2 as pdfium
        try:
            with closing(pdfium.PdfDocument(contenido)) as doc:
                if not 1 <= len(doc) <= 20:
                    raise ValueError('El PDF debe tener entre 1 y 20 páginas.')
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('No se puede leer el PDF. Revisa el archivo antes de subirlo.') from error
        return {'tipo': tipo, 'mime': 'application/pdf', 'extension': 'pdf', 'nombre': nombre, 'contenido': contenido}
    if tipo != 'foto':
        raise ValueError('Tipo de archivo no admitido.')
    try:
        with Image.open(io.BytesIO(contenido)) as foto:
            if foto.format not in ('PNG', 'JPEG') or foto.width * foto.height > 12_000_000:
                raise ValueError('Usa fotografías PNG o JPG de hasta 12 megapíxeles.')
            foto.verify()
        with Image.open(io.BytesIO(contenido)) as foto:
            formato = foto.format
            # Elimina metadatos EXIF (incluida ubicación) al almacenar la fotografía.
            with ImageOps.exif_transpose(foto) as orientada:
                with Image.new('RGB' if formato == 'JPEG' else 'RGBA', orientada.size) as limpia:
                    limpia.paste(orientada.convert(limpia.mode))
                    buffer = io.BytesIO()
                    limpia.save(buffer, format=formato, **({'quality': 95, 'subsampling': 0} if formato == 'JPEG' else {}))
        datos = buffer.getvalue()
        if len(datos) > MAX_ARCHIVO:
            raise ValueError('La fotografía procesada supera los 10 MB.')
        return {'tipo': tipo, 'mime': 'image/jpeg' if formato == 'JPEG' else 'image/png',
                'extension': 'jpg' if formato == 'JPEG' else 'png', 'nombre': nombre, 'contenido': datos}
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError('No se puede leer la fotografía. Usa PNG o JPG.') from error


def grupos_visibles(cliente, ctx, jugador=None):
    consulta = lambda: cliente.table('ent_grupos').select('id,institucion,categoria_id,categorias(nombre)').order('institucion').order('id')
    if jugador is not None or ctx.rol == 'padre':
        if not jugador or jugador.get('categoria_id') is None:
            return []
        consulta = lambda: cliente.table('ent_grupos').select('id,institucion,categoria_id,categorias(nombre)').eq('categoria_id', jugador['categoria_id']).eq('institucion', jugador.get('institucion') or 'Club Juventud').order('id')
    grupos = obtener_paginas(consulta)
    if ctx.rol == 'autoridad':
        grupos = [g for g in grupos if g['institucion'] == 'Colegio Surcos']
    return grupos


def sesiones_grupo(cliente, grupo):
    return obtener_paginas(lambda: cliente.table('ent_sesiones').select('*').eq('grupo_id', grupo['id']).order('fecha', desc=True).order('id'))


def adjuntos_sesion(cliente, sesion):
    return obtener_paginas(lambda: cliente.table('ent_archivos').select('*').eq('sesion_id', sesion['id']).order('created_at').order('id'))


def asistencia_sesion(cliente, sesion, jugador=None):
    def consulta():
        q = cliente.table('ent_asistencias').select('*').eq('sesion_id', sesion['id']).order('jugador_id')
        return q.eq('jugador_id', jugador['id']) if jugador else q
    return obtener_paginas(consulta)


def comprobar_mutacion(respuesta):
    if not respuesta.data:
        raise PermissionError('El servidor no confirmó el cambio. Comprueba tus asignaciones y vuelve a cargar la página.')


def subir_adjunto(cliente, ctx, sesion, archivo):
    exigir_edicion(ctx, sesion)
    id_archivo = str(uuid4())
    ruta = f"{sesion['id']}/{id_archivo}.{archivo['extension']}"
    comprobar_mutacion(cliente.table('ent_archivos').insert({
        'id': id_archivo, 'sesion_id': sesion['id'], 'tipo': archivo['tipo'], 'ruta': ruta,
        'nombre': archivo['nombre'], 'mime': archivo['mime'], 'tamano': len(archivo['contenido']),
    }).execute())
    try:
        cliente.storage.from_(BUCKET).upload(ruta, archivo['contenido'], {'content-type': archivo['mime'], 'upsert': 'false'})
        cliente.rpc('ent_confirmar_archivo', {'p_archivo': id_archivo}).execute()
    except Exception:
        # Solo el objeto nuevo y su metadato pendiente; nunca borra material confirmado.
        try:
            cliente.storage.from_(BUCKET).remove([ruta])
            cliente.table('ent_archivos').delete().eq('id', id_archivo).eq('confirmado', False).execute()
        except Exception:
            logging.getLogger(__name__).warning('Carga pendiente de completar en entrenamientos')
        raise


def crear_sesion(cliente, ctx, grupo, titulo, objetivos, contenido, fecha, archivos=()):
    exigir_edicion(ctx)
    if not 1 <= len(titulo.strip()) <= 160 or not 1 <= len(objetivos.strip()) <= 4000 or not 1 <= len(contenido.strip()) <= 20000:
        raise ValueError('Completa título, objetivos y descripción de la sesión dentro de sus límites.')
    if len(archivos) > 9 or sum(a['tipo'] == 'plan' for a in archivos) > 1 or sum(len(a['contenido']) for a in archivos) > 64 * 1024 * 1024:
        raise ValueError('Admite un PDF y hasta ocho fotografías, con un total máximo de 64 MB.')
    id_sesion = str(uuid4())
    respuesta = cliente.table('ent_sesiones').insert({
        'id': id_sesion, 'grupo_id': grupo['id'], 'fecha': fecha.isoformat(),
        'titulo': titulo.strip(), 'objetivos': objetivos.strip(), 'contenido': contenido.strip(),
    }).execute()
    comprobar_mutacion(respuesta)
    sesion = dict(respuesta.data[0])
    try:
        for archivo in archivos:
            subir_adjunto(cliente, ctx, sesion, archivo)
        publicar_sesion(cliente, ctx, sesion)
    except Exception as error:
        raise RuntimeError('La sesión se creó, pero no se confirmó su publicación. Revisa su estado y sus archivos antes de reintentar; no vuelvas a crear la misma sesión.') from error
    return id_sesion


def publicar_sesion(cliente, ctx, sesion):
    exigir_edicion(ctx, sesion)
    comprobar_mutacion(cliente.table('ent_sesiones').update({'estado': 'publicada'}).eq('id', sesion['id']).execute())


def guardar_asistencia(cliente, ctx, sesion, registros):
    exigir_edicion(ctx, sesion)
    if len(registros) > 300 or any(r['estado'] not in ESTADOS for r in registros):
        raise ValueError('Revisa los estados de asistencia.')
    cliente.rpc('ent_guardar_asistencia', {'p_sesion': sesion['id'], 'p_registros': registros}).execute()


def csv_asistencia(registros, jugadores):
    nombres = {str(j['id']): nombre_jugador(j) for j in jugadores}
    estados = {str(r['jugador_id']): r['estado'] for r in registros}
    def celda(valor):
        texto = str(valor)
        return "'" + texto if texto.lstrip().startswith(('=', '+', '-', '@')) else texto
    salida = io.StringIO(newline='')
    escritor = csv.writer(salida)
    escritor.writerow(['Deportista', 'Asistencia'])
    for identificador in dict.fromkeys([*nombres, *estados]):
        escritor.writerow([celda(nombres.get(identificador, 'Deportista no disponible')), ESTADOS.get(estados.get(identificador), 'Sin registrar')])
    return salida.getvalue().encode('utf-8-sig')


def leer_archivo(cliente, archivo):
    datos = cliente.storage.from_(BUCKET).download(archivo['ruta'])
    if len(datos) > MAX_ARCHIVO:
        raise ValueError('El archivo supera el tamaño admitido.')
    return datos


def paquete_sesion(cliente, ctx, sesion, adjuntos, asistencia, jugadores):
    if not ctx.descarga:
        raise PermissionError('Este rol dispone de consulta en pantalla.')
    salida = io.BytesIO()
    total = 0
    with zipfile.ZipFile(salida, 'w', compression=zipfile.ZIP_DEFLATED) as paquete:
        paquete.writestr('sesion.txt', f"{sesion['titulo']}\nFecha: {sesion['fecha']}\nObjetivos: {sesion['objetivos']}\n\n{sesion['contenido']}")
        paquete.writestr('asistencia.csv', csv_asistencia(asistencia, jugadores))
        for archivo in adjuntos:
            if not archivo['confirmado']:
                continue
            datos = leer_archivo(cliente, archivo)
            total += len(datos)
            if total > 64 * 1024 * 1024:
                raise ValueError('La sesión supera 64 MB. Descarga sus archivos individualmente.')
            paquete.writestr(archivo['id'] + '_' + nombre_seguro(archivo['nombre']), datos)
    return salida.getvalue()


def formulario_sesion(cliente, ctx, grupo):
    import streamlit as st
    if ctx.rol not in ('entrenador', 'administrador'):
        return
    with st.expander('Publicar sesión de entrenamiento'):
        with st.form('ent_nueva_' + grupo['id'], clear_on_submit=False):
            titulo = st.text_input('Título de la sesión', max_chars=160)
            fecha = st.date_input('Fecha del entrenamiento', value=date.today(), format='DD/MM/YYYY')
            objetivos = st.text_area('Objetivos del entrenamiento', max_chars=4000)
            contenido = st.text_area('Descripción y actividades', max_chars=20000, help='Este texto también permite consultar la sesión sin descargar el PDF.')
            plan = st.file_uploader('Plan de sesión en PDF (opcional)', type=['pdf'], max_upload_size=10)
            fotos = st.file_uploader('Evidencia fotográfica (hasta ocho fotos)', type=['png', 'jpg', 'jpeg'], accept_multiple_files=True, max_upload_size=10)
            guardar = st.form_submit_button('Publicar entrenamiento', disabled=ctx.previa)
        if guardar and ctx.edita():
            try:
                if len(fotos) > 8:
                    raise ValueError('Selecciona como máximo ocho fotografías.')
                archivos = ([validar_archivo(plan.name, plan.getvalue(), 'plan')] if plan else [])
                archivos += [validar_archivo(f.name, f.getvalue(), 'foto') for f in fotos]
                crear_sesion(cliente, ctx, grupo, titulo, objetivos, contenido, fecha, archivos)
                st.success('Entrenamiento publicado.')
                st.rerun()
            except (ValueError, RuntimeError) as error:
                st.error(str(error))
            except Exception:
                st.error('No se pudo publicar. Comprueba tu asignación a esta categoría e inténtalo de nuevo.')


def mostrar_documento(cliente, archivo, ctx):
    import streamlit as st
    if st.checkbox('Ver ' + archivo['nombre'], key='ent_ver_' + archivo['id']):
        try:
            datos = leer_archivo(cliente, archivo)
            if archivo['tipo'] == 'foto':
                st.image(datos, caption=archivo['nombre'], use_container_width=True)
            else:
                import pypdfium2 as pdfium
                with closing(pdfium.PdfDocument(datos)) as doc:
                    pagina = st.number_input('Página del documento', min_value=1, max_value=min(len(doc), 20), value=1, key='ent_pag_' + archivo['id'])
                    with closing(doc[pagina-1]) as hoja:
                        dimensiones = hoja.get_size()
                        if any(not math.isfinite(d) or d <= 0 for d in dimensiones):
                            raise ValueError('Dimensiones de página no válidas.')
                        bitmap = hoja.render(scale=min(1.4, 1800 / max(dimensiones)))
                        try:
                            st.image(bitmap.to_pil(), use_container_width=True)
                        finally:
                            bitmap.close()
            if ctx.descarga:
                st.download_button('Descargar ' + archivo['nombre'], datos, file_name=nombre_seguro(archivo['nombre']), mime=archivo['mime'], key='ent_descarga_' + archivo['id'])
        except Exception:
            st.error('No se pudo abrir el archivo. Reintenta y comprueba tu acceso a la sesión.')


def mostrar_sesion(cliente, ctx, sesion, grupo, jugadores, jugador=None):
    import streamlit as st
    st.caption(f"{fecha_legible(sesion['fecha'])} · {sesion.get('autor_nombre') or 'Equipo técnico'} · {sesion['estado'].capitalize()}")
    st.markdown('**Objetivos**')
    st.text(sesion['objetivos'])
    st.markdown('**Actividades**')
    st.text(sesion['contenido'])
    try:
        adjuntos = adjuntos_sesion(cliente, sesion)
        asistencia = asistencia_sesion(cliente, sesion, jugador)
    except Exception:
        st.error('No se pudieron cargar los archivos o la asistencia. Reintenta antes de descargar o registrar cambios.')
        return
    st.markdown('##### Sesión y evidencia fotográfica')
    confirmados = [a for a in adjuntos if a['confirmado']]
    if not confirmados:
        st.caption('No hay archivos adjuntos publicados.')
    for archivo in confirmados:
        mostrar_documento(cliente, archivo, ctx)
    pendientes = [a for a in adjuntos if not a['confirmado']]
    if pendientes and ctx.edita(sesion):
        st.warning('Hay cargas pendientes. Retíralas y vuelve a subirlas antes de publicar.')
        for archivo in pendientes:
            if st.button('Retirar carga pendiente: ' + archivo['nombre'], key='ent_retirar_' + archivo['id']):
                try:
                    exigir_edicion(ctx, sesion)
                    cliente.storage.from_(BUCKET).remove([archivo['ruta']])
                    comprobar_mutacion(cliente.table('ent_archivos').delete().eq('id', archivo['id']).eq('confirmado', False).execute())
                    st.rerun()
                except Exception:
                    st.error('No se pudo retirar la carga pendiente.')
    if ctx.edita(sesion):
        with st.expander('Añadir fotografías o documento de sesión'):
            with st.form('ent_adjuntar_' + sesion['id']):
                tipo = st.selectbox('Contenido que vas a añadir', ['foto', 'plan'], format_func=lambda x: 'Fotografía' if x == 'foto' else 'Plan en PDF')
                nuevo = st.file_uploader('Archivo', type=['png', 'jpg', 'jpeg', 'pdf'], max_upload_size=10)
                subir = st.form_submit_button('Añadir archivo')
            if subir:
                try:
                    if nuevo is None:
                        raise ValueError('Selecciona un archivo.')
                    if len(confirmados) >= 9 or (tipo == 'foto' and sum(a['tipo'] == 'foto' for a in confirmados) >= 8):
                        raise ValueError('Esta sesión ya alcanzó su límite de archivos.')
                    subir_adjunto(cliente, ctx, sesion, validar_archivo(nuevo.name, nuevo.getvalue(), tipo))
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
                except Exception:
                    st.error('No se pudo añadir el archivo. Revisa si ya hay un plan o una carga pendiente.')
        if sesion['estado'] == 'borrador' and not pendientes:
            if st.button('Publicar este borrador', key='ent_publicar_' + sesion['id']):
                try:
                    publicar_sesion(cliente, ctx, sesion)
                    st.rerun()
                except Exception:
                    st.error('No se pudo publicar el borrador.')
    st.markdown('##### Asistencia de mi representado' if jugador else '##### Asistencia de la categoría')
    mapa = {str(r['jugador_id']): r['estado'] for r in asistencia}
    roster = [j for j in jugadores if str(j.get('categoria_id')) == str(grupo['categoria_id']) and (j.get('institucion') or 'Club Juventud') == grupo['institucion']]
    if jugador:
        st.write(ESTADOS.get(mapa.get(str(jugador['id'])), 'Sin registrar'))
    elif roster:
        st.dataframe([{'Deportista': nombre_jugador(j), 'Asistencia': ESTADOS.get(mapa.get(str(j['id'])), 'Sin registrar')} for j in roster], hide_index=True, use_container_width=True)
    else:
        st.caption('No hay deportistas visibles en esta categoría para tu cuenta.')
    if ctx.edita(sesion) and roster:
        with st.expander('Registrar asistencia de la categoría'):
            with st.form('ent_asistencia_' + sesion['id']):
                registros = []
                for j in roster:
                    estado = st.selectbox(nombre_jugador(j), list(ESTADOS), index=list(ESTADOS).index(mapa.get(str(j['id']), 'sin_registrar')), format_func=ESTADOS.get, key=f"ent_asistencia_{sesion['id']}_{j['id']}")
                    registros.append({'jugador_id': j['id'], 'estado': estado})
                guardar = st.form_submit_button('Guardar asistencia')
            if guardar:
                try:
                    guardar_asistencia(cliente, ctx, sesion, registros)
                    st.success('Asistencia guardada.')
                    st.rerun()
                except Exception:
                    st.error('No se pudo guardar. Ningún estado se da por confirmado; vuelve a cargar la asistencia.')
    if ctx.descarga:
        st.download_button('Descargar asistencia CSV', csv_asistencia(asistencia, roster), file_name='asistencia.csv', mime='text/csv', key='ent_csv_' + sesion['id'])
        if st.checkbox('Preparar descarga completa de esta sesión', key='ent_zip_' + sesion['id']):
            try:
                paquete = paquete_sesion(cliente, ctx, sesion, adjuntos, asistencia, roster)
                st.download_button('Descargar sesión completa ZIP', paquete, file_name='entrenamiento_' + str(sesion['fecha']) + '.zip', mime='application/zip', key='ent_zip_descarga_' + sesion['id'])
            except Exception:
                st.error('No se pudo preparar la descarga completa. Puedes consultar o descargar los archivos individualmente.')


def configurar_grupos(cliente, ctx):
    import streamlit as st
    if ctx.rol != 'administrador' or ctx.previa:
        return
    with st.expander('Administrar categorías de entrenamiento y entrenadores'):
        try:
            categorias = obtener_paginas(lambda: cliente.table('categorias').select('id,nombre').eq('activa', True).order('nombre').order('id'))
            entrenadores = obtener_paginas(lambda: cliente.table('perfiles').select('id,nombre_completo').eq('rol', 'entrenador').eq('activo', True).order('id'))
            grupos = grupos_visibles(cliente, ctx)
        except Exception:
            st.info('No se pudieron cargar las categorías o los entrenadores disponibles.')
            return
        if categorias:
            with st.form('ent_crear_grupo'):
                institucion = st.selectbox('Institución del grupo', ['Club Juventud', 'Colegio Surcos'])
                categoria = st.selectbox('Categoría del grupo', categorias, format_func=lambda c: c['nombre'])
                crear = st.form_submit_button('Crear espacio de categoría')
            if crear:
                try:
                    exigir_edicion(ctx)
                    comprobar_mutacion(cliente.table('ent_grupos').insert({'institucion': institucion, 'categoria_id': categoria['id']}).execute())
                    st.rerun()
                except Exception:
                    st.error('No se pudo crear. Comprueba si ya existe ese espacio.')
        if grupos and entrenadores:
            with st.form('ent_asignar'):
                grupo = st.selectbox('Espacio de categoría', grupos, format_func=etiqueta_grupo)
                entrenador = st.selectbox('Entrenador responsable', entrenadores, format_func=lambda e: e.get('nombre_completo') or str(e['id']))
                asignar = st.form_submit_button('Asignar entrenador a esta categoría')
            if asignar:
                try:
                    exigir_edicion(ctx)
                    comprobar_mutacion(cliente.table('ent_asignaciones').insert({'grupo_id': grupo['id'], 'usuario_id': entrenador['id']}).execute())
                    st.rerun()
                except Exception:
                    st.error('No se pudo asignar. Comprueba si ya tiene esa categoría.')
        try:
            asignaciones = obtener_paginas(lambda: cliente.table('ent_asignaciones').select('grupo_id,usuario_id').order('grupo_id').order('usuario_id'))
        except Exception:
            st.info('No se pudieron cargar las asignaciones vigentes.')
            return
        nombres = {str(e['id']): e.get('nombre_completo') or 'Entrenador' for e in entrenadores}
        espacios = {g['id']: etiqueta_grupo(g) for g in grupos}
        if asignaciones:
            st.markdown('**Asignaciones vigentes**')
        for asignacion in asignaciones:
            grupo_id, usuario_id = asignacion['grupo_id'], str(asignacion['usuario_id'])
            st.write(espacios.get(grupo_id, 'Categoría') + ' · ' + nombres.get(usuario_id, 'Entrenador'))
            if st.button('Retirar asignación', key='ent_revocar_' + grupo_id + '_' + usuario_id):
                try:
                    exigir_edicion(ctx)
                    comprobar_mutacion(cliente.table('ent_asignaciones').delete().eq('grupo_id', grupo_id).eq('usuario_id', usuario_id).execute())
                    st.rerun()
                except Exception:
                    st.error('No se pudo retirar la asignación.')


def etiqueta_grupo(grupo):
    categoria = grupo.get('categorias') or {}
    if isinstance(categoria, list):
        categoria = categoria[0] if categoria else {}
    return f"{grupo['institucion']} · {categoria.get('nombre') or 'Categoría'}"


def mostrar_espacio(cliente, ctx, jugadores, jugador=None):
    import streamlit as st
    st.subheader('Entrenamientos y seguimiento')
    st.caption('Actividad publicada para la categoría de tu representado.' if ctx.rol == 'padre' else 'Sesiones, evidencia fotográfica y asistencia de la categoría.')
    try:
        grupos = grupos_visibles(cliente, ctx, jugador)
    except Exception:
        st.info('Este espacio aún no está disponible. Administración debe completar su configuración o comprobar la conexión.')
        return
    if jugador is None:
        configurar_grupos(cliente, ctx)
    if not grupos:
        st.info('Todavía no hay espacios de entrenamiento disponibles para esta cuenta y categoría.')
        return
    if jugador:
        grupo = grupos[0]
    else:
        grupo = st.selectbox('Categoría de entrenamiento', grupos, format_func=etiqueta_grupo, key='ent_grupo_' + ctx.usuario_id + '_' + ctx.rol)
    formulario_sesion(cliente, ctx, grupo)
    try:
        sesiones = sesiones_grupo(cliente, grupo)
    except Exception:
        st.error('No se pudieron cargar las sesiones. Reintenta recargando la página.')
        return
    sesiones = [s for s in sesiones if ctx.rol not in ('padre', 'autoridad') or s['estado'] == 'publicada']
    if not sesiones:
        st.info('Aún no hay sesiones disponibles en esta categoría.')
        return
    sesion = st.selectbox('Sesión de entrenamiento', sesiones,
        format_func=lambda s: f"{fecha_legible(s['fecha'])} · {s['titulo']}",
        key='ent_sesion_' + ctx.usuario_id + '_' + ctx.rol + '_' + grupo['id'])
    with st.container(border=True):
        st.markdown('#### ' + sesion['titulo'])
        mostrar_sesion(cliente, ctx, sesion, grupo, jugadores, jugador if ctx.rol == 'padre' else None)
