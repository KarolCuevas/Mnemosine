# Verificación de la base inicial

- Sintaxis Python: correcta (`compileall`).
- Dependencias Python: instaladas en entorno virtual con Python 3.14.3;
  `pip check` sin conflictos. Versiones guardadas en `requirements.lock.txt`.
- FastAPI: importación, respuesta de la función health y generación del contrato
  OpenAPI comprobadas. No se hizo una prueba HTTP de servidor en ejecución.
- Frontend: dependencias instaladas y `npm run build` completado con éxito.
  Versiones guardadas en `package-lock.json`. Sin revisión visual en navegador.
- Docker Compose: configuración validada con `.env.example` sin iniciar MySQL.
- Pendiente al configurar tus claves: arrancar MySQL y ejecutar `scripts.check_db`.
  No se crearon cuentas, tablas ni datos en un servidor real.

Estas comprobaciones validan el esqueleto, no las funciones futuras del proyecto.
