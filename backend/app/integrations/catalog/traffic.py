"""Limitador multiproceso con conexión autocommit y bloqueo asesor, sin transacción de red."""
import math
from contextlib import contextmanager

from app.repositories import db
from .contract import CatalogError


@contextmanager
def provider_slot(provider: str):
    lock_name = f"mnemosine:catalog:{provider}"
    connection = db.connect(autocommit=True)
    acquired = False
    cooldown = 1.1
    try:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0) AS acquired", (lock_name,))
            acquired = cursor.fetchone()["acquired"] == 1
            if not acquired:
                raise CatalogError("El proveedor está atendiendo otra consulta. Reintenta en un momento.", status=429, retry_after=2)
            cursor.execute(
                "SELECT TIMESTAMPDIFF(MICROSECOND, UTC_TIMESTAMP(6), next_allowed_at) AS wait_us "
                "FROM PROVIDER_TRAFFIC WHERE provider = %s", (provider,),
            )
            row = cursor.fetchone()
            if row and row["wait_us"] > 0:
                raise CatalogError("Espera antes de volver a consultar el proveedor.", status=429,
                                   retry_after=max(1, math.ceil(row["wait_us"] / 1_000_000)))
            # Reservar antes de salir: si el proceso cae, queda un intervalo conservador.
            cursor.execute(
                "INSERT INTO PROVIDER_TRAFFIC (provider, next_allowed_at) "
                "VALUES (%s, TIMESTAMPADD(SECOND, 15, UTC_TIMESTAMP(6))) "
                "ON DUPLICATE KEY UPDATE next_allowed_at = VALUES(next_allowed_at)", (provider,),
            )
            try:
                yield
            except CatalogError as error:
                cooldown = max(cooldown, error.retry_after or (10 if error.status >= 500 else 1.1))
                raise
            finally:
                cursor.execute(
                    "UPDATE PROVIDER_TRAFFIC SET next_allowed_at = TIMESTAMPADD(MICROSECOND, %s, UTC_TIMESTAMP(6)) "
                    "WHERE provider = %s", (int(cooldown * 1_000_000), provider),
                )
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                cursor.fetchall()
        connection.close()
