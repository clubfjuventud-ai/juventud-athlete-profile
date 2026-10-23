# Activación del espacio de entrenamientos

El código está preparado para Supabase, pero **la migración propuesta no se ejecuta al iniciar Streamlit**. Hasta aplicarla, el espacio muestra un mensaje de configuración pendiente y conserva el expediente existente.

## Accesos

| Cuenta | Sesiones y fotos | Asistencia | Descargas | Escritura |
|---|---|---|---|---|
| Entrenador | Sus categorías asignadas | Categoría | PDF, fotos, CSV y ZIP | Sus sesiones y asistencia |
| Autoridad | Sesiones publicadas de Colegio Surcos | Categorías Surcos | PDF, fotos, CSV y ZIP | Ninguna |
| Representante | Sesiones publicadas de la categoría de su representado | Solo su representado | Sin botones de descarga en este espacio | Ninguna |
| Administrador | Todas, incluidos borradores | Todas | PDF, fotos, CSV y ZIP | Gestión de espacios, asignaciones y sesiones |

La vista previa sigue usando la cuenta administradora y bloquea el guardado; no suplanta a otra persona. La protección real se comprueba con cuentas de cada rol y las RLS. Un usuario que puede ver una imagen o un documento siempre puede capturarlo o guardarlo por medios externos; ocultar la descarga no es protección anticopia.

## Propuesta de cambio a revisar y autorizar

[migrations/001_espacios_entrenamiento.sql](../migrations/001_espacios_entrenamiento.sql) crea:

- `ent_grupos`: institución y categoría, con clave foránea a `categorias`.
- `ent_asignaciones`: entrenadores autorizados por grupo.
- `ent_sesiones`: fecha, objetivos, actividades, autor, borrador o publicación.
- `ent_archivos`: metadatos de PDF y fotos, con confirmación de carga.
- `ent_asistencias`: estado por sesión y deportista.
- Un bucket **privado** `entrenamientos-privados` y las políticas propias del módulo.
- Dos operaciones RPC: confirmar un archivo ya almacenado y guardar toda la asistencia en una transacción.

No cambia filas, columnas ni políticas de `jugadores`, `categorias`, `perfiles` o sus vínculos existentes. Añade límites de acceso al nuevo bucket en `storage.objects`, preservando el comportamiento de otros buckets. Es una migración transaccional para aplicar una sola vez; si los nombres ya existen, se detiene para revisión en vez de reemplazarlos. Adapta las claves de categoría y jugador a los tipos existentes.

**Antes de autorizarla:** usar [la consulta de revisión de solo lectura](../migrations/000_revision_entrenamientos.sql) e inspeccionar el esquema real, las políticas y los vínculos de representantes; las lecturas de familias se apoyan en las RLS ya existentes de `jugadores`. Si estas devuelven deportistas ajenos, este módulo no puede inferir el vínculo correcto. Verificar además que el perfil `autoridad` de esta plataforma corresponde a Colegio Surcos.

## Puesta en marcha después de la autorización

1. Aplicar la migración en el proyecto correcto con una conexión administrativa autorizada; nunca utilizar una clave administrativa en el navegador ni desactivar RLS.
2. Instalar las dependencias del repositorio. `pypdfium2` permite observar páginas del PDF sin mostrar un botón de descarga al representante.
3. Como administrador, abrir **Entrenamientos → Administrar categorías de entrenamiento y entrenadores**. Crear un espacio por institución/categoría y asignar cada entrenador. No se crean asignaciones implícitas.
4. Como entrenador asignado, publicar una sesión con objetivos y actividades. Puede añadir un PDF de 1–20 páginas y hasta ocho fotos; cada archivo admite 10 MB, con un máximo combinado de 64 MB al publicar. Las fotos conservan proporción y orientación y se almacenan sin metadatos EXIF.
5. Registrar asistencia: **Sin registrar**, **Presente**, **Ausente** o **Justificado**. Nunca se supone presencia por defecto. La RPC rechaza a deportistas de otra institución/categoría y no deja un lote guardado parcialmente.
6. Probar con cuentas reales: entrenador asignado y no asignado, autoridad, representante con vínculo y sin vínculo y administrador. Confirmar que un representante no ve la asistencia de un compañero, ni sesiones de otras categorías, ni borradores.

Los documentos se descargan bajo la sesión autenticada; no se generan enlaces públicos ni se conserva una caché global. Los borradores y cargas pendientes permiten recuperarse de errores sin publicar material incompleto. No se puede sobrescribir ni borrar material confirmado desde esta interfaz.

## Pruebas locales reproducibles

La batería Python usa clientes en memoria:

```sh
python -B -m unittest discover -s tests -v
```

Las pruebas SQL usan un contenedor PostgreSQL local con datos ficticios y un nombre exclusivo. No aceptan una URL ni credenciales de una base remota:

```sh
docker run -d --name juventud-entrenamientos-test -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
python -B tests/probar_permisos_sql.py
docker rm -f juventud-entrenamientos-test
```

Verifican el aislamiento de grupos, borradores y archivos; la asistencia individual de representantes; el bloqueo de escrituras; la atomicidad del lote; y los límites del bucket incluso si existe una política anterior amplia. No sustituyen la validación del esquema y los vínculos reales antes de aplicar la migración.
