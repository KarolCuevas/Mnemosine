# Arquitectura actual

Flujo: Vue → API FastAPI → servicios → repositorios SQL / almacenamiento.

| Carpeta | Qué implementar |
|---|---|
| frontend/src/views | Pantallas completas |
| frontend/src/components | Reproductor, formularios y elementos reutilizables |
| frontend/src/services | Peticiones a /api y manejo de errores |
| frontend/src/router | Navegación cuando haya varias pantallas |
| frontend/src/stores | Estado compartido cuando sea necesario |
| backend/app/api | Rutas, dependencias de autenticación y códigos HTTP |
| backend/app/schemas | Validación de entradas y salidas con Pydantic |
| backend/app/services | Casos de uso, permisos y límites de transacciones |
| backend/app/repositories | Consultas SQL parametrizadas, sin ORM |
| backend/app/storage | Contrato de almacenamiento y adaptador local |
| backend/app/security | Contraseñas, sesiones revocables y protección CSRF |
| backend/app/core | Configuración e infraestructura común |
| backend/app/integrations/catalog | Contrato, registro y proveedor MusicBrainz sin acceso a audio |
| database/migrations | Evolución ordenada del esquema |
| tests/unit | Reglas aisladas, especialmente permisos |
| tests/integration | MySQL real, transacciones, archivos y API |
| tests/e2e | Recorridos completos desde navegador |

Implementado: sesiones revocables y CSRF, cuentas por invitación, cargas privadas,
validación de audio, reproducción con rangos, descarga autorizada, compartición,
listas, escaneos y administración. Las pruebas existentes están en `backend/scripts`;
Playwright vive en `frontend/e2e` y las nuevas pruebas unitarias en `tests/unit`.

La carga usa `services.metadata` para importar etiquetas ID3, MP4 y Vorbis con
Mutagen, después de validar el audio. Los valores manuales no vacíos prevalecen.
La migración 0017 incorpora `TRACK_METADATA`: artista del álbum, género, año y
portada JPEG derivada, guardados en la misma transacción que TRACK. La portada
es independiente del adaptador de almacenamiento del audio y queda incluida en
los respaldos SQL. El original conserva su SHA-256 y sus bytes.

Solo se decodifican portadas incrustadas JPEG/PNG/WebP: entrada hasta 8 MiB y
16 millones de píxeles, salida hasta 800 px y 512 KiB, sin EXIF. Se prefiere la
imagen frontal. Una imagen inválida genera un aviso sin cancelar la carga.
`GET /api/tracks/{id}/cover` exige sesión y permiso de vista sobre una copia,
sin privilegio extra para ADMIN, y responde `private, no-store`. Las listas de
canciones incluyen una URL autorizada, nunca los bytes de la imagen. No se
consultan proveedores externos ni se reprocesan subidas anteriores.

Desde la primera entrega de integraciones, `get_storage_for_source` resuelve el
adaptador registrado y verifica el estado de SOURCE. El adaptador local conserva
la raíz global: las rutas migradas en 0012 no reciben otro prefijo. El acceso a
audio resuelve primero permisos por copia; el rol ADMIN no salta esa comprobación.
`get_storage` se conserva para preparar temporales locales, sin credenciales remotas.

MusicBrainz usa otro registro independiente. `CATALOG_RECORD` guarda solo campos
públicos permitidos y `EXTERNAL_TRACK` asocia referencias privadas a una cuenta.
No se crean TRACK ni TRACK_LOCATION al consultar o guardar referencias. El backend
controla caché y tráfico compartido mediante MySQL. No hay sincronización periódica.

`TRANSFER_JOB` es una base de esquema reservada: todavía no hay trabajador remoto,
OAuth, Picker, adaptador Google Drive ni endpoints de transferencia habilitados.

Vite envía `/api` al backend durante desarrollo. En producción el servidor web
deberá servir el frontend compilado y reenviar `/api` a FastAPI bajo el mismo
origen. `vite preview` es solo una vista previa local.

Próximo recorrido: conectar Drive por usuario y validar un audio elegido con Picker.
Consulta `INTEGRACIONES.md` para distinguir piezas implementadas y pendientes.
