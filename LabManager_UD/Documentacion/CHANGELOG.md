# LabManager UD

## 2026-10-02 - Mantenimiento de varios equipos por salón

- Selección de salón/laboratorio y checklist de sus equipos, con búsqueda por nombre o identificador.
- Una fecha y franja horaria común; vista previa del total y duración por reporte.
- Reportes individuales vinculados por sesión, reparto calculado en servidor y guardado atómico con auditoría.
- Tiempo visible en intervención, hoja de vida, PDF y Excel; formato institucional A:AA conservado.
- Validación de permisos, pertenencia al salón, selección obligatoria y franja dentro del mismo día; 32 pruebas satisfactorias y comprobación en navegador.

## 2026-10-02 - Inicio automático en red

- Lanzador Iniciar_LabManager.cmd y detección de IP en cada inicio con prioridad por métrica de red.
- Muestra URL local y de red; configura hosts y orígenes CSRF para la IP detectada.
- Comprueba entorno, IP local y puerto libre; usa servir.py para registrar el proceso y permitir detenerlo con detener_web.ps1.

## 2026-10-02 - Identidad visual y navegación web

- Recuperados los logotipos e iconos originales del escritorio en el inicio web.
- Tarjetas principales para equipos, hojas de vida, solicitudes y mantenimientos; administración agrupada.
- Botones explícitos para abrir fichas, exportación por lotes desplegable y formularios en columnas con campos obligatorios señalados.
- Menú adaptable a celulares y estados diferenciados por color.
- Verificación en Edge para computador y celular, navegación a hojas de vida y formularios; 26 pruebas Django satisfactorias.

## v0.1.0 - Motor de lectura
Fecha: 24/07/2026

### Funcionalidades
- Creación de la estructura del proyecto.
- Detección automática de inventarios.
- Lectura de archivos Excel.
- Conversión de filas a objetos Equipo.
- Visualización de los primeros equipos leídos.

Estado: Finalizada.

## 2026-10-02 - Base web multiusuario

- Proyecto_Web: Django, esquema central, roles, inventario, solicitudes y mantenimientos.
- Importador Excel con simulacion, trazabilidad y reporte de incidencias.
- Renderizador Excel separado de COM; PDF mediante LibreOffice con temporales aislados.
- Configuracion PostgreSQL, ejemplo de proxy y guia de ejecucion en README.
- Escritorio conservado. Pendiente validar PostgreSQL, PDF y datos ambiguos antes de produccion.


## 2026-10-02 - Migracion web funcional y datos centrales

- PostgreSQL portable configurado en 127.0.0.1:55432; usuarios y contrasenas conservados.
- Cargados 860 equipos, 150 solicitudes y 111 intervenciones. Conservadas 1308 filas originales y 125 registros para conciliacion manual.
- Incorporadas pantallas de inventario, fotografias, hojas de vida, solicitudes, asignacion, cancelacion, preventivos, historial, estadisticas, usuarios, perfil y auditoria.
- PDF nativo sin Office, Excel institucional y exportaciones ZIP en segundo plano.
- Respaldo PostgreSQL y restauracion verificada en base temporal; configuracion LAN con Waitress y Docker/HTTPS para despliegue.
- 26 pruebas sobre PostgreSQL, incluidas concurrencia y documentos; pantallas verificadas en navegador de escritorio y movil.


## 2026-10-06 - Transferencias de inventario

- Responsable por laboratorio, asignable desde administraci?n; edici?n de inventario limitada al responsable.
- Solicitudes hacia laboratorios propios con justificaci?n, estado temporal y alerta visual actualizada cada 30 segundos.
- Minifichas con origen, destino, t?cnico y serial; aprobaci?n o rechazo con comentario y auditor?a.
- Guardado transaccional, bloqueo de equipos y una solicitud pendiente por equipo; restauraci?n del estado anterior al resolver.
