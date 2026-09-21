# ============================================================
# MeteoGPT — Validation des équivalents locaux des chemins Drive
# ============================================================
#
# LECTURE SEULE.
# Aucune donnée n'est modifiée.
# ============================================================

from pathlib import Path
from collections import Counter, defaultdict
import json

from qdrant_client import QdrantClient


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

QDRANT_PATH = DATA_DIR / "qdrant"

QDRANT_COLLECTION = "meteogpt_api_chunks"

OLD_ROOT = "/content/drive/MyDrive/MeteoGPT"


# ============================================================
# OUTILS
# ============================================================

def convertir_ancien_chemin(value):
    """
    Convertit uniquement conceptuellement un ancien chemin
    Drive en chemin relatif MeteoGPT.

    Aucune écriture n'est effectuée.
    """

    if not isinstance(value, str):
        return None

    normalized = value.replace("\\", "/")

    old_root = OLD_ROOT.rstrip("/")

    if normalized == old_root:
        return Path(".")

    prefix = old_root + "/"

    if not normalized.startswith(prefix):
        return None

    relative_value = normalized[len(prefix):]

    return Path(relative_value)


def parcourir_objet(obj, json_path="$"):
    """
    Recherche récursivement les chaînes utilisant OLD_ROOT.
    """

    results = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            results.extend(
                parcourir_objet(
                    value,
                    f"{json_path}.{key}"
                )
            )

    elif isinstance(obj, list):

        for index, value in enumerate(obj):

            results.extend(
                parcourir_objet(
                    value,
                    f"{json_path}[{index}]"
                )
            )

    elif isinstance(obj, str):

        relative_path = convertir_ancien_chemin(
            obj
        )

        if relative_path is not None:

            local_path = (
                PROJECT_ROOT
                / relative_path
            )

            results.append(
                {
                    "json_path":
                        json_path,

                    "old_value":
                        obj,

                    "relative_path":
                        relative_path.as_posix(),

                    "local_path":
                        local_path,

                    "exists":
                        local_path.exists(),
                }
            )

    return results


def categorie_chemin(relative_path):
    """
    Regroupe les chemins par zone principale du projet.
    """

    path = Path(relative_path)

    parts = path.parts

    if not parts:
        return "autre"

    if len(parts) >= 3 and parts[:3] == (
        "data",
        "extracted",
        "api"
    ):

        if len(parts) >= 4:
            return (
                "data/extracted/api/"
                + parts[3]
            )

    if len(parts) >= 3 and parts[:3] == (
        "data",
        "processed",
        "api"
    ):

        if len(parts) >= 4:
            return (
                "data/processed/api/"
                + parts[3]
            )

    if len(parts) >= 3 and parts[:3] == (
        "data",
        "raw",
        "api"
    ):

        if len(parts) >= 4:
            return (
                "data/raw/api/"
                + parts[3]
            )

    if parts[0] == "data":
        return "data/autre"

    return parts[0]


# ============================================================
# AUDIT JSON
# ============================================================

def analyser_json():

    print()
    print("=" * 100)
    print("VALIDATION DES CHEMINS JSON")
    print("=" * 100)

    occurrences = 0

    unique_paths = {}

    categories = Counter()

    json_files_affected = Counter()

    for json_file in sorted(
        DATA_DIR.rglob("*.json")
    ):

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as f:

                obj = json.load(f)

        except Exception as exc:

            print(
                f"[IGNORÉ] {json_file} -> {exc}"
            )

            continue

        results = parcourir_objet(
            obj
        )

        if not results:
            continue

        relative_json = json_file.relative_to(
            PROJECT_ROOT
        )

        json_files_affected[
            str(relative_json)
        ] += len(results)

        for result in results:

            occurrences += 1

            relative_path = result[
                "relative_path"
            ]

            unique_paths[
                relative_path
            ] = result

            categories[
                categorie_chemin(
                    relative_path
                )
            ] += 1

    existing_unique = [
        item
        for item in unique_paths.values()
        if item["exists"]
    ]

    missing_unique = [
        item
        for item in unique_paths.values()
        if not item["exists"]
    ]

    print()
    print("Occurrences totales :", occurrences)
    print("Chemins uniques      :", len(unique_paths))
    print(
        "Chemins locaux OK    :",
        len(existing_unique)
    )
    print(
        "Chemins locaux ABSENTS :",
        len(missing_unique)
    )

    print()
    print("-" * 100)
    print("RÉPARTITION PAR DOSSIER")
    print("-" * 100)

    for category, count in sorted(
        categories.items()
    ):

        print(
            f"{category:<50} {count}"
        )

    print()
    print("-" * 100)
    print("JSON CONCERNÉS")
    print("-" * 100)

    for filename, count in sorted(
        json_files_affected.items()
    ):

        print(
            f"{filename:<75} {count}"
        )

    print()
    print("-" * 100)
    print("CHEMINS UNIQUES ABSENTS")
    print("-" * 100)

    if not missing_unique:

        print(
            "✓ Tous les chemins Drive ont "
            "un équivalent local."
        )

    else:

        for item in sorted(
            missing_unique,
            key=lambda x:
                x["relative_path"]
        ):

            print()
            print(
                "Drive    :",
                item["old_value"]
            )

            print(
                "Relatif  :",
                item["relative_path"]
            )

            print(
                "Local    :",
                item["local_path"]
            )

    return {
        "occurrences":
            occurrences,

        "unique":
            len(unique_paths),

        "existing":
            len(existing_unique),

        "missing":
            len(missing_unique),
    }


# ============================================================
# AUDIT QDRANT
# ============================================================

def analyser_qdrant():

    print()
    print("=" * 100)
    print("VALIDATION DES CHEMINS QDRANT")
    print("=" * 100)

    client = QdrantClient(
        path=str(QDRANT_PATH)
    )

    points_scanned = 0

    affected_points = 0

    occurrences = 0

    unique_paths = {}

    offset = None

    try:

        while True:

            points, next_offset = (
                client.scroll(
                    collection_name=
                        QDRANT_COLLECTION,

                    offset=
                        offset,

                    limit=
                        100,

                    with_payload=
                        True,

                    with_vectors=
                        False
                )
            )

            for point in points:

                points_scanned += 1

                payload = (
                    point.payload
                    or {}
                )

                results = parcourir_objet(
                    payload,
                    "$payload"
                )

                if not results:
                    continue

                affected_points += 1

                for result in results:

                    occurrences += 1

                    unique_paths[
                        result["relative_path"]
                    ] = result

            if next_offset is None:
                break

            offset = next_offset

    finally:

        client.close()

    missing = [
        item
        for item in unique_paths.values()
        if not item["exists"]
    ]

    existing = [
        item
        for item in unique_paths.values()
        if item["exists"]
    ]

    print()
    print(
        "Points analysés        :",
        points_scanned
    )

    print(
        "Points concernés       :",
        affected_points
    )

    print(
        "Occurrences            :",
        occurrences
    )

    print(
        "Chemins uniques        :",
        len(unique_paths)
    )

    print(
        "Chemins locaux OK      :",
        len(existing)
    )

    print(
        "Chemins locaux ABSENTS :",
        len(missing)
    )

    if missing:

        print()
        print("-" * 100)
        print("CHEMINS QDRANT ABSENTS")
        print("-" * 100)

        for item in sorted(
            missing,
            key=lambda x:
                x["relative_path"]
        ):

            print(
                item["relative_path"]
            )

    return {
        "points_scanned":
            points_scanned,

        "points_affected":
            affected_points,

        "occurrences":
            occurrences,

        "unique":
            len(unique_paths),

        "existing":
            len(existing),

        "missing":
            len(missing),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)
    print(
        "METEOGPT — VALIDATION "
        "DRIVE -> BACKEND LOCAL"
    )
    print("=" * 100)

    print(
        "PROJECT_ROOT :",
        PROJECT_ROOT
    )

    print()
    print(
        "MODE : LECTURE SEULE"
    )

    json_result = analyser_json()

    qdrant_result = analyser_qdrant()

    print()
    print("=" * 100)
    print("RÉSUMÉ FINAL")
    print("=" * 100)

    print(
        "JSON   :",
        json_result
    )

    print(
        "Qdrant :",
        qdrant_result
    )

    print()

    if (
        json_result["missing"] == 0
        and
        qdrant_result["missing"] == 0
    ):

        print(
            "✓ Tous les anciens chemins Drive "
            "ont un équivalent local."
        )

        print(
            "✓ Migration des données possible."
        )

    else:

        print(
            "⚠ Certains fichiers référencés sur "
            "Drive sont absents du backend."
        )

        print(
            "⚠ Ne pas lancer la migration avant "
            "d'avoir traité ces chemins."
        )

    print()
    print(
        "✓ AUCUNE DONNÉE MODIFIÉE."
    )

    print("=" * 100)


if __name__ == "__main__":
    main()