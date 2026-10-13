# Separación de la aplicación web

## Retiro posterior autorizado

El usuario autorizó después la eliminación de la carpeta de escritorio. Se verificaron otra vez los 86 recursos y se creó `backups/escritorio_retirado_20261013_114328.zip`, con 362 archivos originales comprobados mediante SHA-256, incluidos los temporales. Se excluyeron únicamente el entorno virtual, las cachés Python y los archivos `.pyc`. Después se eliminó únicamente la carpeta del escritorio; la web, sus datos y el archivo de respaldo se conservaron. Las secciones siguientes documentan la auditoría anterior al retiro.

Validación realizada el 13 de octubre de 2026. No se eliminó ni modificó ningún archivo de `Proyecto_Python` ni de los inventarios originales.

## Referencias localizadas antes del cambio

- `config/settings.py`: raíz de recursos situada en la carpeta del escritorio.
- `lab/legacy_excel.py`: plantilla de hoja de vida externa.
- `lab/legacy_photo.py`: fotografías externas por marca/modelo.
- `lab/importing.py`: inventarios de una carpeta hermana y Excel de hojas de vida y mantenimientos del escritorio.
- `lab/views.py`: reporte institucional y sus hojas complementarias.
- `lab/management/commands/respaldar.py`: respaldo de plantillas y fotos externas; faltaban las fuentes Excel.
- `lab/tests.py`: dos conjuntos de datos de prueba reproducían esa estructura de carpetas.
- `deployment/Dockerfile`: cuatro COPY desde el escritorio y uno desde Inventarios.
- `deployment/compose.production.yaml`: contexto de construcción situado fuera de la web.
- `.dockerignore` del contenedor padre: dos referencias específicas al escritorio.
- `README.md`: instrucciones de Excel apuntaban a la plantilla externa.
- El comentario de `Proyecto_Python/core/config.py` describe su propia carpeta y permanece intacto.

Se revisaron también los scripts de inicio, configuración PostgreSQL, generación PDF, procesamiento ZIP, configuración de entorno y recursos estáticos. Sus rutas no dependían del escritorio. `sys.path` del instalador PostgreSQL apunta a la propia web y no se cambió.

## Recursos copiados y verificados

Todos están en `Proyecto_Web/resources`. Los 86 archivos suman 3.654.459 bytes. El manifiesto `resources/manifest.json` registra ruta, origen relativo, tamaño y SHA-256 por archivo.

| Recurso | Cantidad | Destino |
| --- | ---: | --- |
| Plantilla institucional HojaVida.xlsx | 1 | `plantillas/` |
| Fotografías de equipos válidas para el catálogo | 77 | `fotos/` |
| Fuente histórica de hojas de vida BASE_DATOS.xlsx | 1 | `base_datos/` |
| Reporte histórico e institucional REPORTE_MANTENIMIENTOS.xlsx | 1 | `mantenimientos/` |
| Inventarios 603, 604, 606, 607, 609 y 706 | 6 | `inventarios/` |

Se verificó la igualdad SHA-256 de cada copia y se comprobaron 321 archivos de recursos/inventarios originales sin cambios durante la copia. Los nueve libros Excel copiados no contienen vínculos externos de Excel.

No se migraron los 220 archivos temporales generados por el escritorio, la plantilla alternativa sin uso `...xlsx`, el archivo de foto llamado `.jpg` (sin identificador y nunca seleccionado por el servicio), los módulos de escritorio, su entorno virtual, su caché, QSS ni sus iconos/logotipos. La web ya dispone de sus propios recursos estáticos y entornos. Todos los archivos omitidos siguen en su lugar original.

## Comportamiento conservado

- `RESOURCES_ROOT` apunta exclusivamente a `BASE_DIR / 'resources'`.
- Las hojas Excel se generan en directorios temporales; no se sobrescribe la plantilla ni las fuentes copiadas.
- Las fotos subidas y documentos siguen en `private_media`, que no se movió.
- No se ejecutaron migraciones ni importaciones sobre la base activa como parte de esta separación.
- La importación conserva nombres, hojas, filas y claves de origen. Repetirla no duplica los datos.
- Los respaldos contienen base, `private_media` y toda la carpeta `resources`, incluidas las fuentes Excel.
- Se cerraron explícitamente las conexiones del respaldo SQLite para liberar los archivos en Windows.
- Docker se construye desde la propia carpeta web, con `.dockerignore` local; no requiere carpetas hermanas.

## Validación sin carpetas de origen

Se copió solamente la aplicación web a `.validation/autonomia-8f2e62cf`, sin `.env`, base activa, archivos privados, entorno virtual ni carpetas hermanas. Se usó el intérprete del entorno de la propia web y una base SQLite de pruebas independiente.

- `django check`: sin errores.
- `makemigrations --check --dry-run`: sin cambios de modelos pendientes.
- `django test lab`: **65 pruebas: 63 aprobadas, 2 omitidas** porque son pruebas de concurrencia que requieren PostgreSQL.
- `collectstatic`: 139 archivos estáticos recopilados correctamente.
- Pruebas nuevas: integridad de las copias, foto de catálogo, Excel con foto, PDF, importación de las ocho fuentes e idempotencia, respaldo y recuperación de SQLite junto con medios/recursos.
- Excel institucional, exportaciones, fotografías subidas y ZIP privados también quedan cubiertos por la suite existente.

Los resultados y registros están en `.validation/independencia-resultados.json` y en la copia de validación. La advertencia de openpyxl sobre extensiones de validación del libro histórico ya corresponde al comportamiento de lectura existente; no altera los originales. La variante PDF nativa sí se ejecutó; la conversión con LibreOffice no se ejecutó porque no está instalado.

Docker no está instalado en este equipo: se revisaron el Dockerfile, el contexto y las exclusiones, pero no se construyó ni arrancó la imagen.

## Referencias restantes y eliminación futura

La auditoría final examinó 158 archivos de texto (sin entornos virtuales, cachés, PostgreSQL ni la copia de validación). En la aplicación web, las únicas referencias textuales a `Proyecto_Python` son las de este informe: documentan la procedencia y la auditoría, y no se usan al ejecutar. `LEGACY_ROOT` fue eliminado de código, pruebas y configuración. En el repositorio permanece el comentario original del escritorio indicado arriba.

La búsqueda dentro de los Excel encontró además dos metadatos `absPath` en `xl/workbook.xml`: uno en `plantillas/HojaVida.xlsx` y otro en `base_datos/BASE_DATOS.xlsx`. Identifican la antigua ubicación donde Excel guardó el archivo. No son vínculos externos de libro ni rutas usadas por la web; no se abren ni se necesitan. Se conservaron para mantener las copias byte a byte idénticas al origen. Ninguno de los nueve libros contiene `xl/externalLinks`. El resultado completo está en `.validation/reference-audit.json`.

**La web ya no necesita la carpeta del escritorio para funcionar.** Es seguro retirarla desde el punto de vista de la web, después de reiniciar cualquier instancia que estuviera abierta con la configuración anterior. No se eliminó esa carpeta durante este trabajo.

Si se quieren conservar también los documentos temporales, archivos alternativos y el programa de escritorio, debe archivarse esa carpeta antes de borrarla: esos archivos no son necesarios para la web y no forman parte de los 86 recursos migrados. La base activa, `private_media` y `resources` deben conservarse junto con la web.
