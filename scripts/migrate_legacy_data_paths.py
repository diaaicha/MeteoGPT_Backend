# ============================================================
# MeteoGPT — Migration des chemins Colab / Drive
# Données persistées uniquement
#
# Cibles :
# - JSON sous data/
# - payloads de la collection Qdrant
#
# Ne modifie PAS les fichiers .py.
# ============================================================

from pathlib import Path
from datetime import datetime
import copy
import json
import shutil

from qdrant_client import QdrantClient


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

QDRANT_PATH = DATA_DIR / "qdrant"

QDRANT_COLLECTION = "meteogpt_api_chunks"


OLD_ROOT = (
    "/content/drive/MyDrive/MeteoGPT"
)

OLD_QDRANT_ROOT = (
    "/content/drive/MyDrive/MeteoGPT/"
    "data/chroma/vector_db/qdrant_local"
)

NEW_QDRANT_RELATIVE = "data/qdrant"


# ------------------------------------------------------------
# IMPORTANT
# ------------------------------------------------------------
# True  = simulation uniquement
# False = migration réelle
# ------------------------------------------------------------

DRY_RUN = False


TIMESTAMP = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

BACKUP_ROOT = (
    PROJECT_ROOT
    / "backups"
    / "path_migration"
    / TIMESTAMP
)


# ============================================================
# 2. CONVERSION D'UNE CHAÎNE
# ============================================================

def migrate_string(value):
    """
    Transforme les anciens chemins MeteoGPT en chemins
    relatifs et portables.

    Cas particulier :
    ancien stockage Qdrant -> data/qdrant
    """

    if not isinstance(value, str):
        return value

    normalized = value.replace(
        "\\",
        "/"
    )

    # ========================================================
    # CAS SPÉCIAL : QDRANT
    # ========================================================

    if normalized == OLD_QDRANT_ROOT:

        return NEW_QDRANT_RELATIVE

    qdrant_prefix = (
        OLD_QDRANT_ROOT.rstrip("/")
        + "/"
    )

    if normalized.startswith(
        qdrant_prefix
    ):

        suffix = normalized[
            len(qdrant_prefix):
        ]

        return (
            NEW_QDRANT_RELATIVE
            + "/"
            + suffix
        )

    # ========================================================
    # RACINE METEOGPT CLASSIQUE
    # ========================================================

    old_prefix = (
        OLD_ROOT.rstrip("/")
        + "/"
    )

    if normalized.startswith(
        old_prefix
    ):

        return normalized[
            len(old_prefix):
        ]

    if normalized == OLD_ROOT:

        return "."

    return value


# ============================================================
# 3. MIGRATION RÉCURSIVE
# ============================================================

def migrate_object(obj):

    if isinstance(obj, str):

        return migrate_string(
            obj
        )

    if isinstance(obj, list):

        return [
            migrate_object(item)
            for item in obj
        ]

    if isinstance(obj, dict):

        return {
            key:
                migrate_object(value)

            for key, value
            in obj.items()
        }

    return obj


# ============================================================
# 4. DÉTECTION
# ============================================================

def contains_legacy_path(obj):

    if isinstance(obj, str):

        normalized = obj.replace(
            "\\",
            "/"
        )

        return (
            OLD_ROOT in normalized
        )

    if isinstance(obj, list):

        return any(
            contains_legacy_path(item)
            for item in obj
        )

    if isinstance(obj, dict):

        return any(
            contains_legacy_path(value)
            for value in obj.values()
        )

    return False


# ============================================================
# 5. BACKUP QDRANT
# ============================================================

def backup_qdrant():

    if DRY_RUN:
        return None

    if not QDRANT_PATH.exists():

        raise FileNotFoundError(
            f"Qdrant introuvable : "
            f"{QDRANT_PATH}"
        )

    destination = (
        BACKUP_ROOT
        / "qdrant"
    )

    print()
    print(
        "Backup Qdrant ->",
        destination
    )

    shutil.copytree(
        QDRANT_PATH,
        destination
    )

    return destination


# ============================================================
# 6. MIGRATION JSON
# ============================================================

def migrate_json_files():

    print()
    print("=" * 100)
    print("MIGRATION JSON")
    print("=" * 100)

    affected_files = 0
    affected_values = 0

    json_files = sorted(
        DATA_DIR.rglob("*.json")
    )

    for json_file in json_files:

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as f:

                original = json.load(f)

        except Exception as exc:

            print(
                "[IGNORÉ]",
                json_file,
                "->",
                exc
            )

            continue

        migrated = migrate_object(
            copy.deepcopy(
                original
            )
        )

        if migrated == original:
            continue

        affected_files += 1

        # Compter les valeurs affectées
        original_text = json.dumps(
            original,
            ensure_ascii=False
        )

        occurrences = (
            original_text.count(
                OLD_ROOT
            )
        )

        affected_values += (
            occurrences
        )

        relative_path = (
            json_file.relative_to(
                PROJECT_ROOT
            )
        )

        print(
            f"{relative_path} "
            f"-> {occurrences} valeur(s)"
        )

        if DRY_RUN:
            continue

        # ====================================================
        # BACKUP
        # ====================================================

        backup_file = (
            BACKUP_ROOT
            / "json"
            / relative_path
        )

        backup_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            json_file,
            backup_file
        )

        # ====================================================
        # ÉCRITURE ATOMIQUE
        # ====================================================

        temp_file = (
            json_file.parent
            / (
                json_file.name
                + ".migration.tmp"
            )
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                migrated,
                f,
                ensure_ascii=False,
                indent=2
            )

        temp_file.replace(
            json_file
        )

    print()
    print(
        "Fichiers JSON concernés :",
        affected_files
    )

    print(
        "Valeurs concernées       :",
        affected_values
    )

    return {
        "files":
            affected_files,

        "values":
            affected_values,
    }


# ============================================================
# 7. MIGRATION QDRANT
# ============================================================

def migrate_qdrant_payloads():

    print()
    print("=" * 100)
    print("MIGRATION QDRANT")
    print("=" * 100)

    client = QdrantClient(
        path=str(
            QDRANT_PATH
        )
    )

    scanned = 0
    affected = 0
    affected_values = 0

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

                scanned += 1

                payload = (
                    point.payload
                    or {}
                )

                migrated_payload = (
                    migrate_object(
                        copy.deepcopy(
                            payload
                        )
                    )
                )

                if (
                    migrated_payload
                    ==
                    payload
                ):
                    continue

                affected += 1

                # Le corpus actuel contient
                # principalement image_path.
                payload_text = json.dumps(
                    payload,
                    ensure_ascii=False
                )

                affected_values += (
                    payload_text.count(
                        OLD_ROOT
                    )
                )

                if DRY_RUN:

                    continue

                client.set_payload(
                    collection_name=
                        QDRANT_COLLECTION,

                    payload=
                        migrated_payload,

                    points=[
                        point.id
                    ]
                )

            if next_offset is None:
                break

            offset = next_offset

    finally:

        client.close()

    print()
    print(
        "Points analysés   :",
        scanned
    )

    print(
        "Points concernés  :",
        affected
    )

    print(
        "Valeurs concernées:",
        affected_values
    )

    return {
        "scanned":
            scanned,

        "affected":
            affected,

        "values":
            affected_values,
    }


# ============================================================
# 8. AUDIT FINAL
# ============================================================

def audit_remaining_json():

    remaining = []

    for json_file in sorted(
        DATA_DIR.rglob("*.json")
    ):

        try:

            content = (
                json_file.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            continue

        count = content.count(
            OLD_ROOT
        )

        if count:

            remaining.append(
                (
                    json_file.relative_to(
                        PROJECT_ROOT
                    ),
                    count
                )
            )

    return remaining


def audit_remaining_qdrant():

    client = QdrantClient(
        path=str(
            QDRANT_PATH
        )
    )

    remaining = 0

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

                payload = json.dumps(
                    point.payload or {},
                    ensure_ascii=False
                )

                remaining += (
                    payload.count(
                        OLD_ROOT
                    )
                )

            if next_offset is None:
                break

            offset = next_offset

    finally:

        client.close()

    return remaining


# ============================================================
# 9. MAIN
# ============================================================

def main():

    print("=" * 100)
    print(
        "METEOGPT — MIGRATION "
        "DES CHEMINS DE DONNÉES"
    )
    print("=" * 100)

    print(
        "PROJECT_ROOT :",
        PROJECT_ROOT
    )

    print(
        "DRY_RUN      :",
        DRY_RUN
    )

    print()

    if not DRY_RUN:

        BACKUP_ROOT.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_qdrant()

    json_result = (
        migrate_json_files()
    )

    qdrant_result = (
        migrate_qdrant_payloads()
    )

    print()
    print("=" * 100)
    print("RÉSUMÉ")
    print("=" * 100)

    print(
        "JSON   :",
        json_result
    )

    print(
        "Qdrant :",
        qdrant_result
    )

    if DRY_RUN:

        print()
        print(
            "✓ DRY RUN TERMINÉ."
        )

        print(
            "✓ AUCUNE DONNÉE MODIFIÉE."
        )

    else:

        remaining_json = (
            audit_remaining_json()
        )

        remaining_qdrant = (
            audit_remaining_qdrant()
        )

        print()
        print(
            "Chemins Drive restants JSON :",
            sum(
                count
                for _, count
                in remaining_json
            )
        )

        print(
            "Chemins Drive restants Qdrant :",
            remaining_qdrant
        )

        print()
        print(
            "Backup :",
            BACKUP_ROOT
        )

        if (
            not remaining_json
            and
            remaining_qdrant == 0
        ):

            print()
            print(
                "✓ MIGRATION DES DONNÉES "
                "RÉUSSIE."
            )

        else:

            print()
            print(
                "⚠ Des chemins Drive "
                "subsistent."
            )

    print("=" * 100)


if __name__ == "__main__":
    main()