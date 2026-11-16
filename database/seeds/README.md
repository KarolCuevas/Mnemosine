# Datos de prueba

`0001_demo.sql` inserta un catálogo sintético (un dispositivo, una fuente,
artistas `Kältmare` y `Aya Duarte`, álbumes `Sol` y `Marea baja`).
**Una sola vez**, sobre una base ya migrada; re-ejecutarlo da errores de
clave duplicada sin corromper datos.

Con `mysql` instalado, desde la raíz del repositorio:

```powershell
mysql --host 127.0.0.1 --port 3307 --user mnemosine_app -p mnemosine < database/seeds/0001_demo.sql
```

Sin cliente `mysql` en Windows, desde `backend/` usando el entorno virtual:

```powershell
.\.venv\Scripts\python.exe -c "
from pathlib import Path
import mysql.connector
from app.core.config import get_settings
from scripts.migrate import split_statements
s = get_settings()
conn = mysql.connector.connect(host=s.db_host, port=s.db_port, database=s.db_name, user=s.db_user, password=s.db_password, autocommit=True)
with conn.cursor() as cur:
    for stmt in split_statements(Path('../database/seeds/0001_demo.sql').read_text(encoding='utf-8')):
        cur.execute(stmt)
conn.close()"
```

Sin usuarios, contraseñas ni audio: las cuentas y las copias privadas se crean
desde la aplicación (H2/H3). Sin material con copyright.
No ejecutes seeds de demostración sobre producción.
