# Club Juventud Athlete Profile — estructura modular (etapa 1)

Esta versión separa funciones existentes de `app.py` en módulos, procurando conservar el comportamiento actual. **No incluye migraciones SQL ni cambios a Supabase.**

## Estructura

- `app.py`: interfaz principal y flujos actuales.
- `modules/configuracion.py`: rutas de logos y nombres de instituciones.
- `modules/autenticacion.py`: conexión Supabase y cierre de sesión.
- `modules/utilidades.py`: consultas y funciones auxiliares de la interfaz.
- `modules/informes_pdf.py`: generación del expediente PDF.
- `modules/interfaz.py`: estilos, cabecera compacta, resumen de fechas y PDF bajo demanda.
- `modules/evaluaciones_visuales.py`: panel de atributos, comparación por fecha y cuadros vectoriales de evaluación.
- `assets/`: coloca aquí los logos originales `logo_juventud.png` y `logo_surcos.png`.

## Configuración local

1. Instala dependencias: `pip install -r requirements.txt`
2. Crea `.streamlit/secrets.toml` con las mismas claves que usa tu despliegue:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
3. Ejecuta `streamlit run app.py`.

No publiques `secrets.toml`, claves privadas ni contraseñas en GitHub.

## Antes de desplegar

Prueba esta versión en una rama separada o en una copia del repositorio. Esta etapa es una reorganización del código; todavía no implementa la gestión de usuarios, los permisos nuevos, las pruebas EIR/cualidades volitivas ni la carga de entrenamientos. Esas funciones requieren una siguiente etapa y revisión del esquema/políticas RLS de Supabase.

## Evaluaciones visuales

- Pases y tiros al arco: aciertos enteros de 0 a 5. Un campo vacío es una prueba no realizada; cero significa que no hubo aciertos.
- Conducción, Illinois y velocidades de 10 y 20 m: tiempos positivos en segundos.
- Course Navette de 20 m: último nivel completo alcanzado, entero de 1 a 21. Velocidad del nivel = 8 + 0,5 × nivel (km/h).
- La evaluación actitudinal se retiró de formularios, panel, gráficos y PDF. No se borran ni modifican columnas de la base de datos.

El radar conserva el estilo de perfil del deportista: en pases y tiros, 5 aciertos equivalen al 100%; para tiempos y Navette, el 100% corresponde al mejor registro del historial del propio deportista. Los resultados reales y sus unidades permanecen en las tarjetas. Ambos perfiles comparados usan las mismas referencias. No representa un baremo por edad ni una calificación global.

### VO₂máx estimado

Se deriva al consultar o exportar y no se escribe una columna nueva. Se utiliza la ecuación de [Léger et al. (1988)](https://pubmed.ncbi.nlm.nih.gov/3184250/):

`VO2max = 31.025 + 3.238 × v − 3.248 × A + 0.1536 × A × v`, en ml/kg/min.

Se calcula la edad cumplida en la fecha de la evaluación, no la edad actual. Para adultos se fija A=18, siguiendo el artículo. Solo se aplica entre 8 y 50 años, con fecha de nacimiento y nivel válidos y bajo el protocolo de 20 m indicado; en otros casos se muestra sin estimación. No es una medición directa.

## Análisis de rendimiento inteligente

En **Expediente individual → Evolución**, el botón genera un informe local con los registros visibles para la cuenta. Lo pueden consultar padres, entrenadores, administración y autoridades con acceso al deportista. No llama a una API de IA, no es IA generativa, no realiza búsquedas externas y no tiene costes de consulta. No requiere claves adicionales ni modifica Supabase o RLS.

Compara la primera y última fecha válidas, explica cada prueba y señala el último intervalo cuando hay más registros. Distingue cero aciertos de datos ausentes, identifica resultados contradictorios de una misma fecha y no presenta una prueba antigua como si estuviera actualizada. Las comparaciones incompletas quedan fuera del resumen global. La explicación del VO₂máx distingue el efecto de la edad del cambio del nivel de Navette.

El informe incluye preguntas frecuentes sobre unidades, evolución, registros faltantes y contexto deportivo. Los datos académicos solo se incorporan cuando la vista actual los permite; los representantes conservan la restricción existente. No asigna causas, diagnósticos, baremos por edad ni una nota global sin evidencia.

El resultado puede descargarse como texto, se conserva en la sesión de la cuenta y se invalida si cambian los datos. No se comparte una caché de informes entre cuentas ni deportistas.


## Navegación y vista previa de roles

La institución abre en **Expediente individual → Evolución**. El directorio admite búsqueda por código, nombre o apellido. Los datos personales, trayectoria, académico, evidencias e informe PDF tienen espacios propios; los formularios aparecen según el rol. En móvil, el menú lateral empieza cerrado y las pestañas permiten desplazamiento horizontal.

Surcos usa su nombre, logo y acentos verdes y azules. Juventud conserva su identidad negra y dorada dentro de su sección. Las páginas generales no muestran logos.

Solo una cuenta administradora dispone de **menú lateral → Vista previa de roles → Ver la interfaz como**. Permite elegir Entrenador, Autoridad o Representante y regresar a **Mi cuenta**. La vista previa conserva la sesión real y sus datos visibles; no suplanta a otra persona, no reproduce sus filtros RLS ni sus vínculos. Las opciones de guardar están deshabilitadas y los manejadores de escritura rechazan la vista previa. Las consultas siguen usando el cliente autenticado existente. Representante oculta la pestaña y consultas académicas, manteniendo las restricciones de exportación existentes.

En **Informe PDF**, pulsa **Preparar expediente PDF** antes de descargarlo. El resultado solo se guarda en la sesión y deja de ofrecerse cuando cambian el deportista, los datos incluidos, las opciones, la cuenta o la vista de rol.
