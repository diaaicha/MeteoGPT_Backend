# ============================================================
# MeteoGPT — Audit des anciens chemins Colab / Google Drive
# ============================================================
#
# IMPORTANT :
# Ce script est STRICTEMENT EN LECTURE.
#
# Il ne modifie :
# - aucun fichier Python ;
# - aucun fichier JSON ;
# - aucun payload Qdrant ;
# - aucune image ;
# - aucun PDF ;
# - aucun embedding.
#
# ============================================================

from pathlib import Path
import json

from qdrant_client import QdrantClient


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

QDRANT_PATH = DATA_DIR / "qdrant"

QDRANT_COLLECTION = "meteogpt_api_chunks"


# Motifs historiques à rechercher.
OLD_PATTERNS = [
    "/content/drive/MyDrive/MeteoGPT",
    "/content/meteogpt",
    "/content/",
    "MyDrive",
    "data/chroma/vector_db",
]


# ============================================================
# 2. OUTILS
# ============================================================

def contient_ancien_chemin(value):
    """
    Retourne les motifs anciens trouvés dans une chaîne.
    """

    if not isinstance(value, str):
        return []

    normalized = value.replace("\\", "/")

    return [
        pattern
        for pattern in OLD_PATTERNS
        if pattern in normalized
    ]


def parcourir_json(obj, path="$"):
    """
    Parcourt récursivement un objet JSON.

    Retourne les chaînes contenant
    un ancien chemin Colab / Drive.
    """

    resultats = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            child_path = f"{path}.{key}"

            resultats.extend(
                parcourir_json(
                    value,
                    child_path
                )
            )

    elif isinstance(obj, list):

        for index, value in enumerate(obj):

            child_path = (
                f"{path}[{index}]"
            )

            resultats.extend(
                parcourir_json(
                    value,
                    child_path
                )
            )

    elif isinstance(obj, str):

        motifs = contient_ancien_chemin(
            obj
        )

        if motifs:

            resultats.append(
                {
                    "json_path":
                        path,

                    "value":
                        obj,

                    "patterns":
                        motifs,
                }
            )

    return resultats


# ============================================================
# 3. AUDIT PYTHON
# ============================================================

def audit_python_files():

    print()
    print("=" * 100)
    print("AUDIT DES FICHIERS PYTHON")
    print("=" * 100)

    total_occurrences = 0
    fichiers_concernes = 0

    python_files = sorted(
        PROJECT_ROOT.rglob("*.py")
    )

    for python_file in python_files:

        # Ne jamais analyser l'environnement virtuel.
        if ".venv" in python_file.parts:
            continue

        try:

            lines = python_file.read_text(
                encoding="utf-8"
            ).splitlines()

        except Exception as exc:

            print(
                f"[IGNORÉ] {python_file} : {exc}"
            )

            continue

        matches = []

        for line_number, line in enumerate(
            lines,
            start=1
        ):

            motifs = contient_ancien_chemin(
                line
            )

            if motifs:

                matches.append(
                    {
                        "line":
                            line_number,

                        "text":
                            line.strip(),

                        "patterns":
                            motifs,
                    }
                )

        if not matches:
            continue

        fichiers_concernes += 1
        total_occurrences += len(matches)

        relative_path = (
            python_file.relative_to(
                PROJECT_ROOT
            )
        )

        print()
        print(
            f"[PY] {relative_path}"
        )

        for match in matches:

            print(
                f"  L{match['line']} "
                f"-> {match['text']}"
            )

    print()
    print(
        "Fichiers Python concernés :",
        fichiers_concernes
    )

    print(
        "Occurrences détectées     :",
        total_occurrences
    )

    return {
        "files":
            fichiers_concernes,

        "occurrences":
            total_occurrences,
    }


# ============================================================
# 4. AUDIT JSON
# ============================================================

def audit_json_files():

    print()
    print("=" * 100)
    print("AUDIT DES FICHIERS JSON")
    print("=" * 100)

    total_occurrences = 0
    fichiers_concernes = 0

    json_files = sorted(
        DATA_DIR.rglob("*.json")
    )

    for json_file in json_files:

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as file:

                obj = json.load(
                    file
                )

        except Exception as exc:

            print(
                f"[IGNORÉ] {json_file} : {exc}"
            )

            continue

        matches = parcourir_json(
            obj
        )

        if not matches:
            continue

        fichiers_concernes += 1
        total_occurrences += len(matches)

        relative_path = (
            json_file.relative_to(
                PROJECT_ROOT
            )
        )

        print()
        print(
            f"[JSON] {relative_path}"
        )

        for match in matches:

            print(
                f"  {match['json_path']}"
            )

            print(
                f"    -> {match['value']}"
            )

    print()
    print(
        "Fichiers JSON concernés :",
        fichiers_concernes
    )

    print(
        "Valeurs concernées       :",
        total_occurrences
    )

    return {
        "files":
            fichiers_concernes,

        "occurrences":
            total_occurrences,
    }


# ============================================================
# 5. AUDIT QDRANT
# ============================================================

def audit_qdrant():

    print()
    print("=" * 100)
    print("AUDIT DES PAYLOADS QDRANT")
    print("=" * 100)

    if not QDRANT_PATH.exists():

        print(
            "Qdrant introuvable :",
            QDRANT_PATH
        )

        return {
            "points_scanned": 0,
            "points_affected": 0,
            "occurrences": 0,
        }

    client = QdrantClient(
        path=str(
            QDRANT_PATH
        )
    )

    scanned_points = 0
    affected_points = 0
    total_occurrences = 0

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

                scanned_points += 1

                payload = (
                    point.payload
                    or {}
                )

                matches = parcourir_json(
                    payload,
                    path="$payload"
                )

                if not matches:
                    continue

                affected_points += 1
                total_occurrences += len(
                    matches
                )

                print()
                print(
                    f"[QDRANT] point={point.id}"
                )

                for match in matches:

                    print(
                        f"  {match['json_path']}"
                    )

                    print(
                        f"    -> {match['value']}"
                    )

            if next_offset is None:
                break

            offset = next_offset

    finally:

        client.close()

    print()
    print(
        "Points analysés       :",
        scanned_points
    )

    print(
        "Points concernés      :",
        affected_points
    )

    print(
        "Valeurs concernées    :",
        total_occurrences
    )

    return {
        "points_scanned":
            scanned_points,

        "points_affected":
            affected_points,

        "occurrences":
            total_occurrences,
    }


# ============================================================
# 6. MAIN
# ============================================================

def main():

    print("=" * 100)
    print(
        "METEOGPT — AUDIT COLAB / GOOGLE DRIVE"
    )
    print("=" * 100)

    print(
        "Projet :",
        PROJECT_ROOT
    )

    print()
    print(
        "MODE : LECTURE SEULE — "
        "AUCUNE MODIFICATION"
    )

    python_result = (
        audit_python_files()
    )

    json_result = (
        audit_json_files()
    )

    qdrant_result = (
        audit_qdrant()
    )

    print()
    print("=" * 100)
    print("RÉSUMÉ GLOBAL")
    print("=" * 100)

    print(
        "Python :",
        python_result
    )

    print(
        "JSON   :",
        json_result
    )

    print(
        "Qdrant :",
        qdrant_result
    )

    print()
    print(
        "✓ AUDIT TERMINÉ."
    )

    print(
        "✓ AUCUN FICHIER MODIFIÉ."
    )

    print(
        "✓ AUCUN PAYLOAD QDRANT MODIFIÉ."
    )

    print("=" * 100)


if __name__ == "__main__":
    main()