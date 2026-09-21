# ============================================================
# MeteoGPT — Pipeline d'actualisation API
# Fichier exportable pour backend / VS Code
# ============================================================

import json
import csv
import re
import uuid
import hashlib
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)
# ============================================================
# CONFIGURATION
# ============================================================

class MeteoGPTApiConfig:
    """
    Configuration centrale du pipeline d'actualisation API MeteoGPT.
    """

    def __init__(
        self,
        root_dir: Optional[str] = None,
        api_url: str = "http://213.154.77.59:8000/mat/api_meteo.php",
        collection_name: str = "meteogpt_api_chunks"
    ):

        self.root_dir = (
            PROJECT_ROOT
            if root_dir is None
            else Path(root_dir).resolve()
        )

        self.api_url = api_url

        self.collection_name = collection_name

        # ----------------------------------------------------
        # Données brutes API
        # ----------------------------------------------------

        self.raw_api_dir = (
            self.root_dir /
            "data/raw/api"
        )

        self.raw_api_pdf_dir = (
            self.raw_api_dir /
            "pdf"
        )

        self.api_registry_file = (
            self.raw_api_dir /
            "api_bulletins.csv"
        )

        # ----------------------------------------------------
        # Données extraites API
        # ----------------------------------------------------

        self.extracted_api_dir = (
            self.root_dir /
            "data/extracted/api"
        )

        self.text_units_file = (
            self.extracted_api_dir /
            "texts/text_units_api.json"
        )

        self.visual_units_file = (
            self.extracted_api_dir /
            "visuals/visual_units/visual_units_api.json"
        )

        self.page_image_units_file = (
            self.extracted_api_dir /
            "page_image_units/page_image_units_api.json"
        )

        self.document_units_file = (
            self.extracted_api_dir /
            "document_units/document_units_api.json"
        )

        self.chunks_file = (
            self.extracted_api_dir /
            "chunks/chunks_api.json"
        )

        # ----------------------------------------------------
        # Données traitées API
        # ----------------------------------------------------

        self.processed_api_dir = (
            self.root_dir /
            "data/processed/api"
        )

        self.embeddings_file = (
            self.processed_api_dir /
            "embeddings/embeddings_api.json"
        )

        # ----------------------------------------------------
        # Qdrant local
        # ----------------------------------------------------

        self.qdrant_dir = (
            self.root_dir
            / "data"
            / "qdrant"
        )

        self.qdrant_audit_dir = (
            self.root_dir
            / "data"
            / "extracted"
            / "qdrant"
            / "vector_db"
            / "audit"
        )
        self.qdrant_audit_file = (
            self.qdrant_audit_dir /
            "qdrant_index_audit_api.json"
        )

        # ----------------------------------------------------
        # Logs
        # ----------------------------------------------------

        self.logs_dir = (
            self.root_dir
            / "logs"
            / "api_updates"
        )
        self.ensure_directories()


    def ensure_directories(self):
        """
        Crée les répertoires nécessaires au pipeline.
        """

        directories = [
            self.raw_api_dir,
            self.raw_api_pdf_dir,
            self.extracted_api_dir,
            self.processed_api_dir,
            self.embeddings_file.parent,
            self.qdrant_dir,
            self.qdrant_audit_dir,
            self.logs_dir
        ]

        for directory in directories:

            directory.mkdir(
                parents=True,
                exist_ok=True
            )


# ============================================================
# LOGGING
# ============================================================

def setup_logger(config: MeteoGPTApiConfig) -> logging.Logger:
    """
    Configure le logger du pipeline.
    """

    logger = logging.getLogger(
        "meteogpt_update_api_pipeline"
    )

    logger.setLevel(
        logging.INFO
    )

    if logger.handlers:

        return logger

    log_file = (
        config.logs_dir /
        f"update_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8"
    )

    file_handler.setFormatter(
        formatter
    )

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        file_handler
    )

    logger.addHandler(
        console_handler
    )

    return logger


# ============================================================
# OUTILS JSON
# ============================================================

def load_json(path: Path, default=None):
    """
    Charge un fichier JSON.
    """

    path = Path(path)

    if not path.exists():

        return default

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_json(data, path: Path):
    """
    Sauvegarde un objet Python en JSON.
    """

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def ensure_list(obj, possible_keys=None):
    """
    Convertit un objet JSON en liste.
    """

    if possible_keys is None:

        possible_keys = [
            "items",
            "data",
            "units",
            "chunks",
            "embeddings",
            "text_units",
            "visual_units",
            "page_image_units",
            "document_units"
        ]

    if obj is None:

        return []

    if isinstance(obj, list):

        return obj

    if isinstance(obj, dict):

        for key in possible_keys:

            if key in obj and isinstance(obj[key], list):

                return obj[key]

    raise TypeError(
        f"Format JSON non supporté : {type(obj)}"
    )


# ============================================================
# OUTILS IDENTIFIANTS / FICHIERS
# ============================================================

def normalize_source_file(source_file: str) -> Optional[str]:
    """
    Normalise le nom d'un fichier source.
    """

    if not source_file:

        return None

    name = Path(str(source_file)).name.lower().strip()

    name = re.sub(
        r"\.pdf$",
        "",
        name
    )

    name = re.sub(
        r"[^a-z0-9]+",
        "_",
        name
    )

    name = re.sub(
        r"_+",
        "_",
        name
    )

    return name.strip("_")


def get_source_file(item: Dict[str, Any]) -> Optional[str]:
    """
    Récupère le nom du fichier source depuis une unité.
    """

    if not isinstance(item, dict):

        return None

    metadata = item.get(
        "metadata",
        {}
    )

    return (
        item.get("source_file")
        or item.get("filename")
        or item.get("fichier")
        or metadata.get("source_file")
        or metadata.get("filename")
    )


def sha256_file(path: Path) -> str:
    """
    Calcule l'empreinte SHA256 d'un fichier.
    """

    h = hashlib.sha256()

    with open(
        path,
        "rb"
    ) as f:

        for block in iter(
            lambda: f.read(1024 * 1024),
            b""
        ):

            h.update(
                block
            )

    return h.hexdigest()


def stable_uuid(value: str) -> str:
    """
    Génère un UUID stable à partir d'une chaîne.
    """

    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            str(value)
        )
    )


# ============================================================
# FUSION INCRÉMENTALE DES JSON GLOBAUX
# ============================================================

def merge_units_by_source_file(
    existing_units: List[Dict[str, Any]],
    new_units: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Fusionne les nouvelles unités avec les unités existantes.

    Règle :
    - les unités des documents nouvellement traités remplacent
      les anciennes unités du même document ;
    - les autres unités sont conservées.
    """

    new_keys = set()

    for unit in new_units:

        source_file = get_source_file(
            unit
        )

        key = normalize_source_file(
            source_file
        )

        if key:

            new_keys.add(
                key
            )

    cleaned_existing = []

    for unit in existing_units:

        source_file = get_source_file(
            unit
        )

        key = normalize_source_file(
            source_file
        )

        if key not in new_keys:

            cleaned_existing.append(
                unit
            )

    return cleaned_existing + new_units


def update_global_json_file(
    file_path: Path,
    new_units: List[Dict[str, Any]],
    possible_keys: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Met à jour un JSON global avec les unités nouvellement produites.
    """

    existing_json = load_json(
        file_path,
        default=[]
    )

    existing_units = ensure_list(
        existing_json,
        possible_keys=possible_keys
    )

    merged_units = merge_units_by_source_file(
        existing_units,
        new_units
    )

    save_json(
        merged_units,
        file_path
    )

    return merged_units


# ============================================================
# FONCTIONS PIPELINE — API / REGISTRE / TÉLÉCHARGEMENT
# ============================================================

def interroger_api_anacim(
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Interroge l'API ANACIM et retourne la liste des bulletins disponibles.
    """

    response = requests.get(
        config.api_url,
        timeout=30
    )

    response.raise_for_status()

    data_api = response.json()

    if isinstance(data_api, list):

        bulletins_bruts = data_api

    elif isinstance(data_api, dict):

        bulletins_bruts = (
            data_api.get("bulletins")
            or data_api.get("data")
            or data_api.get("items")
            or []
        )

    else:

        raise ValueError(
            f"Format API non supporté : {type(data_api)}"
        )

    if not isinstance(bulletins_bruts, list):

        raise ValueError(
            "Format API invalide : la liste des bulletins est introuvable."
        )

    bulletins_valides = []

    for bulletin in bulletins_bruts:

        if not isinstance(bulletin, dict):

            continue

        chemin = str(
            bulletin.get("chemin", "")
        ).strip()

        if not chemin:

            continue

        bulletins_valides.append(
            {
                "chemin":
                    chemin,

                "type":
                    bulletin.get("type"),

                "evenement":
                    bulletin.get("evenement"),

                "date_modification":
                    str(
                        bulletin.get("date_modification", "")
                    ).strip()
            }
        )

    return bulletins_valides


def charger_registre_api(
    config: MeteoGPTApiConfig
) -> Dict[str, Dict[str, Any]]:
    """
    Charge le registre persistant des bulletins API.

    Le registre est indexé par le champ 'chemin'.
    """

    registre = {}

    if not config.api_registry_file.exists():

        return registre

    with open(
        config.api_registry_file,
        "r",
        encoding="utf-8",
        newline=""
    ) as f:

        reader = csv.DictReader(
            f
        )

        for row in reader:

            chemin = str(
                row.get("chemin", "")
            ).strip()

            if chemin:

                registre[
                    chemin
                ] = row

    return registre


def detecter_bulletins_a_traiter(
    bulletins_api: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Compare les bulletins de l'API avec le registre local.

    Retourne les bulletins :
    - nouveaux ;
    - modifiés ;
    - téléchargés mais non encore entièrement traités.
    """

    registre = charger_registre_api(
        config
    )

    bulletins_a_traiter = []

    for bulletin in bulletins_api:

        chemin = str(
            bulletin.get("chemin", "")
        ).strip()

        if not chemin:

            continue

        date_modification = str(
            bulletin.get("date_modification", "")
        ).strip()

        ligne_registre = registre.get(
            chemin
        )

        bulletin_copie = dict(
            bulletin
        )

        # ----------------------------------------------------
        # Cas 1 : bulletin absent du registre
        # ----------------------------------------------------

        if ligne_registre is None:

            bulletin_copie["update_status"] = "new"

            bulletins_a_traiter.append(
                bulletin_copie
            )

            continue

        ancienne_date_modification = str(
            ligne_registre.get("date_modification", "")
        ).strip()

        ancien_status = str(
            ligne_registre.get("update_status", "")
        ).strip()

        # ----------------------------------------------------
        # Cas 2 : bulletin modifié côté API
        # ----------------------------------------------------

        if date_modification != ancienne_date_modification:

            bulletin_copie["update_status"] = "modified"

            bulletins_a_traiter.append(
                bulletin_copie
            )

            continue

        # ----------------------------------------------------
        # Cas 3 : téléchargement déjà fait mais pipeline incomplet
        # ----------------------------------------------------

        if ancien_status and ancien_status != "processed":

            bulletin_copie["update_status"] = "resume_processing"

            bulletin_copie["source_file"] = ligne_registre.get(
                "source_file"
            )

            bulletin_copie["local_pdf_path"] = ligne_registre.get(
                "local_pdf_path"
            )

            bulletin_copie["sha256"] = ligne_registre.get(
                "sha256"
            )

            bulletins_a_traiter.append(
                bulletin_copie
            )

            continue

    return bulletins_a_traiter


def nom_pdf_depuis_url(
    url: str
) -> str:
    """
    Extrait un nom de fichier PDF propre depuis une URL.
    """

    from urllib.parse import urlparse, unquote

    parsed = urlparse(
        url
    )

    name = Path(
        unquote(
            parsed.path
        )
    ).name

    if not name.lower().endswith(
        ".pdf"
    ):

        name = name + ".pdf"

    name = re.sub(
        r"[^A-Za-z0-9À-ÿ ._\-]+",
        "_",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


def telecharger_un_pdf(
    url: str,
    destination: Path
) -> Path:
    """
    Télécharge un PDF depuis son URL et l'écrit sur Drive.
    """

    response = requests.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    contenu = response.content

    if not contenu:

        raise ValueError(
            f"Fichier vide téléchargé : {url}"
        )

    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    if (
        "pdf" not in content_type
        and not contenu[:4] == b"%PDF"
    ):

        raise ValueError(
            f"Le fichier téléchargé ne semble pas être un PDF : {url}"
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        destination,
        "wb"
    ) as f:

        f.write(
            contenu
        )

    return destination


def enregistrer_etat_registre_api(
    bulletins: List[Dict[str, Any]],
    config: MeteoGPTApiConfig,
    status: str
) -> None:
    """
    Met à jour le registre API avec un état donné.

    États utilisés :
    - downloaded : PDF téléchargé ;
    - processed  : pipeline complet terminé ;
    - failed     : erreur pendant le traitement.
    """

    registre = charger_registre_api(
        config
    )

    updated_at = datetime.now().isoformat(
        timespec="seconds"
    )

    for bulletin in bulletins:

        chemin = str(
            bulletin.get("chemin", "")
        ).strip()

        if not chemin:

            continue

        ancienne_ligne = registre.get(
            chemin,
            {}
        )

        source_file = (
            bulletin.get("source_file")
            or ancienne_ligne.get("source_file")
        )

        local_pdf_path = (
            bulletin.get("local_pdf_path")
            or ancienne_ligne.get("local_pdf_path")
        )

        sha256 = (
            bulletin.get("sha256")
            or ancienne_ligne.get("sha256")
        )

        downloaded_at = ancienne_ligne.get(
            "downloaded_at"
        )

        processed_at = ancienne_ligne.get(
            "processed_at"
        )

        failed_at = ancienne_ligne.get(
            "failed_at"
        )

        error_message = ancienne_ligne.get(
            "error_message"
        )

        if status == "downloaded":

            downloaded_at = updated_at

        if status == "processed":

            processed_at = updated_at
            error_message = ""

        if status == "failed":

            failed_at = updated_at
            error_message = bulletin.get(
                "error_message",
                ""
            )

        registre[
            chemin
        ] = {
            "chemin":
                chemin,

            "type":
                bulletin.get("type") or ancienne_ligne.get("type"),

            "evenement":
                bulletin.get("evenement") or ancienne_ligne.get("evenement"),

            "date_modification":
                bulletin.get("date_modification")
                or ancienne_ligne.get("date_modification"),

            "source_file":
                source_file,

            "local_pdf_path":
                local_pdf_path,

            "sha256":
                sha256,

            "update_status":
                status,

            "downloaded_at":
                downloaded_at,

            "processed_at":
                processed_at,

            "failed_at":
                failed_at,

            "error_message":
                error_message,

            "registry_updated_at":
                updated_at
        }

    config.api_registry_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = [
        "chemin",
        "type",
        "evenement",
        "date_modification",
        "source_file",
        "local_pdf_path",
        "sha256",
        "update_status",
        "downloaded_at",
        "processed_at",
        "failed_at",
        "error_message",
        "registry_updated_at"
    ]

    with open(
        config.api_registry_file,
        "w",
        encoding="utf-8",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for chemin in sorted(
            registre.keys()
        ):

            row = registre[
                chemin
            ]

            writer.writerow(
                {
                    field:
                        row.get(field, "")
                    for field in fieldnames
                }
            )


def telecharger_bulletins_api(
    bulletins_a_traiter: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> List[Path]:
    """
    Télécharge les bulletins nouveaux ou modifiés dans data/raw/api/pdf.

    Après téléchargement réussi, le registre est mis à jour avec :
    update_status = downloaded.
    """

    fichiers_telecharges = []

    erreurs = []

    for bulletin in bulletins_a_traiter:

        chemin = str(
            bulletin.get("chemin", "")
        ).strip()

        if not chemin:

            continue

        try:

            nom_pdf = nom_pdf_depuis_url(
                chemin
            )

            destination = (
                config.raw_api_pdf_dir /
                nom_pdf
            )

            # --------------------------------------------------------
            # Reprise après interruption
            # --------------------------------------------------------
            # Si le bulletin avait déjà été téléchargé lors d'une
            # exécution précédente interrompue, on réutilise le PDF
            # local au lieu de le télécharger une seconde fois.
            # --------------------------------------------------------

            is_resume = (
                bulletin.get("update_status")
                == "resume_processing"
            )

            local_pdf_reusable = (
                is_resume
                and destination.exists()
                and destination.is_file()
                and destination.stat().st_size > 0
            )


            bulletin["pdf_reused"] = bool(
                local_pdf_reusable
            )

            bulletin["pdf_downloaded_network"] = bool(
                not local_pdf_reusable
            )

            if not local_pdf_reusable:

                telecharger_un_pdf(
                    chemin,
                    destination
                )

            bulletin["source_file"] = nom_pdf

            bulletin["local_pdf_path"] = str(
                destination
            )

            bulletin["sha256"] = sha256_file(
                destination
            )

            bulletin["downloaded_at"] = datetime.now().isoformat(
                timespec="seconds"
            )

            bulletin["update_status"] = "downloaded"

            fichiers_telecharges.append(
                destination
            )

        except Exception as e:

            bulletin["update_status"] = "failed"

            bulletin["error_message"] = str(
                e
            )

            erreurs.append(
                {
                    "chemin":
                        chemin,

                    "error":
                        str(e)
                }
            )

    # --------------------------------------------------------
    # Mise à jour du registre après téléchargement
    # --------------------------------------------------------

    bulletins_reussis = [
        bulletin
        for bulletin in bulletins_a_traiter
        if bulletin.get("update_status") == "downloaded"
    ]

    bulletins_echoues = [
        bulletin
        for bulletin in bulletins_a_traiter
        if bulletin.get("update_status") == "failed"
    ]

    if bulletins_reussis:

        enregistrer_etat_registre_api(
            bulletins_reussis,
            config,
            status="downloaded"
        )

    if bulletins_echoues:

        enregistrer_etat_registre_api(
            bulletins_echoues,
            config,
            status="failed"
        )

    if erreurs:

        raise RuntimeError(
            "Erreur lors du téléchargement de certains bulletins : "
            + json.dumps(
                erreurs,
                ensure_ascii=False
            )
        )

    return fichiers_telecharges


def mettre_a_jour_registre_api(
    bulletins_a_traiter: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> None:
    """
    Marque les bulletins comme entièrement traités après succès complet
    du pipeline : extraction, chunks, embeddings et indexation Qdrant.
    """

    enregistrer_etat_registre_api(
        bulletins_a_traiter,
        config,
        status="processed"
    )

# ============================================================
# FONCTIONS PIPELINE — EXTRACTION DES UNITÉS
# ============================================================

def nettoyer_texte_simple(
    texte: str
) -> str:
    """
    Nettoie légèrement un texte extrait d'un PDF.
    """

    if texte is None:

        return ""

    texte = str(
        texte
    )

    texte = texte.replace(
        "\r",
        "\n"
    )

    texte = re.sub(
        r"\n{3,}",
        "\n\n",
        texte
    )

    texte = re.sub(
        r"[ \t]+",
        " ",
        texte
    )

    return texte.strip()


def nom_fichier_securise_api(
    nom: str
) -> str:
    """
    Produit un identifiant propre et stable à partir d'un nom.
    """

    nom = str(
        nom
    )

    nom = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        nom
    )

    nom = re.sub(
        r"_+",
        "_",
        nom
    )

    return nom.strip(
        "_"
    )


def inferer_categorie_document_api(
    source_file: str
) -> Dict[str, Any]:
    """
    Infère la catégorie et le type documentaire à partir du nom du fichier.
    """

    nom = Path(
        str(source_file)
    ).name.lower()

    if "meteo 72h" in nom or "meteo_72h" in nom:

        return {
            "category":
                "meteo_72h",

            "document_type":
                "bulletin_meteo_72h"
        }

    if "meteo matin" in nom or "meteo_matin" in nom:

        return {
            "category":
                "meteo_matin",

            "document_type":
                "bulletin_meteo_matin"
        }

    if "navigation cotiere" in nom or "navigation_cotiere" in nom:

        return {
            "category":
                "navigation_cotiere",

            "document_type":
                "bulletin_navigation_cotiere"
        }

    if "peche artisanale" in nom or "peche_artisanale" in nom or "pêche" in nom:

        return {
            "category":
                "peche_artisanale",

            "document_type":
                "bulletin_peche_artisanale"
        }

    return {
        "category":
            "autre",

        "document_type":
            "bulletin_api"
    }


def extraire_date_depuis_nom_fichier_api(
    source_file: str
) -> Optional[str]:
    """
    Extrait une date au format YYYY-MM-DD depuis un nom de fichier
    contenant une date du type JJ-MM-AAAA.
    """

    nom = Path(
        str(source_file)
    ).name

    match = re.search(
        r"(\d{2})-(\d{2})-(\d{4})",
        nom
    )

    if not match:

        return None

    jour, mois, annee = match.groups()

    return f"{annee}-{mois}-{jour}"


def inferer_validite_api(
    source_file: str,
    category: str
) -> Dict[str, Any]:
    """
    Infère les métadonnées temporelles principales à partir du nom
    et de la catégorie du bulletin.

    Les bulletins de navigation côtière peuvent ne pas avoir de date
    de fin explicite.
    """

    from datetime import datetime, timedelta

    date_publication = extraire_date_depuis_nom_fichier_api(
        source_file
    )

    if not date_publication:

        return {
            "date_publication":
                None,

            "date_debut_validite":
                None,

            "date_fin_validite":
                None
        }

    date_base = datetime.strptime(
        date_publication,
        "%Y-%m-%d"
    )

    debut = date_base.replace(
        hour=12,
        minute=0,
        second=0
    )

    if category == "meteo_72h":

        fin = debut + timedelta(
            hours=60
        )

    elif category == "meteo_matin":

        fin = debut + timedelta(
            hours=24
        )

    elif category == "peche_artisanale":

        fin = debut + timedelta(
            hours=24
        )

    elif category == "navigation_cotiere":

            fin = debut + timedelta(
                hours=24
        )

    else:

        fin = None

    return {
        "date_publication":
            date_publication,

        "date_debut_validite":
            debut.strftime(
                "%Y-%m-%d %H:%M"
            ),

        "date_fin_validite":
            (
                fin.strftime(
                    "%Y-%m-%d %H:%M"
                )
                if fin
                else None
            )
    }


def construire_text_units_api(
    pdf_paths: List[Path],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit les TextUnits des nouveaux documents API.

    Principe :
    - extraction du texte natif PDF avec PyMuPDF ;
    - une TextUnit narrative par document ;
    - conservation des métadonnées de provenance.
    """

    try:

        import pymupdf as fitz

    except ImportError:

        raise ImportError(
            "❌ PyMuPDF n'est pas installé. Exécute : !pip install -q pymupdf"
        )

    text_units = []

    for pdf_path in pdf_paths:

        pdf_path = Path(
            pdf_path
        )

        if not pdf_path.exists():

            continue

        source_file = pdf_path.name

        document_id = nom_fichier_securise_api(
            pdf_path.stem
        )

        infos_doc = inferer_categorie_document_api(
            source_file
        )

        category = infos_doc[
            "category"
        ]

        document_type = infos_doc[
            "document_type"
        ]

        infos_temps = inferer_validite_api(
            source_file,
            category
        )

        textes_pages = []

        pages = []

        with fitz.open(
            pdf_path
        ) as doc:

            total_pages = len(
                doc
            )

            for page_index in range(
                total_pages
            ):

                page = doc[
                    page_index
                ]

                texte_page = page.get_text(
                    "text"
                )

                texte_page = nettoyer_texte_simple(
                    texte_page
                )

                if texte_page:

                    pages.append(
                        page_index + 1
                    )

                    textes_pages.append(
                        texte_page
                    )

        contenu = nettoyer_texte_simple(
            "\n\n".join(
                textes_pages
            )
        )

        if not contenu:

            continue

        text_unit = {
            "text_unit_id":
                f"{document_id}_TEXT",

            "unit_id":
                f"{document_id}_TEXT",

            "type":
                "text_unit",

            "document_id":
                document_id,

            "source_file":
                source_file,

            "source_pdf":
                str(
                    pdf_path
                ),

            "category":
                category,

            "document_type":
                document_type,

            "date_publication":
                infos_temps.get(
                    "date_publication"
                ),

            "date_debut_validite":
                infos_temps.get(
                    "date_debut_validite"
                ),

            "date_fin_validite":
                infos_temps.get(
                    "date_fin_validite"
                ),

            "pages":
                pages,

            "page":
                pages[0] if pages else None,

            "content":
                contenu,

            "text_length":
                len(
                    contenu
                ),

            "created_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "processing_step":
                "3.5.9.3",

            "pipeline":
                "API_EXPORT"
        }

        text_units.append(
            text_unit
        )

    return text_units


def construire_visual_units_api(
    pdf_paths: List[Path],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit ou récupère les VisualUnits associées aux documents API.

    Dans cette version exportable, la fonction récupère les VisualUnits
    déjà existantes dans visual_units_api.json lorsqu'elles correspondent
    aux PDF traités.

    Si aucun VisualUnit n'existe pour un nouveau PDF, la fonction retourne
    une liste vide pour ce document. Le PageImageUnit garde alors la
    traçabilité multimodale complète.
    """

    source_files = {
        Path(
            pdf_path
        ).name
        for pdf_path in pdf_paths
    }

    if not config.visual_units_file.exists():

        return []

    visual_json = load_json(
        config.visual_units_file,
        default=[]
    )

    visual_units_globales = ensure_list(
        visual_json,
        possible_keys=[
            "visual_units",
            "units",
            "data",
            "documents"
        ]
    )

    visual_units_filtrees = []

    for unit in visual_units_globales:

        if not isinstance(
            unit,
            dict
        ):

            continue

        source_file = get_source_file(
            unit
        )

        if source_file in source_files:

            visual_units_filtrees.append(
                unit
            )

    return visual_units_filtrees


def construire_page_image_units_api(
    pdf_paths: List[Path],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit les PageImageUnits pour les nouveaux documents API.

    Chaque page PDF est rendue sous forme d'image PNG afin de conserver
    la page complète pour les besoins multimodaux.
    """

    try:

        import pymupdf as fitz

    except ImportError:

        raise ImportError(
            "❌ PyMuPDF n'est pas installé. Exécute : !pip install -q pymupdf"
        )

    page_images_dir = (
        config.extracted_api_dir /
        "page_images"
    )

    page_images_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    page_image_units = []

    # --------------------------------------------------------
    # Index des VisualUnits existantes par document/page
    # --------------------------------------------------------

    visual_units = construire_visual_units_api(
        pdf_paths,
        config
    )

    panels_by_document_page = {}

    for vu in visual_units:

        doc_id = (
            vu.get("document_id")
            or vu.get("document_source_id")
        )

        page = vu.get(
            "page"
        )

        if doc_id and page:

            key = (
                str(doc_id),
                int(page)
            )

            panels_by_document_page.setdefault(
                key,
                []
            ).append(
                vu
            )

    for pdf_path in pdf_paths:

        pdf_path = Path(
            pdf_path
        )

        if not pdf_path.exists():

            continue

        source_file = pdf_path.name

        document_id = nom_fichier_securise_api(
            pdf_path.stem
        )

        infos_doc = inferer_categorie_document_api(
            source_file
        )

        category = infos_doc[
            "category"
        ]

        document_type = infos_doc[
            "document_type"
        ]

        infos_temps = inferer_validite_api(
            source_file,
            category
        )

        with fitz.open(
            pdf_path
        ) as doc:

            total_pages = len(
                doc
            )

            for page_index in range(
                total_pages
            ):

                page_number = page_index + 1

                page = doc[
                    page_index
                ]

                page_text = nettoyer_texte_simple(
                    page.get_text(
                        "text"
                    )
                )

                image_name = (
                    f"{document_id}_P{page_number:02d}.png"
                )

                image_path = (
                    page_images_dir /
                    image_name
                )

                if not image_path.exists():

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(
                            2.5,
                            2.5
                        ),
                        alpha=False
                    )

                    pix.save(
                        image_path
                    )

                contains_table = bool(
                    re.search(
                        r"température|vent|direction|intensité|houle|visibilité|station|prévision",
                        page_text,
                        flags=re.IGNORECASE
                    )
                )

                contains_map = (
                    len(
                        page.get_images(
                            full=True
                        )
                    ) > 0
                )

                contains_panel = (
                    (
                        document_id,
                        page_number
                    )
                    in panels_by_document_page
                )

                multimodal_priority = (
                    3
                    if contains_table or contains_map or contains_panel
                    else 0
                )

                page_image_unit = {
                    "page_image_unit_id":
                        f"{document_id}_PAGE_{page_number:02d}",

                    "unit_id":
                        f"{document_id}_PAGE_{page_number:02d}",

                    "type":
                        "page_image_unit",

                    "document_id":
                        document_id,

                    "source_file":
                        source_file,

                    "source_pdf":
                        str(
                            pdf_path
                        ),

                    "category":
                        category,

                    "document_type":
                        document_type,

                    "date_publication":
                        infos_temps.get(
                            "date_publication"
                        ),

                    "date_debut_validite":
                        infos_temps.get(
                            "date_debut_validite"
                        ),

                    "date_fin_validite":
                        infos_temps.get(
                            "date_fin_validite"
                        ),

                    "page":
                        page_number,

                    "pages":
                        [
                            page_number
                        ],

                    "total_pages":
                        total_pages,

                    "image_path":
                        str(
                            image_path
                        ),

                    "contains_table":
                        contains_table,

                    "contains_map":
                        contains_map,

                    "contains_panel":
                        contains_panel,

                    "contains_visual_units":
                        contains_panel,

                    "multimodal_priority":
                        multimodal_priority,

                    "usage_hint":
                        (
                            "Page complète exploitable par un LLM multimodal "
                            "si le texte ou les VisualUnits ne suffisent pas."
                        ),

                    "created_at":
                        datetime.now().isoformat(
                            timespec="seconds"
                        ),

                    "processing_step":
                        "3.5.9.3",

                    "pipeline":
                        "API_EXPORT"
                }

                page_image_units.append(
                    page_image_unit
                )

    return page_image_units

# ============================================================
# FONCTIONS PIPELINE — CONSOLIDATION / CHUNKING
# ============================================================

def construire_document_units_api(
    text_units: List[Dict[str, Any]],
    visual_units: List[Dict[str, Any]],
    page_image_units: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit les DocumentUnits des documents traités.

    La consolidation se fait par source_file normalisé afin de relier :
    - TextUnits ;
    - VisualUnits ;
    - PageImageUnits.
    """

    from collections import defaultdict

    def first_non_null(values):

        for value in values:

            if value is not None and value != "":

                return value

        return None


    def unique_list(values):

        seen = set()

        result = []

        for value in values:

            if value is None or value == "":

                continue

            if value not in seen:

                seen.add(
                    value
                )

                result.append(
                    value
                )

        return result


    def collect_pages(units):

        pages = []

        for unit in units:

            page = unit.get(
                "page"
            )

            if page is not None:

                try:

                    pages.append(
                        int(page)
                    )

                except Exception:

                    pass

            pages_list = unit.get(
                "pages"
            )

            if isinstance(
                pages_list,
                list
            ):

                for p in pages_list:

                    try:

                        pages.append(
                            int(p)
                        )

                    except Exception:

                        pass

        return sorted(
            set(
                pages
            )
        )


    def collect_localities(visuals):

        localities = []

        for visual in visuals:

            localite = (
                visual.get("localite")
                or visual.get("localité")
                or visual.get("locality")
            )

            if localite:

                localities.append(
                    str(
                        localite
                    ).strip()
                )

        return unique_list(
            localities
        )


    def get_unit_id_export(unit):

        return (
            unit.get("text_unit_id")
            or unit.get("visual_unit_id")
            or unit.get("page_image_unit_id")
            or unit.get("document_unit_id")
            or unit.get("unit_id")
        )


    text_units_by_file = defaultdict(
        list
    )

    visual_units_by_file = defaultdict(
        list
    )

    page_image_units_by_file = defaultdict(
        list
    )

    for unit in text_units:

        key = normalize_source_file(
            get_source_file(
                unit
            )
        )

        if key:

            text_units_by_file[
                key
            ].append(
                unit
            )

    for unit in visual_units:

        key = normalize_source_file(
            get_source_file(
                unit
            )
        )

        if key:

            visual_units_by_file[
                key
            ].append(
                unit
            )

    for unit in page_image_units:

        key = normalize_source_file(
            get_source_file(
                unit
            )
        )

        if key:

            page_image_units_by_file[
                key
            ].append(
                unit
            )

    all_file_keys = sorted(
        set(
            text_units_by_file.keys()
        )
        |
        set(
            visual_units_by_file.keys()
        )
        |
        set(
            page_image_units_by_file.keys()
        )
    )

    document_units = []

    for file_key in all_file_keys:

        doc_text_units = text_units_by_file.get(
            file_key,
            []
        )

        doc_visual_units = visual_units_by_file.get(
            file_key,
            []
        )

        doc_page_image_units = page_image_units_by_file.get(
            file_key,
            []
        )

        all_units_doc = (
            doc_text_units
            + doc_visual_units
            + doc_page_image_units
        )

        source_file = first_non_null(
            [
                get_source_file(
                    unit
                )
                for unit in all_units_doc
            ]
        )

        if not source_file:

            continue

        document_id = nom_fichier_securise_api(
            Path(
                source_file
            ).stem
        )

        source_pdf = first_non_null(
            [
                unit.get(
                    "source_pdf"
                )
                for unit in all_units_doc
            ]
        )

        category = first_non_null(
            [
                unit.get("category")
                or unit.get("source_category")
                for unit in all_units_doc
            ]
        )

        document_type = first_non_null(
            [
                unit.get("document_type")
                or unit.get("type_document")
                for unit in all_units_doc
            ]
        )

        date_publication = first_non_null(
            [
                unit.get(
                    "date_publication"
                )
                for unit in all_units_doc
            ]
        )

        date_debut_validite = first_non_null(
            [
                unit.get(
                    "date_debut_validite"
                )
                for unit in all_units_doc
            ]
        )

        date_fin_validite = first_non_null(
            [
                unit.get(
                    "date_fin_validite"
                )
                for unit in all_units_doc
            ]
        )

        text_unit_ids = unique_list(
            [
                get_unit_id_export(
                    unit
                )
                for unit in doc_text_units
            ]
        )

        visual_unit_ids = unique_list(
            [
                get_unit_id_export(
                    unit
                )
                for unit in doc_visual_units
            ]
        )

        page_image_unit_ids = unique_list(
            [
                get_unit_id_export(
                    unit
                )
                for unit in doc_page_image_units
            ]
        )

        pages_text = collect_pages(
            doc_text_units
        )

        pages_visual = collect_pages(
            doc_visual_units
        )

        pages_images = collect_pages(
            doc_page_image_units
        )

        pages_all = sorted(
            set(
                pages_text
            )
            |
            set(
                pages_visual
            )
            |
            set(
                pages_images
            )
        )

        localities = collect_localities(
            doc_visual_units
        )

        page_image_paths = [
            unit.get(
                "image_path"
            )
            for unit in doc_page_image_units
            if unit.get(
                "image_path"
            )
        ]

        has_text = len(
            doc_text_units
        ) > 0

        has_visual_units = len(
            doc_visual_units
        ) > 0

        has_page_images = len(
            doc_page_image_units
        ) > 0

        has_tables = any(
            unit.get(
                "contains_table"
            ) is True
            for unit in doc_page_image_units
        )

        has_maps = any(
            unit.get(
                "contains_map"
            ) is True
            for unit in doc_page_image_units
        )

        has_panels = any(
            unit.get(
                "contains_panel"
            ) is True
            or unit.get(
                "contains_visual_units"
            ) is True
            for unit in doc_page_image_units
        )

        max_multimodal_priority = max(
            [
                unit.get(
                    "multimodal_priority",
                    0
                )
                for unit in doc_page_image_units
            ]
            or [
                0
            ]
        )

        primary_units = []

        if has_text:

            primary_units.append(
                "text"
            )

        if has_visual_units:

            primary_units.append(
                "visual"
            )

        secondary_units = []

        if has_page_images:

            secondary_units.append(
                "page_image"
            )

        document_unit = {
            "document_unit_id":
                document_id,

            "type":
                "document",

            "sous_type":
                "document_consolide_api",

            "document_id":
                document_id,

            "source_file":
                source_file,

            "source_file_key":
                file_key,

            "source_pdf":
                source_pdf,

            "category":
                category,

            "document_type":
                document_type,

            "date_publication":
                date_publication,

            "date_debut_validite":
                date_debut_validite,

            "date_fin_validite":
                date_fin_validite,

            "pages":
                pages_all,

            "total_pages":
                len(
                    pages_images
                ),

            "unit_references": {
                "text_unit_ids":
                    text_unit_ids,

                "visual_unit_ids":
                    visual_unit_ids,

                "page_image_unit_ids":
                    page_image_unit_ids
            },

            "resources": {
                "text_units_file":
                    str(
                        config.text_units_file
                    ),

                "visual_units_file":
                    str(
                        config.visual_units_file
                    ),

                "page_image_units_file":
                    str(
                        config.page_image_units_file
                    ),

                "page_image_paths":
                    page_image_paths
            },

            "available_modalities": {
                "text":
                    has_text,

                "visual_units":
                    has_visual_units,

                "page_images":
                    has_page_images
            },

            "multimodal_flags": {
                "has_panels":
                    has_panels,

                "has_tables":
                    has_tables,

                "has_maps":
                    has_maps,

                "max_multimodal_priority":
                    max_multimodal_priority
            },

            "document_summary": {
                "text_units_count":
                    len(
                        doc_text_units
                    ),

                "visual_units_count":
                    len(
                        doc_visual_units
                    ),

                "page_image_units_count":
                    len(
                        doc_page_image_units
                    ),

                "localities_count":
                    len(
                        localities
                    ),

                "localities":
                    localities,

                "pages_with_text":
                    pages_text,

                "pages_with_visual_units":
                    pages_visual,

                "pages_with_page_images":
                    pages_images
            },

            "retrieval": {
                "primary_units":
                    primary_units,

                "secondary_units":
                    secondary_units,

                "retrieval_strategy_hint":
                    (
                        "Utiliser d'abord les TextUnits et VisualUnits. "
                        "Charger les PageImageUnits uniquement si la question "
                        "nécessite une lecture visuelle, un tableau, une carte "
                        "ou une page complète."
                    )
            },

            "statistics": {
                "total_pages":
                    len(
                        pages_images
                    ),

                "text_units_count":
                    len(
                        doc_text_units
                    ),

                "visual_units_count":
                    len(
                        doc_visual_units
                    ),

                "page_image_units_count":
                    len(
                        doc_page_image_units
                    )
            },

            "provenance": {
                "pipeline":
                    "API_EXPORT",

                "processing_step":
                    "3.5.9.3",

                "created_at":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "construction":
                    "consolidation_by_normalized_source_file"
            }
        }

        document_units.append(
            document_unit
        )

    return document_units



def construire_chunks_api(
    text_units: List[Dict[str, Any]],
    visual_units: List[Dict[str, Any]],
    page_image_units: List[Dict[str, Any]],
    document_units: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit les chunks RAG des documents traités.

    Stratégie retenue :
    - TextChunks : contenu narratif principal ;
    - VisualChunks : panneaux météorologiques structurés ;
    - PageImageChunks : références vers images complètes de pages ;
    - DocumentChunks : résumé documentaire consolidé.
    """

    from collections import Counter

    CHUNK_VERSION = "1.0"

    TEXT_CHUNK_MAX_CHARS = 1500

    TEXT_CHUNK_OVERLAP_CHARS = 150

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    chunks = []

    # ========================================================
    # OUTILS INTERNES
    # ========================================================

    def nettoyer_texte_chunk(texte):

        if texte is None:

            return ""

        texte = str(
            texte
        )

        texte = texte.replace(
            "\r",
            "\n"
        )

        texte = re.sub(
            r"\n{3,}",
            "\n\n",
            texte
        )

        texte = re.sub(
            r"[ \t]+",
            " ",
            texte
        )

        return texte.strip()


    def get_unit_id_local(unit):

        return (
            unit.get("text_unit_id")
            or unit.get("visual_unit_id")
            or unit.get("page_image_unit_id")
            or unit.get("document_unit_id")
            or unit.get("unit_id")
        )


    def get_pages_local(unit):

        pages = []

        if unit.get("page") is not None:

            try:

                pages.append(
                    int(
                        unit.get("page")
                    )
                )

            except Exception:

                pass

        if isinstance(
            unit.get("pages"),
            list
        ):

            for page in unit.get("pages"):

                try:

                    pages.append(
                        int(page)
                    )

                except Exception:

                    pass

        return sorted(
            set(
                pages
            )
        )


    def first_page_local(unit):

        pages = get_pages_local(
            unit
        )

        if pages:

            return pages[0]

        return None


    def get_document_id_local(unit):

        if unit.get("document_id"):

            return unit.get(
                "document_id"
            )

        if unit.get("document_source_id"):

            return unit.get(
                "document_source_id"
            )

        source_file = get_source_file(
            unit
        )

        if source_file:

            return nom_fichier_securise_api(
                Path(
                    source_file
                ).stem
            )

        return None


    def get_category_local(unit):

        return (
            unit.get("category")
            or unit.get("source_category")
        )


    def get_document_type_local(unit):

        return (
            unit.get("document_type")
            or unit.get("type_document")
        )


    def get_text_content(unit):

        candidats = [
            "content",
            "texte",
            "text",
            "texte_structure",
            "texte_nettoye",
            "texte_combine",
            "raw_text"
        ]

        for champ in candidats:

            valeur = unit.get(
                champ
            )

            if valeur:

                return nettoyer_texte_chunk(
                    valeur
                )

        return ""


    def decouper_texte_si_long(
        texte,
        max_chars=1500,
        overlap=150
    ):

        texte = nettoyer_texte_chunk(
            texte
        )

        if len(
            texte
        ) <= max_chars:

            return [
                texte
            ]

        paragraphes = [
            p.strip()
            for p in re.split(
                r"\n\s*\n",
                texte
            )
            if p.strip()
        ]

        chunks_text = []

        courant = ""

        for paragraphe in paragraphes:

            if len(
                paragraphe
            ) > max_chars:

                if courant.strip():

                    chunks_text.append(
                        courant.strip()
                    )

                    courant = ""

                start = 0

                while start < len(
                    paragraphe
                ):

                    end = start + max_chars

                    morceau = paragraphe[
                        start:end
                    ].strip()

                    if morceau:

                        chunks_text.append(
                            morceau
                        )

                    start = end - overlap

                    if start < 0:

                        start = 0

                    if start >= len(
                        paragraphe
                    ):

                        break

                continue

            if len(
                courant
            ) + len(
                paragraphe
            ) + 2 <= max_chars:

                courant = (
                    courant
                    + "\n\n"
                    + paragraphe
                ).strip()

            else:

                if courant.strip():

                    chunks_text.append(
                        courant.strip()
                    )

                courant = paragraphe

        if courant.strip():

            chunks_text.append(
                courant.strip()
            )

        return chunks_text


    def construire_metadata_base(unit):

        return {
            "date_publication":
                unit.get("date_publication"),

            "date_debut_validite":
                unit.get("date_debut_validite"),

            "date_fin_validite":
                unit.get("date_fin_validite"),

            "document_type":
                get_document_type_local(
                    unit
                ),

            "pages":
                get_pages_local(
                    unit
                ),

            "page":
                first_page_local(
                    unit
                )
        }


    # ========================================================
    # 1. TEXTCHUNKS
    # ========================================================

    for text_unit in text_units:

        if not isinstance(
            text_unit,
            dict
        ):

            continue

        unit_id = get_unit_id_local(
            text_unit
        )

        document_id = get_document_id_local(
            text_unit
        )

        source_file = get_source_file(
            text_unit
        )

        category = get_category_local(
            text_unit
        )

        content = get_text_content(
            text_unit
        )

        if not content:

            continue

        morceaux = decouper_texte_si_long(
            content,
            max_chars=TEXT_CHUNK_MAX_CHARS,
            overlap=TEXT_CHUNK_OVERLAP_CHARS
        )

        for index_morceau, morceau in enumerate(
            morceaux,
            start=1
        ):

            chunk_id = (
                f"{unit_id}"
                f"_CHUNK_"
                f"{index_morceau:03d}"
            )

            metadata = construire_metadata_base(
                text_unit
            )

            metadata.update({
                "source_unit_id":
                    unit_id,

                "source_unit_type":
                    "text_unit",

                "source_file":
                    source_file,

                "chunk_length_chars":
                    len(
                        morceau
                    ),

                "text_unit_length_chars":
                    len(
                        content
                    ),

                "split_strategy":
                    (
                        "single_text_unit"
                        if len(morceaux) == 1
                        else "paragraph_based_with_light_overlap"
                    ),

                "image_path":
                    None,

                "localite":
                    None
            })

            chunk = {
                "chunk_id":
                    chunk_id,

                "chunk_type":
                    "text",

                "unit_id":
                    unit_id,

                "unit_type":
                    "text_unit",

                "document_id":
                    document_id,

                "source_file":
                    source_file,

                "category":
                    category,

                "page":
                    metadata.get(
                        "page"
                    ),

                "content":
                    morceau,

                "retrieval_role":
                    "primary",

                "metadata":
                    metadata,

                "chunk_version":
                    CHUNK_VERSION,

                "created_at":
                    created_at,

                "processing_step":
                    "3.5.9.4",

                "pipeline":
                    "API_EXPORT"
            }

            chunks.append(
                chunk
            )

    # ========================================================
    # 2. VISUALCHUNKS
    # ========================================================

    for visual_unit in visual_units:

        if not isinstance(
            visual_unit,
            dict
        ):

            continue

        unit_id = get_unit_id_local(
            visual_unit
        )

        document_id = get_document_id_local(
            visual_unit
        )

        source_file = get_source_file(
            visual_unit
        )

        category = get_category_local(
            visual_unit
        )

        localite = (
            visual_unit.get("localite")
            or visual_unit.get("localité")
            or visual_unit.get("locality")
        )

        temperature_min = (
            visual_unit.get("temperature_min")
            or visual_unit.get("temp_min")
            or visual_unit.get("tmin")
        )

        temperature_max = (
            visual_unit.get("temperature_max")
            or visual_unit.get("temp_max")
            or visual_unit.get("tmax")
        )

        temps = (
            visual_unit.get("temps")
            or visual_unit.get("weather")
            or visual_unit.get("etat_ciel")
        )

        phenomene = (
            visual_unit.get("phenomene")
            or visual_unit.get("phénomène")
            or visual_unit.get("phenomenon")
        )

        direction_vent = (
            visual_unit.get("direction_vent")
            or visual_unit.get("vent_direction")
            or visual_unit.get("wind_direction")
        )

        intensite_vent = (
            visual_unit.get("intensite_vent")
            or visual_unit.get("intensité_vent")
            or visual_unit.get("wind_intensity")
        )

        morceaux_content = [
            "Prévision météorologique locale issue d'un panneau météo structuré."
        ]

        if localite:

            morceaux_content.append(
                f"Localité : {localite}"
            )

        if temperature_min or temperature_max:

            morceaux_content.append(
                f"Température : {temperature_min} °C / {temperature_max} °C"
            )

        if temps:

            morceaux_content.append(
                f"Temps : {temps}"
            )

        if phenomene:

            morceaux_content.append(
                f"Phénomène : {phenomene}"
            )

        if direction_vent:

            morceaux_content.append(
                f"Direction du vent : {direction_vent}"
            )

        if intensite_vent:

            morceaux_content.append(
                f"Intensité du vent : {intensite_vent}"
            )

        raw_content = (
            visual_unit.get("content")
            or visual_unit.get("texte")
            or visual_unit.get("raw_text")
        )

        if raw_content:

            morceaux_content.append(
                nettoyer_texte_chunk(
                    raw_content
                )
            )

        content = nettoyer_texte_chunk(
            " ".join(
                [
                    str(x)
                    for x in morceaux_content
                    if x is not None and str(x).strip()
                ]
            )
        )

        if not content:

            continue

        metadata = construire_metadata_base(
            visual_unit
        )

        metadata.update({
            "source_unit_id":
                unit_id,

            "source_unit_type":
                "visual_unit",

            "source_file":
                source_file,

            "localite":
                localite,

            "temperature_min":
                temperature_min,

            "temperature_max":
                temperature_max,

            "temps":
                temps,

            "phenomene":
                phenomene,

            "direction_vent":
                direction_vent,

            "intensite_vent":
                intensite_vent,

            "image_path":
                visual_unit.get(
                    "image_path"
                ),

            "bbox":
                visual_unit.get(
                    "bbox"
                )
        })

        chunk_id = (
            f"{unit_id}"
            f"_CHUNK_001"
        )

        chunk = {
            "chunk_id":
                chunk_id,

            "chunk_type":
                "visual",

            "unit_id":
                unit_id,

            "unit_type":
                "visual_unit",

            "document_id":
                document_id,

            "source_file":
                source_file,

            "category":
                category,

            "page":
                metadata.get(
                    "page"
                ),

            "content":
                content,

            "retrieval_role":
                "primary",

            "metadata":
                metadata,

            "chunk_version":
                CHUNK_VERSION,

            "created_at":
                created_at,

            "processing_step":
                "3.5.9.4",

            "pipeline":
                "API_EXPORT"
        }

        chunks.append(
            chunk
        )

    # ========================================================
    # 3. PAGEIMAGECHUNKS
    # ========================================================

    for page_unit in page_image_units:

        if not isinstance(
            page_unit,
            dict
        ):

            continue

        unit_id = get_unit_id_local(
            page_unit
        )

        document_id = get_document_id_local(
            page_unit
        )

        source_file = get_source_file(
            page_unit
        )

        category = get_category_local(
            page_unit
        )

        page = page_unit.get(
            "page"
        )

        image_path = page_unit.get(
            "image_path"
        )

        contains_table = page_unit.get(
            "contains_table"
        )

        contains_map = page_unit.get(
            "contains_map"
        )

        contains_panel = (
            page_unit.get("contains_panel")
            or page_unit.get("contains_visual_units")
        )

        content_parts = [
            f"Page complète du document {source_file}.",
            f"Catégorie : {category}.",
            f"Page : {page}.",
            (
                "Cette unité référence une image complète de page PDF "
                "pouvant être transmise à un LLM multimodal."
            )
        ]

        if contains_table:

            content_parts.append(
                "La page peut contenir un tableau ou des données structurées visuelles."
            )

        if contains_map:

            content_parts.append(
                "La page peut contenir une carte ou un contenu visuel complexe."
            )

        if contains_panel:

            content_parts.append(
                "La page contient ou peut contenir des panneaux météorologiques."
            )

        content = nettoyer_texte_chunk(
            " ".join(
                content_parts
            )
        )

        metadata = construire_metadata_base(
            page_unit
        )

        metadata.update({
            "source_unit_id":
                unit_id,

            "source_unit_type":
                "page_image_unit",

            "source_file":
                source_file,

            "image_path":
                image_path,

            "contains_table":
                contains_table,

            "contains_map":
                contains_map,

            "contains_panel":
                contains_panel,

            "multimodal_priority":
                page_unit.get(
                    "multimodal_priority"
                ),

            "localite":
                None
        })

        chunk_id = (
            f"{unit_id}"
            f"_CHUNK_001"
        )

        chunk = {
            "chunk_id":
                chunk_id,

            "chunk_type":
                "page_image",

            "unit_id":
                unit_id,

            "unit_type":
                "page_image_unit",

            "document_id":
                document_id,

            "source_file":
                source_file,

            "category":
                category,

            "page":
                page,

            "content":
                content,

            "retrieval_role":
                "secondary",

            "metadata":
                metadata,

            "chunk_version":
                CHUNK_VERSION,

            "created_at":
                created_at,

            "processing_step":
                "3.5.9.4",

            "pipeline":
                "API_EXPORT"
        }

        chunks.append(
            chunk
        )

    # ========================================================
    # 4. DOCUMENTCHUNKS
    # ========================================================

    for doc_unit in document_units:

        if not isinstance(
            doc_unit,
            dict
        ):

            continue

        unit_id = (
            doc_unit.get("document_unit_id")
            or doc_unit.get("document_id")
        )

        document_id = doc_unit.get(
            "document_id"
        )

        source_file = get_source_file(
            doc_unit
        )

        category = get_category_local(
            doc_unit
        )

        document_type = get_document_type_local(
            doc_unit
        )

        pages = doc_unit.get(
            "pages",
            []
        )

        available_modalities = doc_unit.get(
            "available_modalities",
            {}
        )

        document_summary = doc_unit.get(
            "document_summary",
            {}
        )

        multimodal_flags = doc_unit.get(
            "multimodal_flags",
            {}
        )

        content = nettoyer_texte_chunk(
            " ".join([
                f"Document météorologique consolidé : {source_file}.",
                f"Catégorie : {category}.",
                f"Type documentaire : {document_type}.",
                f"Date de publication : {doc_unit.get('date_publication')}.",
                (
                    f"Période de validité : "
                    f"{doc_unit.get('date_debut_validite')} → "
                    f"{doc_unit.get('date_fin_validite')}."
                ),
                f"Pages disponibles : {pages}.",
                f"Modalités disponibles : {available_modalities}.",
                f"Résumé documentaire : {document_summary}.",
                f"Contenu multimodal : {multimodal_flags}.",
                (
                    "Utiliser d'abord les TextUnits et VisualUnits. "
                    "Utiliser les PageImageUnits si la question nécessite "
                    "une lecture visuelle, une carte, un tableau ou une page complète."
                )
            ])
        )

        if not content:

            continue

        metadata = {
            "date_publication":
                doc_unit.get(
                    "date_publication"
                ),

            "date_debut_validite":
                doc_unit.get(
                    "date_debut_validite"
                ),

            "date_fin_validite":
                doc_unit.get(
                    "date_fin_validite"
                ),

            "document_type":
                document_type,

            "pages":
                pages,

            "page":
                pages[0] if pages else None,

            "source_unit_id":
                unit_id,

            "source_unit_type":
                "document_unit",

            "source_file":
                source_file,

            "available_modalities":
                available_modalities,

            "document_summary":
                document_summary,

            "multimodal_flags":
                multimodal_flags,

            "image_path":
                None,

            "localite":
                None
        }

        chunk_id = (
            f"{unit_id}"
            f"_CHUNK_001"
        )

        chunk = {
            "chunk_id":
                chunk_id,

            "chunk_type":
                "document",

            "unit_id":
                unit_id,

            "unit_type":
                "document_unit",

            "document_id":
                document_id,

            "source_file":
                source_file,

            "category":
                category,

            "page":
                metadata.get(
                    "page"
                ),

            "content":
                content,

            "retrieval_role":
                "secondary",

            "metadata":
                metadata,

            "chunk_version":
                CHUNK_VERSION,

            "created_at":
                created_at,

            "processing_step":
                "3.5.9.4",

            "pipeline":
                "API_EXPORT"
        }

        chunks.append(
            chunk
        )

    # ========================================================
    # 5. CONTRÔLES ESSENTIELS
    # ========================================================

    chunk_ids = [
        chunk.get(
            "chunk_id"
        )
        for chunk in chunks
    ]

    duplicates = [
        item
        for item, count in Counter(chunk_ids).items()
        if item and count > 1
    ]

    if duplicates:

        raise ValueError(
            "❌ Chunks dupliqués détectés : "
            + str(
                duplicates[:10]
            )
        )

    chunks_vides = [
        chunk.get(
            "chunk_id"
        )
        for chunk in chunks
        if not chunk.get(
            "content"
        )
        or not str(
            chunk.get(
                "content"
            )
        ).strip()
    ]

    if chunks_vides:

        raise ValueError(
            "❌ Chunks vides détectés : "
            + str(
                chunks_vides[:10]
            )
        )

    return chunks



# ============================================================
# FONCTIONS PIPELINE — EMBEDDINGS / QDRANT
# ============================================================

def construire_embeddings_api(
    chunks: List[Dict[str, Any]],
    config: MeteoGPTApiConfig
) -> List[Dict[str, Any]]:
    """
    Construit les embeddings des chunks avec intfloat/multilingual-e5-base.

    Les embeddings sont calculés uniquement à partir du champ content.
    Les métadonnées restent associées aux chunks et seront stockées
    comme payloads dans Qdrant.
    """

    import numpy as np

    try:

        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer, AutoModel
        from tqdm import tqdm

    except ImportError:

        raise ImportError(
            "❌ Dépendances embeddings absentes. "
            "Installe : torch transformers sentencepiece safetensors tokenizers tqdm"
        )

    EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"

    EMBEDDING_VERSION = "1.0"

    MAX_LENGTH = 512

    BATCH_SIZE = 16

    NORMALIZE_EMBEDDINGS = True

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    def nettoyer_content_embedding(content):

        if content is None:

            return ""

        content = str(
            content
        )

        content = content.replace(
            "\r",
            " "
        )

        content = content.replace(
            "\n",
            " "
        )

        content = " ".join(
            content.split()
        )

        return content.strip()


    def preparer_passage_e5(content):

        content = nettoyer_content_embedding(
            content
        )

        return "passage: " + content


    def verifier_chunk_valide(chunk):

        if not isinstance(
            chunk,
            dict
        ):

            return False

        if not chunk.get(
            "chunk_id"
        ):

            return False

        if not chunk.get(
            "content"
        ):

            return False

        if not str(
            chunk.get(
                "content"
            )
        ).strip():

            return False

        return True


    def average_pool(
        last_hidden_states,
        attention_mask
    ):

        last_hidden = last_hidden_states.masked_fill(
            ~attention_mask[..., None].bool(),
            0.0
        )

        return last_hidden.sum(
            dim=1
        ) / attention_mask.sum(
            dim=1
        )[..., None]


    chunks_valides = []

    passages_e5 = []

    for chunk in chunks:

        if not verifier_chunk_valide(
            chunk
        ):

            continue

        chunks_valides.append(
            chunk
        )

        passages_e5.append(
            preparer_passage_e5(
                chunk.get(
                    "content"
                )
            )
        )

    if not chunks_valides:

        return []

    tokenizer = AutoTokenizer.from_pretrained(
        EMBEDDING_MODEL_NAME
    )

    model = AutoModel.from_pretrained(
        EMBEDDING_MODEL_NAME
    )

    model.to(
        device
    )

    model.eval()

    all_embeddings = []

    with torch.no_grad():

        for start in tqdm(
            range(
                0,
                len(
                    passages_e5
                ),
                BATCH_SIZE
            ),
            desc="Calcul embeddings"
        ):

            end = start + BATCH_SIZE

            batch_passages = passages_e5[
                start:end
            ]

            batch_tokens = tokenizer(
                batch_passages,
                max_length=MAX_LENGTH,
                padding=True,
                truncation=True,
                return_tensors="pt"
            )

            batch_tokens = {
                key:
                    value.to(
                        device
                    )
                for key, value in batch_tokens.items()
            }

            outputs = model(
                **batch_tokens
            )

            embeddings_batch = average_pool(
                outputs.last_hidden_state,
                batch_tokens["attention_mask"]
            )

            if NORMALIZE_EMBEDDINGS:

                embeddings_batch = F.normalize(
                    embeddings_batch,
                    p=2,
                    dim=1
                )

            embeddings_batch = embeddings_batch.cpu().numpy()

            all_embeddings.append(
                embeddings_batch
            )

    embeddings_matrix = np.vstack(
        all_embeddings
    )

    embeddings_api = []

    for index, chunk in enumerate(
        chunks_valides
    ):

        vecteur = embeddings_matrix[
            index
        ]

        embedding_item = {
            "embedding_id":
                chunk.get(
                    "chunk_id"
                )
                + "_EMB",

            "chunk_id":
                chunk.get(
                    "chunk_id"
                ),

            "embedding_model":
                EMBEDDING_MODEL_NAME,

            "embedding_dimension":
                int(
                    vecteur.shape[0]
                ),

            "embedding_version":
                EMBEDDING_VERSION,

            "normalized":
                NORMALIZE_EMBEDDINGS,

            "embedding":
                vecteur.astype(
                    float
                ).tolist(),

            "created_at":
                created_at,

            "processing_step":
                "3.5.9.4",

            "pipeline":
                "API_EXPORT"
        }

        embeddings_api.append(
            embedding_item
        )

    # --------------------------------------------------------
    # Contrôles essentiels
    # --------------------------------------------------------

    dimensions = sorted(
        set(
            item.get(
                "embedding_dimension"
            )
            for item in embeddings_api
        )
    )

    if len(
        dimensions
    ) != 1:

        raise ValueError(
            f"❌ Dimensions embeddings incohérentes : {dimensions}"
        )

    embedding_ids = [
        item.get(
            "embedding_id"
        )
        for item in embeddings_api
    ]

    if len(
        embedding_ids
    ) != len(
        set(
            embedding_ids
        )
    ):

        raise ValueError(
            "❌ Embedding IDs dupliqués détectés."
        )

    return embeddings_api


def construire_payload_qdrant_api(
    chunk: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Construit le payload Qdrant associé à un chunk.

    Les métadonnées ne sont pas vectorisées : elles sont stockées
    dans le payload pour permettre le filtrage et la reconstruction
    du contexte.
    """

    metadata = chunk.get(
        "metadata",
        {}
    )

    payload = {
        "chunk_id":
            chunk.get(
                "chunk_id"
            ),

        "chunk_type":
            chunk.get(
                "chunk_type"
            ),

        "retrieval_role":
            chunk.get(
                "retrieval_role"
            ),

        "unit_type":
            chunk.get(
                "unit_type"
            ),

        "unit_id":
            chunk.get(
                "unit_id"
            ),

        "document_id":
            chunk.get(
                "document_id"
            ),

        "source_file":
            chunk.get(
                "source_file"
            ),

        "category":
            chunk.get(
                "category"
            ),

        "page":
            chunk.get(
                "page"
            ),

        "content":
            chunk.get(
                "content"
            ),

        "date_publication":
            metadata.get(
                "date_publication"
            ),

        "date_debut_validite":
            metadata.get(
                "date_debut_validite"
            ),

        "date_fin_validite":
            metadata.get(
                "date_fin_validite"
            ),

        "document_type":
            metadata.get(
                "document_type"
            ),

        "pages":
            metadata.get(
                "pages"
            ),

        "localite":
            metadata.get(
                "localite"
            ),

        "image_path":
            metadata.get(
                "image_path"
            ),

        "contains_table":
            metadata.get(
                "contains_table"
            ),

        "contains_map":
            metadata.get(
                "contains_map"
            ),

        "contains_panel":
            metadata.get(
                "contains_panel"
            ),

        "multimodal_priority":
            metadata.get(
                "multimodal_priority"
            ),

        "chunk_version":
            chunk.get(
                "chunk_version"
            ),

        "created_at":
            chunk.get(
                "created_at"
            ),

        "processing_step":
            chunk.get(
                "processing_step"
            ),

        "pipeline":
            chunk.get(
                "pipeline"
            )
    }

    return payload


def indexer_qdrant_api(
    chunks: List[Dict[str, Any]],
    embeddings: List[Dict[str, Any]],
    config: MeteoGPTApiConfig,
    qdrant_client=None,
    source_files_to_replace: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Met à jour incrémentalement la collection Qdrant.

    Principes :
    - un point Qdrant par chunk ;
    - aucune suppression globale de la collection existante ;
    - les points des documents retraités sont supprimés par source_file ;
    - les nouveaux points sont ensuite ajoutés par upsert ;
    - un client Qdrant existant peut être réutilisé par le backend.
    """

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import (
            Distance,
            VectorParams,
            PointStruct,
            Filter,
            FieldCondition,
            MatchValue,
            FilterSelector,
        )

    except ImportError:
        raise ImportError(
            "qdrant-client n'est pas installé."
        )

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    if not chunks:
        raise ValueError(
            "Aucun chunk fourni pour l'indexation Qdrant."
        )

    if not embeddings:
        raise ValueError(
            "Aucun embedding fourni pour l'indexation Qdrant."
        )

    embeddings_by_chunk_id = {
        item.get("chunk_id"): item
        for item in embeddings
        if item.get("chunk_id")
    }

    points = []
    missing_embeddings = []
    vector_size = None

    for chunk in chunks:

        chunk_id = chunk.get("chunk_id")

        if not chunk_id:
            continue

        embedding_item = embeddings_by_chunk_id.get(
            chunk_id
        )

        if embedding_item is None:
            missing_embeddings.append(
                chunk_id
            )
            continue

        vector = embedding_item.get(
            "embedding"
        )

        if not vector:
            missing_embeddings.append(
                chunk_id
            )
            continue

        if vector_size is None:
            vector_size = len(vector)

        elif len(vector) != vector_size:
            raise ValueError(
                "Dimensions d'embeddings incohérentes."
            )

        point = PointStruct(
            id=stable_uuid(chunk_id),
            vector=vector,
            payload=construire_payload_qdrant_api(
                chunk
            ),
        )

        points.append(point)

    if missing_embeddings:
        raise ValueError(
            "Certains chunks n'ont pas d'embedding associé. "
            f"Exemples : {missing_embeddings[:10]}"
        )

    if not points:
        raise ValueError(
            "Aucun point Qdrant construit."
        )

    if vector_size is None:
        raise ValueError(
            "Dimension vectorielle introuvable."
        )

    config.qdrant_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    client_owned = False

    if qdrant_client is None:

        client = QdrantClient(
            path=str(
                config.qdrant_dir
            )
        )

        client_owned = True

    else:

        if not isinstance(
            qdrant_client,
            QdrantClient
        ):
            raise TypeError(
                "qdrant_client doit être une instance de QdrantClient."
            )

        client = qdrant_client

    try:

        existing_collections = {
            collection.name
            for collection
            in client.get_collections().collections
        }

        # ----------------------------------------------------
        # Création uniquement si la collection n'existe pas
        # ----------------------------------------------------

        if config.collection_name not in existing_collections:

            client.create_collection(
                collection_name=config.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )

        else:

            collection_info = client.get_collection(
                collection_name=config.collection_name
            )

            existing_vectors = (
                collection_info
                .config
                .params
                .vectors
            )

            existing_vector_size = getattr(
                existing_vectors,
                "size",
                None
            )

            if (
                existing_vector_size is not None
                and existing_vector_size != vector_size
            ):
                raise ValueError(
                    "Dimension Qdrant incompatible : "
                    f"collection={existing_vector_size}, "
                    f"embeddings={vector_size}."
                )

        # ----------------------------------------------------
        # Suppression ciblée des anciennes versions
        # ----------------------------------------------------

        replaced_sources = sorted(
            {
                Path(str(source_file)).name
                for source_file in (
                    source_files_to_replace or []
                )
                if source_file
            }
        )

        for source_file in replaced_sources:

            client.delete(
                collection_name=config.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="source_file",
                                match=MatchValue(
                                    value=source_file
                                ),
                            )
                        ]
                    )
                ),
                wait=True,
            )

        # ----------------------------------------------------
        # Upsert des nouveaux points
        # ----------------------------------------------------

        client.upsert(
            collection_name=config.collection_name,
            points=points,
            wait=True,
        )

        collection_info = client.get_collection(
            collection_name=config.collection_name
        )

        audit = {
            "processing_step": "B6_INCREMENTAL_UPDATE",
            "pipeline": "API_EXPORT",
            "created_at": created_at,
            "collection_name": config.collection_name,
            "qdrant_dir": str(
                config.qdrant_dir
            ),
            "vector_size": vector_size,
            "distance": "COSINE",
            "chunks_input": len(chunks),
            "embeddings_input": len(embeddings),
            "points_upserted": len(points),
            "source_files_replaced": replaced_sources,
            "collection_points_count":
                collection_info.points_count,
        }

        save_json(
            audit,
            config.qdrant_audit_file
        )

        return {
            "status": "success",
            "collection_name":
                config.collection_name,
            "qdrant_dir":
                str(config.qdrant_dir),
            "points_indexed":
                len(points),
            "points_upserted":
                len(points),
            "source_files_replaced":
                replaced_sources,
            "collection_points_count":
                collection_info.points_count,
            "vector_size":
                vector_size,
            "distance":
                "COSINE",
            "audit_file":
                str(config.qdrant_audit_file),
        }

    finally:

        if client_owned:

            client.close()

# ============================================================
# FONCTION PRINCIPALE EXPORTABLE
# ============================================================

def update_api_pipeline(
    root_dir: Optional[str] = None,
    api_url: str = "http://213.154.77.59:8000/mat/api_meteo.php",
    collection_name: str = "meteogpt_api_chunks",
    dry_run: bool = False,
    qdrant_client=None
) -> Dict[str, Any]:
    """
    Fonction principale d'actualisation API MeteoGPT.

    Cette fonction sera appelée par :
    - le backend ;
    - un script planifié ;
    - un ordonnanceur quotidien.
    """

    config = MeteoGPTApiConfig(
        root_dir=root_dir,
        api_url=api_url,
        collection_name=collection_name
    )

    logger = setup_logger(
        config
    )

    started_at = datetime.now().isoformat(
        timespec="seconds"
    )

    result = {
        "status":
            "started",

        "started_at":
            started_at,

        "finished_at":
            None,

        "dry_run":
            dry_run,

        "root_dir":
            str(
                config.root_dir
            ),

        "api_url":
            config.api_url,

        "collection_name":
            config.collection_name,

        "counts":
            {},

        "files":
            {},

        "qdrant":
            {},

        "errors":
            []
    }

    try:

        logger.info(
            "Démarrage du pipeline d'actualisation API MeteoGPT."
        )

        # ----------------------------------------------------
        # 1. Interrogation API
        # ----------------------------------------------------

        bulletins_api = interroger_api_anacim(
            config
        )

        result["counts"]["bulletins_api"] = len(
            bulletins_api
        )

        logger.info(
            f"Bulletins reçus depuis l'API : {len(bulletins_api)}"
        )

        # ----------------------------------------------------
        # 2. Détection des bulletins à traiter
        # ----------------------------------------------------

        bulletins_a_traiter = detecter_bulletins_a_traiter(
            bulletins_api,
            config
        )

        result["counts"]["bulletins_a_traiter"] = len(
            bulletins_a_traiter
        )

        logger.info(
            f"Bulletins à traiter : {len(bulletins_a_traiter)}"
        )

        if not bulletins_a_traiter:

            result["status"] = "no_update"

            result["finished_at"] = datetime.now().isoformat(
                timespec="seconds"
            )

            logger.info(
                "Aucun nouveau bulletin ou bulletin modifié."
            )

            return result

        if dry_run:

            result["status"] = "dry_run"

            result["finished_at"] = datetime.now().isoformat(
                timespec="seconds"
            )

            logger.info(
                "Dry run activé : aucun traitement lourd exécuté."
            )

            return result

        # ----------------------------------------------------
        # 3. Téléchargement
        # ----------------------------------------------------

        pdf_paths = telecharger_bulletins_api(
            bulletins_a_traiter,
            config
        )

        result["counts"]["pdf_ready"] = len(
            pdf_paths
        )

        result["counts"]["pdf_downloaded"] = sum(
            1
            for bulletin in bulletins_a_traiter
            if bulletin.get(
                "pdf_downloaded_network"
            )
        )

        result["counts"]["pdf_reused"] = sum(
            1
            for bulletin in bulletins_a_traiter
            if bulletin.get(
                "pdf_reused"
            )
        )

        result["files"]["pdf_paths"] = [
            str(path)
            for path in pdf_paths
        ]

        logger.info(
            "PDF prêts : %s | téléchargés : %s | réutilisés : %s",
            result["counts"]["pdf_ready"],
            result["counts"]["pdf_downloaded"],
            result["counts"]["pdf_reused"],
        )

        # ----------------------------------------------------
        # 4. Extraction des unités
        # ----------------------------------------------------

        new_text_units = construire_text_units_api(
            pdf_paths,
            config
        )

        new_visual_units = construire_visual_units_api(
            pdf_paths,
            config
        )

        new_page_image_units = construire_page_image_units_api(
            pdf_paths,
            config
        )

        result["counts"]["new_text_units"] = len(
            new_text_units
        )

        result["counts"]["new_visual_units"] = len(
            new_visual_units
        )

        result["counts"]["new_page_image_units"] = len(
            new_page_image_units
        )

        # ----------------------------------------------------
        # 5. Consolidation documentaire
        # ----------------------------------------------------

        new_document_units = construire_document_units_api(
            new_text_units,
            new_visual_units,
            new_page_image_units,
            config
        )

        result["counts"]["new_document_units"] = len(
            new_document_units
        )

        # ----------------------------------------------------
        # 6. Chunking
        # ----------------------------------------------------

        new_chunks = construire_chunks_api(
            new_text_units,
            new_visual_units,
            new_page_image_units,
            new_document_units,
            config
        )

        result["counts"]["new_chunks"] = len(
            new_chunks
        )

        # ----------------------------------------------------
        # 7. Embeddings
        # ----------------------------------------------------

        new_embeddings = construire_embeddings_api(
            new_chunks,
            config
        )

        result["counts"]["new_embeddings"] = len(
            new_embeddings
        )

        # ----------------------------------------------------
        # 8. Mise à jour des fichiers JSON globaux
        # ----------------------------------------------------

        all_text_units = update_global_json_file(
            config.text_units_file,
            new_text_units,
            possible_keys=[
                "text_units",
                "items",
                "units",
                "data"
            ]
        )

        all_visual_units = update_global_json_file(
            config.visual_units_file,
            new_visual_units,
            possible_keys=[
                "visual_units",
                "items",
                "units",
                "data"
            ]
        )

        all_page_image_units = update_global_json_file(
            config.page_image_units_file,
            new_page_image_units,
            possible_keys=[
                "page_image_units",
                "items",
                "units",
                "data"
            ]
        )

        all_document_units = update_global_json_file(
            config.document_units_file,
            new_document_units,
            possible_keys=[
                "document_units",
                "items",
                "units",
                "data"
            ]
        )

        all_chunks = update_global_json_file(
            config.chunks_file,
            new_chunks,
            possible_keys=[
                "chunks",
                "items",
                "data"
            ]
        )

        all_embeddings = update_global_json_file(
            config.embeddings_file,
            new_embeddings,
            possible_keys=[
                "embeddings",
                "items",
                "data"
            ]
        )

        result["counts"]["total_text_units"] = len(
            all_text_units
        )

        result["counts"]["total_visual_units"] = len(
            all_visual_units
        )

        result["counts"]["total_page_image_units"] = len(
            all_page_image_units
        )

        result["counts"]["total_document_units"] = len(
            all_document_units
        )

        result["counts"]["total_chunks"] = len(
            all_chunks
        )

        result["counts"]["total_embeddings"] = len(
            all_embeddings
        )

        source_files_to_replace = [
            nom_pdf_depuis_url(
                bulletin.get("chemin", "")
            )
            for bulletin in bulletins_a_traiter
            if (
                bulletin.get("chemin")
                and bulletin.get("update_status")
                in {
                    "modified",
                    "resume_processing",
                }
            )
        ]


        # ----------------------------------------------------
        # 9. Indexation Qdrant
        # ----------------------------------------------------

        qdrant_result = indexer_qdrant_api(
            new_chunks,
            new_embeddings,
            config,
            qdrant_client=qdrant_client,
            source_files_to_replace=source_files_to_replace,
        )

        result["qdrant"] = qdrant_result

        # ----------------------------------------------------
        # 10. Registre processed
        # ----------------------------------------------------

        mettre_a_jour_registre_api(
            bulletins_a_traiter,
            config
        )

        # ----------------------------------------------------
        # 11. Fin
        # ----------------------------------------------------

        result["status"] = "success"

        result["finished_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        logger.info(
            "Pipeline d'actualisation API terminé avec succès."
        )

        return result

    except Exception as e:

        result["status"] = "error"

        result["finished_at"] = datetime.now().isoformat(
            timespec="seconds"
        )

        result["errors"].append(
            str(e)
        )

        logger.exception(
            "Erreur pendant le pipeline d'actualisation API."
        )

        return result


# ============================================================
# EXÉCUTION MANUELLE
# ============================================================

if __name__ == "__main__":

    output = update_api_pipeline()

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        )
    )
