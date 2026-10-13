# Recursos institucionales de la web

Esta carpeta pertenece a la aplicación y se incluye en el contexto Docker y los respaldos.

- `plantillas/`: plantilla usada para generar hojas de vida.
- `fotos/`: catálogo de imágenes por marca y modelo.
- `base_datos/`, `mantenimientos/`, `inventarios/`: fuentes históricas para importación y formato del reporte institucional.
- `manifest.json`: inventario de las 86 copias verificadas con SHA-256.

La base activa es PostgreSQL. Estos Excel se conservan como fuentes; no se sobrescriben al generar documentos ni se reimportan automáticamente al iniciar.
Las fotografías subidas por usuarios y documentos generados se almacenan en `private_media`, separado de estas fuentes.
