from fastapi import FastAPI

from app.api import admin, auth

app = FastAPI(title="Mnemosine", version="0.2.0")

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Confirma que la API responde; no comprueba MySQL ni el disco."""
    return {"status": "ok", "project": "Mnemosine"}
