# Almacenamiento local

Reservado para audio y archivos temporales. Su contenido se excluye de Git.
No configurar esta carpeta como directorio público de FastAPI o del frontend.
Cuando implementes cargas, separa `audio/` y `tmp/`, usa rutas normalizadas y
verifica propietario y permiso en cada solicitud. El audio no se almacena en MySQL.
En producción configura una raíz fuera del código y respaldos independientes.
