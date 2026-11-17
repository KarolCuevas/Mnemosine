# Mnemosine — Despliegue, HTTPS y acceso remoto

El MVP local funciona en `127.0.0.1`. Para exponer la aplicación fuera del
equipo, los mínimos son:

1. **HTTPS** con un proxy inverso (Caddy o nginx) delante del frontend y de la API.
2. `SESSION_COOKIE_SECURE=true` en `backend/.env` (sin esto, la cookie de sesión
   no viaja por HTTPS).
3. MySQL accesible **solo** desde 127.0.0.1 (ya lo fija `compose.yaml`). No lo
   expongas a Internet.
4. Respaldos regulares y probados (`docs/MANUAL.md §5`).
5. La cuenta ADMIN con contraseña nueva y fuera del código.

## Caddy (ejemplo) — producción

Servir el frontend compilado (`npm run build` → `frontend/dist`) y enviar solo
`/api/*` a FastAPI. Un único origen; las cookies HttpOnly funcionan sin CORS:

```caddyfile
mnemosine.tudominio.com {
	root * /ruta/a/frontend/dist
	try_files {path} /index.html
	file_server
	encode zstd gzip
	
	reverse_proxy /api/* 127.0.0.1:8000
}
```

(El puerto 5173 es el servidor de desarrollo de Vite; no usarlo en producción.)

## nginx (alternativa)

```nginx
server {
    listen 443 ssl http2;
    server_name mnemosine.tudominio.com;
    ssl_certificate     /ruta/fullchain.pem;
    ssl_certificate_key /ruta/privkey.pem;

    root /ruta/a/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;   # SPA
    }
}
```

## Checklist de publicación

- [ ] `docker compose ps` healthy; migraciones aplicadas (`scripts.check_db`)
- [ ] Certificados TLS válidos (ACME/Caddy automático o Let's Encrypt en nginx)
- [ ] `SESSION_COOKIE_SECURE=true` en `backend/.env`
- [ ] Respaldo restaurado en un entorno limpio (ver `scripts/restore.py`)
- [ ] `ALLOWED_EXTENSIONS`/límites de carga revisados (`backend/app/core/config.py`)
- [ ] MySQL sin puertos publicados fuera de 127.0.0.1 (revisar `compose.yaml`)
- [ ] Reinicio del servicio probado (paso por paso desde cero en un clon limpio)

## Actualización

1. `git pull`
2. `backend`: `pip install -r requirements.lock.txt`; `python -m scripts.migrate`
3. `frontend`: `npm ci`; `npm run build`
4. Reinicia uvicorn y el proxy inverso.
5. Repite respaldo/restauración de verificación.
