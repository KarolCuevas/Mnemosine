"""Verificación aislada de la política de permisos (H2).

Ejecutar desde backend: python -m scripts.verify_permissions

Prueba la matriz completa de docs/DECISIONES.md contra la función can(): dueño,
destinatario PUBLIC, destinatario con shares (stream/download), y el rol ADMIN
implícito (no interviene: mismas reglas para cualquier account id, incluido un
administrador).
"""

import sys

from app.services.permissions import LocationFacts, can

OWNER, OTHER = 1, 2


def facts(*, owner=OWNER, visibility="PRIVATE", public_dl=False, s_stream=False, s_dl=False, availability="AVAILABLE") -> LocationFacts:
    return LocationFacts(
        owner_user_id=owner,
        visibility=visibility,
        public_download_allowed=public_dl,
        share_stream=s_stream,
        share_download=s_dl,
        availability=availability,
    )


CASES = [
    ("dueño ve/reproduce/descarga su copia privada", OWNER, "can total", facts(), {"view": True, "stream": True, "download": True}),
    ("ajeno en copia privada sin share: nada", OTHER, "denied", facts(), {"view": False, "stream": False, "download": False}),
    ("ajeno en copia PUBLIC: ve y reproduce; no descarga", OTHER, "public", facts(visibility="PUBLIC"), {"view": True, "stream": True, "download": False}),
    ("ajeno en copia PUBLIC con descarga pública autorizada", OTHER, "public-dl", facts(visibility="PUBLIC", public_dl=True), {"view": True, "stream": True, "download": True}),
    ("ajeno con share stream (privada): ve y reproduce; no descarga", OTHER, "share-stream", facts(s_stream=True), {"view": True, "stream": True, "download": False}),
    ("ajeno con share download (privada): ve y descarga; no reproduce", OTHER, "share-dl", facts(s_dl=True), {"view": True, "stream": False, "download": True}),
    ("ajeno con share download en PUBLIC sin public_download: sí descarga por share", OTHER, "public-share-dl", facts(visibility="PUBLIC", s_dl=True), {"view": True, "stream": True, "download": True}),
    ("copia MISSING: ni dueño entrega bytes", OWNER, "missing", facts(availability="MISSING"), {"view": True, "stream": False, "download": False}),
    ("copia con ERROR: ajeno no entrega bytes aunque sea PUBLIC", OTHER, "error", facts(visibility="PUBLIC", availability="ERROR"), {"view": True, "stream": False, "download": False}),
    ("admin hipotético (id 99) sin dueño ni share ni PUBLIC: nada", 99, "admin-no-bypass", facts(), {"view": False, "stream": False, "download": False}),
    ("admin como dueño: todo", 99, "admin-owner", facts(owner=99), {"view": True, "stream": True, "download": True}),
    ("admin como destinatario autorizado: share manda", 99, "admin-share", facts(s_stream=True), {"view": True, "stream": True, "download": False}),
    ("PUBLIC con descarga pública aplica también a quien no tenga cuenta conocida", 777, "public-dl-any", facts(visibility="PUBLIC", public_dl=True), {"view": True, "stream": True, "download": True}),
]


def main() -> int:
    failures = 0
    for label, actor, _name, f, expected in CASES:
        for action, want in expected.items():
            got = can(actor_user_id=actor, action=action, facts=f)  # type: ignore[arg-type]
            ok = got == want
            if not ok:
                failures += 1
            print(f"  {'ok  ' if ok else 'FALLO'} {label}: {action}={'si' if got else 'no'} (esperado {'si' if want else 'no'})")
    print()
    if failures:
        print(f"Verificación de permisos: {failures} fallo(s).", file=sys.stderr)
        return 1
    print(f"Verificación de permisos: {len(CASES)} escenarios correctos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
