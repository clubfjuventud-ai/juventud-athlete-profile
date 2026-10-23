# Logos institucionales

Los archivos originales deben guardarse como:

- `logo_juventud.png`: escudo de Club Juventud negro con dorado, sin el escudo blanco de la imagen comparativa.
- `logo_surcos.png`: logo original de Colegio Surcos.

La interfaz fija únicamente el ancho. Los PDF ajustan cada imagen dentro de una caja conservando su proporción original. Si falta una imagen o no se puede leer, se mantiene el nombre de la institución.

Los PNG originales están incluidos. Las pruebas verifican tanto estos archivos como imágenes temporales para cubrir proporciones distintas y archivos ausentes o inválidos.

Validación: `python -B -m unittest discover -s tests -v`.
