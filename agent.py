
# -*- coding: utf-8 -*-

"""
MeteoGPT — agent.py

Agent / orchestrateur de MeteoGPT.

Responsabilités :
- normalisation des requêtes ;
- détection des interactions évidentes ;
- classification déterministe des intentions ;
- fallback sémantique local E5 ;
- contextualisation conversationnelle ;
- personnalisation ;
- clarification ;
- décision multimodale ;
- orchestration LangGraph ;
- exposition de la fonction publique analyze_query().

Le Retriever reste implémenté séparément dans retriever.py.
La génération reste implémentée séparément dans generation.py.
"""


# ============================================================
# IMPORTS
# ============================================================

import re
import time
import unicodedata

import numpy as np

from datetime import datetime

from typing_extensions import (
    TypedDict,
    NotRequired,
)

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.checkpoint.memory import (
    InMemorySaver,
)

import retriever


# ============================================================
# 1. ROUTES
# ============================================================

ROUTE_RAG = "rag"

ROUTE_DIRECT_LLM = "direct_llm"

ROUTE_STATIC = "static"

ROUTE_CLARIFY = "clarify"

ROUTE_OUT_OF_SCOPE = "out_of_scope"


AGENT_ROUTES = {
    ROUTE_RAG,
    ROUTE_DIRECT_LLM,
    ROUTE_STATIC,
    ROUTE_CLARIFY,
    ROUTE_OUT_OF_SCOPE,
}


# ============================================================
# 2. INTENTIONS
# ============================================================

INTENT_METEO_GENERALE = "meteo_generale"

INTENT_METEO_LOCALE = "meteo_locale"

INTENT_METEO_72H = "meteo_72h"

INTENT_NAVIGATION_COTIERE = "navigation_cotiere"

INTENT_PECHE_ARTISANALE = "peche_artisanale"

INTENT_MARINE_NATIONALE = "marine_nationale"

INTENT_HISTORIQUE = "historique"

INTENT_METEO_KNOWLEDGE = "meteo_knowledge"

INTENT_GREETING = "greeting"

INTENT_CAPABILITIES = "capabilities"

INTENT_PERSONALIZATION = "personalization"

INTENT_OUT_OF_SCOPE = "out_of_scope"

INTENT_UNKNOWN = "unknown"


AGENT_INTENTS = {
    INTENT_METEO_GENERALE,
    INTENT_METEO_LOCALE,
    INTENT_METEO_72H,
    INTENT_NAVIGATION_COTIERE,
    INTENT_MARINE_NATIONALE,
    INTENT_PECHE_ARTISANALE,
    INTENT_HISTORIQUE,
    INTENT_METEO_KNOWLEDGE,
    INTENT_GREETING,
    INTENT_CAPABILITIES,
    INTENT_PERSONALIZATION,
    INTENT_OUT_OF_SCOPE,
    INTENT_UNKNOWN,
}


# ============================================================
# 3. MAPPING INTENTION → ROUTE
# ============================================================

INTENT_TO_ROUTE = {

    INTENT_METEO_GENERALE:
        ROUTE_RAG,

    INTENT_METEO_LOCALE:
        ROUTE_RAG,

    INTENT_METEO_72H:
        ROUTE_RAG,

    INTENT_NAVIGATION_COTIERE:
        ROUTE_RAG,

    INTENT_MARINE_NATIONALE:
        ROUTE_RAG,

    INTENT_PECHE_ARTISANALE:
        ROUTE_RAG,

    INTENT_HISTORIQUE:
        ROUTE_RAG,

    INTENT_METEO_KNOWLEDGE:
        ROUTE_DIRECT_LLM,

    INTENT_GREETING:
        ROUTE_STATIC,

    INTENT_CAPABILITIES:
        ROUTE_STATIC,

    INTENT_PERSONALIZATION:
        ROUTE_STATIC,

    INTENT_OUT_OF_SCOPE:
        ROUTE_OUT_OF_SCOPE,

    INTENT_UNKNOWN:
        ROUTE_CLARIFY,
}


# ============================================================
# 4. STRUCTURE STANDARD D'UNE DÉCISION
# ============================================================

def construire_decision_agent(
    query,
    route,
    intent,
    *,
    needs_retrieval=False,
    needs_visual=False,
    needs_clarification=False,
    clarification_message=None,
    offer_personalization=False,
    personalization_action=None,
    context_used=False,
    confidence=1.0
):
    """
    Construit la structure standard retournée
    par l'Agent MeteoGPT.
    """

    # --------------------------------------------------------
    # Validation requête
    # --------------------------------------------------------

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )

    query = " ".join(
        query.split()
    ).strip()

    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )

    # --------------------------------------------------------
    # Validation route
    # --------------------------------------------------------

    if route not in AGENT_ROUTES:

        raise ValueError(
            f"Route Agent inconnue : {route}"
        )

    # --------------------------------------------------------
    # Validation intention
    # --------------------------------------------------------

    if intent not in AGENT_INTENTS:

        raise ValueError(
            f"Intention Agent inconnue : {intent}"
        )

    # --------------------------------------------------------
    # Validation confiance
    # --------------------------------------------------------

    confidence = float(
        confidence
    )

    if not (
        0.0
        <= confidence
        <= 1.0
    ):

        raise ValueError(
            "confidence doit être comprise entre 0 et 1."
        )

    return {

        "query":
            query,

        "route":
            route,

        "intent":
            intent,

        "needs_retrieval":
            bool(
                needs_retrieval
            ),

        "needs_visual":
            bool(
                needs_visual
            ),

        "needs_clarification":
            bool(
                needs_clarification
            ),

        "clarification_message":
            clarification_message,

        "offer_personalization":
            bool(
                offer_personalization
            ),

        "personalization_action":
            personalization_action,

        "context_used":
            bool(
                context_used
            ),

        "confidence":
            confidence,
    }


# ============================================================
# 5. NORMALISATION DE LA REQUÊTE
# ============================================================

def normaliser_requete_agent(
    query: str
) -> str:
    """
    Normalise une requête pour les règles
    déterministes de l'Agent.
    """

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )

    query = (
        query
        .strip()
        .lower()
    )

    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )

    # Unicode / accents
    query = unicodedata.normalize(
        "NFKD",
        query
    )

    query = "".join(
        char
        for char in query
        if not unicodedata.combining(
            char
        )
    )

    # Ponctuation
    query = (
        query
        .replace(
            "’",
            "'"
        )
        .replace(
            "`",
            "'"
        )
        .replace(
            "-",
            " "
        )
    )

    query = re.sub(
        r"[!?.,;:]+",
        " ",
        query
    )

    query = " ".join(
        query.split()
    )

    return query


# ============================================================
# 6. INTERACTIONS ÉVIDENTES
# ============================================================

SALUTATIONS_AGENT = {
    "bonjour",
    "bonsoir",
    "salut",
    "hello",
    "hi",
    "coucou",
    "hey",
    "salam",
    "salam aleikoum",
    "assalamou aleikoum",
}


EXPRESSIONS_CAPABILITIES = [
    "que peux tu faire",
    "qu est ce que tu peux faire",
    "quelles sont tes fonctionnalites",
    "quelles sont vos fonctionnalites",
    "comment peux tu m aider",
    "comment pouvez vous m aider",
    "a quoi sers tu",
    "a quoi sert meteogpt",
    "presente toi",
    "qui es tu",
]


EXPRESSIONS_PERSONALIZATION = [
    "personnaliser",
    "personnalisation",
    "personnalise",
    "mes preferences",
    "mes preferences meteo",
    "modifier mes preferences",
    "changer mes preferences",
    "ma localite par defaut",
    "ville par defaut",
    "localite par defaut",
    "mes informations par defaut",
]


def detecter_interaction_evidente(
    query: str
):
    """
    Détecte une interaction pouvant être routée
    immédiatement sans analyse météorologique avancée.
    """

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    # --------------------------------------------------------
    # Salutation
    # --------------------------------------------------------

    if query_norm in SALUTATIONS_AGENT:

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_STATIC,

            intent=
                INTENT_GREETING,

            needs_retrieval=False,

            needs_visual=False,

            needs_clarification=False,

            offer_personalization=False,

            confidence=1.0
        )

    # --------------------------------------------------------
    # Capacités
    # --------------------------------------------------------

    if any(
        expression in query_norm
        for expression
        in EXPRESSIONS_CAPABILITIES
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_STATIC,

            intent=
                INTENT_CAPABILITIES,

            needs_retrieval=False,

            needs_visual=False,

            needs_clarification=False,

            offer_personalization=False,

            confidence=1.0
        )

    # --------------------------------------------------------
    # Personnalisation
    # --------------------------------------------------------

    if any(
        expression in query_norm
        for expression
        in EXPRESSIONS_PERSONALIZATION
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_STATIC,

            intent=
                INTENT_PERSONALIZATION,

            needs_retrieval=False,

            needs_visual=False,

            needs_clarification=False,

            offer_personalization=False,

            personalization_action=
                "open_personalization",

            confidence=1.0
        )

    return None


# ============================================================
# 7. NORMALISATION POUR INTENTION
# ============================================================

def normaliser_pour_intention(
    query: str
) -> str:
    """
    Normalisation adaptée à la détection
    d'intention.
    """

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    query_norm = (
        query_norm
        .replace(
            "'",
            " "
        )
        .replace(
            "’",
            " "
        )
    )

    query_norm = " ".join(
        query_norm.split()
    )

    return query_norm


def correspond_a_un_pattern(
    texte,
    patterns
):

    return any(
        re.search(
            pattern,
            texte,
            flags=re.IGNORECASE
        )
        is not None
        for pattern in patterns
    )


# ============================================================
# 8. PATTERNS MÉTÉOROLOGIQUES
# ============================================================

PATTERNS_72H = [

    r"\b72\s*(?:h|heures?)\b",

    r"\b72\s+prochain(?:e|es|s)?\s+heures?\b",

    r"\b(?:3|trois)\s+jours?\b",

    r"\b(?:3|trois)\s+prochain(?:e|es|s)?\s+jours?\b",

    r"\bprochain(?:e|es|s)?\s+(?:3|trois)\s+jours?\b",

    r"\b(?:3|trois)\s+jours?\s+a\s+venir\b",
]


PATTERNS_KNOWLEDGE_FORM = [

    r"\bqu est ce qu\b",

    r"\bc est quoi\b",

    r"\bque signifie\b",

    r"\bque veut dire\b",

    r"\bdefinition\b",

    r"\bexplique(?:r)?\b",

    r"\bexplique moi\b",

    r"\bcomment .* fonctionne\b",

    r"\bcomment .* se forme\b",

    r"\bcomment se forme\b",

    r"\bpourquoi\b",

    r"\bquelle est la difference\b",

    r"\bquelle difference\b",
]


PATTERNS_CONCEPTS_METEO = [

    r"\bmeteo(?:rologie)?\b",

    r"\bclimat\b",

    r"\banticyclon",

    r"\bdepression(?:\s+atmospherique)?\b",

    r"\bpression\s+atmospherique\b",

    r"\bonde\s+tropicale\b",

    r"\bcyclon",

    r"\bouragan",

    r"\btornad",

    r"\borage",

    r"\bfoudre\b",

    r"\beclair",

    r"\bnuage",

    r"\bprecipitation",

    r"\bhumidit",

    r"\btemperature\b",

    r"\bvent\b",

    r"\bhoule\b",

    r"\bbrouillard\b",

    r"\bvisibilite\b",

    r"\bmousson\b",

    r"\bharmattan\b",

    r"\balize",

    r"\bfront\s+froid\b",

    r"\bfront\s+chaud\b",

    r"\bisobare",

    r"\bpoint\s+de\s+rosee\b",

    r"\bconvection\b",
]


PATTERNS_DONNEES_METEO = [

    r"\bmeteo\b",

    r"\btemps\b",

    r"\bprevision",

    r"\bpleuv",

    r"\bpluie",

    r"\baverse",

    r"\borages?\b",

    r"\btemperature",

    r"\bchaud\b",

    r"\bfroid\b",

    r"\bvent",

    r"\bhoule\b",

    r"\betat\s+de\s+la\s+mer\b",

    r"\bmer\b",

    r"\bvisibilite\b",

    r"\bciel\b",

    r"\bnuage",

    r"\bhumidite\b",
]


# ============================================================
# 9. DÉTECTION DÉTERMINISTE DES INTENTIONS MÉTÉO
# ============================================================

def detecter_intention_meteo(
    query: str,
    now=None
):
    """
    Premier niveau de classification.

    Retourne une décision uniquement lorsqu'une
    intention peut être déterminée avec une
    confiance suffisamment élevée.

    Sinon retourne None.
    """

    if now is None:

        now = datetime.now(
            retriever.METEOGPT_TIMEZONE
        )

    query_norm = (
        normaliser_pour_intention(
            query
        )
    )

    # ========================================================
    # A. CONNAISSANCE MÉTÉOROLOGIQUE
    # ========================================================

    forme_connaissance = (
        correspond_a_un_pattern(
            query_norm,
            PATTERNS_KNOWLEDGE_FORM
        )
    )

    concept_meteo = (
        correspond_a_un_pattern(
            query_norm,
            PATTERNS_CONCEPTS_METEO
        )
    )

    if (
        forme_connaissance
        and
        concept_meteo
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_DIRECT_LLM,

            intent=
                INTENT_METEO_KNOWLEDGE,

            needs_retrieval=False,

            needs_visual=False,

            needs_clarification=False,

            offer_personalization=False,

            confidence=0.98
        )

    # ========================================================
    # B. CATÉGORIE MÉTIER
    # ========================================================

    categorie = (
        retriever.detecter_categories_requete(
            query
        )
    )

    categories = (
        categorie.get(
            "categories",
            []
        )
    )


    # Marine nationale explicite
    if categories == [
        "marine_nationale"
    ]:

        return construire_decision_agent(
            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_MARINE_NATIONALE,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=1.0
        )

    # Navigation côtière
    if (
        categories == [
            "navigation_cotiere"
        ]
        or
        set(categories)
        == {
            "navigation_cotiere",
            "marine_nationale",
        }
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_NAVIGATION_COTIERE,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=1.0
        )

    # Pêche artisanale
    if categories == [
        "peche_artisanale"
    ]:

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_PECHE_ARTISANALE,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=1.0
        )

    # ========================================================
    # C. PRÉVISIONS 72H
    # ========================================================

    demande_72h = (
        categories == [
            "meteo_72h"
        ]
        or
        correspond_a_un_pattern(
            query_norm,
            PATTERNS_72H
        )
    )

    if demande_72h:

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_METEO_72H,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=1.0
        )

    # ========================================================
    # D. TEMPORALITÉ / HISTORIQUE
    # ========================================================

    temporalite = (
        retriever.resoudre_temporalite(
            query,
            now=now
        )
    )

    target_start = (
        temporalite.get(
            "start"
        )
    )

    expression_temporelle = (
        temporalite.get(
            "expression"
        )
    )

    est_historique = False

    if (
        expression_temporelle
        == "hier"
    ):

        est_historique = True

    elif (
        target_start is not None
        and
        target_start.date()
        < now.date()
    ):

        est_historique = True

    if est_historique:

        if correspond_a_un_pattern(
            query_norm,
            PATTERNS_DONNEES_METEO
        ):

            return construire_decision_agent(

                query=query,

                route=
                    ROUTE_RAG,

                intent=
                    INTENT_HISTORIQUE,

                needs_retrieval=True,

                offer_personalization=False,

                confidence=0.98
            )

    # ========================================================
    # E. LOCALITÉ CONNUE
    # ========================================================

    localite = (
        retriever.detecter_localite_requete(
            query
        )
    )

    if (
        localite.get(
            "mode"
        )
        ==
        "specific"
        and
        correspond_a_un_pattern(
            query_norm,
            PATTERNS_DONNEES_METEO
        )
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_METEO_LOCALE,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=1.0
        )

    # ========================================================
    # F. MÉTÉO GÉNÉRALE
    # ========================================================

    if correspond_a_un_pattern(
        query_norm,
        PATTERNS_DONNEES_METEO
    ):

        return construire_decision_agent(

            query=query,

            route=
                ROUTE_RAG,

            intent=
                INTENT_METEO_GENERALE,

            needs_retrieval=True,

            offer_personalization=True,

            confidence=0.90
        )

    # Aucun classement déterministe fiable.
    return None


# ============================================================
# 10. FALLBACK SÉMANTIQUE E5
# ============================================================

INTENT_PROTOTYPES = {

    INTENT_METEO_GENERALE: [
        "quelle est la météo aujourd'hui",
        "quel temps fera-t-il",
        "est-ce qu'il va pleuvoir",
    ],

    INTENT_METEO_LOCALE: [
        "quelle est la météo à Dakar",
        "quel temps fera-t-il dans cette ville",
        "prévisions météorologiques pour une localité précise",
    ],

    INTENT_METEO_72H: [
        "prévisions météorologiques pour les trois prochains jours",
        "météo pour les prochaines 72 heures",
    ],

    INTENT_MARINE_NATIONALE: [
        "donne-moi le bulletin marine nationale",
        "quelle est la météo marine nationale",
        "prévisions du bulletin marine nationale",
    ],

    INTENT_NAVIGATION_COTIERE: [
        "quel est l'état de la mer",
        "quelle est la houle pour la navigation côtière",
        "conditions maritimes pour naviguer",
    ],

    INTENT_PECHE_ARTISANALE: [
        "quelles sont les conditions pour les pêcheurs artisanaux",
        "conditions météo pour aller pêcher",
    ],

    INTENT_HISTORIQUE: [
        "quel temps faisait-il hier",
        "quelle était la météo à une date passée",
    ],

    INTENT_METEO_KNOWLEDGE: [
        "pourquoi se forme un orage",
        "expliquer un phénomène météorologique",
        "comment fonctionne un phénomène climatique",
        "pourquoi l'air chaud contient davantage de vapeur d'eau",
    ],

    INTENT_GREETING: [
        "bonjour",
        "salut",
    ],

    INTENT_CAPABILITIES: [
        "que peux-tu faire",
        "quels services peux-tu me rendre",
        "quelles sont les fonctionnalités de MeteoGPT",
    ],

    INTENT_PERSONALIZATION: [
        "je veux personnaliser mes prévisions",
        "adapter les prévisions à ma ville",
        "modifier mes préférences MeteoGPT",
    ],

    INTENT_OUT_OF_SCOPE: [
        "quel est le prix du Bitcoin",
        "qui a gagné le match",
        "donne-moi une recette de cuisine",
        "parle-moi de football",
    ],
}


# ============================================================
# 11. CONSTRUCTION DES VECTEURS PROTOTYPES
# ============================================================

def _construire_vecteurs_intentions():
    """
    Encode une seule fois les exemples de chaque
    intention afin de construire les prototypes E5.
    """

    vecteurs_intentions = {}

    for intent, exemples in (
        INTENT_PROTOTYPES.items()
    ):

        vecteurs = [

            retriever.encoder_requete(
                exemple
            )

            for exemple in exemples
        ]

        prototype = np.mean(
            vecteurs,
            axis=0
        )

        prototype = (
            prototype
            /
            (
                np.linalg.norm(
                    prototype
                )
                +
                1e-12
            )
        )

        vecteurs_intentions[
            intent
        ] = prototype

    return vecteurs_intentions


INTENT_VECTORS = (
    _construire_vecteurs_intentions()
)


# ============================================================
# 12. CLASSIFICATEUR E5
# ============================================================

def classifier_fallback_e5(
    query: str
):
    """
    Compare une requête aux prototypes d'intention
    à partir des embeddings E5.
    """

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )

    query = " ".join(
        query.split()
    ).strip()

    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )

    debut = (
        time.perf_counter()
    )

    query_vector = (
        retriever.encoder_requete(
            query
        )
    )

    scores = {

        intent:
            float(
                np.dot(
                    query_vector,
                    prototype
                )
            )

        for intent, prototype
        in INTENT_VECTORS.items()
    }

    classement = sorted(

        scores.items(),

        key=lambda item:
            item[1],

        reverse=True
    )

    best_intent, best_score = (
        classement[0]
    )

    second_intent, second_score = (
        classement[1]
    )

    latence_ms = (
        time.perf_counter()
        -
        debut
    ) * 1000

    return {

        "intent":
            best_intent,

        "score":
            best_score,

        "second_intent":
            second_intent,

        "second_score":
            second_score,

        "margin":
            (
                best_score
                -
                second_score
            ),

        "latency_ms":
            latence_ms,
    }


# ============================================================
# 13. VALIDATION DU FALLBACK E5
# ============================================================

FALLBACK_E5_MIN_SCORE = 0.88

FALLBACK_E5_MIN_MARGIN = 0.02


def classifier_requete_fallback(
    query: str
):
    """
    Retourne une décision Agent uniquement si la
    classification E5 est suffisamment fiable.
    """

    resultat = (
        classifier_fallback_e5(
            query
        )
    )

    intent = resultat[
        "intent"
    ]

    score = resultat[
        "score"
    ]

    margin = resultat[
        "margin"
    ]

    # --------------------------------------------------------
    # Confiance
    # --------------------------------------------------------

    if (
        score
        < FALLBACK_E5_MIN_SCORE
        or
        margin
        < FALLBACK_E5_MIN_MARGIN
    ):

        return None

    route = INTENT_TO_ROUTE[
        intent
    ]

    needs_retrieval = (
        route == ROUTE_RAG
    )

    offer_personalization = (

        intent
        in {
            INTENT_METEO_GENERALE,
            INTENT_METEO_LOCALE,
            INTENT_METEO_72H,
            INTENT_NAVIGATION_COTIERE,
            INTENT_PECHE_ARTISANALE,
            INTENT_MARINE_NATIONALE,
        }
    )

    personalization_action = (

        "open_personalization"

        if intent
        == INTENT_PERSONALIZATION

        else None
    )

    return construire_decision_agent(

        query=query,

        route=route,

        intent=intent,

        needs_retrieval=
            needs_retrieval,

        needs_visual=False,

        needs_clarification=False,

        clarification_message=None,

        offer_personalization=
            offer_personalization,

        personalization_action=
            personalization_action,

        context_used=False,

        confidence=score
    )


# ============================================================
# 14. PROFILS ET PRÉFÉRENCES
# ============================================================

USER_TYPES = {
    "grand_public",
    "agriculteur",
    "pecheur",
    "navigation",
    "aviation",
    "autorite",
}


# NOTE :
# Cette valeur est conservée telle qu'elle existe dans
# la version actuellement validée du notebook.
AUTHORITY_SUBTYPES = {
    "administrite",
    "collectivite_locale",
    "protection_civile",
    "gestion_crise",
    "securite",
}


DEFAULT_USER_PREFERENCES = {
    "preferred_location": None,
    "user_type": None,
    "user_subtype": None,
    "interests": [],
    "detail_level": "normal",
}


def normaliser_preferences_utilisateur(
    user_preferences=None
):
    """
    Construit un profil utilisateur propre et validé.
    """

    preferences = dict(
        DEFAULT_USER_PREFERENCES
    )

    if user_preferences:

        preferences.update(
            user_preferences
        )

    user_type = preferences.get(
        "user_type"
    )

    if (
        user_type is not None
        and
        user_type not in USER_TYPES
    ):

        raise ValueError(
            f"Type utilisateur invalide : {user_type}"
        )

    user_subtype = preferences.get(
        "user_subtype"
    )

    if (
        user_type == "autorite"
        and
        user_subtype is not None
        and
        user_subtype not in AUTHORITY_SUBTYPES
    ):

        raise ValueError(
            f"Sous-type d'autorité invalide : {user_subtype}"
        )

    if user_type != "autorite":

        preferences[
            "user_subtype"
        ] = None

    return preferences


# ============================================================
# 15. DÉTECTION D'UNE REQUÊTE DE SUIVI
# ============================================================

def est_requete_de_suivi(
    query: str
) -> bool:
    """
    Détecte les formulations dépendant du
    contexte conversationnel précédent.
    """

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    patterns = [
        r"^et\b",
        r"^demain\b",
        r"^apres demain\b",
        r"^aujourd hui\b",
        r"^hier\b",
        r"\bla bas\b",
        r"\bici\b",
        r"\bchez moi\b",
        r"\bdans ma zone\b",
    ]

    return any(
        re.search(
            pattern,
            query_norm
        )
        for pattern in patterns
    )


# ============================================================
# 16. CONTEXTUALISATION
# ============================================================

def enrichir_requete_contexte(
    query: str,
    session_context=None,
    user_preferences=None
):
    """
    Applique la priorité :

    requête explicite
        >
    contexte de session
        >
    préférences utilisateur

    Un profil métier ne remplace jamais une intention
    explicitement formulée par l'utilisateur.
    """

    session_context = dict(
        session_context
        or {}
    )

    preferences = (
        normaliser_preferences_utilisateur(
            user_preferences
        )
    )

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )

    query = " ".join(
        query.split()
    ).strip()

    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )

    effective_query = query

    context_used = False

    context_sources = []

    # ========================================================
    # LOCALITÉ EXPLICITE
    # ========================================================

    localisation = (
        retriever.detecter_localite_requete(
            query
        )
    )

    explicit_location = (

        localisation.get(
            "localite"
        )

        if localisation.get(
            "mode"
        ) == "specific"

        else None
    )

    # ========================================================
    # RÉSOLUTION DE LA LOCALITÉ
    # ========================================================

    resolved_location = (
        explicit_location
    )

    if resolved_location is None:

        session_location = (
            session_context.get(
                "last_location"
            )
        )

        if session_location:

            resolved_location = (
                session_location
            )

            context_sources.append(
                "session_location"
            )

        elif preferences.get(
            "preferred_location"
        ):

            resolved_location = (
                preferences[
                    "preferred_location"
                ]
            )

            context_sources.append(
                "preferred_location"
            )

    # ========================================================
    # PROFIL
    # ========================================================

    resolved_user_type = (

        session_context.get(
            "last_user_type"
        )

        or

        preferences.get(
            "user_type"
        )
    )

    resolved_user_subtype = (

        preferences.get(
            "user_subtype"
        )

        if resolved_user_type
        == "autorite"

        else None
    )

    # ========================================================
    # REQUÊTE DE SUIVI
    # ========================================================

    if (
        est_requete_de_suivi(
            query
        )
        and
        explicit_location is None
        and
        resolved_location
    ):

        effective_query = (
            query.rstrip(
                " ?"
            )
            +
            f" à {resolved_location} ?"
        )

        context_used = True

    # ========================================================
    # DEMANDES GÉNÉRIQUES
    # ========================================================

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    patterns_metier_explicites = [
        r"\bpeche\b",
        r"\bpecheur\b",
        r"\bpecheurs\b",
        r"\bnavigation\b",
        r"\bnaviguer\b",
        r"\bmaritime\b",
        r"\bmer\b",
        r"\bhoule\b",
    ]

    contient_metier_explicite = any(

        re.search(
            pattern,
            query_norm
        )

        for pattern
        in patterns_metier_explicites
    )

    demande_conditions_generique = (
        "conditions"
        in query_norm

        and

        not contient_metier_explicite
    )

    # --------------------------------------------------------
    # Localité pour demande générique
    # --------------------------------------------------------

    if (
        demande_conditions_generique
        and
        explicit_location is None
        and
        resolved_location
        and
        resolved_location.lower()
        not in effective_query.lower()
    ):

        effective_query = (
            effective_query.rstrip(
                " ?"
            )
            +
            f" à {resolved_location} ?"
        )

        context_used = True

    # --------------------------------------------------------
    # Profil pêcheur
    # --------------------------------------------------------

    if demande_conditions_generique:

        if (
            resolved_user_type
            == "pecheur"
        ):

            effective_query = (
                effective_query.rstrip(
                    " ?"
                )
                +
                " pour la pêche artisanale ?"
            )

            context_used = True

            if (
                "user_type"
                not in context_sources
            ):

                context_sources.append(
                    "user_type"
                )

        # ----------------------------------------------------
        # Profil navigation
        # ----------------------------------------------------

        elif (
            resolved_user_type
            == "navigation"
        ):

            effective_query = (
                effective_query.rstrip(
                    " ?"
                )
                +
                " pour la navigation côtière ?"
            )

            context_used = True

            if (
                "user_type"
                not in context_sources
            ):

                context_sources.append(
                    "user_type"
                )

    return {

        "query":
            query,

        "effective_query":
            effective_query,

        "resolved_location":
            resolved_location,

        "resolved_user_type":
            resolved_user_type,

        "resolved_user_subtype":
            resolved_user_subtype,

        "interests":
            preferences.get(
                "interests",
                []
            ),

        "detail_level":
            preferences.get(
                "detail_level",
                "normal"
            ),

        "context_used":
            context_used,

        "context_sources":
            context_sources,
    }


# ============================================================
# 17. MÉMOIRE DE SESSION
# ============================================================

def mettre_a_jour_contexte_session(
    session_context,
    contextualisation,
    decision=None
):
    """
    Met à jour uniquement les informations utiles
    à la continuité conversationnelle.
    """

    contexte = dict(
        session_context
        or {}
    )

    # Localité
    if contextualisation.get(
        "resolved_location"
    ):

        contexte[
            "last_location"
        ] = contextualisation[
            "resolved_location"
        ]

    # Profil
    if contextualisation.get(
        "resolved_user_type"
    ):

        contexte[
            "last_user_type"
        ] = contextualisation[
            "resolved_user_type"
        ]

    # Intention
    if (
        decision
        and
        decision.get(
            "intent"
        )
        not in {
            INTENT_GREETING,
            INTENT_CAPABILITIES,
            INTENT_OUT_OF_SCOPE,
            INTENT_UNKNOWN,
        }
    ):

        contexte[
            "last_intent"
        ] = decision[
            "intent"
        ]

    return contexte


# ============================================================
# 18. CLARIFICATION
# ============================================================

def detecter_besoin_clarification(
    query: str,
    session_context=None,
    user_preferences=None
):
    """
    Détecte uniquement les ambiguïtés empêchant
    réellement l'interprétation de la requête.
    """

    session_context = dict(
        session_context
        or {}
    )

    preferences = (
        normaliser_preferences_utilisateur(
            user_preferences
        )
    )

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    references_ambigues = [
        r"\bla bas\b",
        r"\bdans cette zone\b",
        r"\ba cet endroit\b",
        r"\bpour eux\b",
        r"\bchez eux\b",
    ]

    reference_ambigue = any(

        re.search(
            pattern,
            query_norm
        )

        for pattern
        in references_ambigues
    )

    if not reference_ambigue:

        return {
            "needs_clarification":
                False,

            "clarification_message":
                None,
        }

    contexte_disponible = any([
        session_context.get(
            "last_location"
        ),
        session_context.get(
            "last_intent"
        ),
        preferences.get(
            "preferred_location"
        ),
    ])

    if contexte_disponible:

        return {
            "needs_clarification":
                False,

            "clarification_message":
                None,
        }

    return {

        "needs_clarification":
            True,

        "clarification_message":
            (
                "Pouvez-vous préciser la localité ou "
                "la zone météorologique concernée ?"
            ),
    }


# ============================================================
# 19. BESOIN VISUEL EXPLICITE
# ============================================================

def detecter_besoin_visuel(
    query: str
) -> bool:
    """
    Détecte une demande nécessitant potentiellement
    l'analyse d'un élément visuel.
    """

    query_norm = (
        normaliser_requete_agent(
            query
        )
    )

    termes_visuels = [
        r"\bcette carte\b",
        r"\bla carte\b",
        r"\bcette image\b",
        r"\bl image\b",
        r"\bcette figure\b",
        r"\ble graphique\b",
        r"\bcette capture\b",
        r"\bmontre cette\b",
        r"\bque montre\b",
        r"\binterpreter.*carte\b",
        r"\banalyser.*image\b",

        r"\bce visuel\b",
        r"\ble visuel\b",
        r"\bvisuel meteo\b",
        r"\bregarder.*visuel\b",
        r"\banalyser.*visuel\b",
    ]

    return any(

        re.search(
            pattern,
            query_norm
        )

        for pattern
        in termes_visuels
    )


# ============================================================
# 20. MULTIMODALITÉ IMPOSÉE PAR LA SOURCE
# ============================================================

VISUAL_SOURCE_INTENTS = {
    INTENT_NAVIGATION_COTIERE,
    INTENT_PECHE_ARTISANALE,
}


def determiner_besoin_multimodal(
    intent: str,
    needs_visual: bool = False
):
    """
    Distingue :
    - besoin visuel explicite utilisateur ;
    - besoin visuel imposé par la source.
    """

    source_requires_visual = (
        intent
        in VISUAL_SOURCE_INTENTS
    )

    use_multimodal = (
        bool(
            needs_visual
        )
        or
        source_requires_visual
    )

    return {

        "needs_visual":
            bool(
                needs_visual
            ),

        "source_requires_visual":
            source_requires_visual,

        "use_multimodal":
            use_multimodal,
    }


# ============================================================
# 21. STATE LANGGRAPH
# ============================================================

class AgentState(
    TypedDict
):

    query: str

    effective_query: NotRequired[
        str
    ]

    session_context: NotRequired[
        dict
    ]

    user_preferences: NotRequired[
        dict
    ]

    contextualisation: NotRequired[
        dict
    ]

    needs_visual: NotRequired[
        bool
    ]

    decision: NotRequired[
        dict | None
    ]


# ============================================================
# 22. NŒUD — CONTEXTUALISATION
# ============================================================

def node_contextualiser(
    state: AgentState
):
    """
    Construit la requête effective selon :
    requête > session > préférences.
    """

    resultat = (
        enrichir_requete_contexte(

            query=
                state[
                    "query"
                ],

            session_context=
                state.get(
                    "session_context",
                    {}
                ),

            user_preferences=
                state.get(
                    "user_preferences",
                    {}
                )
        )
    )

    return {

        "effective_query":
            resultat[
                "effective_query"
            ],

        "contextualisation":
            resultat,

        # Nettoyage de l'état transitoire
        "decision":
            None,

        "needs_visual":
            False,
    }


# ============================================================
# 23. NŒUD — CAS SPÉCIAUX
# ============================================================

def node_analyser_cas_speciaux(
    state: AgentState
):
    """
    Analyse :
    - clarification ;
    - besoin visuel explicite.
    """

    query = state[
        "effective_query"
    ]

    clarification = (
        detecter_besoin_clarification(

            query=query,

            session_context=
                state.get(
                    "session_context",
                    {}
                ),

            user_preferences=
                state.get(
                    "user_preferences",
                    {}
                )
        )
    )

    needs_visual = (
        detecter_besoin_visuel(
            query
        )
    )

    if clarification[
        "needs_clarification"
    ]:

        decision = (
            construire_decision_agent(

                query=
                    state[
                        "query"
                    ],

                route=
                    ROUTE_CLARIFY,

                intent=
                    INTENT_UNKNOWN,

                needs_retrieval=False,

                needs_visual=
                    needs_visual,

                needs_clarification=True,

                clarification_message=
                    clarification[
                        "clarification_message"
                    ],

                offer_personalization=False,

                context_used=
                    state[
                        "contextualisation"
                    ][
                        "context_used"
                    ],

                confidence=1.0
            )
        )

        return {

            "needs_visual":
                needs_visual,

            "decision":
                decision,
        }

    return {

        "needs_visual":
            needs_visual,

        "decision":
            None,
    }


# ============================================================
# 24. INTENTIONS HÉRITABLES EN SUIVI
# ============================================================

FOLLOWUP_INHERITABLE_INTENTS = {
    INTENT_METEO_GENERALE,
    INTENT_METEO_LOCALE,
    INTENT_METEO_72H,
    INTENT_NAVIGATION_COTIERE,
    INTENT_PECHE_ARTISANALE,
    INTENT_HISTORIQUE,
    INTENT_MARINE_NATIONALE,
}


# ============================================================
# 25. NŒUD — CLASSIFICATION
# ============================================================

def node_classifier(
    state: AgentState
):
    """
    Pipeline :

    interaction évidente
        ↓
    classification météo déterministe
        ↓
    continuité conversationnelle
        ↓
    fallback E5
    """

    query_originale = state[
        "query"
    ]

    query_effective = state[
        "effective_query"
    ]

    # ========================================================
    # A. INTERACTION ÉVIDENTE
    # ========================================================

    decision = (
        detecter_interaction_evidente(
            query_effective
        )
    )

    # ========================================================
    # B. CLASSIFICATION DÉTERMINISTE
    # ========================================================

    if decision is None:

        decision = (
            detecter_intention_meteo(
                query_effective
            )
        )

    # ========================================================
    # C. CONTINUITÉ CONVERSATIONNELLE
    # ========================================================

    if (
        decision is None
        and
        est_requete_de_suivi(
            query_originale
        )
    ):

        last_intent = (

            state
            .get(
                "session_context",
                {}
            )
            .get(
                "last_intent"
            )
        )

        if (
            last_intent
            in FOLLOWUP_INHERITABLE_INTENTS
        ):

            route = (
                INTENT_TO_ROUTE[
                    last_intent
                ]
            )

            decision = (
                construire_decision_agent(

                    query=
                        query_originale,

                    route=
                        route,

                    intent=
                        last_intent,

                    needs_retrieval=
                        (
                            route
                            == ROUTE_RAG
                        ),

                    needs_visual=
                        state.get(
                            "needs_visual",
                            False
                        ),

                    needs_clarification=False,

                    clarification_message=None,

                    offer_personalization=False,

                    personalization_action=None,

                    context_used=True,

                    confidence=1.0
                )
            )

    # ========================================================
    # D. FALLBACK E5
    # ========================================================

    if decision is None:

        decision = (
            classifier_requete_fallback(
                query_effective
            )
        )

    # ========================================================
    # E. TOUJOURS INDÉTERMINÉ
    # ========================================================

    if decision is None:

        decision = (
            construire_decision_agent(

                query=
                    query_originale,

                route=
                    ROUTE_CLARIFY,

                intent=
                    INTENT_UNKNOWN,

                needs_retrieval=False,

                needs_visual=
                    state.get(
                        "needs_visual",
                        False
                    ),

                needs_clarification=True,

                clarification_message=
                    (
                        "Pouvez-vous préciser votre demande "
                        "météorologique ?"
                    ),

                offer_personalization=False,

                personalization_action=None,

                context_used=
                    state[
                        "contextualisation"
                    ][
                        "context_used"
                    ],

                confidence=0.0
            )
        )

    # ========================================================
    # F. INFORMATIONS FINALES
    # ========================================================

    decision[
        "query"
    ] = query_originale

    decision[
        "needs_visual"
    ] = state.get(
        "needs_visual",
        False
    )

    decision[
        "context_used"
    ] = state[
        "contextualisation"
    ][
        "context_used"
    ]

    return {
        "decision":
            decision
    }


# ============================================================
# 26. NŒUD — FINALISATION
# ============================================================

def node_finaliser(
    state: AgentState
):
    """
    Met à jour la mémoire conversationnelle courte.
    """

    nouveau_contexte = (
        mettre_a_jour_contexte_session(

            session_context=
                state.get(
                    "session_context",
                    {}
                ),

            contextualisation=
                state[
                    "contextualisation"
                ],

            decision=
                state.get(
                    "decision"
                )
        )
    )

    return {

        "session_context":
            nouveau_contexte
    }


# ============================================================
# 27. ROUTAGE APRÈS CAS SPÉCIAUX
# ============================================================

def route_apres_cas_speciaux(
    state: AgentState
):
    """
    Évite la classification lorsqu'une clarification
    a déjà été décidée.
    """

    decision = state.get(
        "decision"
    )

    if (
        decision
        and
        decision.get(
            "needs_clarification"
        )
    ):

        return "finaliser"

    return "classifier"


# ============================================================
# 28. CONSTRUCTION DU WORKFLOW LANGGRAPH
# ============================================================

workflow = StateGraph(
    AgentState
)


workflow.add_node(
    "contextualiser",
    node_contextualiser
)


workflow.add_node(
    "cas_speciaux",
    node_analyser_cas_speciaux
)


workflow.add_node(
    "classifier",
    node_classifier
)


workflow.add_node(
    "finaliser",
    node_finaliser
)


# ------------------------------------------------------------
# Transitions
# ------------------------------------------------------------

workflow.add_edge(
    START,
    "contextualiser"
)


workflow.add_edge(
    "contextualiser",
    "cas_speciaux"
)


workflow.add_conditional_edges(

    "cas_speciaux",

    route_apres_cas_speciaux,

    {
        "classifier":
            "classifier",

        "finaliser":
            "finaliser",
    }
)


workflow.add_edge(
    "classifier",
    "finaliser"
)


workflow.add_edge(
    "finaliser",
    END
)


# ============================================================
# 29. MÉMOIRE DE SESSION
# ============================================================

agent_checkpointer = (
    InMemorySaver()
)


# ============================================================
# 30. COMPILATION DU GRAPHE
# ============================================================

agent_graph = workflow.compile(
    checkpointer=
        agent_checkpointer
)


# ============================================================
# 31. FONCTION PUBLIQUE analyze_query()
# ============================================================

def analyze_query(
    query: str,
    thread_id: str = "default",
    user_preferences=None
):
    """
    Point d'entrée public de l'Agent MeteoGPT.

    Parameters
    ----------
    query : str
        Requête utilisateur.

    thread_id : str
        Identifiant de la conversation LangGraph.

    user_preferences : dict | None
        Préférences facultatives utilisateur.

    Returns
    -------
    dict
        Décision structurée utilisable par le pipeline.
    """

    # ========================================================
    # 1. VALIDATION
    # ========================================================

    if not isinstance(
        query,
        str
    ):

        raise TypeError(
            "query doit être une chaîne de caractères."
        )

    query = " ".join(
        query.split()
    ).strip()

    if not query:

        raise ValueError(
            "query ne peut pas être vide."
        )

    if not isinstance(
        thread_id,
        str
    ):

        raise TypeError(
            "thread_id doit être une chaîne de caractères."
        )

    # ========================================================
    # 2. ENTRÉE DU WORKFLOW
    # ========================================================

    graph_input = {
        "query":
            query
    }

    # Les préférences déjà mémorisées dans la session
    # ne sont remplacées que si un profil est fourni.
    if user_preferences is not None:

        graph_input[
            "user_preferences"
        ] = (
            normaliser_preferences_utilisateur(
                user_preferences
            )
        )

    # ========================================================
    # 3. CONFIGURATION SESSION
    # ========================================================

    config = {

        "configurable": {

            "thread_id":
                thread_id
        }
    }

    # ========================================================
    # 4. EXÉCUTION LANGGRAPH
    # ========================================================

    state = (
        agent_graph.invoke(

            graph_input,

            config=config
        )
    )

    decision = state[
        "decision"
    ]

    # ========================================================
    # 5. MULTIMODALITÉ
    # ========================================================

    multimodal = (
        determiner_besoin_multimodal(

            intent=
                decision[
                    "intent"
                ],

            needs_visual=
                decision[
                    "needs_visual"
                ]
        )
    )

    contextualisation = state.get(
        "contextualisation",
        {}
    )

    # ========================================================
    # 6. SORTIE PUBLIQUE
    # ========================================================

    return {

        "query":
            query,

        "effective_query":
            state.get(
                "effective_query",
                query
            ),

        "route":
            decision[
                "route"
            ],

        "intent":
            decision[
                "intent"
            ],

        "needs_retrieval":
            decision[
                "needs_retrieval"
            ],

        "needs_visual":
            multimodal[
                "needs_visual"
            ],

        "source_requires_visual":
            multimodal[
                "source_requires_visual"
            ],

        "use_multimodal":
            multimodal[
                "use_multimodal"
            ],

        "needs_clarification":
            decision[
                "needs_clarification"
            ],

        "clarification_message":
            decision[
                "clarification_message"
            ],

        "offer_personalization":
            decision[
                "offer_personalization"
            ],

        "personalization_action":
            decision[
                "personalization_action"
            ],

        "context_used":
            decision[
                "context_used"
            ],

        "confidence":
            decision[
                "confidence"
            ],

        # ----------------------------------------------------
        # Informations destinées à generation.py
        # ----------------------------------------------------

        "resolved_location":
            contextualisation.get(
                "resolved_location"
            ),

        "user_type":
            contextualisation.get(
                "resolved_user_type"
            ),

        "user_subtype":
            contextualisation.get(
                "resolved_user_subtype"
            ),

        "interests":
            contextualisation.get(
                "interests",
                []
            ),

        "detail_level":
            contextualisation.get(
                "detail_level",
                "normal"
            ),
    }
