"""Serializa escrituras por cuenta. Bloquear antes de otras lecturas de la transacción."""
from app.core.config import get_settings


class QuotaExceededError(Exception):
    pass


def lock_account(cursor, user_id: int) -> None:
    cursor.execute("SELECT is_active FROM USER_ACCOUNT WHERE user_id = %s FOR UPDATE", (user_id,))
    account = cursor.fetchone()
    if not account or not account["is_active"]:
        raise QuotaExceededError("la cuenta no está activa")


def check_capacity(cursor, user_id: int, size_bytes: int) -> None:
    cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) AS used FROM TRACK_LOCATION WHERE owner_user_id = %s", (user_id,))
    used = cursor.fetchone()["used"]
    cursor.execute("SELECT COALESCE(SUM(reserved_bytes), 0) AS reserved FROM TRANSFER_JOB WHERE actor_user_id = %s "
                   "AND status IN ('PENDING','RUNNING','VERIFYING','RETRY_WAIT','AUTH_REQUIRED')", (user_id,))
    if used + cursor.fetchone()["reserved"] + size_bytes > get_settings().max_user_quota_bytes:
        raise QuotaExceededError("esta copia supera la cuota disponible de la cuenta")
