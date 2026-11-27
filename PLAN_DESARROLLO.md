# Plan de desarrollo de Mnemosine

Fecha: 15 de noviembre de 2026.

Estado: planificación inicial; no hay aplicación implementada todavía.

Fuente: «Plantilla SRS - Especificacion de Requerimientos de Software V2.pdf», 35 páginas, proyecto denominado Mneme, fecha interna 9/10/2026. Se usa Mnemosine como nombre solicitado por el usuario. Los requisitos del PDF se tratan como especificación del producto. Las decisiones adicionales de este plan son propuestas y se identifican como tales.

## 1. Resultado esperado

Construir una aplicación web multiusuario para cargar música autorizada, organizar una biblioteca privada, compartir copias, buscar canciones y reproducir o descargar únicamente archivos disponibles y permitidos.

El MVP completo incluye RF-01 a RF-21. Las referencias musicales externas RF-22 a RF-25 quedan para una segunda versión. Una primera demostración privada será un hito intermedio y no se presentará como cumplimiento del MVP completo.

Restricciones tomadas del SRS:

- Vue 3 y Tailwind CSS en la interfaz; Python y FastAPI en el servidor.
- MySQL, SQL explícito parametrizado y sin ORM en el alcance académico inicial.
- Audio fuera de MySQL, inicialmente en almacenamiento central del servidor.
- Aplicación adaptable a escritorio y móvil; no aplicación móvil nativa.
- HTTPS y autenticación para acceso remoto; MySQL sin exposición directa a Internet.
- Sin conversión avanzada, sincronización automática entre dispositivos, extracción de audio externo ni integraciones completas con Drive o R2 en el MVP.

## 2. Reglas que guían la implementación

1. TRACK representa una canción; TRACK_LOCATION representa una copia con dueño, ubicación, disponibilidad y permisos. Toda entrega de audio debe resolver una ubicación autorizada.
2. Las cargas son privadas por defecto. PUBLIC significa accesible para las cuentas autenticadas del sistema; no supone acceso anónimo.
3. Publicar permite reproducción, pero la descarga requiere autorización adicional. Reproducción y descarga se evalúan por separado.
4. El administrador puede gestionar la plataforma sin obtener acceso automático a archivos privados.
5. Conocer un identificador, una ruta o un hash no concede acceso. Compartir SHA-256 tampoco transfiere derechos.
6. Las nuevas solicitudes deben respetar inmediatamente los permisos vigentes, incluidas las solicitudes parciales de audio. La revocación no puede recuperar bytes ya entregados.
7. Una fuente desconectada no borra metadatos. No se informa disponibilidad sin verificar el archivo.
8. Las transacciones SQL no revierten el sistema de archivos: las cargas requieren temporales, compensación y recuperación de fallos.
9. Eliminar registros no debe eliminar audio automáticamente. No se implementará borrado físico implícito.

## 3. Decisiones a cerrar durante el primer hito

Estas cuestiones no impiden preparar el proyecto, pero sí deben quedar acordadas antes de completar sus funciones dependientes.

| Tema | Propuesta inicial | Momento límite |
|---|---|---|
| Nombre Mneme/Mnemosine | Mnemosine en la aplicación; conservar referencia al SRS original | Diseño de interfaz |
| Registro autorizado | Registro por invitación o habilitado por administrador; evitar alta pública sin una decisión explícita | Autenticación |
| Propiedad de archivos escaneados | Exigir un propietario explícito al iniciar la importación; no inferirlo de SOURCE.owner_user_id, que puede ser NULL | Escaneo |
| Formatos y límites de carga | Definir lista de formatos, máximo por archivo y cuota por cuenta; validar reproducción en navegadores elegidos sin prometer compatibilidad por extensión | Cargas |
| Declaración de autorización | Registrar declaración del propietario antes de compartir, fecha y alcance; esto documenta la declaración, no verifica una licencia por sí solo | Compartición |
| Auditoría de permisos | Agregar una tabla de eventos de auditoría: FILE_OPERATION solo enumera UPLOAD, DOWNLOAD y SCAN, pero RNF-14 exige cambios de permisos | Modelo de datos |
| Sesiones | Sesión revocable con cookie HttpOnly y protección de solicitudes que modifican datos; documentar expiración, cierre y desactivación de cuentas | Autenticación |
| Descarga sin reproducción | Conservar independencia de ambos permisos; un permiso de descarga no activa automáticamente reproducción | Motor de permisos |
| Revocación sobre una copia pública | Quitar un permiso individual no quita el acceso público; para impedirlo debe retirarse también la publicación | Compartición |
| Metadatos compartidos | Definir quién corrige un TRACK utilizado por varias cuentas; propuesta: corrección administrada, sin edición global libre por cualquier propietario | Catálogo |
| Canciones no disponibles | Biblioteca personal y listas conservan su referencia; descubrimiento compartido prioriza copias disponibles, conciliando HU-11 con RF-10 | Consultas |
| Entorno y dedicación | Confirmar servidor, capacidad de disco, navegadores objetivo, equipo y horas disponibles | Estimación y despliegue |

## 4. Arquitectura y organización propuesta

Flujo: navegador → API FastAPI → servicios de negocio → consultas SQL / adaptador de almacenamiento local.

El frontend no decide permisos ni accede directamente a rutas físicas. Las respuestas describen los permisos efectivos y la disponibilidad. El servidor vuelve a validarlos al reproducir o descargar.

Estructura prevista, todavía sin crear:

```text
frontend/src/
  views/          # Acceso, biblioteca, catálogo, listas y administración
  components/     # Reproductor, tablas, cargas y controles de permisos
  services/       # Comunicación con la API
backend/app/
  api/            # Rutas y validación de solicitudes
  services/       # Reglas del catálogo, permisos, cargas y listas
  repositories/   # SQL parametrizado y transacciones
  storage/        # Contrato de almacenamiento y adaptador local
  security/       # Contraseñas y sesiones
database/
  migrations/     # Cambios SQL numerados y reproducibles
  seeds/          # Datos de demostración sin secretos ni música no autorizada
tests/            # Pruebas de integración, permisos y recorridos
docs/             # Modelo, API, decisiones y operación
```

Propuesta: mantener un solo backend y un único almacenamiento local en el MVP. Diseñar el contrato del adaptador desde el inicio sin construir conectores futuros. El escaneo debe tener estado persistente y poder informar fallos o interrupciones sin bloquear la interfaz.

## 5. Fases y entregas verificables

Los esfuerzos son estimaciones preliminares en jornadas de una persona con experiencia y dedicación completa; no son fechas comprometidas. Incluyen implementación y pruebas de cada fase. Deben recalibrarse tras el primer recorrido funcional.

| Hito | Esfuerzo | Trabajo y entregables | Criterio de salida | Depende de |
|---|---:|---|---|---|
| H0. Diseño y acuerdos | 2–3 días | Cerrar decisiones críticas, matriz de permisos, bocetos, DER y backlog | Recorridos y reglas documentados; dueño de cada archivo inequívoco | — |
| H1. Base técnica y datos | 3–4 días | Estructura del proyecto, configuración, conexión MySQL, migraciones SQL, datos de prueba y adaptador local | Instalación reproducible y restricciones relacionales comprobadas | H0 |
| H2. Cuentas y aislamiento | 3–5 días | Registro autorizado, login/logout, sesiones, roles, desactivación y servicio central de permisos | Dos usuarios y un administrador no acceden indebidamente a recursos privados | H1 |
| H3. Biblioteca privada funcional | 5–7 días | Subida validada, temporales, SHA-256, metadatos, biblioteca, búsqueda, reproductor y descarga propia autorizada | Un usuario carga, encuentra y escucha un archivo; otro no puede descubrirlo ni obtenerlo | H2 |
| H4. Compartición y listas | 5–7 días | Publicación, permisos individuales, revocación, catálogo compartido, bibliotecas públicas y listas ordenadas | Compartir y revocar modifica nuevas solicitudes; listas ajenas siguen protegidas | H3 |
| H5. Fuentes y administración | 4–6 días | Fuentes, escaneos, duplicados, estados, operaciones, moderación y gestión de cuentas | Reescanear no duplica rutas ni cambia dueños/permisos; desconexiones conservan catálogo | H3; integrar H4 |
| H6. Validación y entrega | 4–6 días | Pruebas integrales, 10.000 canciones, navegadores móviles/escritorio, HTTPS, respaldo/restauración y manual | Criterios de la sección 10 cumplidos y demostración reproducible | H4 y H5 |

Total orientativo: 26–38 jornadas, aproximadamente 6–8 semanas de trabajo a tiempo completo. Reservar un 20 % adicional para incertidumbres de formatos, entorno y correcciones. En dedicación parcial o aprendizaje, convertir el esfuerzo a calendario según horas reales.

**Primera demostración útil: H3.** Registro → carga privada → biblioteca → búsqueda → reproducción, con aislamiento entre dos cuentas. No esperar a construir todas las pantallas para comprobar este recorrido.

## 6. Backlog trazable al SRS

| Tarea | Requisitos | Hito | Verificación principal |
|---|---|---|---|
| B01. Migraciones, DER y restricciones | RNF-02; sección 5 | H1 | PK, FK, UNIQUE, NOT NULL y CHECK pertinentes; rollback real ante fallo |
| B02. Cuentas, sesiones y administración | RF-12, RF-16; HU-09 | H2, H5 | Cuenta única, contraseña protegida, rol por defecto USER, sesión invalidada al cerrar o desactivar |
| B03. Política de acceso reutilizable | RF-12, RF-17, RF-20; RNF-11 | H2–H4 | Solicitudes directas por ID y acceso de administrador no eluden permisos |
| B04. Cargas y biblioteca propia | RF-08, RF-17; HU-04, HU-10 | H3 | Archivo válido, dueño correcto, privado por defecto y visible solo tras finalizar |
| B05. Catálogo, metadatos y búsqueda | RF-03, RF-05; HU-01 | H3 | Buscar por título, artista y álbum sin filtrar metadatos privados a terceros |
| B06. Identidad de archivos | RF-04 | H3, H5 | Ruta única por fuente; hash idéntico no mezcla propiedad ni permisos |
| B07. Reproducción | RF-06; HU-02 | H3 | Reproducir, pausar, cambiar pista y buscar posición en formato compatible; autorización en cada solicitud |
| B08. Descarga original | RF-09; HU-05 | H3, H4 | Bytes originales y permiso específico; reproducción pública no concede descarga |
| B09. Visibilidad y permisos por usuario | RF-18, RF-20; HU-11, HU-12, HU-14 | H4 | Publicar, volver a privado, conceder y revocar; auditoría de cambios |
| B10. Descubrimiento compartido | RF-19, RF-21; HU-13 | H4 | Biblioteca de otra cuenta muestra solo publicaciones permitidas, sin recursos privados |
| B11. Listas privadas ordenadas | RF-07; HU-03 | H4 | Crear, consultar, renombrar, eliminar, agregar, quitar y reordenar solo como propietario |
| B12. Fuentes e importación | RF-01, RF-02; HU-06 | H5 | Fuente autorizada, propietario de importación definido, conteos y errores verificables |
| B13. Disponibilidad y fallos | RF-10, RF-15; HU-07 | H3–H5 | Archivo faltante o fuente caída bloquean entrega sin eliminar la canción |
| B14. Registro de operaciones | RF-13; HU-08; RNF-14 | H3–H5 | Subidas, descargas, escaneos y permisos registran responsable y resultado sin secretos |
| B15. Adaptador de almacenamiento | RF-14; RNF-08 | H1, H5 | Lógica de catálogo y acceso no depende de una ruta local concreta |
| B16. Interfaz adaptable | RF-11; RNF-04, RNF-05 | H0–H6 | Flujos principales utilizables desde escritorio y móvil con errores y progreso claros |
| B17. Seguridad, rendimiento y respaldo | RNF-01, RNF-03, RNF-06, RNF-07, RNF-09, RNF-10, RNF-11 | H2–H6 | Aislamiento, validación, búsqueda objetivo y restauración comprobados |
| B18. Referencias externas | RF-22–RF-25; HU-15–HU-16; RNF-12, RNF-13 | Versión 2 | Enlaces y metadatos sin extracción de audio; fallos externos no afectan biblioteca interna |

## 7. Modelo de datos y ajustes necesarios

Implementar las 14 entidades iniciales: DEVICE, SOURCE, SCAN_JOB, TRACK, TRACK_LOCATION, ALBUM, ARTIST, TRACK_ARTIST, ALBUM_ARTIST, PLAYLIST, PLAYLIST_TRACK, FILE_OPERATION, USER_ACCOUNT y TRACK_SHARE. EXTERNAL_TRACK y USER_EXTERNAL_SHARE se reservan para versión 2. USER_PREFERENCE es una extensión, no una obligación inicial.

Antes de escribir las migraciones:

- Confirmar longitudes, codificación e índices: la unicidad de SOURCE + file_path debe ser viable con la longitud y codificación elegidas. No sustituirla por un índice de prefijo que cambie silenciosamente la regla de unicidad.
- Definir rutas relativas normalizadas y comparación de mayúsculas según el almacenamiento; rechazar rutas que salgan de la raíz, incluidos enlaces que conduzcan fuera de ella.
- Indexar relaciones usadas en filtros por propietario, visibilidad, destinatario, fuente y hash. Evaluar búsqueda con datos representativos antes de añadir infraestructura adicional.
- SHA-256 identifica bytes, no grabaciones distintas ni licencia. No imponer unicidad global al hash ni deduplicar físicamente entre usuarios en la primera entrega.
- No unir canciones automáticamente solo por título y artista. Registrar la política para reutilizar TRACK cuando haya evidencia suficiente y no sobrescribir metadatos compartidos accidentalmente.
- Conservar la clave compuesta de PLAYLIST_TRACK: la misma canción aparece una sola vez por lista según el SRS. Reordenar dentro de una transacción sin violar la unicidad de posición.
- Añadir, como propuesta, almacenamiento de sesiones revocables y auditoría de permisos; documentar estas extensiones al modelo original.
- Registrar la autorización declarada para publicar o permitir descarga, con trazabilidad de quién la declaró.
- Mantener CASCADE solo en asociaciones apropiadas, RESTRICT en recursos con dependencias y SET NULL en referencias históricas opcionales, conforme a la sección 5.2 del SRS.

## 8. Interfaz y contratos de API

Pantallas previstas: registro/inicio de sesión; mi biblioteca; catálogo compartido; carga con progreso; detalle de canción y copias accesibles; listas; permisos de una copia; biblioteca pública de una cuenta; administración de usuarios, fuentes, escaneos y operaciones. Reproductor persistente en las pantallas de biblioteca.

Conservar como base las rutas de la sección 8.3 del SRS. Completar el contrato antes de implementarlo:

- Agregar logout y comportamiento de expiración de sesión.
- Definir paginación, filtros, errores uniformes y respuestas sin rutas físicas ni ubicaciones privadas.
- En `/api/tracks/{id}/audio` y `/download`, resolver una copia autorizada para esa operación. Si se admite `location_id`, verificar que pertenece a la canción y al ámbito de acceso del solicitante.
- Definir entrega parcial de audio y manejo de rangos inválidos; cada nueva solicitud comprueba sesión y permisos. No servir los archivos mediante un directorio estático público.
- Completar consulta de detalle, renombrado, eliminación y reordenamiento de listas, ausentes de la lista inicial de rutas.
- Completar rutas de administración de cuentas, fuentes, escaneos, operaciones y retirada de publicaciones.
- Distinguir entre transferencia finalizada por el servidor y archivo efectivamente guardado por el navegador; no afirmar que el usuario guardó un archivo cuando no se puede comprobar.
- Definir respuesta ante recurso inexistente/no autorizado evitando revelar existencia de archivos privados.

## 9. Primer bloque de trabajo ejecutable

Orden propuesto para empezar el desarrollo:

1. Documentar matriz de acceso con usuario A, usuario B y administrador; cerrar propiedad de escaneos, registro y límites de carga.
2. Dibujar biblioteca, carga, reproductor y panel de permisos, incluyendo estados vacíos y errores.
3. Crear estructura frontend/backend/database/tests y guía de ejecución local.
4. Fijar dependencias al implementar, preparar configuración de ejemplo sin secretos y una comprobación de conexión a MySQL.
5. Escribir migraciones SQL numeradas y datos de demostración; validar restricciones con MySQL real.
6. Implementar cuentas y sesiones; probar intentos de acceso cruzado antes de conectar archivos.
7. Implementar una carga privada completa con archivo temporal, validación, hash y compensación ante error.
8. Mostrar la carga en biblioteca y reproducirla desde una ruta protegida.
9. Demostrar que B y el administrador no pueden consultar ni reproducir la copia privada de A.

El entregable de este bloque es el recorrido funcional de H3 y sus instrucciones de ejecución. La implementación de este bloque es trabajo posterior al presente documento de planificación.

## 10. Pruebas y definición de terminado

Probar la lógica de permisos de forma aislada; las restricciones, consultas y transacciones contra MySQL; y los recorridos principales desde navegador. No reemplazar MySQL por otra base para validar sus restricciones específicas.

Escenarios obligatorios de aceptación:

- A sube un archivo privado; B no lo encuentra, consulta, reproduce ni descarga, incluso con su ID. El administrador tampoco obtiene acceso libre.
- A publica: B puede reproducir; no puede descargar hasta recibir autorización adicional.
- A comparte una copia privada con B; al revocar, una nueva solicitud de reproducción, rango o descarga queda denegada. Verificar aparte el caso de copia todavía pública.
- Dos usuarios cargan los mismos bytes: sus permisos permanecen independientes. Repetir un escaneo no duplica la misma ruta ni cambia su propietario.
- Una copia deja de estar disponible: la interfaz muestra el estado y conserva la canción; no usa otra copia sin verificar sus permisos.
- Cargas incompletas, archivos falsamente renombrados, rutas maliciosas, límite excedido y errores de disco no dejan archivos disponibles incorrectamente ni referencias huérfanas sin recuperación.
- Listas: solo el dueño cambia contenido y orden; si pierde permiso sobre una canción, la lista no otorga acceso al audio.
- Desactivar una cuenta invalida su acceso. Los cambios de permisos y operaciones quedan trazados sin contraseñas, tokens ni rutas sensibles.
- Reproducir, pausar, cambiar de canción, avanzar y descargar en los navegadores de escritorio y móvil definidos. Documentar formatos no compatibles sin introducir conversión fuera de alcance.
- Ejecutar búsquedas por título, artista y álbum con 10.000 canciones y permisos representativos. Registrar hardware, consultas, condiciones y tiempos; objetivo del SRS: máximo de dos segundos en búsquedas habituales del entorno de desarrollo.
- Restaurar un respaldo en un entorno limpio: comprobar base de datos, audio, propietarios y permisos. Un respaldo solo de metadatos no supera esta prueba.

El MVP se considera terminado cuando RF-01 a RF-21 tienen evidencia, no quedan fallos críticos de acceso o pérdida de datos y se entregan: código ejecutable, migraciones, DER, diccionario actualizado, contrato API, guía de instalación, manual breve, procedimiento de respaldo/restauración y resultados de pruebas. El acceso remoto se habilita con HTTPS y la base de datos permanece privada.

## 11. Riesgos y tratamiento

| Riesgo | Tratamiento previsto |
|---|---|
| Fuga entre usuarios por compartir TRACK | Autorizar cada ubicación; filtrar consultas y probar identificadores directos |
| Subida registrada pero archivo incompleto | Temporal, validación, movimiento controlado, compensación y revisión de operaciones interrumpidas |
| Escaneos sin propietario | Exigir asignación previa; nunca publicar automáticamente |
| Audio no compatible con navegador | Matriz de formatos y navegadores; mensaje explícito sin prometer transcodificación |
| Crecimiento de disco | Límites y cuotas acordados, capacidad visible y procedimiento de mantenimiento |
| Consultas lentas por permisos y duplicados | Datos representativos, paginación e índices medidos antes de ampliar arquitectura |
| Plan académico mayor que tiempo disponible | Entregas H0–H6 y demostración privada temprana; cualquier recorte del MVP se documenta |

## 12. Versión posterior

Tras aceptar el MVP, implementar referencias externas de manera independiente: metadatos y enlaces oficiales, publicaciones de referencias, coincidencias sugeridas por ISRC/metadatos y confirmación de casos ambiguos. Validar disponibilidad y condiciones de cada proveedor al iniciar esa fase. Nunca incorporar extracción de audio como parte de estas integraciones.

Las fuentes remotas adicionales y preferencias personales serán extensiones separadas. Su indisponibilidad no debe afectar la carga, búsqueda y reproducción de la biblioteca central.

### Ampliación acordada el 24 de noviembre de 2026

El [plan de integraciones](docs/PLAN_INTEGRACIONES.md) concreta la siguiente etapa: servicios musicales para consultar listados y metadatos; Google Drive por usuario para subir, vincular y recuperar archivos; copias entre Drive y el servidor; y adaptadores para otros medios. Esta solicitud incorpora escritura en Drive al alcance posterior al MVP. Las coincidencias automáticas y la reproducción o descarga desde servicios musicales no forman parte de esta entrega. Cada usuario conectará su propia cuenta de Drive, según la decisión confirmada.

Actualización del 25 de noviembre: MusicBrainz pasa a ser el catálogo principal para búsqueda e indexación progresiva de nombres y metadatos básicos. Deezer se descarta para ese índice bajo sus condiciones estándar actuales, según la evaluación enlazada en el plan de integraciones. El almacenamiento se mantiene modular con contratos, capacidades y registro de adaptadores: servidor y Drive personal primero, otras fuentes incorporables después sin rehacer biblioteca o permisos.
