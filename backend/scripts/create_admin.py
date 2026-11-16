"""Crear una cuenta ADMIN (bootstrap de la plataforma).

Uso desde backend: python -m scripts.create_admin
Pide credenciales interactivamente (la contraseña no pasa por argv ni por el
historial). Idempotente a medias: si el usuario existe, falla sin tocar nada.
"""

import getpass
import sys

import mysql.connector

from app.repositories import users
from app.repositories import db as repos_db
from app.security import passwords
from app.security.passwords import MIN_PASSWORD_LENGTH


def main() -> int:
    username = input("Usuario admin (a-z 0-9 . _ -): ").strip().lower()
    email = input("Correo: ").strip().lower()
    display_name = input("Nombre visible (opcional): ").strip() or None
    password = getpass.getpass(f"Contraseña (mínimo {MIN_PASSWORD_LENGTH} caracteres): ")
    password2 = getpass.getpass("Repite la contraseña: ")
    if password != password2:
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 1
    if len(password) < MIN_PASSWORD_LENGTH or password.strip() != password or " " in password:
        print(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres y sin espacios.", file=sys.stderr)
        return 1

    if users.username_or_email_taken(username, email):
        print("Ya existe una cuenta con ese usuario o correo.", file=sys.stderr)
        return 1

    password_hash = passwords.hash_password(password)
    try:
        with repos_db.transaction() as cursor:
            users.create_user(cursor, username=username, email=email,
                              password_hash=password_hash, display_name=display_name, role="ADMIN")
    except mysql.connector.Error as error:
        print(f"No se pudo crear la cuenta (código {error.errno}).", file=sys.stderr)
        return 1

    print(f"Cuenta ADMIN creada: {username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
