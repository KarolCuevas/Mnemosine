# Dónde escribir cada parte

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
| database/migrations | Evolución ordenada del esquema |
| tests/unit | Reglas aisladas, especialmente permisos |
| tests/integration | MySQL real, transacciones, archivos y API |
| tests/e2e | Recorridos completos desde navegador |

Lo implementado es únicamente el arranque de Vue, Tailwind y FastAPI, `/api/health`
y una comprobación de conexión a MySQL. No hay autenticación, tablas, cargas,
reproductor, consultas del catálogo ni migrador.

Vite envía `/api` al backend durante desarrollo. En producción el servidor web
deberá servir el frontend compilado y reenviar `/api` a FastAPI bajo el mismo
origen. `vite preview` es solo una vista previa local.

Primer recorrido a programar: cuentas y sesiones → carga privada → consulta de
biblioteca → reproducción autorizada. Prueba el aislamiento con dos cuentas antes
de compartir archivos. El plan original conserva los requisitos y criterios de aceptación.
