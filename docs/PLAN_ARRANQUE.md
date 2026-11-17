# Plan de arranque — Mnemosine (hasta H3)

Fecha: 15 de noviembre de 2026 (ubicado en `docs/` el 16 de noviembre).
Base: [`PLAN_DESARROLLO.md`](../PLAN_DESARROLLO.md) + [ARQUITECTURA](ARQUITECTURA.md) y [MODELO_DATOS](MODELO_DATOS.md).
Alcance: fases 0–3 (H0 → demo privada H3). Compartición, listas, fuentes,
administración y validación final (H4–H6) quedan fuera de este arranque.

Estado del repositorio al planificar: esqueleto Vue 3 + Tailwind + Vite y
FastAPI con `/api/health` validado; MySQL 8.4 configurado en `compose.yaml`
(puerto 3307); sin autenticación, tablas ni lógica de negocio implementadas.

Reglas del plan maestro que este arranque respeta:

- TRACK = canción; TRACK_LOCATION = copia con dueño, ubicación y permisos.
  Toda entrega de audio resuelve una ubicación autorizada.
- Cargas privadas por defecto; PUBLIC nunca implica acceso anónimo.
- Reproducción y descarga se autorizan por separado.
- El administrador no obtiene acceso a archivos privados por su rol.
- Conocer ID, ruta o hash no concede acceso.
- Toda petición (incluidos rangos de audio) vuelve a comprobar permisos.
- SQL explícito parametrizado, sin ORM; audio fuera de MySQL.

Estado de ejecución: **Fase 0 (documentada y decisiones aprobadas), Fase 1, Fase 2
(cuentas, invitaciones, sesiones revocables y aislamiento A/B/admin, con ajustes D4/D8/D13),
Fase 3 (carga privada, biblioteca, búsqueda, reproductor y descarga propia), Fase 4
(compartición con declaración, descubrimiento, revocación en caliente y listas) y Fase 5
(fuentes, escaneos, disponibilidad, operaciones y administración) completadas y verificadas
el 17/11/2026. Pendiente: Fase 6 (validación final H6) y demo completa.**

## Fase 0 — Acuerdos y diseño (H0, ≈2–3 días)

Objetivo: cerrar lo imprescindible para no rehacer trabajo en H1–H3.

1. Cerrar decisiones pendientes (ver [DECISIONES.md](DECISIONES.md)):
   nombre visible Mnemosine; registro por invitación o alta habilitada por el
   administrador; formatos MP3/M4A/FLAC/OGG/WAV con 50 MB por archivo y 5 GB
   de cuota por cuenta; sesión cookie HttpOnly + SameSite con CSRF, expiración
   deslizante de 7 días; hashing argon2; auditoría de permisos mediante
   PERMISSION_AUDIT; propietario explícito para escaneos; declaración de
   autorización al publicar o permitir descarga.
2. Matriz de acceso con 3 actores (usuario A, usuario B, administrador) ×
   recurso × operación (ver [DECISIONES.md](DECISIONES.md)).
3. Bocetos de las pantallas clave (ver [BOCETOS.md](BOCETOS.md)).
4. DER y diccionario de datos inicial (ver [DER.md](DER.md)): 14 entidades
   del SRS + USER_SESSION + PERMISSION_AUDIT + INVITATION.
5. Entorno: Docker Desktop para MySQL 8.4 (3307); puertos 8000 (API) y 5173
   (Vite); navegadores objetivo de escritorio y móvil; e2e previsto con
   Playwright; estado de sesión con composables o Pinia (propuesta: Pinia).

Criterio de salida: recorridos y reglas documentados; dueño inequívoco de
cada archivo previsto.

## Fase 1 — Base de datos y migraciones (H1, ≈3–4 días)

Requisito previo: Docker Desktop iniciado; `docker compose up -d db` en
`healthy`; claves propias en `.env` y `backend/.env`.

1. Ejecutor de migraciones propio (`backend/scripts/migrate.py`), tabla
   `schema_migrations` con versión, fecha y checksum. Detecta cambios en
   migraciones ya aplicadas, se detiene ante fallos y evita ejecución
   simultánea (bloqueo). MySQL hace commit implícito en DDL: el ejecutor no
   promete rollback transaccional de CREATE/ALTER.
2. Migraciones numeradas en `database/migrations/`:
   `0001_identidad` → `0002_fuentes` → `0003_catalogo` → `0004_copias` →
   `0005_comparticion` → `0006_listas` → `0007_operaciones`.
3. Restricciones comprobadas contra MySQL real (ver docs del DER).
4. Seeds de demostración sintéticos (`database/seeds/`), sin credenciales
   reales ni audio con copyright (tonos generados aparte, fuera de Git).
5. Adaptador de almacenamiento: contrato en `backend/app/storage/contract.py`
   + implementación local `LocalStorageAdapter` con raíz en `storage/`;
   rechazo de rutas que escapen de la raíz, incluidos enlaces.
6. `python -m scripts.check_db` extendido: conexión + esquema aplicado +
   conteos mínimos.
7. Pruebas de integración de restricciones en `tests/integration/`.

Criterio de salida: instalación reproducible de cero
(compose → migrate → seed → check_db) con restricciones comprobadas.

## Fase 2 — Cuentas y aislamiento (H2, ≈3–5 días)

1. argon2 para contraseñas; tokens opacos hasheados en USER_SESSION; cookie
   HttpOnly + SameSite; CSRF en mutaciones; revocación al desactivar.
2. Registro por invitación; roles USER/ADMIN; USER por defecto.
3. Endpoints `/api/auth/*`: register, login, logout, me. Rate limiting básico;
   errores que no revelan existencia de cuentas.
4. Dependencia `get_current_user` en FastAPI.
5. Servicio central de permisos (`services/permissions.py`), política «negar
   por defecto»; en H2 basta la rama dueño/no-dueño testeada.
6. Frontend: vistas de acceso, guard de navegación, cliente API con manejo
   uniforme de errores.
7. Pruebas de integración negativas antes de conectar archivos.

Criterio de salida: A, B y admin autenticados; pruebas de aislamiento en verde.

## Fase 3 — Primer recorrido funcional (H3, ≈5–7 días)

1. Carga privada de extremo a extremo (temporal → validación de tipo/tamaño →
   SHA-256 en streaming → movimiento atómico → TRACK + TRACK_LOCATION PRIVATE
   en una transacción → compensación ante fallo → FILE_OPERATION(UPLOAD)).
2. Biblioteca privada paginada y búsqueda por título/artista/álbum.
3. Reproducción: `/api/tracks/{id}/audio` con Range (206/416), autorización en
   cada solicitud, sin directorio estático público.
4. Descarga propia: `/api/tracks/{id}/download`, permiso de descarga separado.
5. Frontend del recorrido: carga con progreso, biblioteca, detalle, reproductor
   persistente, errores y estados vacíos.
6. Pruebas de integración del flujo completo y e2e (Playwright) del recorrido;
   aislamiento A/B/admin como suite permanente.

Criterio de salida (demo privada): registro → carga → biblioteca → búsqueda →
reproducción → descarga propia en navegador; B ni el administrador pueden
descubrir, reproducir ni descargar la copia privada de A, ni con su ID directo.

## Orden, dependencias y esfuerzo

H0 → H1 → H2 → H3 secuencial. Pruebas de permisos desde H2. Demo al cerrar H3.

Esfuerzo orientativo: 13–19 jornadas ≈ 3–4 semanas a tiempo completo
(reservar ~20 % extra). Primera demo útil: al cerrar H3.

## Riesgos del arranque

| Riesgo | Tratamiento |
|---|---|
| Docker daemon apagado | Iniciar Docker Desktop antes de H1; alternativa: MySQL 8.4 local propio |
| OneDrive bloquea `.venv` / `storage/` / volumen | Excluir del sync o mover fuera de OneDrive |
| Puertos 8000/5173/3307 ocupados | Comprobar y ajustar configs |
| Python 3.14 vs dependencias nuevas | Fijar cada dependencia nueva en `requirements.lock.txt` |
| Formatos no compatibles en navegador | Matriz de formatos/navegadores; sin transcodificar (fuera de alcance) |
| Cobertura de pruebas insuficiente | Permisos y migraciones primero; e2e del recorrido H3 obligatorio |

## Fuera de alcance de este arranque

Compartición y PUBLIC (H4), listas (H4), fuentes, escaneos y duplicados (H5),
administración completa (H5), 10.000 canciones, HTTPS, respaldo/restauración
(H6), referencias externas RF-22–RF-25 y USER_PREFERENCE.
