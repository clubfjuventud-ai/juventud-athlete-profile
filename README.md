# Club Juventud Athlete Profile — estructura modular (etapa 1)

Esta versión separa funciones existentes de `app.py` en módulos, procurando conservar el comportamiento actual. **No incluye migraciones SQL ni cambios a Supabase.**

## Estructura

- `app.py`: interfaz principal y flujos actuales.
- `modules/configuracion.py`: rutas de logos y nombres de instituciones.
- `modules/autenticacion.py`: conexión Supabase y cierre de sesión.
- `modules/utilidades.py`: consultas y funciones auxiliares de la interfaz.
- `modules/informes_pdf.py`: generación del expediente PDF.
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
