from fastapi import FastAPI

app = FastAPI(title="Mnemosine", version="0.1.0")


@app.get("/api/health", tags=["Sistema"])
def health() -> dict[str, str]:
    """Confirma que la API responde; no comprueba MySQL ni el disco."""
    return {"status": "ok", "project": "Mnemosine"}
