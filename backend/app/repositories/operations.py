"""Registro de operaciones de archivo (FILE_OPERATION) y auditoría de permisos
(PERMISSION_AUDIT). Sin contraseñas, tokens, rutas físicas ni secretos."""

from app.repositories import db


def record_file_operation(cursor, *, type_: str, result: str, actor_user_id: int | None,
                          location_id: int | None = None, bytes_transferred: int | None = None,
                          detail: str | None = None) -> None:
    cursor.execute(
        "INSERT INTO FILE_OPERATION (type, result, actor_user_id, location_id, bytes_transferred, detail) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (type_, result, actor_user_id, location_id, bytes_transferred, detail),
    )


def record_permission_audit(cursor, *, action: str, actor_user_id: int | None,
                            location_id: int | None = None, target_user_id: int | None = None,
                            declaration: str | None = None, details: str | None = None) -> None:
    cursor.execute(
        "INSERT INTO PERMISSION_AUDIT (action, actor_user_id, location_id, target_user_id, declaration, details) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (action, actor_user_id, location_id, target_user_id, declaration, details),
    )
