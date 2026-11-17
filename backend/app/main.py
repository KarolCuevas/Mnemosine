from fastapi import FastAPI

from app.api import admin, auth, discovery, locations, playlists, tracks

app = FastAPI(title="Mnemosine", version="0.4.0")

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(tracks.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(playlists.router, prefix="/api")


@app.get("/api/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Confirma que la API responde; no comprueba MySQL ni el disco."""
    return {"status": "ok", "project": "Mnemosine"}
