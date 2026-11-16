"""Servicio central de permisos sobre copias (RF-12, RF-17, RF-20; RNF-11).

Regla única para toda la aplicación: nadie (ni el administrador) obtiene acceso
sin una regla explícita. El rol NO interviene en el permiso sobre contenido:
allí somos todos usuarios (matriz de acceso revisada). En H3/H4 se amplia la
fábrica de hechos a consultas SQL reales; la política vive aquí y se prueba
aislada.
"""

from dataclasses import dataclass
from typing import Literal

Action = Literal["view", "stream", "download"]


@dataclass(frozen=True)
class LocationFacts:
    owner_user_id: int
    visibility: str            # 'PRIVATE' | 'PUBLIC'
    public_download_allowed: bool
    share_stream: bool         # destinatario con share activo can_stream=1
    share_download: bool       # destinatario con share activo can_download=1
    availability: str          # 'AVAILABLE' | 'MISSING' | 'ERROR'


def can(*, actor_user_id: int, action: Action, facts: LocationFacts) -> bool:
    # Una copia no disponible nunca entrega bytes (la referencia se conserva).
    if action in ("stream", "download") and facts.availability != "AVAILABLE":
        return False
    # El dueño conserva siempre ver/reproducir/descargar su copia.
    if actor_user_id == facts.owner_user_id:
        return True
    if action == "view":
        return (
            facts.visibility == "PUBLIC"
            or facts.share_stream
            or facts.share_download
        )
    if action == "stream":
        return facts.visibility == "PUBLIC" or facts.share_stream
    if action == "download":
        return (facts.visibility == "PUBLIC" and facts.public_download_allowed) or facts.share_download
    raise ValueError(f"acción desconocida: {action}")
