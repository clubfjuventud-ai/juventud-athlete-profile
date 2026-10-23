# Club Juventud Athlete Profile — estructura modular (etapa 1)

Esta versión separa funciones existentes de `app.py` en módulos, procurando conservar el comportamiento actual. **No incluye migraciones SQL ni cambios a Supabase.**

## Estructura

- `app.py`: interfaz principal y flujos actuales.
- `modules/configuracion.py`: rutas de logos y nombres de instituciones.
- `modules/autenticacion.py`: conexión Supabase y cierre de sesión.
- `modules/utilidades.py`: consultas y funciones auxiliares de la interfaz.
- `modules/informes_pdf.py`: generación del expediente PDF.
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
