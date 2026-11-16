# Guía para diseñar la base de datos

Las migraciones numeradas viven en `database/migrations/` (0001–0008) y se
aplican con `python -m scripts.migrate`. El detalle ejecutable está en el DER
inicial del repo. No sustituye el DER ni el diccionario del SRS.

| Bloque | Tablas previstas | Responsabilidad |
|---|---|---|
| Identidad | USER_ACCOUNT | Cuentas, roles y desactivación |
| Fuentes | DEVICE, SOURCE, SCAN_JOB | Ubicación de archivos e importaciones |
| Catálogo | TRACK, ALBUM, ARTIST, TRACK_ARTIST, ALBUM_ARTIST | Canciones y metadatos |
| Copias | TRACK_LOCATION | Dueño, ruta relativa, hash, disponibilidad y visibilidad |
| Compartición | TRACK_SHARE | Permisos independientes de reproducción y descarga por copia |
| Listas | PLAYLIST, PLAYLIST_TRACK | Dueño, canciones y orden |
| Operaciones | FILE_OPERATION | Cargas, descargas y escaneos |
| Extensiones propuestas | USER_SESSION, PERMISSION_AUDIT, INVITATION, AUTHORIZATION_DECLARATION | Sesiones revocables, traza de permisos, registro por invitación y autorización ligada a la copia |

Relaciones clave: TRACK tiene muchas TRACK_LOCATION; cada copia tiene un dueño y
una fuente. TRACK_SHARE se refiere a una copia y un destinatario. Una lista tiene
un dueño y asocia canciones sin otorgar derechos sobre sus archivos.

Antes de escribir CREATE TABLE:

1. Confirmar campos, tipos, nulabilidad, claves y acciones de borrado con el SRS.
2. Definir invitaciones/registro, sesiones y declaración de autorización para compartir.
3. Resolver longitud y comparación de rutas para unicidad (fuente, ruta completa).
4. Mantener SHA-256 sin unicidad global: dos copias pueden tener permisos diferentes.
5. Crear índices para propietario, fuente, destinatario y filtros frecuentes.
6. Garantizar unicidad de (lista, canción) y de posición dentro de la lista.
7. Probar restricciones con MySQL real y mantener el audio fuera de sus tablas.

Orden sugerido: identidad → catálogo y fuentes → copias → permisos → listas →
operaciones y auditoría. Mantén las claves foráneas habilitadas al validar datos.
