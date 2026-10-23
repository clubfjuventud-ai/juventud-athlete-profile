# Logos institucionales

- `logo_juventud.png`: escudo negro con dorado, 3283 × 3840 píxeles, con transparencia.
- `logo_surcos.png`: logo de Colegio Surcos, 3840 × 2307 píxeles.

Versiones ampliadas desde los PNG originales con remuestreo Lanczos y un enfoque suave, conservando proporciones, composición y colores. La ampliación aumenta la resolución del archivo; no convierte los originales en ilustraciones vectoriales ni recupera detalle nativo inexistente.

Cada logo se muestra únicamente en la sección y ficha de su institución y en sus PDF. El acceso, Inicio, menú lateral y administración no muestran logos. Si falta la imagen en una sección institucional, se muestra su nombre sin provocar errores.

La web envía una imagen de hasta tres píxeles por píxel CSS mediante URI de datos, evitando la reducción de resolución de Streamlit. La interfaz fija únicamente el ancho. Los PDF ajustan cada imagen dentro de una caja conservando su proporción original.

Validación: `python -B -m unittest discover -s tests -v`.

Los PDF usan la paleta de cada institución: negro y dorado para Juventud; azul y verde para Surcos. Encabezados, tablas, línea de pie, autor y lema corresponden a la institución del deportista.
