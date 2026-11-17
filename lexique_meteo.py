"""Identification lexicale de concepts météo, indépendante du routage Agent."""

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

LEXIQUE_PATH = (
    Path(__file__).resolve().parent
    / "data" / "referentiels" / "lexique_meteo.csv"
)


def normaliser_terme(texte: str) -> str:
    if not isinstance(texte, str):
        raise TypeError("texte doit être une chaîne de caractères")
    texte = unicodedata.normalize("NFKD", texte.casefold())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


@lru_cache(maxsize=8)
def _charger_lexique(chemin: str, mtime_ns: int, taille: int):
    index = {}
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier, delimiter=";")
        if not lecteur.fieldnames or not {
            "famille", "concept", "variantes"
        }.issubset(lecteur.fieldnames):
            raise ValueError("Colonnes attendues : famille;concept;variantes")

        for numero, ligne in enumerate(lecteur, start=2):
            famille = (ligne.get("famille") or "").strip()
            concept = (ligne.get("concept") or "").strip()
            if not famille or not concept:
                raise ValueError(f"Famille/concept absent à la ligne {numero}")
            formes = [concept, *((ligne.get("variantes") or "").split("|"))]
            for forme in formes:
                alias = normaliser_terme(forme)
                if not alias:
                    continue
                ancien = index.get(alias)
                if ancien and ancien != (famille, concept):
                    raise ValueError(
                        f"Variante ambiguë '{alias}' : {ancien[1]} / {concept}"
                    )
                index[alias] = (famille, concept)
    if not index:
        raise ValueError("Lexique météorologique vide")
    return tuple((alias, *meta) for alias, meta in index.items())


def reconnaitre_concepts_meteo(texte: str, chemin=None) -> list[dict]:
    """Repère des concepts dans le texte, sans décider de l'intention.

    Préfère une expression spécifique à un mot plus court qui la compose.
    Ne fait aucun appel au Retriever, à E5 ou à Gemini.
    """
    texte_normalise = normaliser_terme(texte)
    if not texte_normalise:
        return []
    fichier = Path(chemin) if chemin is not None else LEXIQUE_PATH
    stat = fichier.stat()  # Échec explicite si le référentiel manque.
    entrees = _charger_lexique(str(fichier.resolve()), stat.st_mtime_ns, stat.st_size)

    candidats = []
    for alias, famille, concept in entrees:
        motif = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        for match in re.finditer(motif, texte_normalise):
            candidats.append((match.start(), match.end(), famille, concept, alias))

    # Les expressions longues priment sur les sous-expressions.
    candidats.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
    retenus = []
    for candidat in candidats:
        debut, fin = candidat[:2]
        if any(debut < b and a < fin for a, b, *_ in retenus):
            continue
        retenus.append(candidat)

    resultat = []
    vus = set()
    for _, _, famille, concept, alias in sorted(retenus):
        identifiant = (famille, concept)
        if identifiant in vus:
            continue
        vus.add(identifiant)
        resultat.append({
            "famille": famille,
            "concept": concept,
            "expression": alias,
        })
    return resultat
