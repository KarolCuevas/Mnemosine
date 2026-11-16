# Crecimiento por etapas

## Desarrollo y primera entrega

Mantén un frontend, un backend, MySQL y almacenamiento local. No necesitas Redis,
Kubernetes ni microservicios para comenzar. Usa paginación, límites de carga y
consultas parametrizadas. Añade un pool de conexiones acotado al implementar los
repositorios; el script de conexión actual es solo diagnóstico.

## Antes de publicar

- Configura dominio, HTTPS y proxy inverso; sirve el frontend compilado.
- Ejecuta FastAPI como servicio supervisado, sin `--reload` y con secretos externos.
- Mantén MySQL en una red privada. Separa el usuario de migraciones del usuario
  de la API, que solo necesita los permisos de lectura y escritura correspondientes.
- Implementa sesiones revocables, cookies seguras, CSRF, cuotas y límites de solicitudes.
- Reserva almacenamiento persistente para audio y temporales; supervisa espacio libre.
- Respalda conjuntamente base y archivos con un procedimiento consistente (por
  ejemplo, detener escrituras durante una primera versión del respaldo).
  Prueba una restauración en otro entorno, incluidos propietarios y permisos.
- Registra errores, latencia, fallos de cargas y cambios de permisos sin secretos.
- Fija dependencias con locks validados y una versión/digest probado de MySQL.
  La etiqueta `8.4` de desarrollo puede incorporar actualizaciones.

## Cuando las mediciones lo justifiquen

| Señal | Siguiente acción |
|---|---|
| Búsquedas lentas | Medir consultas, usar EXPLAIN, ajustar índices y paginación |
| Escaneos bloquean solicitudes | Trabajador separado con cola y estado persistente |
| Disco próximo al límite | Cuotas, alertas y ampliación del volumen |
| Necesitas varias instancias de API | Sesiones compartidas, almacenamiento accesible para todas, límites coordinados |
| Almacenamiento local ya no basta | Implementar otro adaptador tras aceptar el MVP y revisar reglas de acceso |

No introduzcas cachés de permisos sin invalidación inmediata. Varias instancias no
pueden depender de sus propios discos locales para acceder a las mismas copias.
Los enlaces de audio de larga duración tampoco deben eludir la revocación.

Capacidad: estima cantidad de copias × tamaño promedio, más temporales, crecimiento
y respaldos. Mide con 10.000 canciones antes de cambiar arquitectura; el objetivo
de búsqueda del plan es como máximo dos segundos en el entorno definido.
