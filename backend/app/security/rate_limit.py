"""Limitador de intentos en memoria (proceso único) para el login.

Ventana fija por clave (p. ej. "login:ip:usuario"). No sustituye a un limitador
distribuido: al publicar la aplicación debe revisarse (H6). Documentado en el
manual de operación.
"""

import threading
import time


class FixedWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, tuple[int, float]] = {}

    def check_and_hit(self, key: str, *, limit: int, window_minutes: int) -> bool:
        """True si el intento está permitido; False si se superó el límite."""
        now = time.monotonic()
        window_seconds = window_minutes * 60
        with self._lock:
            count, start = self._hits.get(key, (0, now))
            if now - start >= window_seconds:
                count, start = 0, now
            count += 1
            self._hits[key] = (count, start)
            return count <= limit

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


login_limiter = FixedWindowLimiter()
