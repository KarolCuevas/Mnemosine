"""Instala configuración privada local sin mostrar valores ni tocar credenciales existentes.

python -m scripts.prepare_google <json-oauth> --project-id <id> --project-number <n>
Agregar --picker-key-file <archivo> para completar y habilitar la conexión.
"""
import argparse
import json
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import set_key

BACKEND = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("client_file", type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-number", required=True)
    parser.add_argument("--picker-key-file", type=Path)
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    client_bytes = args.client_file.read_bytes()
    document = json.loads(client_bytes.decode("utf-8-sig"))["web"]
    if document["project_id"] != args.project_id or not args.project_number.isdigit():
        parser.error("El cliente no corresponde al proyecto indicado.")
    private = BACKEND / ".secrets"
    private.mkdir(exist_ok=True)
    client_path, keys_path, picker_path = private / "google-oauth.json", private / "google-token-keys.json", private / "google-picker.txt"
    if client_path.exists() and client_path.read_bytes() != client_bytes:
        parser.error("Ya existe un cliente diferente. Revisa la configuración antes de sustituirlo.")
    client_path.write_bytes(client_bytes)
    if not keys_path.exists():
        with keys_path.open("x", encoding="utf-8") as handle:
            json.dump({"current": "v1", "keys": {"v1": Fernet.generate_key().decode()}}, handle)
    if args.picker_key_file:
        key = args.picker_key_file.read_text(encoding="utf-8-sig").strip()
        if not key.startswith("AIza") or len(key) > 200 or any(char.isspace() for char in key):
            parser.error("El archivo no contiene una clave de Picker válida.")
        picker_path.write_text(key, encoding="utf-8")
    values = {
        "GOOGLE_PROJECT_ID": args.project_id, "GOOGLE_PROJECT_NUMBER": args.project_number,
        "GOOGLE_APP_ORIGIN": args.origin, "GOOGLE_OAUTH_CLIENT_FILE": client_path.as_posix(),
        "GOOGLE_TOKEN_KEYS_FILE": keys_path.as_posix(), "GOOGLE_PICKER_KEY_FILE": picker_path.as_posix(),
        "GOOGLE_DRIVE_ENABLED": "true" if picker_path.exists() else "false",
    }
    for key, value in values.items():
        set_key(str(BACKEND / ".env"), key, value, quote_mode="always")
    print("Cliente OAuth y cifrado preparados. " + ("Picker configurado." if picker_path.exists() else "Falta el archivo de la clave de Picker."))


if __name__ == "__main__":
    main()
