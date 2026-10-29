
from __future__ import annotations

import json
import re
import time
import unicodedata
import atexit

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import torch
import torch.nn.functional as F

from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from transformers import AutoModel, AutoTokenizer


# ============================================================
# 1. CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent

CHUNKS_FILE = (
    ROOT
    / "data"
    / "extracted"
    / "api"
    / "chunks"
    / "chunks_api.json"
)

QDRANT_PATH = (
    ROOT
    / "data"
    / "qdrant"
)

COLLECTION_NAME = "meteogpt_api_chunks"

EMBEDDING_MODEL_NAME = (
    "intfloat/multilingual-e5-base"
)

QUERY_PREFIX = "query: "

MAX_QUERY_LENGTH = 512

NORMALIZE_QUERY_EMBEDDINGS = True

DEFAULT_TOP_K = 5

HYBRID_METADATA_CANDIDATE_K = 20

RRF_K = 60

METEOGPT_TIMEZONE = ZoneInfo(
    "Africa/Dakar"
)

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


GENERAL_METEO_CATEGORIES = {
    "meteo_matin",
    "meteo_soir",
    "meteo_72h",
}

SPECIALIZED_CATEGORIES = {
    "navigation_cotiere",
    "peche_artisanale",
    "marine_nationale",
}
CATEGORIES_LOCALITE_STRUCTUREE = set()


FRENCH_MONTHS = {
    "janvier": 1,
    "jan": 1,
    "janv": 1,
    "fevrier": 2,
    "février": 2,
    "fev": 2,
    "fevr": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "jull": 7,
    "aout": 8,
    "out": 8,
    "août": 8,
    "septembre": 9,
    "sept": 9,
    "sep": 9,
    "octobre": 10,
    "oct": 10,
    "novembre": 11,
    "nov": 11,
    "decembre": 12,
    "décembre": 12,
    "dec": 12,

}


# ============================================================
# 2. RESSOURCES CHARGÉES UNE SEULE FOIS
# ============================================================

BM25_CHUNKS = []

BM25_CORPUS_TOKENS = []

BM25_POSITION_BY_CHUNK_ID = {}

LOCALITES_CONNNUES = {}

bm25_index = None

query_tokenizer = None

query_embedding_model = None

qdrant_client = None
qdrant_client_owned = False

_INITIALIZED = False

# ============================================================
# 3. OUTILS GÉNÉRAUX
# ============================================================ 
def nettoyer_requete(query: str) -> str:

    if not isinstance(query, str):
        raise TypeError(
            "La requête doit être une chaîne de caractères."
        )

    query = (
        query
        .replace("\r", " ")
        .replace("\n", " ")
    )

    query = " ".join(
        query.split()
    ).strip()

    if not query:
        raise ValueError(
            "La requête utilisateur ne peut pas être vide."
        )

    return query


def normaliser_valeur_metadata(value):

    if value is None:
        return None

    value = str(
        value
    ).strip().lower()

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.replace(
        "-",
        " "
    )

    return " ".join(
        value.split()
    )


def lire_champ_chunk(
    chunk,
    key
):

    if not isinstance(chunk, dict):
        return None

    value = chunk.get(
        key
    )

    if value not in (
        None,
        ""
    ):
        return value

    metadata = (
        chunk.get("metadata")
        or {}
    )

    return metadata.get(
        key
    )


# ============================================================
# 4. CHARGEMENT DES CHUNKS
# ============================================================

def _charger_chunks():

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Fichier chunks introuvable : {CHUNKS_FILE}"
        )

    with open(
        CHUNKS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in [
            "chunks",
            "items",
            "data",
        ]:

            if isinstance(
                data.get(key),
                list
            ):
                return data[key]

    raise ValueError(
        "Format de chunks_api.json non reconnu."
    )


# ============================================================
# 5. BM25
# ============================================================

TOKEN_PATTERN_BM25 = re.compile(
    r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+",
    flags=re.UNICODE
)


def normaliser_texte_bm25(
    texte
):

    if texte is None:
        return ""

    texte = unicodedata.normalize(
        "NFKC",
        str(texte)
    )

    texte = (
        texte
        .lower()
        .replace("\r", " ")
        .replace("\n", " ")
    )

    return " ".join(
        texte.split()
    ).strip()


def tokeniser_bm25(
    texte
):

    texte = normaliser_texte_bm25(
        texte
    )

    return TOKEN_PATTERN_BM25.findall(
        texte
    )


def _construire_index_bm25():

    global BM25_CHUNKS
    global BM25_CORPUS_TOKENS
    global BM25_POSITION_BY_CHUNK_ID
    global LOCALITES_CONNNUES
    global CATEGORIES_LOCALITE_STRUCTUREE
    global bm25_index

    source_chunks = _charger_chunks()

    BM25_CHUNKS = []
    BM25_CORPUS_TOKENS = []

    for chunk in source_chunks:

        if not isinstance(
            chunk,
            dict
        ):
            continue

        chunk_id = chunk.get(
            "chunk_id"
        )

        content = chunk.get(
            "content"
        )

        if not chunk_id or not content:
            continue

        tokens = tokeniser_bm25(
            content
        )

        if not tokens:
            continue

        BM25_CHUNKS.append(
            chunk
        )

        BM25_CORPUS_TOKENS.append(
            tokens
        )

    if not BM25_CHUNKS:
        raise RuntimeError(
            "Aucun chunk exploitable pour BM25."
        )

    bm25_index = BM25Okapi(
        BM25_CORPUS_TOKENS
    )

    BM25_POSITION_BY_CHUNK_ID = {
        chunk.get("chunk_id"): index
        for index, chunk
        in enumerate(BM25_CHUNKS)
        if chunk.get("chunk_id")
    }

    # --------------------------------------------------------
    # Localités réellement présentes dans le corpus
    # --------------------------------------------------------

    LOCALITES_CONNNUES = {}
    CATEGORIES_LOCALITE_STRUCTUREE = set()

    for chunk in BM25_CHUNKS:

        localite = lire_champ_chunk(
            chunk,
            "localite"
        )

        if not localite:
            continue

        localite_norm = (
            normaliser_valeur_metadata(
                localite
            )
        )

        if not localite_norm:
            continue

        LOCALITES_CONNNUES[
            localite_norm
        ] = localite

        category = lire_champ_chunk(
            chunk,
            "category"
        )

        if category:

            CATEGORIES_LOCALITE_STRUCTUREE.add(
                category
            )

# ============================================================
# 6. MODÈLE E5
# ============================================================

def _charger_modele_embedding():

    global query_tokenizer
    global query_embedding_model

    if (
        query_tokenizer is not None
        and
        query_embedding_model is not None
    ):
        return

    query_tokenizer = (
        AutoTokenizer.from_pretrained(
            EMBEDDING_MODEL_NAME
        )
    )

    query_embedding_model = (
        AutoModel.from_pretrained(
            EMBEDDING_MODEL_NAME
        )
    )

    query_embedding_model.to(
        DEVICE
    )

    query_embedding_model.eval()


def preparer_requete_e5(
    query
):

    return (
        QUERY_PREFIX
        + nettoyer_requete(query)
    )


def average_pool_query(
    last_hidden_states,
    attention_mask
):

    last_hidden = (
        last_hidden_states.masked_fill(
            ~attention_mask[
                ...,
                None
            ].bool(),
            0.0
        )
    )

    return (
        last_hidden.sum(dim=1)
        /
        attention_mask.sum(
            dim=1
        )[..., None]
    )


def encoder_requete(
    query: str
) -> np.ndarray:

    _charger_modele_embedding()

    query_e5 = preparer_requete_e5(
        query
    )

    tokens = query_tokenizer(
        [query_e5],
        max_length=MAX_QUERY_LENGTH,
        padding=True,
        truncation=True,
        return_tensors="pt"
    )

    tokens = {
        key: value.to(DEVICE)
        for key, value
        in tokens.items()
    }

    with torch.no_grad():

        outputs = (
            query_embedding_model(
                **tokens
            )
        )

        embedding = average_pool_query(
            outputs.last_hidden_state,
            tokens["attention_mask"]
        )

        if NORMALIZE_QUERY_EMBEDDINGS:

            embedding = F.normalize(
                embedding,
                p=2,
                dim=1
            )

    return (
        embedding[0]
        .cpu()
        .numpy()
        .astype(
            np.float32
        )
    )

# ============================================================
# 7. QDRANT
# ============================================================

qdrant_client = None
qdrant_client_owned = False


def set_qdrant_client(
    client
):
    """
    Permet de réutiliser un client déjà ouvert,
    notamment dans le notebook Colab ou plus tard
    dans le backend FastAPI.
    """

    global qdrant_client
    global qdrant_client_owned

    if not isinstance(
        client,
        QdrantClient
    ):
        raise TypeError(
            "client doit être une instance de QdrantClient."
        )

    # Si un client local avait été créé par ce module,
    # on le ferme proprement avant de le remplacer.
    fermer_client_qdrant_actif()

    qdrant_client = client
    qdrant_client_owned = False


def obtenir_client_qdrant_actif():

    global qdrant_client
    global qdrant_client_owned

    if isinstance(
        qdrant_client,
        QdrantClient
    ):
        return qdrant_client

    qdrant_client = QdrantClient(
        path=str(
            QDRANT_PATH
        )
    )

    qdrant_client_owned = True

    return qdrant_client


def fermer_client_qdrant_actif():

    global qdrant_client
    global qdrant_client_owned

    if (
        isinstance(
            qdrant_client,
            QdrantClient
        )
        and
        qdrant_client_owned
    ):
        try:
            qdrant_client.close()
        except Exception:
            pass

    qdrant_client = None
    qdrant_client_owned = False

atexit.register(
    fermer_client_qdrant_actif
)
# ============================================================
# 8. DÉTECTION DE LA CATÉGORIE
# ============================================================


def detecter_categories_requete(query):

    query_norm = (
        normaliser_valeur_metadata(query)
        or ""
    )

    # --------------------------------------------------------
    # 1. PÊCHE ARTISANALE
    # --------------------------------------------------------

    peche_patterns = [
        r"\bpeche artisanale\b",
        r"\bpecheurs?\b",
        r"\bpirogues?\b",

        # Variantes supplémentaires
        r"\bpecheuses?\b",
        r"\bpeche\b",
        r"\bpecher\b",
        r"\bpechant\b",
        r"\bfilets?\s+de\s+peche\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in peche_patterns
    ):
        return {
            "mode": "explicit",
            "categories": ["peche_artisanale"],
        }

    # --------------------------------------------------------
    # 2. MARINE NATIONALE
    # --------------------------------------------------------

    marine_nationale_patterns = [
        r"\bmarine nationale\b",
        r"\bbulletin marine national(?:e)?\b",
        r"\bmeteo marine nationale\b",
        r"\bmeteorologie marine nationale\b",

        # Variantes supplémentaires
        r"\bforces navales\b",
        r"\bnavires? militaires?\b",
        r"\bbatiments?\s+de\s+guerre\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in marine_nationale_patterns
    ):
        return {
            "mode": "explicit",
            "categories": ["marine_nationale"],
        }

    # --------------------------------------------------------
    # 3. NAVIGATION CÔTIÈRE
    # --------------------------------------------------------

    navigation_patterns = [
        r"\bnavigation cotiere\b",
        r"\bnavigation\b",

        # Variantes supplémentaires
        r"\bnavigu(?:er|e|es|ent|ons|ez)\b",
        r"\bcabotage\b",
        r"\b(?:traversee|trajet)\s+(?:maritime|en mer)\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in navigation_patterns
    ):
        return {
            "mode": "explicit",
            "categories": ["navigation_cotiere"],
        }

    # --------------------------------------------------------
    # 4. MÉTÉO MARITIME GÉNÉRALE
    # --------------------------------------------------------

    maritime_patterns = [
        r"\bhoule\b",
        r"\bau large\b",
        r"\betat de la mer\b",
        r"\bmaritime\b",
        r"\ben mer\b",

        # Variantes supplémentaires ciblées
        r"\bhoules\b",
        r"\bmaritimes\b",
        r"\bmarees?\b",
        r"\bmer\s+(?:agitee|calme|forte|demontee)\b",
        r"\bhauteur\s+(?:des?\s+)?vagues?\b",
        r"\bvagues?\s+(?:en mer|au large)\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in maritime_patterns
    ):
        return {
            "mode": "explicit",
            "categories": [
                "navigation_cotiere",
                "marine_nationale",
            ],
        }

    # --------------------------------------------------------
    # 5. PRÉVISIONS 72 HEURES
    # --------------------------------------------------------

    patterns_72h = [
        r"\b72\s*h\b",
        r"\b72\s*(?:prochaines?\s+)?heures?\b",
        r"\b(?:3|trois)\s+(?:prochains?\s+)?jours?\b",

        # Variantes supplémentaires
        r"\b72\s*hrs?\b",
        r"\b72\s*heur\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in patterns_72h
    ):
        return {
            "mode": "explicit",
            "categories": ["meteo_72h"],
        }

    # --------------------------------------------------------
    # 6. BULLETIN MATIN
    # --------------------------------------------------------

    matin_patterns = [
        r"\bbulletin du matin\b",
        r"\bmeteo du matin\b",

        # Variantes supplémentaires
        r"\b(?:bulletin|meteo|previsions?)\s+(?:du\s+)?matin\b",
        r"\bbulletin\s+meteo\s+(?:du\s+)?matin\b",
        r"\bbulletin\s+matinal\b",
        r"\bprevisions?\s+matinales?\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in matin_patterns
    ):
        return {
            "mode": "explicit",
            "categories": ["meteo_matin"],
        }

    # --------------------------------------------------------
    # 7. BULLETIN SOIR
    # --------------------------------------------------------

    soir_patterns = [
        r"\bbulletin du soir\b",
        r"\bmeteo du soir\b",

        # Variantes supplémentaires
        r"\b(?:bulletin|meteo|previsions?)\s+(?:du\s+)?soir\b",
        r"\bbulletin\s+meteo\s+(?:du\s+)?soir\b",
        r"\bbulletin\s+vesperal\b",
        r"\bprevisions?\s+(?:de\s+la\s+)?soiree\b",
    ]

    if any(
        re.search(pattern, query_norm)
        for pattern in soir_patterns
    ):
        return {
            "mode": "explicit",
            "categories": ["meteo_soir"],
        }

    # --------------------------------------------------------
    # 8. MÉTÉO GÉNÉRALE
    # --------------------------------------------------------

    return {
        "mode": "general",
        "categories": [
            "meteo_matin",
            "meteo_soir",
            "meteo_72h",
        ],
    }


# ============================================================
# 9. DÉTECTION DE LA LOCALITÉ
# ============================================================

def detecter_localite_requete(
    query: str
):

    query_norm = (
        normaliser_valeur_metadata(
            query
        )
    )

    localites_triees = sorted(
        LOCALITES_CONNNUES.keys(),
        key=len,
        reverse=True
    )

    for localite_norm in localites_triees:

        pattern = (
            r"\b"
            + re.escape(
                localite_norm
            )
            + r"\b"
        )

        if re.search(
            pattern,
            query_norm
        ):

            return {
                "mode": "specific",
                "localite":
                    LOCALITES_CONNNUES[
                        localite_norm
                    ],
            }

    return {
        "mode": "general",
        "localite": None,
    }


# ============================================================
# 10. TEMPORALITÉ
# ============================================================

def construire_periode_jour(
    date_obj
):

    start = datetime(
        date_obj.year,
        date_obj.month,
        date_obj.day,
        0,
        0,
        0,
        tzinfo=METEOGPT_TIMEZONE
    )

    end = datetime(
        date_obj.year,
        date_obj.month,
        date_obj.day,
        23,
        59,
        59,
        tzinfo=METEOGPT_TIMEZONE
    )

    return start, end


def _extraire_date_explicite(query_temporal, now, raw_query=None):
    """Extrait une date numérique ou une date française."""

    match_numeric = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        str(raw_query or query_temporal),
    )

    if match_numeric:
        jour, mois, annee = map(int, match_numeric.groups())
        cible = date(annee, mois, jour)
        return cible, match_numeric.group(0)

    noms_mois = "|".join(
        re.escape(nom)
        for nom in sorted(FRENCH_MONTHS, key=len, reverse=True)
    )

    match_fr = re.search(
        rf"\b(\d{{1,2}})\s+({noms_mois})(?:\s+(\d{{4}}))?\b",
        query_temporal,
    )

    if not match_fr:
        return None

    jour = int(match_fr.group(1))
    mois = FRENCH_MONTHS[match_fr.group(2)]
    annee = (
        int(match_fr.group(3))
        if match_fr.group(3)
        else now.year
    )

    cible = date(annee, mois, jour)

    return cible, match_fr.group(0)


def resoudre_temporalite(query, now=None):
    """
    Résout la temporalité d'une requête météorologique.

    Gère :
    - aujourd'hui et ses abréviations ;
    - hier, demain, après-demain ;
    - dates numériques et françaises ;
    - bulletin publié à une date précise ;
    - horizon de prévision sur 72 heures ;
    - période historique de trois jours.
    """

    if now is None:
        now = datetime.now(METEOGPT_TIMEZONE)

    query_norm = normaliser_valeur_metadata(query) or ""

    query_temporal = " ".join(
        query_norm
        .replace("'", " ")
        .replace("’", " ")
        .split()
    )

    # --------------------------------------------------------
    # 1. EXTRACTION D'UNE DATE EXPLICITE
    # --------------------------------------------------------

    cible = None
    expression_date = None

    # Date numérique : 17/09/2026 ou 17-09-2026
    match_numeric = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
        str(query).lower()
    )

    if match_numeric:

        jour, mois, annee = map(
            int,
            match_numeric.groups()
        )

        cible = date(annee, mois, jour)
        expression_date = match_numeric.group(0)

    else:

        # Normalisation des noms de mois existants
        mois_fr = {
            normaliser_valeur_metadata(nom): numero
            for nom, numero in FRENCH_MONTHS.items()
        }

        month_pattern = "|".join(
            re.escape(nom)
            for nom in sorted(
                mois_fr,
                key=len,
                reverse=True
            )
        )

        match_french = re.search(
            rf"\b(\d{{1,2}})\s+({month_pattern})"
            rf"(?:\s+(\d{{4}}))?\b",
            query_temporal
        )

        if match_french:

            jour = int(match_french.group(1))
            mois = mois_fr[match_french.group(2)]

            annee = (
                int(match_french.group(3))
                if match_french.group(3)
                else now.year
            )

            cible = date(annee, mois, jour)
            expression_date = match_french.group(0)

    # --------------------------------------------------------
    # 2. PÉRIODE HISTORIQUE ANCRÉE À UNE DATE
    # --------------------------------------------------------

    if cible is not None:

        horizon_historique = re.search(
            r"\b(?:3|trois)\s+jours?\s+suivants?\b",
            query_temporal
        )

        if horizon_historique:

            # Exemple : trois jours suivant le 17 septembre
            # => 18, 19 et 20 septembre

            start, _ = construire_periode_jour(
                cible + timedelta(days=1)
            )

            _, end = construire_periode_jour(
                cible + timedelta(days=3)
            )

            return {
                "mode": "duration",
                "expression": (
                    f"3 jours suivant {expression_date}"
                ),
                "start": start,
                "end": end,
                "publication_cutoff": cible,
            }

        # ----------------------------------------------------
        # 3. BULLETIN PUBLIÉ À UNE DATE PRÉCISE
        # ----------------------------------------------------

        expression_norm = normaliser_valeur_metadata(
            expression_date
        )

        mention_document = re.search(
            r"\b(?:bulletin|previ\w*)\b",
            query_temporal
        )

        date_introduite_par_du = re.search(
            r"\bdu\s+"
            + re.escape(expression_norm)
            + r"\b",
            query_temporal
        )

        if mention_document and date_introduite_par_du:

            start, end = construire_periode_jour(cible)

            return {
                "mode": "publication",
                "expression": expression_date,
                "start": start,
                "end": end,
            }

    # --------------------------------------------------------
    # 4. APRÈS-DEMAIN, DEMAIN ET HIER
    # --------------------------------------------------------

    expressions_relatives = [
        (
            r"\b(?:apres\s+(?:demain|dmain|dm)"
            r"|apresdemain)\b",
            2,
            "apres-demain",
        ),
        (
            r"\b(?:demain|dmain|dm)\b",
            1,
            "demain",
        ),
        (
            r"\bhier\b",
            -1,
            "hier",
        ),
    ]

    for pattern, decalage, expression in expressions_relatives:

        if re.search(pattern, query_temporal):

            cible_relative = (
                now.date()
                + timedelta(days=decalage)
            )

            start, end = construire_periode_jour(
                cible_relative
            )

            return {
                "mode": "relative",
                "expression": expression,
                "start": start,
                "end": end,
            }

    # --------------------------------------------------------
    # 5. AUJOURD'HUI ET ABRÉVIATIONS SMS
    #
    # Règle métier conservée :
    # aujourd'hui = instant exact de la requête
    # --------------------------------------------------------

    if re.search(
        r"\b(?:aujourd\s+hui|aujourdhui"
        r"|ojd|aujd|ajd|auj)\b",
        query_temporal
    ):

        return {
            "mode": "current",
            "expression": "aujourd'hui",
            "start": now,
            "end": now,
        }

    # --------------------------------------------------------
    # 6. DATE EXPLICITE ORDINAIRE
    # --------------------------------------------------------

    if cible is not None:

        start, end = construire_periode_jour(cible)

        return {
            "mode": "explicit",
            "expression": expression_date,
            "start": start,
            "end": end,
        }

    # --------------------------------------------------------
    # 7. HORIZON DES 72 HEURES
    # Sans date explicite
    # --------------------------------------------------------

    patterns_72h = [
        r"\b72\s*h\b",
        r"\b72\s*(?:prochaines?\s+)?heures?\b",
        r"\b72\s*heur\b",
        r"\b(?:3|trois)\s+(?:prochains?\s+)?jours?\b",
    ]

    if any(
        re.search(pattern, query_temporal)
        for pattern in patterns_72h
    ):

        return {
            "mode": "duration",
            "expression": "72 heures",
            "start": now,
            "end": now + timedelta(hours=72),
        }

    # --------------------------------------------------------
    # 8. AUCUNE DATE RECONNUE
    #
    # Règle initiale conservée :
    # météo courante = instant présent
    # --------------------------------------------------------

    return {
        "mode": "current",
        "expression": "maintenant",
        "start": now,
        "end": now,
    }



def analyser_contraintes_metadata(
    query,
    now=None
):

    return {
        "temporal":
            resoudre_temporalite(
                query,
                now=now
            ),

        "location":
            detecter_localite_requete(
                query
            ),

        "category":
            detecter_categories_requete(
                query
            ),
    }


# ============================================================
# 11. OUTILS TEMPORELS SUR LES CHUNKS
# ============================================================

def parser_datetime_metadata(
    value
):

    if value is None:
        return None

    if isinstance(
        value,
        datetime
    ):
        dt = value

    elif isinstance(
        value,
        date
    ):

        dt = datetime(
            value.year,
            value.month,
            value.day
        )

    else:

        value = str(
            value
        ).strip()

        if not value:
            return None

        try:

            dt = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError:

            dt = None

            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
            ]

            for fmt in formats:

                try:

                    dt = datetime.strptime(
                        value,
                        fmt
                    )

                    break

                except ValueError:
                    continue

            if dt is None:
                return None

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=METEOGPT_TIMEZONE
        )

    else:

        dt = dt.astimezone(
            METEOGPT_TIMEZONE
        )

    return dt


def obtenir_date_publication(
    chunk
):

    publication = (
        parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_publication"
            )
        )
    )

    if publication is None:
        return None

    return publication.date()


def intervalles_se_chevauchent(
    start_1,
    end_1,
    start_2,
    end_2
):

    if any(
        value is None
        for value in [
            start_1,
            end_1,
            start_2,
            end_2,
        ]
    ):
        return False

    return (
        start_1 <= end_2
        and
        end_1 >= start_2
    )


def chunk_couvre_periode(
    chunk,
    target_start,
    target_end
):

    valid_start = (
        parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_debut_validite"
            )
        )
    )

    valid_end = (
        parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_fin_validite"
            )
        )
    )

    if (
        valid_start is None
        or
        valid_end is None
    ):
        return False

    return intervalles_se_chevauchent(
        valid_start,
        valid_end,
        target_start,
        target_end
    )


def conserver_date_publication(
    chunks,
    date_retenue
):

    return [
        chunk
        for chunk in chunks
        if obtenir_date_publication(
            chunk
        ) == date_retenue
    ]



def selectionner_chunks_temporels(chunks, temporalite, now):
    """
    Sélectionne les chunks selon la temporalité demandée.

    - Demande courante : validité + fraîcheur par catégorie.
    - Date future : dernière publication disponible couvrant
      la période.
    - Date historique : conservation des sources disponibles
      à cette date.
    - Publication précise : correspondance sur la date
      de publication, indépendamment de la validité.
    """

    if not chunks or not temporalite:
        return []

    target_start = temporalite.get("start")
    target_end = temporalite.get("end")
    mode = temporalite.get("mode")

    if target_start is None or target_end is None:
        return []

    today = now.date()
    target_date = target_start.date()

    # --------------------------------------------------------
    # 1. Vérifier la disponibilité réelle d'un document
    # --------------------------------------------------------

    def publication_disponible(chunk, limite):
        publication = parser_datetime_metadata(
            lire_champ_chunk(chunk, "date_publication")
        )

        return (
            publication is not None
            and publication <= now
            and publication.date() <= limite
        )

    # --------------------------------------------------------
    # 2. Garder la dernière publication par catégorie
    # Logique initiale conservée
    # --------------------------------------------------------

    def garder_plus_recents_par_categorie(candidats):
        par_categorie = defaultdict(list)

        for chunk in candidats:
            categorie = lire_champ_chunk(chunk, "category")

            if categorie is not None:
                par_categorie[categorie].append(chunk)

        resultats = []

        for category_chunks in par_categorie.values():
            dates = [
                obtenir_date_publication(chunk)
                for chunk in category_chunks
                if obtenir_date_publication(chunk) is not None
            ]

            if not dates:
                continue

            date_retenue = max(dates)

            resultats.extend(
                chunk
                for chunk in category_chunks
                if obtenir_date_publication(chunk) == date_retenue
            )

        return resultats

    # --------------------------------------------------------
    # A. BULLETIN PUBLIÉ À UNE DATE PRÉCISE
    # --------------------------------------------------------

    if mode == "publication":
        if target_date > today:
            return []

        return [
            chunk
            for chunk in chunks
            if (
                publication_disponible(chunk, target_date)
                and obtenir_date_publication(chunk) == target_date
            )
        ]

    # --------------------------------------------------------
    # B. MAINTENANT / AUJOURD'HUI
    # --------------------------------------------------------

    if (
        mode == "current"
        or temporalite.get("expression") == "aujourd'hui"
    ):
        candidats = [
            chunk
            for chunk in chunks
            if (
                publication_disponible(chunk, today)
                and chunk_couvre_periode(chunk, now, now)
            )
        ]

        return garder_plus_recents_par_categorie(candidats)

    # --------------------------------------------------------
    # C. HORIZON DE PRÉVISION
    # --------------------------------------------------------

    if mode == "duration":
        cutoff = temporalite.get("publication_cutoff")

        if isinstance(cutoff, datetime):
            cutoff = cutoff.date()

        limite = min(cutoff or today, today)

        candidats = [
            chunk
            for chunk in chunks
            if (
                publication_disponible(chunk, limite)
                and chunk_couvre_periode(
                    chunk,
                    target_start,
                    target_end
                )
            )
        ]

        # Horizon historique ancré à une date :
        # conserver les sources disponibles à cette date.
        if cutoff is not None:
            return candidats

        # Horizon courant :
        # privilégier les publications les plus récentes.
        return garder_plus_recents_par_categorie(candidats)

    # --------------------------------------------------------
    # D. DATE EXPLICITE OU RELATIVE
    # --------------------------------------------------------

    candidats = [
        chunk
        for chunk in chunks
        if (
            publication_disponible(
                chunk,
                min(target_date, today)
            )
            and chunk_couvre_periode(
                chunk,
                target_start,
                target_end
            )
        )
    ]

    # Date passée ou aujourd'hui explicitement daté :
    # conserver les éditions disponibles à cette date.
    if target_date <= today:
        return candidats

    # Date future : conserver la dernière publication
    # disponible par catégorie.
    return garder_plus_recents_par_categorie(candidats)



# ============================================================
# 12. FILTRAGE GÉOGRAPHIQUE
# ============================================================

def chunk_geographiquement_admissible(
    chunk,
    contrainte_localite
):

    category = lire_champ_chunk(
        chunk,
        "category"
    )

    chunk_localite = (
        lire_champ_chunk(
            chunk,
            "localite"
        )
    )

    if contrainte_localite is None:
        return True

    location_mode = (
        contrainte_localite.get(
            "mode"
        )
    )

    localite_cible = (
        contrainte_localite.get(
            "localite"
        )
    )

    if (
        category
        not in
        CATEGORIES_LOCALITE_STRUCTUREE
    ):
        return True

    if (
        location_mode == "general"
        or
        localite_cible is None
    ):

        return (
            chunk_localite is None
        )

    if chunk_localite is None:
        return True

    return (
        normaliser_valeur_metadata(
            chunk_localite
        )
        ==
        normaliser_valeur_metadata(
            localite_cible
        )
    )

# ============================================================
# 12' fallback pour chunks expirés
# ============================================================


def selectionner_chunks_fallback_expire(
    chunks,
    temporalite,
    now
):
    """
    Sélectionne les dernières informations expirées
    pour la période demandée.

    Exclut les documents non encore publiés à la date
    de référence ou indisponibles au moment de la requête.
    """

    if not chunks:
        return []

    temporalite = temporalite or {}

    reference = (
        temporalite.get("start")
        or now
    )

    # Ne jamais utiliser une publication future
    # ou postérieure à la période historique demandée.
    limite_publication = min(
        reference.date(),
        now.date()
    )

    # Pour un horizon historique ancré à une date,
    # respecter la date limite de publication.
    cutoff = temporalite.get("publication_cutoff")

    if cutoff is not None:

        cutoff_dt = parser_datetime_metadata(cutoff)

        if cutoff_dt is None:
            return []

        limite_publication = min(
            limite_publication,
            cutoff_dt.date()
        )

    candidats = []

    for chunk in chunks:

        publication = parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_publication"
            )
        )

        date_fin = parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_fin_validite"
            )
        )

        # Une publication inconnue ne permet pas
        # de confirmer la disponibilité historique.
        if publication is None or date_fin is None:
            continue

        if (
            publication > now
            or publication.date() > limite_publication
        ):
            continue

        if date_fin < reference:
            candidats.append(
                (date_fin, chunk)
            )

    if not candidats:
        return []

    # Logique initiale conservée :
    # dernière fin de validité disponible.
    derniere_fin_validite = max(
        date_fin
        for date_fin, _ in candidats
    )

    return [
        chunk
        for date_fin, chunk in candidats
        if date_fin == derniere_fin_validite
    ]


# ============================================================
# 13. SOUS-CORPUS ADMISSIBLE
# ============================================================

def selectionner_chunks_admissibles(
    query,
    contraintes=None,
    now=None
):

    if now is None:

        now = datetime.now(
            METEOGPT_TIMEZONE
        )

    if contraintes is None:

        contraintes = (
            analyser_contraintes_metadata(
                query,
                now=now
            )
        )


    # ========================================================
    # 1. RECHERCHE NORMALE :
    # catégories correspondant à la requête
    # ========================================================

    categories_autorisees = set(
        contraintes[
            "category"
        ][
            "categories"
        ]
    )

    chunks_categorie = [
        chunk
        for chunk
        in BM25_CHUNKS
        if lire_champ_chunk(
            chunk,
            "category"
        )
        in categories_autorisees
    ]


    # ========================================================
    # 2. FILTRAGE GÉOGRAPHIQUE
    # Avant la sélection de la publication la plus récente
    # ========================================================

    chunks_geographiques = [
        chunk
        for chunk in chunks_categorie
        if chunk_geographiquement_admissible(
            chunk,
            contraintes["location"]
        )
    ]

    # ========================================================
    # 3. FILTRAGE TEMPOREL
    # Sur les chunks géographiquement admissibles
    # ========================================================

    chunks_temporels = selectionner_chunks_temporels(
        chunks=chunks_geographiques,
        temporalite=contraintes["temporal"],
        now=now
    )

    chunks_finaux = chunks_temporels


    # ========================================================
    # 4. FALLBACK MÊME DATE / MÊME PÉRIODE
    #
    # Seulement pour une demande météo générale.
    #
    # Si aucun bulletin météo général n'est disponible,
    # on regarde les autres catégories disponibles pour
    # la même période avant de conclure à une absence et localite en
    # premiere si elle existe.
   # ========================================================

    fallback_used = False
    data_status = "valid"

    category_mode = contraintes["category"].get("mode")
    chunks_alternatifs = []

    if not chunks_finaux and category_mode == "general":

        contrainte_localite = contraintes["location"]

        demande_localisee = (
            contrainte_localite is not None
            and contrainte_localite.get("mode") == "specific"
            and contrainte_localite.get("localite") is not None
        )

        # Filtrage géographique AVANT la sélection
        # temporelle et la fraîcheur par catégorie.
        candidats_alternatifs_geo = [
            chunk
            for chunk in BM25_CHUNKS
            if chunk_geographiquement_admissible(
                chunk,
                contrainte_localite,
            )
        ]

        chunks_alternatifs = selectionner_chunks_temporels(
            chunks=candidats_alternatifs_geo,
            temporalite=contraintes["temporal"],
            now=now,
        )

        # Assouplissement réservé aux demandes
        # sans localité précise.
        if not chunks_alternatifs and not demande_localisee:

            chunks_alternatifs = selectionner_chunks_temporels(
                chunks=BM25_CHUNKS,
                temporalite=contraintes["temporal"],
                now=now,
          )

        if chunks_alternatifs:

            chunks_finaux = chunks_alternatifs
            fallback_used = True
            data_status = "alternative_same_date"

        else:

            data_status = "unavailable"


    elif not chunks_finaux:

        data_status = "unavailable"


    # ========================================================
    # 5. FALLBACK VERS UNE AUTRE DATE
    # ========================================================

    mode_temporel = contraintes["temporal"].get("mode")

        # Conserver la contrainte géographique
    # également pour les bulletins expirés.
    chunks_fallback_geographiques = [
        chunk
        for chunk in chunks_categorie
        if chunk_geographiquement_admissible(
            chunk,
            contraintes["location"]
        )
    ]

    if not chunks_finaux and mode_temporel != "publication":

        chunks_finaux = (
            selectionner_chunks_fallback_expire(
                chunks=
                    chunks_fallback_geographiques,
                temporalite=
                    contraintes["temporal"],
                now=
                    now
            )
        )

        if chunks_finaux:

            fallback_used = True
            data_status = "stale"

        else:

            data_status = "unavailable"



    # ========================================================
    # 6. IDENTIFIANTS DES CHUNKS ADMISSIBLES
    # ========================================================

    chunk_ids = [
        chunk.get(
            "chunk_id"
        )
        for chunk
        in chunks_finaux
        if chunk.get(
            "chunk_id"
        )
    ]

    latest_available_until = None

    dates_fin = [
        parser_datetime_metadata(
            lire_champ_chunk(
                chunk,
                "date_fin_validite"
            )
        )
        for chunk in chunks_finaux
    ]

    dates_fin = [
        value
        for value in dates_fin
        if value is not None
    ]

    if dates_fin:
        latest_available_until = (
            max(
                dates_fin
            ).isoformat()
        )


    # ========================================================
    # 7. RÉSULTAT
    # ========================================================

    return {
        "query":
            query,

        "constraints":
            contraintes,

        "counts": {
            "initial":
                len(BM25_CHUNKS),

            "after_category":
                len(
                    chunks_categorie
                ),

            "after_temporal":
                len(
                    chunks_temporels
                ),


            "after_geography":
                len(chunks_geographiques),

            "after_temporal":
                len(chunks_temporels),


            "alternative_same_date":
                len(
                    chunks_alternatifs
                ),

            "final":
                len(
                    chunks_finaux
                ),
        },

        "data_status":
            data_status,

        "fallback_used":
            fallback_used,

        "chunks":
            chunks_finaux,

        "chunk_ids":
            chunk_ids,
        "latest_available_until":
            latest_available_until,
    }

# ============================================================
# 14. DENSE FILTRÉ
# ============================================================

def dense_retrieve_filtered(
    query,
    admissible_chunk_ids,
    top_k=HYBRID_METADATA_CANDIDATE_K
):

    start_total = (
        time.perf_counter()
    )

    admissible_chunk_ids = list(
        dict.fromkeys(
            admissible_chunk_ids
            or []
        )
    )

    if not admissible_chunk_ids:

        return {
            "retriever":
                "dense_filtered",
            "query":
                query,
            "top_k":
                top_k,
            "latency_ms":
                0.0,
            "results":
                [],
        }

    effective_top_k = min(
        int(top_k),
        len(
            admissible_chunk_ids
        )
    )

    query_vector = (
        encoder_requete(
            query
        )
    )

    client = (
        obtenir_client_qdrant_actif()
    )

    qdrant_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="chunk_id",
                match=models.MatchAny(
                    any=
                        admissible_chunk_ids
                )
            )
        ]
    )

    response = client.query_points(
        collection_name=
            COLLECTION_NAME,
        query=
            query_vector.tolist(),
        query_filter=
            qdrant_filter,
        limit=
            effective_top_k,
        with_payload=True,
        with_vectors=False
    )

    results = []

    for rank, point in enumerate(
        response.points,
        start=1
    ):

        payload = (
            point.payload
            or {}
        )

        metadata = (
            payload.get("metadata")
            or {}
        )

        def field(name):

            value = payload.get(
                name
            )

            if value not in (
                None,
                ""
            ):
                return value

            return metadata.get(
                name
            )

        results.append(
            {
                "rank":
                    rank,

                "score":
                    float(
                        point.score
                    ),

                "chunk_id":
                    field(
                        "chunk_id"
                    ),

                "content":
                    field(
                        "content"
                    ),

                "chunk_type":
                    field(
                        "chunk_type"
                    ),

                "retrieval_role":
                    field(
                        "retrieval_role"
                    ),

                "source_file":
                    field(
                        "source_file"
                    ),

                "category":
                    field(
                        "category"
                    ),

                "page":
                    field(
                        "page"
                    ),

                "localite":
                    field(
                        "localite"
                    ),

                "date_publication":
                    field(
                        "date_publication"
                    ),

                "date_debut_validite":
                    field(
                        "date_debut_validite"
                    ),

                "date_fin_validite":
                    field(
                        "date_fin_validite"
                    ),

                "image_path":
                    field(
                        "image_path"
                    ),
            }
        )

    return {
        "retriever":
            "dense_filtered",

        "query":
            query,

        "top_k":
            effective_top_k,

        "latency_ms":
            (
                time.perf_counter()
                - start_total
            ) * 1000,

        "results":
            results,
    }


# ============================================================
# 15. BM25 FILTRÉ
# ============================================================

def bm25_retrieve_filtered(
    query,
    admissible_chunk_ids,
    top_k=HYBRID_METADATA_CANDIDATE_K
):

    start_total = (
        time.perf_counter()
    )

    admissible_ids = set(
        admissible_chunk_ids
        or []
    )

    if not admissible_ids:

        return {
            "retriever":
                "bm25_filtered",
            "query":
                query,
            "top_k":
                top_k,
            "latency_ms":
                0.0,
            "results":
                [],
        }

    query_tokens = (
        tokeniser_bm25(
            query
        )
    )

    if not query_tokens:

        return {
            "retriever":
                "bm25_filtered",
            "query":
                query,
            "top_k":
                top_k,
            "latency_ms":
                0.0,
            "results":
                [],
        }

    scores = np.asarray(
        bm25_index.get_scores(
            query_tokens
        ),
        dtype=float
    )

    admissible_positions = [
        BM25_POSITION_BY_CHUNK_ID[
            chunk_id
        ]
        for chunk_id
        in admissible_ids
        if chunk_id
        in BM25_POSITION_BY_CHUNK_ID
    ]

    if not admissible_positions:

        return {
            "retriever":
                "bm25_filtered",
            "query":
                query,
            "top_k":
                top_k,
            "latency_ms":
                (
                    time.perf_counter()
                    - start_total
                ) * 1000,
            "results":
                [],
        }

    ranked_positions = sorted(
        admissible_positions,
        key=lambda index: (
            -scores[index],
            index
        )
    )

    positive_positions = [
        index
        for index in ranked_positions
        if scores[index] > 0
    ]

    if positive_positions:
        ranked_positions = (
            positive_positions
        )

    ranked_positions = (
        ranked_positions[
            :min(
                int(top_k),
                len(
                    ranked_positions
                )
            )
        ]
    )

    results = []

    for rank, index in enumerate(
        ranked_positions,
        start=1
    ):

        chunk = BM25_CHUNKS[
            index
        ]

        results.append(
            {
                "rank":
                    rank,

                "score":
                    float(
                        scores[index]
                    ),

                "chunk_id":
                    lire_champ_chunk(
                        chunk,
                        "chunk_id"
                    ),

                "content":
                    lire_champ_chunk(
                        chunk,
                        "content"
                    ),

                "chunk_type":
                    lire_champ_chunk(
                        chunk,
                        "chunk_type"
                    ),

                "retrieval_role":
                    lire_champ_chunk(
                        chunk,
                        "retrieval_role"
                    ),

                "source_file":
                    lire_champ_chunk(
                        chunk,
                        "source_file"
                    ),

                "category":
                    lire_champ_chunk(
                        chunk,
                        "category"
                    ),

                "page":
                    lire_champ_chunk(
                        chunk,
                        "page"
                    ),

                "localite":
                    lire_champ_chunk(
                        chunk,
                        "localite"
                    ),

                "date_publication":
                    lire_champ_chunk(
                        chunk,
                        "date_publication"
                    ),

                "date_debut_validite":
                    lire_champ_chunk(
                        chunk,
                        "date_debut_validite"
                    ),

                "date_fin_validite":
                    lire_champ_chunk(
                        chunk,
                        "date_fin_validite"
                    ),

                "image_path":
                    lire_champ_chunk(
                        chunk,
                        "image_path"
                    ),
            }
        )

    return {
        "retriever":
            "bm25_filtered",

        "query":
            query,

        "top_k":
            len(results),

        "latency_ms":
            (
                time.perf_counter()
                - start_total
            ) * 1000,

        "results":
            results,
    }


# ============================================================
# 16. FUSION RRF
# ============================================================

def fusion_rrf_metadata(
    dense_results,
    bm25_results,
    top_k,
    rrf_k=RRF_K
):

    fused = {}

    for (
        source_name,
        source_results
    ) in [
        (
            "dense",
            dense_results
        ),
        (
            "bm25",
            bm25_results
        ),
    ]:

        for item in source_results:

            chunk_id = item.get(
                "chunk_id"
            )

            if not chunk_id:
                continue

            rank = int(
                item["rank"]
            )

            if chunk_id not in fused:

                fused[
                    chunk_id
                ] = dict(
                    item
                )

                fused[
                    chunk_id
                ][
                    "rrf_score"
                ] = 0.0

                fused[
                    chunk_id
                ][
                    "retrieved_by"
                ] = []

            fused[
                chunk_id
            ][
                "rrf_score"
            ] += (
                1.0
                /
                (
                    rrf_k
                    + rank
                )
            )

            fused[
                chunk_id
            ][
                f"{source_name}_rank"
            ] = rank

            fused[
                chunk_id
            ][
                f"{source_name}_score"
            ] = float(
                item["score"]
            )

            fused[
                chunk_id
            ][
                "retrieved_by"
            ].append(
                source_name
            )

    fused_results = sorted(
        fused.values(),
        key=lambda item: (
            -item[
                "rrf_score"
            ],

            item.get(
                "dense_rank",
                float("inf")
            ),

            item.get(
                "bm25_rank",
                float("inf")
            ),

            str(
                item.get(
                    "chunk_id",
                    ""
                )
            )
        )
    )

    final_results = (
        fused_results[
            :top_k
        ]
    )

    for rank, item in enumerate(
        final_results,
        start=1
    ):

        item["rank"] = rank

        item["score"] = float(
            item[
                "rrf_score"
            ]
        )

    return final_results


# ============================================================
# 17. RETRIEVER FINAL
# ============================================================

def hybrid_metadata_retrieve(
    query,
    top_k=DEFAULT_TOP_K,
    candidate_k=
        HYBRID_METADATA_CANDIDATE_K,
    rrf_k=RRF_K,
    now=None
):

    _ensure_initialized()

    query = nettoyer_requete(
        query
    )

    if (
        not isinstance(
            top_k,
            int
        )
        or
        top_k <= 0
    ):
        raise ValueError(
            "top_k doit être un entier strictement positif."
        )

    start_total = (
        time.perf_counter()
    )

    start_filtering = (
        time.perf_counter()
    )

    admissibilite = (
        selectionner_chunks_admissibles(
            query=query,
            now=now
        )
    )

    admissible_chunk_ids = (
        admissibilite[
            "chunk_ids"
        ]
    )

    filtering_ms = (
        time.perf_counter()
        - start_filtering
    ) * 1000

    if not admissible_chunk_ids:

        return {
            "retriever":
                "hybrid_rrf_metadata",

            "query":
                query,

            "top_k":
                top_k,

            "candidate_k":
                candidate_k,

            "rrf_k":
                rrf_k,

            "constraints":
                admissibilite[
                    "constraints"
                ],

            "data_status":
                admissibilite.get(
                    "data_status",
                    "unavailable"
                ),

            "fallback_used":
                admissibilite.get(
                    "fallback_used",
                    False
                ),

            "latest_available_until":
                admissibilite.get(
                    "latest_available_until"
                ),

            "filter_counts":
                admissibilite[
                    "counts"
                ],

            "admissible_count":
                0,

            "latencies_ms": {
                "filtering":
                    filtering_ms,

                "parallel_retrieval":
                    0.0,

                "fusion":
                    0.0,

                "total":
                    (
                        time.perf_counter()
                        - start_total
                    ) * 1000,
            },

            "results":
                [],
        }

    effective_candidate_k = min(
        int(candidate_k),
        len(
            admissible_chunk_ids
        )
    )

    start_parallel = (
        time.perf_counter()
    )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        dense_future = (
            executor.submit(
                dense_retrieve_filtered,
                query,
                admissible_chunk_ids,
                effective_candidate_k
            )
        )

        bm25_future = (
            executor.submit(
                bm25_retrieve_filtered,
                query,
                admissible_chunk_ids,
                effective_candidate_k
            )
        )

        dense_output = (
            dense_future.result()
        )

        bm25_output = (
            bm25_future.result()
        )

    parallel_ms = (
        time.perf_counter()
        - start_parallel
    ) * 1000

    start_fusion = (
        time.perf_counter()
    )

    final_results = (
        fusion_rrf_metadata(
            dense_results=
                dense_output[
                    "results"
                ],

            bm25_results=
                bm25_output[
                    "results"
                ],

            top_k=
                top_k,

            rrf_k=
                rrf_k
        )
    )

    fusion_ms = (
        time.perf_counter()
        - start_fusion
    ) * 1000

    total_ms = (
        time.perf_counter()
        - start_total
    ) * 1000

    return {
        "retriever":
            "hybrid_rrf_metadata",

        "query":
            query,

        "top_k":
            top_k,

        "candidate_k":
            effective_candidate_k,

        "rrf_k":
            rrf_k,

        "constraints":
            admissibilite[
                "constraints"
            ],

        "data_status":
            admissibilite.get(
                "data_status",
                "valid"
            ),

        "fallback_used":
            admissibilite.get(
                "fallback_used",
                False
            ),

        "latest_available_until":
            admissibilite.get(
                "latest_available_until"
            ),

        "filter_counts":
            admissibilite[
                "counts"
            ],

        "admissible_count":
            len(
                admissible_chunk_ids
            ),

        "latencies_ms": {
            "filtering":
                filtering_ms,

            "parallel_retrieval":
                parallel_ms,

            "fusion":
                fusion_ms,

            "total":
                total_ms,
        },

        "results":
            final_results,
    }


# ============================================================
# 18. INTERFACE PUBLIQUE
# ============================================================

def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    now=None
):
    """
    Point d'entrée principal du Retriever MeteoGPT.

    En production, `now` reste None et l'heure courante
    d'Afrique/Dakar est utilisée automatiquement.

    `now` peut être fourni uniquement pour les tests
    reproductibles.
    """

    return hybrid_metadata_retrieve(
        query=query,
        top_k=top_k,
        now=now
    )


# ============================================================
# 19. INITIALISATION / RAFRAÎCHISSEMENT
# ============================================================

def initialize_retriever(
    client=None
):

    global _INITIALIZED

    if client is not None:
        set_qdrant_client(
            client
        )

    _construire_index_bm25()

    _charger_modele_embedding()

    obtenir_client_qdrant_actif()

    _INITIALIZED = True

    return {
        "initialized":
            True,

        "chunks":
            len(
                BM25_CHUNKS
            ),

        "localites":
            len(
                LOCALITES_CONNNUES
            ),

        "device":
            DEVICE,

        "embedding_model":
            EMBEDDING_MODEL_NAME,

        "collection":
            COLLECTION_NAME,

        "top_k":
            DEFAULT_TOP_K,
    }


def refresh_bm25_index():
    """
    À appeler après une mise à jour du corpus lorsque
    chunks_api.json a changé.
    """

    _construire_index_bm25()

    return {
        "chunks":
            len(
                BM25_CHUNKS
            ),

        "localites":
            len(
                LOCALITES_CONNNUES
            ),
    }


def _ensure_initialized():

    if not _INITIALIZED:
        initialize_retriever()


__all__ = [
    "initialize_retriever",
    "refresh_bm25_index",
    "retrieve",
    "hybrid_metadata_retrieve",
    "analyser_contraintes_metadata",
    "resoudre_temporalite",
    "DEFAULT_TOP_K",
]
