# LabManager UD · Aplicación web

La aplicación web conserva el escritorio y los Excel originales. El servidor mantiene los datos centrales; los compañeros acceden desde un navegador, cada uno con su cuenta.

## Funcionalidad

| Escritorio / necesidad | Web |
| --- | --- |
| Inicio e indicadores | Equipos, activos, dañados, obsoletos, laboratorios y pendientes |
| Inventario | Búsqueda por placa, interno, serial, descripción, marca y modelo; filtros; creación y edición; exportación |
| Fotografías | Fotografías existentes por marca/modelo y carga de foto individual por equipo |
| Hojas de vida | Consulta, edición de adquisición/especificaciones, Excel institucional, PDF, impresión |
| Exportaciones por laboratorio | ZIP de hojas de vida del filtro completo, generado en segundo plano |
| Solicitudes | Datos de solicitante, equipo, asignatura, banco, descripción; asignación y cancelación |
| Tipos de mantenimiento | MIC, MEC, MIP, MEP, MIPV, MEPV; compatibilidad Correctivo/Preventivo |
| Atención | Registro de diagnóstico, intervención, repuestos, empresa, garantía; cierre transaccional |
| Preventivos | Registro independiente de solicitud |
| Historial y estadísticas | Filtros de tipo, laboratorio y fechas; lectura de registros históricos sin vínculo |
| Reportes Excel | Inventario, mantenimientos y reporte institucional A:AA con hojas complementarias |
| Usuarios | Creación, roles, activación, edición y restablecimiento de contraseña |
| Mi perfil | Cambio de usuario, datos personales y contraseña |
| Importación | Simulación/aplicación de fuentes existentes o inventario adjunto |
| Conciliación | Filas originales, incidencias y vinculación manual justificada |
| Trazabilidad | Auditoría de operaciones web y registro original de importación |

## Datos migrados en esta instalación

- **860 equipos**, en seis espacios incluidos los archivos de 706.
- **150 solicitudes**, con estados originales normalizados (Finalizada → Cerrada).
- **111 intervenciones**; se conserva la ausencia de fecha cuando no estaba registrada.
- **1.308 filas originales** archivadas en RegistroLegacy, incluidas plantillas/pies.
- **125 registros pendientes de revisión**: 119 reportes sin equipo identificado, uno además sin fecha de intervención y cinco fichas complementarias sin vínculo seguro.

Las solicitudes e intervenciones sin vínculo se muestran en sus listados. No se asignan por aproximación ni se inventan equipos. En **Revisión de históricos**, consulte el original, seleccione el equipo confirmado y explique la vinculación. Para equipos que no figuren en los inventarios adjuntos, cree primero el equipo con datos verificados. Las filas de plantilla/pie se pueden consultar cambiando el filtro de estado.

El usuario técnico `archivo_historico` permanece inactivo; sirve para registrar procedencia y no concede acceso. Nombres, documentos, contactos y técnicos históricos están conservados en campos propios y datos_legacy. No se transformaron nombres históricos en cuentas de acceso.

## Ejecución local

La instalaci?n qued? ejecut?ndose en http://127.0.0.1:8000/ con Waitress en segundo plano. Para detener esa instancia y arrancar otra en terminal, ejecute `powershell -ExecutionPolicy Bypass -File .\detener_web.ps1` antes de los comandos siguientes.

Desde PowerShell:

```powershell
cd "C:\Users\Laboratorios\Downloads\LabManager_UD (2)\LabManager_UD\Proyecto_Web"
.\.venv\Scripts\python manage.py runserver
```

Abra **http://127.0.0.1:8000/** y use la cuenta `laboratorios` con la contraseña que estableció. La migración conserva usuarios y contraseñas; no hay contraseña compartida incorporada en código. Si el servidor estaba abierto durante la actualización, deténgalo con Ctrl+C y vuelva a ejecutarlo.

Después de reiniciar Windows, `manage.py` inicia automáticamente la instancia PostgreSQL portable de este proyecto, cuando `.env` apunta a su puerto 55432. No modifica servicios PostgreSQL ajenos. También puede ejecutar:

```powershell
.\iniciar.ps1
```

Ese script instala dependencias faltantes, aplica migraciones, configura roles y arranca el servidor local. Mantenga la terminal abierta. El servidor de desarrollo se utiliza para pruebas.

Para compartir la aplicacion en la red local, ejecute `Iniciar_LabManager.cmd`. Si `.venv` no existe, el lanzador lo crea e instala `requirements.txt` (requiere Python para Windows). Si no existe `.env`, copia `.env.example` y se detiene para que configure la clave Django y la conexion PostgreSQL antes de volver a iniciarlo. La red local requiere PostgreSQL; mantenga la ventana abierta y use la URL de red que muestra el lanzador.

Para recuperar acceso:

```powershell
.\.venv\Scripts\python manage.py changepassword laboratorios
```

## Entorno y estructura

`.env` contiene la clave de Django y las credenciales generadas de PostgreSQL; no se publica. `.env.example` documenta las variables. La base portable se aloja en `.runtime/pgdata`, escucha únicamente en `127.0.0.1:55432` y se usa como base central a través del backend. SQLite queda conservado como respaldo del estado anterior.

```text
Proyecto_Web/
├── manage.py
├── iniciar.ps1 / iniciar_red.ps1
├── requirements.txt / requirements-dev.txt
├── config/                  # Django, WSGI y arranque de base portable
├── lab/
│   ├── models.py            # Modelo central
│   ├── forms.py / views.py / urls.py
│   ├── importing.py         # Migración conservando filas originales
│   ├── documents.py         # PDF portable y conversión opcional
│   ├── legacy_excel.py      # Plantilla institucional adaptada
│   ├── jobs.py              # Exportación documental en segundo plano
│   ├── migrations/
│   └── management/commands/
├── templates/               # Pantallas web
├── static/                  # CSS y JS locales, sin CDN
├── deployment/              # Docker, proxy y configuración local
├── private_media/           # Fotos nuevas y documentos por usuario
├── backups/                 # Respaldos y traslado de base
├── validacion/              # Capturas y documentos de prueba
└── .runtime/                # PostgreSQL portable, datos y configuración privada
```

Modelo: Laboratorio → Equipo → Solicitud/Mantenimiento. Solicitud permite una o varias intervenciones históricas; el flujo operativo registra una atención y cierra la solicitud. Equipo incluye datos complementarios de hoja de vida y fotografía. RegistroLegacy conserva fuente, fila, hash y estado de conciliación. TrabajoDocumento mantiene propietario, formato, progreso, archivo y errores. Auditoria registra usuario, operación y cambios.

## Acceso desde otros equipos de la red

Con PostgreSQL configurado, detenga primero la instancia local si est? abierta y luego inicie la red:

```powershell
powershell -ExecutionPolicy Bypass -File .\detener_web.ps1
powershell -ExecutionPolicy Bypass -File .\iniciar_red.ps1
```

También puede abrir `Iniciar_LabManager.cmd` con doble clic. El inicio detecta la IP del computador actual en cada ejecución y muestra **URL local** y **URL de red local**, sin guardar una IP fija. Comparta la URL de red que aparezca en esa terminal. Si cambia de computador, prepare antes su entorno Python, configuración y base PostgreSQL siguiendo este documento; no copie la carpeta `.venv` entre equipos. La detección de IP no abre el firewall ni configura el acceso entre redes.

Puede indicar la IP explícitamente si hay varias interfaces de red:

```powershell
.\iniciar_red.ps1 -IpServidor 192.168.1.50 -Puerto 8000
```

Los compañeros abren `http://192.168.1.50:8000/`. Se utiliza Waitress y los archivos estáticos se sirven con WhiteNoise. Reserve la IP en la red y habilite el puerto únicamente para la red del laboratorio. El script no altera el firewall. Esta modalidad es un perfil HTTP para la LAN; para acceso institucional permanente o internet utilice HTTPS.

Una URL interna requiere un registro DNS institucional que apunte al servidor. Configurar el nombre y certificado requiere conocer el dominio y la infraestructura de la institución; no se ha publicado un dominio desde esta instalación.

## Roles

### Mantenimiento por salón

En **Mantenimientos → Mantenimiento por salón**, el técnico selecciona un salón/laboratorio, carga sus equipos y marca los intervenidos. Ingresa la fecha, las horas de inicio y fin (del mismo día) y el trabajo común. La pantalla muestra el reparto y el servidor lo recalcula al guardar, creando una intervención por equipo en una transacción.

Ejemplo: 08:00–10:00 y cuatro equipos generan cuatro reportes de 30 minutos. Se conserva la duración total y el número de equipos para calcular fracciones sin redondear al almacenarlas; la pantalla muestra dos decimales. Los tiempos aparecen en cada intervención y en las exportaciones. Los registros anteriores permanecen sin duración conocida. El permiso requerido es `lab.add_mantenimiento`.

Los salones corresponden al campo laboratorio del inventario actual. Cada lote usa los mismos datos de trabajo para sus equipos; las solicitudes existentes no se finalizan automáticamente mediante este flujo. Tras actualizar otra instalación, ejecute `python manage.py migrate` y `python manage.py collectstatic --noinput`, y reinicie el servidor.

| Rol | Acceso |
| --- | --- |
| Consulta | Inventario, hojas de vida e historial, sin edición |
| Solicitante | Crear y consultar sus solicitudes; cancelar las propias abiertas |
| Tecnico | Inventario, historial y atención de solicitudes asignadas; preventivos |
| Coordinador | Inventario, laboratorios, solicitudes, asignación, mantenimientos, conciliación y auditoría |
| Administrador | Gestión general y de cuentas |

El administrador principal conserva el atributo superusuario. Las operaciones se autorizan en el servidor; ocultar botones no sustituye permisos. Un administrador de grupo no recibe automáticamente `is_staff` ni `is_superuser`; la gestión normal se realiza en las pantallas web. `/admin/` se reserva para administración avanzada y requiere `is_staff`.

Las ediciones de equipos, fichas, solicitudes y mantenimientos comprueban versiones. La finalización bloquea la solicitud en PostgreSQL dentro de una transacción para evitar cierres dobles. Cambios de cuenta y contraseña se realizan sin imprimir contraseñas.

## Excel y PDF

Excel utiliza `resources/plantillas/HojaVida.xlsx` y las fotografías de `resources/fotos`, ambas dentro de esta aplicación. Cada trabajo usa un directorio temporal independiente; no escribe en los temporales del escritorio. Los ZIP se conservan en private_media y solo los descarga su propietario con acceso vigente al inventario.

**PDF_BACKEND=native**, predeterminado, genera un PDF paginado con ReportLab sin Office ni LibreOffice. Contiene la información del equipo y todo el historial. Su diagramación es propia: no es una reproducción idéntica de la hoja Excel. Para reproducir la maquetación de Excel mediante conversión, instale LibreOffice y configure:

```dotenv
PDF_BACKEND=libreoffice
PDF_EXECUTABLE=C:/Program Files/LibreOffice/program/soffice.exe
```

La ruta LibreOffice tiene perfiles aislados y límite de 90 segundos por conversión. No se certificó esa variante en este equipo porque LibreOffice no está instalado. La variante PDF nativa y los Excel sí están probados. `Abrir PDF` permite imprimir desde el visor; `Imprimir ficha` utiliza el navegador.

## Importación y trazabilidad

La importación ya fue aplicada a los datos locales. No necesita repetirla para que aparezcan los equipos. Puede usar la pantalla de importación o:

```powershell
.\.venv\Scripts\python manage.py importar_legacy --user archivo_historico --report simulacion.json
.\.venv\Scripts\python manage.py importar_legacy --user archivo_historico --apply --report importacion.json
```

La primera orden simula y revierte todas las escrituras. La segunda aplica. Repetir los mismos archivos no duplica equipos, solicitudes ni intervenciones. No es sincronización continua con Excel: no reordene las filas de origen para luego reimportar. Si una fila cambia, se marca para revisión sin sobrescribir datos web. Las vinculaciones manuales revisadas se conservan.

## Respaldos

```powershell
.\.venv\Scripts\python manage.py respaldar
```

Se guarda la base y se copian `private_media` (fotos y documentos cargados) y toda la carpeta `resources` (plantillas, fotografías de catálogo y fuentes Excel). En PostgreSQL requiere `pg_dump`; para la instancia portable se usa el ejecutable incluido en `.runtime/pgsql/bin`. Los respaldos contienen datos de usuarios y deben permanecer privados. Se conservó el respaldo previo de SQLite y un fixture del traslado.

La recuperación requiere restaurar la base (`pg_restore` para el dump PostgreSQL), los archivos en `private_media` y el contenido de `resources` en sus carpetas homónimas dentro de esta aplicación. Pruebe una restauración en una base separada antes de establecer el procedimiento institucional.

## Servidor permanente / internet

Se incluyen Dockerfile, PostgreSQL, Waitress y Caddy en `deployment/compose.production.yaml`. Configure `deployment/.env` a partir de su ejemplo y cambie el dominio:

```powershell
docker compose --env-file deployment/.env -f deployment/compose.production.yaml up -d --build
docker compose --env-file deployment/.env -f deployment/compose.production.yaml exec web python manage.py createsuperuser
docker compose --env-file deployment/.env -f deployment/compose.production.yaml exec web python manage.py importar_legacy --user SU_USUARIO --apply
```

Para trasladar exactamente la base local con usuarios y cambios web, use un fixture, en lugar de reimportar solo Excel:

```powershell
.\.venv\Scripts\python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions --output backups/traslado.json
docker compose --env-file deployment/.env -f deployment/compose.production.yaml cp backups/traslado.json web:/tmp/traslado.json
docker compose --env-file deployment/.env -f deployment/compose.production.yaml exec web python manage.py loaddata /tmp/traslado.json
```

Copie también private_media al volumen correspondiente. Los recursos históricos van incluidos en la imagen desde la carpeta propia `resources`; el contexto Docker es únicamente esta aplicación. Haga el traslado con las escrituras detenidas. El despliegue utiliza otra base: no reutiliza automáticamente la instancia portable. No publique `.env`, `.runtime`, respaldos ni el puerto PostgreSQL. Un dominio público requiere DNS y conectividad a 80/443; para un dominio solo interno use certificado institucional o `tls internal` en Caddy y distribuya su CA a los equipos.

La configuración Docker se entrega para despliegue; Docker no está instalado en este equipo y no se ha ejecutado aquí. En Windows también puede ejecutar Waitress detrás del Caddyfile incluido, configurando DEBUG=false, hosts, orígenes HTTPS y un servicio con arranque automático.

## Validación

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python manage.py collectstatic --noinput
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test lab
```

Se ejecutaron **26 pruebas sobre PostgreSQL**, todas satisfactorias. Las pruebas cubren pantallas, roles, privacidad, CSRF, asignación/cancelación/cierre, edición obsoleta, importación con encabezados reales, registros sin vínculo, conciliación, fotografías, PDF paginado, Excel con más de siete intervenciones, exportación institucional y ZIP privado. Las pruebas de concurrencia utilizan conexiones PostgreSQL independientes.

Capturas de navegador y ejemplos de documento se encuentran en validacion/. Se probó una exportación real de tres equipos. El escritorio permanece disponible y los archivos originales no se modificaron. Después de establecer la web como sistema oficial, evite escribir en ambos sistemas en paralelo.

Binarios PostgreSQL: distribución oficial enlazada por [PostgreSQL para Windows](https://www.postgresql.org/download/windows/) y [EDB](https://www.enterprisedb.com/download-postgresql-binaries).


## Transferencias de inventario entre t?cnicos

1. Un coordinador asigna responsables desde **Administraci?n ? Laboratorios ? Asignar responsable**. No se asignan responsables autom?ticamente a los laboratorios existentes. Cada laboratorio tiene un responsable y un t?cnico puede estar a cargo de varios.
2. El grupo **Tecnico** permite consultar el inventario y gestionar equipos propios. La edici?n, las fotograf?as y la hoja de vida se restringen al responsable; el superusuario conserva acceso administrativo. Los laboratorios sin responsable quedan disponibles para consulta y deben configurarse antes de pedir traslados.
3. El t?cnico abre la ficha de un equipo de otro laboratorio, pulsa **Pedir traslado**, elige uno de sus laboratorios e ingresa una justificaci?n.
4. El equipo queda **En proceso de traslado**, conserva su origen y bloquea la edici?n y otras solicitudes pendientes. El responsable del origen recibe una alerta visual en el panel; se consulta cada 30 segundos mientras la pesta?a est? visible.
5. En **Traslados de inventario**, el responsable del origen aprueba o rechaza desde una minificha con origen, destino, solicitante, serial y justificaci?n. Puede agregar un comentario de respuesta.
6. Aprobar cambia la ubicaci?n al destino; rechazar mantiene el origen. Ambas decisiones restauran el estado operativo anterior, guardan fecha y auditor?a y se reflejan en el panel del solicitante.

La ubicaci?n del equipo no se cambia desde su formulario de edici?n. El flujo usa transacciones, bloqueo de filas y una restricci?n de un ?nico traslado pendiente por equipo. Las decisiones requieren POST con CSRF y solo puede responder el responsable del origen. Antes de cambiar un responsable se deben resolver los traslados pendientes.

Al actualizar otra instalaci?n, ejecutar `python manage.py migrate`, actualizar el grupo Tecnico con los permisos `add_equipo` y `change_equipo` (o usar `python manage.py crear_roles` para restaurar los grupos est?ndar), ejecutar `python manage.py collectstatic --noinput` y reiniciar el servidor.


## Recursos propios y portabilidad

El inventario de dependencias, recursos copiados y validaciones está en [INDEPENDENCIA.md](INDEPENDENCIA.md).

La aplicación es autocontenida: `RESOURCES_ROOT = BASE_DIR / 'resources'`.
No requiere carpetas hermanas para ejecutar, importar o exportar.

| Carpeta o archivo | Uso |
| --- | --- |
| `resources/plantillas/HojaVida.xlsx` | Plantilla institucional para hojas de vida Excel |
| `resources/fotos/` | Fotografías de catálogo por marca y modelo |
| `resources/base_datos/BASE_DATOS.xlsx` | Fuente histórica de hojas de vida |
| `resources/mantenimientos/REPORTE_MANTENIMIENTOS.xlsx` | Fuente histórica y hojas complementarias del reporte institucional |
| `resources/inventarios/*.xlsx` | Inventarios históricos para la importación predeterminada |
| `resources/manifest.json` | Tamaño y SHA-256 de cada recurso copiado |

Los Excel originales copiados se conservan como fuentes, no como base activa.
La base PostgreSQL y `private_media` siguen siendo los datos activos: no se reimportan ni modifican por esta separación.
La importación mantiene nombres de archivos, hojas y números de fila, conservando las claves de origen y la idempotencia.

Para construir desde esta carpeta: `docker build -f deployment/Dockerfile .`.
`deployment/compose.production.yaml` ya usa este mismo contexto y no copia archivos externos.
Docker no debe recibir `.env`, `.runtime`, respaldos ni medios privados en el contexto; se excluyen en `.dockerignore`.
El respaldo de esta aplicación incluye base, `private_media` y `resources`.
#   I N V E N T A R I O S - U D  
 