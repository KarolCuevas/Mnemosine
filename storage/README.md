# Almacenamiento local

Reservado para audio y archivos temporales. Su contenido se excluye de Git.
No configurar esta carpeta como directorio público de FastAPI o del frontend.
El audio no se almacena en MySQL. En producción, raíz fuera del código y
respaldos independientes (incluido el audio, nunca solo metadatos).

## Implementación (H1)

El contrato y el adaptador local viven en `backend/app/storage/`:

- `contract.py` — interfaz `StorageAdapter`, normalización de rutas relativas
  (rechaza absolutas, unidades, `..`, caracteres de control y más de 512
  caracteres) y tipo `StagedUpload` (carga temporal opaca).
- `local.py` — `LocalStorageAdapter(raíz)`; temporales en
  `<raíz>/.tmp_uncommitted`, publicación atómica con `os.replace` en
  `commit()` (nunca sobrescribe), `recover_stale_temps()` para interrumpidos.

La lógica de catálogo y acceso no debe depender de rutas concretas: usa
siempre la interfaz. Rutas, permisos y autorización se verifican en la capa
de servicios en cada solicitud.
