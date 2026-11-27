"""Consulta real mínima: python -m scripts.check_musicbrainz [título] [artista]."""
import sys

from app.integrations.catalog.contract import CatalogError
from app.services.external_catalog import search, lookup


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--lookup":
            record = lookup("musicbrainz", sys.argv[2])
            print(f"MusicBrainz lookup: {record.provider_id} - {record.title}; {len(record.releases)} ediciones conocidas")
            return 0
        result = search("musicbrainz", title=sys.argv[1] if len(sys.argv) > 1 else "Clair de lune",
                        artist=sys.argv[2] if len(sys.argv) > 2 else "Claude Debussy", cursor=None, limit=5)
    except CatalogError as error:
        print(f"Consulta no completada: {error}")
        return 1
    print(f"MusicBrainz: {len(result['items'])} registros consultados; origen={result['origin']}")
    for item in result["items"]:
        print(f"  {item['provider_id']} - {item['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
