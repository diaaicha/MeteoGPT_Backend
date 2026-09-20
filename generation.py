
# -*- coding: utf-8 -*-

"""
MeteoGPT — generation.py

Couche de génération.

Responsabilités :
- construction du contexte RAG à partir des résultats du Retriever ;
- préparation multimodale ;
- personnalisation de la présentation ;
- construction des prompts ;
- vulgarisation des informations ANACIM ;
- recommandations pratiques contextualisées ;
- génération avec Gemini ;
- gestion des erreurs Gemini ;
- production d'une sortie structurée.

Ce module ne réalise pas :
- la classification des intentions ;
- le retrieval ;
- l'indexation ;
- la transcription audio ;
- la synthèse vocale.
"""


# ============================================================
# IMPORTS
# ============================================================

import os
import time
import mimetypes

from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ============================================================
# 1. CONFIGURATION GEMINI
# ============================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

GEMINI_TIMEOUT_MS = 20_000

GEMINI_TEMPERATURE = 0.2

GEMINI_MAX_OUTPUT_TOKENS = 1200


# ============================================================
# 2. CONFIGURATION RAG / MULTIMODAL
# ============================================================

MAX_RAG_RESULTS = 5

MAX_MULTIMODAL_IMAGES = 3


IMAGE_TYPE_PRIORITY = {
    "page_image": 0,
    "visual": 1,
}


# ============================================================
# 3. MODES DE GÉNÉRATION
# ============================================================

GENERATION_STATIC = "static"

GENERATION_DIRECT = "direct_llm"

GENERATION_RAG_TEXT = "rag_text"

GENERATION_RAG_MULTIMODAL = "rag_multimodal"

GENERATION_CLARIFY = "clarify"

GENERATION_OUT_OF_SCOPE = "out_of_scope"


# ============================================================
# 4. PERSONNALISATION
# ============================================================

PROFILE_INSTRUCTIONS = {

    "grand_public":
        (
            "Réponds dans un français simple et naturel. "
            "Explique brièvement les termes météorologiques techniques "
            "qui pourraient ne pas être évidents pour le grand public."
        ),

    "agriculteur":
        (
            "Utilise un langage accessible tout en mettant en avant pluie, "
            "température, vent et évolution du temps lorsqu'ils sont disponibles. "
            "Explique brièvement les termes techniques utiles. "
            "N'invente aucune recommandation agricole."
        ),

    "pecheur":
        (
            "Utilise un vocabulaire pratique pour la pêche artisanale. "
            "Tu peux conserver des termes comme houle, visibilité ou état de la mer "
            "s'ils sont utiles, mais explique-les brièvement lorsque nécessaire. "
            "Ne déclare jamais qu'une sortie est sûre si les sources ne le disent pas."
        ),

    "navigation":
        (
            "Conserve les termes maritimes utiles à la navigation, mais ajoute "
            "une courte explication lorsqu'un terme peut être ambigu. "
            "Mets en avant vent, houle, visibilité, état de la mer, zones "
            "et période de validité."
        ),

    "aviation":
        (
            "Conserve le vocabulaire météorologique nécessaire au contexte aéronautique "
            "tout en restant clair. Ne transforme jamais une prévision générale "
            "en bulletin aéronautique."
        ),

    "autorite":
        (
            "Utilise un style synthétique et professionnel. "
            "Les termes techniques peuvent être conservés, mais les conséquences "
            "météorologiques doivent être exprimées clairement lorsque les sources "
            "permettent de les établir."
        ),
}


DETAIL_LEVEL_INSTRUCTIONS = {

    "court":
        (
            "Réponds très brièvement, avec uniquement "
            "les informations essentielles."
        ),

    "normal":
        (
            "Fournis une réponse concise mais suffisamment informative."
        ),

    "detaille":
        (
            "Fournis une réponse plus détaillée et structurée, "
            "sans ajouter d'informations absentes des sources."
        ),
}


# ============================================================
# 5. PROMPT SYSTÈME COMMUN
# ============================================================

BASE_SYSTEM_PROMPT = """
Tu es MeteoGPT, un assistant météorologique de l'ANACIM
(Agence nationale de l'aviation civile et de la météorologie)
conçu pour rendre les informations météorologiques de l'ANACIM
faciles à comprendre.

Ton rôle n'est pas de recopier un bulletin météorologique.
Ton rôle est d'en conserver fidèlement les informations tout en les
reformulant dans un langage naturel, clair et accessible.

RÈGLES DE FIDÉLITÉ
- Ne jamais inventer une donnée météorologique.
- Ne jamais modifier une valeur numérique provenant des sources.
- Respecter les dates et périodes de validité.
- Ne jamais créer une alerte ou un risque qui n'existe pas dans les sources.
- Ne jamais présenter une recommandation comme officielle si elle ne figure
  pas explicitement dans les sources.
- Si une information nécessaire est absente, le signaler clairement.

RÈGLES DE VULGARISATION
- Ne recopie pas mot pour mot le style administratif ou technique du bulletin.
- Reformule les informations comme dans une conversation naturelle.
- Lorsqu'un terme météorologique peut être difficile à comprendre,
  explique-le brièvement avec des mots simples.
- L'explication doit rester courte et ne pas alourdir inutilement la réponse.
- Conserve les termes techniques lorsqu'ils sont utiles, mais accompagne-les
  d'une reformulation simple lorsque nécessaire.
- Évite les formulations trop institutionnelles comme :
  "vent de secteur Ouest", "échéance", "phénomènes significatifs"
  lorsqu'une formulation plus simple est possible.
- N'ajoute pas d'explication qui changerait le sens scientifique de la donnée.

STYLE DE RÉPONSE
- Réponds directement à l'utilisateur.
- Privilégie des phrases naturelles.
- N'imite pas la structure du bulletin source.
- N'utilise des listes que lorsqu'elles rendent réellement la réponse plus claire.
- Commence par l'information la plus utile pour répondre à la question.
- Pour une réponse courte, privilégie un ou deux paragraphes naturels plutôt
  qu'une succession systématique de rubriques.
- Ne mentionne jamais les chunks, le Retriever, Qdrant, les embeddings ou
  les mécanismes internes de MeteoGPT.

RECOMMANDATIONS PRATIQUES
- Lorsque les informations météorologiques fournies permettent de déduire
  un conseil pratique simple et fiable, tu peux le proposer.
- Toute recommandation doit être directement justifiée par les conditions
  météorologiques présentes dans le contexte.
- Ne recommande rien à partir d'une condition qui n'est pas mentionnée.
- Les recommandations doivent rester simples, prudentes et utiles au quotidien.
- Distingue toujours une recommandation pratique de MeteoGPT d'une
  recommandation officielle de l'ANACIM.
- Ne présente jamais une recommandation comme une consigne officielle sauf
  si elle figure explicitement dans la source.

Exemples :
- pluie ou averses prévues :
  proposer un parapluie ou un vêtement imperméable ;
- forte chaleur :
  recommander de boire régulièrement de l'eau, rechercher l'ombre
  et éviter une exposition prolongée à la chaleur ;
- fort ensoleillement explicitement mentionné :
  proposer un chapeau, un parasol ou des lunettes de soleil ;
- vent fort :
  recommander de sécuriser les objets légers à l'extérieur ;
- brouillard ou mauvaise visibilité :
  recommander davantage de prudence lors des déplacements ;
- orages :
  conseiller d'éviter les zones très exposées pendant l'orage ;
- conditions maritimes dégradées :
  appeler à la prudence pour les activités en mer sans déclarer
  qu'une sortie est sûre ou dangereuse si la source ne le précise pas.

IMPORTANT :
Une forte chaleur ne signifie pas automatiquement qu'il y a un fort
ensoleillement. Ne recommande donc pas des lunettes de soleil ou un
parasol uniquement parce que la température est élevée si les sources
ne mentionnent pas de conditions ensoleillées.

La recommandation doit rester courte et proportionnée à la situation.
""".strip()


# ============================================================
# 6. CLÉ API GEMINI
# ============================================================

def charger_gemini_api_key():
    """
    Récupère la clé Gemini depuis l'environnement backend.
    """

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "Clé GEMINI_API_KEY introuvable."
        )

    return api_key

# ============================================================
# 7. CLIENT GEMINI
# ============================================================

def creer_client_gemini(
    api_key=None
):
    """
    Crée le client Gemini.

    Configuration :
    - timeout : 20 secondes ;
    - une seule tentative ;
    - pas de boucle de retry applicative.
    """

    if api_key is None:

        api_key = charger_gemini_api_key()

    return genai.Client(

        api_key=api_key,

        http_options=types.HttpOptions(

            timeout=
                GEMINI_TIMEOUT_MS,

            retry_options=
                types.HttpRetryOptions(
                    attempts=1
                )
        )
    )


# Client réutilisable par la couche de génération.
gemini_client = creer_client_gemini()


# ============================================================
# 8. CONSTRUCTION DU CONTEXTE RAG
# ============================================================

def construire_contexte_rag(
    retrieval_result,
    max_results=MAX_RAG_RESULTS
):
    """
    Transforme la sortie de retriever.retrieve()
    en contexte exploitable par Gemini.

    Aucun appel Gemini n'est réalisé ici.
    """

    if not isinstance(
        retrieval_result,
        dict
    ):

        raise TypeError(
            "retrieval_result doit être un dictionnaire."
        )

    results = retrieval_result.get(
        "results",
        []
    )

    if not isinstance(
        results,
        list
    ):

        raise TypeError(
            "retrieval_result['results'] doit être une liste."
        )

    # --------------------------------------------------------
    # Aucun résultat
    # --------------------------------------------------------

    if not results:

        return {
            "context_text": "",
            "sources": [],
            "image_paths": [],
            "context_count": 0,
            "has_context": False,
        }

    blocs = []

    sources = []

    image_paths = []

    # --------------------------------------------------------
    # Conservation de max_results sources
    # --------------------------------------------------------

    for index, item in enumerate(
        results[:max_results],
        start=1
    ):

        if not isinstance(
            item,
            dict
        ):

            continue

        content = (
            item.get("content")
            or ""
        ).strip()

        if not content:

            continue

        # ----------------------------------------------------
        # Métadonnées
        # ----------------------------------------------------

        chunk_id = item.get(
            "chunk_id"
        )

        chunk_type = item.get(
            "chunk_type"
        )

        source_file = item.get(
            "source_file"
        )

        category = item.get(
            "category"
        )

        page = item.get(
            "page"
        )

        localite = item.get(
            "localite"
        )

        date_publication = item.get(
            "date_publication"
        )

        date_debut_validite = item.get(
            "date_debut_validite"
        )

        date_fin_validite = item.get(
            "date_fin_validite"
        )

        image_path = item.get(
            "image_path"
        )

        # ----------------------------------------------------
        # Métadonnées transmises au LLM
        # ----------------------------------------------------

        metadata_lines = [
            f"Source : {source_file}",
            f"Catégorie : {category}",
            f"Type de chunk : {chunk_type}",
        ]

        if page is not None:

            metadata_lines.append(
                f"Page : {page}"
            )

        if localite:

            metadata_lines.append(
                f"Localité : {localite}"
            )

        if date_publication:

            metadata_lines.append(
                f"Date de publication : {date_publication}"
            )

        if date_debut_validite:

            metadata_lines.append(
                f"Début de validité : {date_debut_validite}"
            )

        if date_fin_validite:

            metadata_lines.append(
                f"Fin de validité : {date_fin_validite}"
            )

        # ----------------------------------------------------
        # Bloc textuel
        # ----------------------------------------------------

        bloc = (
            f"[SOURCE {index}]\n"
            +
            "\n".join(
                metadata_lines
            )
            +
            "\n\n"
            +
            content
        )

        blocs.append(
            bloc
        )

        # ----------------------------------------------------
        # Source structurée
        # ----------------------------------------------------

        sources.append(
            {
                "rank":
                    item.get(
                        "rank",
                        index
                    ),

                "chunk_id":
                    chunk_id,

                "chunk_type":
                    chunk_type,

                "source_file":
                    source_file,

                "category":
                    category,

                "page":
                    page,

                "localite":
                    localite,

                "date_publication":
                    date_publication,

                "date_debut_validite":
                    date_debut_validite,

                "date_fin_validite":
                    date_fin_validite,

                "image_path":
                    image_path,
            }
        )

        # ----------------------------------------------------
        # Images potentielles
        # ----------------------------------------------------

        if (
            image_path
            and
            image_path not in image_paths
        ):

            image_paths.append(
                image_path
            )

    # --------------------------------------------------------
    # Contexte final
    # --------------------------------------------------------

    context_text = (
        "\n\n"
        + "=" * 70
        + "\n\n"
    ).join(
        blocs
    )

    return {
        "context_text":
            context_text,

        "sources":
            sources,

        "image_paths":
            image_paths,

        "context_count":
            len(
                sources
            ),

        "has_context":
            bool(
                sources
            ),
    }


# ============================================================
# 9. PRÉPARATION MULTIMODALE
# ============================================================

def preparer_images_multimodales(
    agent_result,
    contexte_rag,
    max_images=MAX_MULTIMODAL_IMAGES
):
    """
    Prépare les images à transmettre au LLM.

    Règles :
    - aucune image si use_multimodal=False ;
    - priorité aux PageImageChunks ;
    - suppression des doublons ;
    - vérification de l'existence du fichier ;
    - limitation du nombre d'images.

    Aucun appel Gemini n'est effectué ici.
    """

    if not isinstance(
        agent_result,
        dict
    ):

        raise TypeError(
            "agent_result doit être un dictionnaire."
        )

    if not isinstance(
        contexte_rag,
        dict
    ):

        raise TypeError(
            "contexte_rag doit être un dictionnaire."
        )

    # --------------------------------------------------------
    # Décision de l'Agent
    # --------------------------------------------------------

    use_multimodal = bool(
        agent_result.get(
            "use_multimodal",
            False
        )
    )

    if not use_multimodal:

        return {
            "use_multimodal":
                False,

            "multimodal_ready":
                False,

            "images":
                [],

            "missing_images":
                [],

            "image_count":
                0,
        }

    # --------------------------------------------------------
    # Sources avec image_path
    # --------------------------------------------------------

    sources = contexte_rag.get(
        "sources",
        []
    )

    candidats = []

    for index, source in enumerate(
        sources
    ):

        if not isinstance(
            source,
            dict
        ):

            continue

        image_path = source.get(
            "image_path"
        )

        if not image_path:

            continue

        chunk_type = source.get(
            "chunk_type"
        )

        priority = IMAGE_TYPE_PRIORITY.get(
            chunk_type,
            99
        )

        candidats.append(
            {
                "priority":
                    priority,

                "original_order":
                    index,

                "chunk_id":
                    source.get(
                        "chunk_id"
                    ),

                "chunk_type":
                    chunk_type,

                "source_file":
                    source.get(
                        "source_file"
                    ),

                "page":
                    source.get(
                        "page"
                    ),

                "image_path":
                    image_path,
            }
        )

    # --------------------------------------------------------
    # PageImage prioritaire
    # --------------------------------------------------------

    candidats.sort(
        key=lambda item: (
            item[
                "priority"
            ],
            item[
                "original_order"
            ],
        )
    )

    images = []

    missing_images = []

    seen_paths = set()

    # --------------------------------------------------------
    # Validation des fichiers images
    # --------------------------------------------------------

    for candidat in candidats:

        image_path = candidat[
            "image_path"
        ]

        if image_path in seen_paths:

            continue

        seen_paths.add(
            image_path
        )

        path = Path(
            image_path
        )

        if not path.is_file():

            missing_images.append(
                image_path
            )

            continue

        mime_type = (
            mimetypes.guess_type(
                str(
                    path
                )
            )[0]
            or
            "image/png"
        )

        images.append(
            {
                "path":
                    str(
                        path
                    ),

                "mime_type":
                    mime_type,

                "chunk_id":
                    candidat[
                        "chunk_id"
                    ],

                "chunk_type":
                    candidat[
                        "chunk_type"
                    ],

                "source_file":
                    candidat[
                        "source_file"
                    ],

                "page":
                    candidat[
                        "page"
                    ],

                "size_bytes":
                    path.stat().st_size,
            }
        )

        if len(
            images
        ) >= max_images:

            break

    return {
        "use_multimodal":
            True,

        "multimodal_ready":
            bool(
                images
            ),

        "images":
            images,

        "missing_images":
            missing_images,

        "image_count":
            len(
                images
            ),
    }


# ============================================================
# 10. INSTRUCTION DE PERSONNALISATION
# ============================================================

def construire_instruction_personnalisation(
    agent_result
):
    """
    Construit uniquement les consignes de présentation.

    La personnalisation ne modifie jamais les faits
    météorologiques.
    """

    user_type = (
        agent_result.get(
            "user_type"
        )
        or
        "grand_public"
    )

    user_subtype = agent_result.get(
        "user_subtype"
    )

    interests = agent_result.get(
        "interests",
        []
    )

    detail_level = agent_result.get(
        "detail_level",
        "normal"
    )

    profil_instruction = (
        PROFILE_INSTRUCTIONS.get(
            user_type,
            PROFILE_INSTRUCTIONS[
                "grand_public"
            ]
        )
    )

    detail_instruction = (
        DETAIL_LEVEL_INSTRUCTIONS.get(
            detail_level,
            DETAIL_LEVEL_INSTRUCTIONS[
                "normal"
            ]
        )
    )

    parties = [
        profil_instruction,
        detail_instruction,
    ]

    # --------------------------------------------------------
    # Sous-type autorité
    # --------------------------------------------------------

    if (
        user_type == "autorite"
        and user_subtype
    ):

        parties.append(
            f"Le profil d'autorité est : {user_subtype}. "
            "Adapte uniquement la présentation à ce contexte."
        )

    # --------------------------------------------------------
    # Centres d'intérêt
    # --------------------------------------------------------

    if interests:

        interests_text = ", ".join(
            str(
                item
            )
            for item in interests
        )

        parties.append(
            "Lorsque les sources contiennent ces informations, "
            f"accorde une attention particulière à : {interests_text}."
        )

    return "\n".join(
        parties
    )


# ============================================================
# 11. PROMPT RAG
# ============================================================

def construire_prompt_rag(
    agent_result,
    contexte_rag,
    multimodal_context=None
):
    """
    Construit le prompt pour une réponse fondée
    sur les données ANACIM.
    """

    query = (
        agent_result.get(
            "effective_query"
        )
        or
        agent_result.get(
            "query",
            ""
        )
    )

    context_text = contexte_rag.get(
        "context_text",
        ""
    )

    personnalisation = (
        construire_instruction_personnalisation(
            agent_result
        )
    )

    use_multimodal = bool(
        agent_result.get(
            "use_multimodal",
            False
        )
    )

    # --------------------------------------------------------
    # Prompt système RAG
    # --------------------------------------------------------

    system_prompt = (
        BASE_SYSTEM_PROMPT
        +
        """

RÈGLES SPÉCIFIQUES AU MODE RAG
- Réponds uniquement à partir des informations ANACIM fournies.
- Ne complète jamais une prévision avec des données météorologiques
  opérationnelles provenant de tes connaissances générales.
- Utilise uniquement les sources réellement pertinentes pour la question.
- Respecte strictement la localité, les dates, la période de validité
  et les valeurs indiquées.
- Si les informations sont insuffisantes ou contradictoires,
  indique-le clairement.
- Ne cite jamais les identifiants internes comme [SOURCE 1],
  les chunks ou les mécanismes techniques du système.

VULGARISATION
- Ne recopie pas le bulletin mot pour mot.
- Transforme le langage météorologique technique en une réponse naturelle.
- Explique brièvement les termes qui pourraient être difficiles
  à comprendre pour le public visé.
- L'explication doit rester courte et utile.
- Conserve exactement le sens scientifique de la donnée.

Exemples de reformulation :
- "vent de secteur Ouest" →
  "un vent venant principalement de l'ouest" ;
- "vent d'intensité modérée" →
  "un vent modéré, ni faible ni particulièrement fort" ;
- "passages nuageux" →
  "des nuages passeront par moments dans le ciel" ;
- "activités pluvio-orageuses" →
  "des pluies accompagnées d'orages".

Ces exemples servent uniquement à guider le style.
Ils ne doivent jamais remplacer les informations réellement présentes
dans le contexte.

RECOMMANDATIONS PRATIQUES
- Tu peux ajouter un conseil pratique lorsque les conditions
  météorologiques du contexte le justifient réellement.
- Le conseil doit découler directement d'une information présente
  dans les sources.
- N'invente jamais une condition météorologique pour justifier un conseil.
- La recommandation doit rester courte, prudente et proportionnée.
- Présente-la comme un conseil pratique de MeteoGPT, jamais comme
  une consigne officielle de l'ANACIM, sauf si la source contient
  explicitement cette consigne.
- N'ajoute pas systématiquement une recommandation si elle n'apporte
  rien d'utile.

Exemples :
- pluie ou averses →
  suggérer un parapluie ou un vêtement imperméable ;
- forte chaleur →
  suggérer de boire régulièrement de l'eau, rechercher l'ombre
  et éviter une exposition prolongée à la chaleur ;
- fort ensoleillement explicitement mentionné →
  suggérer un chapeau, un parasol ou des lunettes de soleil ;
- vent fort →
  conseiller de sécuriser les objets légers à l'extérieur ;
- mauvaise visibilité ou brouillard →
  conseiller davantage de prudence lors des déplacements ;
- orages →
  conseiller d'éviter les endroits très exposés pendant l'orage ;
- conditions maritimes dégradées →
  appeler à la prudence pour les activités en mer.

IMPORTANT :
Une forte chaleur ne signifie pas automatiquement qu'il y a un fort
ensoleillement. Ne recommande donc pas des lunettes de soleil ou un
parasol uniquement parce que la température est élevée si les sources
ne mentionnent pas de conditions ensoleillées.

Pour la pêche et la navigation :
- ne dis jamais qu'une sortie est "sans risque" ;
- ne dis jamais qu'une sortie est "interdite" sauf si une source
  officielle le dit explicitement ;
- explique plutôt les conditions observées et appelle à la prudence
  lorsqu'elles le justifient.
"""
    )

    # --------------------------------------------------------
    # Règles multimodales
    # --------------------------------------------------------

    if use_multimodal:

        system_prompt += (
            "\n\nRÈGLES MULTIMODALES\n"
            "- Des images de bulletins ANACIM peuvent accompagner "
            "le contexte. Analyse-les lorsque l'information demandée "
            "n'est pas suffisamment présente dans le texte.\n"
            "- Ne décris pas inutilement toute l'image : extrais seulement "
            "les informations pertinentes pour la question.\n"
            "- Les informations lues dans l'image sont considérées comme "
            "faisant partie du contexte ANACIM fourni.\n"
            "- En cas de doute sur une valeur ou un élément visuel, "
            "ne l'invente pas."
        )

    # --------------------------------------------------------
    # Prompt utilisateur
    # --------------------------------------------------------

    user_prompt = f"""
QUESTION UTILISATEUR
{query}

ADAPTATION DE LA RÉPONSE
{personnalisation}

CONTEXTE ANACIM
{context_text}

CONSIGNE FINALE
Réponds directement à la question en français naturel.
Commence par les informations les plus utiles.
Vulgarise les formulations techniques lorsque nécessaire.
Ajoute un conseil pratique uniquement si les conditions fournies
permettent réellement de le justifier.
""".strip()

    return {
        "system_prompt":
            system_prompt,

        "user_prompt":
            user_prompt,

        "mode":
            (
                "rag_multimodal"
                if use_multimodal
                else
                "rag_text"
            ),
    }


# ============================================================
# 12. PROMPT DIRECT LLM
# ============================================================

def construire_prompt_direct_llm(
    agent_result
):
    """
    Prompt pour les questions de connaissance
    météorologique générale.
    """

    query = (
        agent_result.get(
            "effective_query"
        )
        or
        agent_result.get(
            "query",
            ""
        )
    )

    personnalisation = (
        construire_instruction_personnalisation(
            agent_result
        )
    )

    system_prompt = (
        BASE_SYSTEM_PROMPT
        +
        """

Mode connaissance météorologique générale :
- tu peux utiliser tes connaissances générales ;
- explique les phénomènes météorologiques de façon pédagogique ;
- ne présente pas cette réponse comme une prévision ANACIM ;
- ne donne pas de données météorologiques opérationnelles actuelles
  si elles n'ont pas été fournies.
"""
    )

    user_prompt = f"""
QUESTION UTILISATEUR
{query}

ADAPTATION DE LA RÉPONSE
{personnalisation}

Réponds clairement et pédagogiquement.
""".strip()

    return {
        "system_prompt":
            system_prompt,

        "user_prompt":
            user_prompt,

        "mode":
            "direct_llm",
    }


# ============================================================
# 13. CLASSIFICATION DES ERREURS GEMINI
# ============================================================

def classifier_erreur_gemini(
    exception
):
    """
    Convertit une exception Gemini en catégorie
    exploitable par MeteoGPT.
    """

    message = str(
        exception
    ).lower()

    status_code = getattr(
        exception,
        "status_code",
        None
    )

    # --------------------------------------------------------
    # Quota / Rate limit
    # --------------------------------------------------------

    if (
        status_code == 429
        or "429" in message
        or "resource_exhausted" in message
        or "quota" in message
    ):

        return "rate_limit"

    # --------------------------------------------------------
    # Service indisponible
    # --------------------------------------------------------

    if (
        status_code == 503
        or "503" in message
        or "service unavailable" in message
        or "unavailable" in message
    ):

        return "service_unavailable"

    # --------------------------------------------------------
    # Timeout
    # --------------------------------------------------------

    if (
        "timeout" in message
        or "timed out" in message
        or "deadline" in message
    ):

        return "timeout"

    # --------------------------------------------------------
    # Authentification
    # --------------------------------------------------------

    if (
        status_code in {
            401,
            403,
        }
        or "api key" in message
        or "permission" in message
    ):

        return "authentication"

    return "api_error"


# ============================================================
# 14. MESSAGE D'ERREUR UTILISATEUR
# ============================================================

def message_erreur_generation(
    error_type
):
    """
    Retourne un message utilisateur contrôlé
    en cas d'échec Gemini.
    """

    messages = {

        "rate_limit":
            (
                "Le service de génération est temporairement "
                "limité. Veuillez réessayer dans quelques instants."
            ),

        "service_unavailable":
            (
                "Le service de génération est momentanément "
                "indisponible. Veuillez réessayer plus tard."
            ),

        "timeout":
            (
                "La génération de la réponse a pris trop de temps. "
                "Veuillez réessayer."
            ),

        "authentication":
            (
                "Le service de génération n'est pas correctement "
                "configuré."
            ),

        "api_error":
            (
                "Une erreur est survenue pendant la génération "
                "de la réponse."
            ),
    }

    return messages.get(
        error_type,
        messages[
            "api_error"
        ]
    )


# ============================================================
# 15. APPEL GEMINI
# ============================================================

def appeler_gemini(
    prompt_bundle,
    multimodal_context=None,
    client=None,
    model=None
):
    """
    Exécute une génération Gemini.

    Supporte :
    - texte seul ;
    - texte + images.

    Aucune boucle de retry applicative.
    """

    start_time = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not isinstance(
        prompt_bundle,
        dict
    ):

        raise TypeError(
            "prompt_bundle doit être un dictionnaire."
        )

    system_prompt = prompt_bundle.get(
        "system_prompt",
        ""
    )

    user_prompt = prompt_bundle.get(
        "user_prompt",
        ""
    )

    generation_mode = prompt_bundle.get(
        "mode",
        "unknown"
    )

    if not user_prompt:

        raise ValueError(
            "Le prompt utilisateur est vide."
        )

    active_client = (
        client
        or
        gemini_client
    )

    active_model = (
        model
        or
        GEMINI_MODEL
    )

    # --------------------------------------------------------
    # Construction du contenu
    # --------------------------------------------------------

    contents = [
        user_prompt
    ]

    images_used = []

    if multimodal_context:

        for image in multimodal_context.get(
            "images",
            []
        ):

            path = image.get(
                "path"
            )

            mime_type = image.get(
                "mime_type",
                "image/png"
            )

            if not path:

                continue

            with open(
                path,
                "rb"
            ) as file:

                image_bytes = (
                    file.read()
                )

            contents.append(

                types.Part.from_bytes(

                    data=
                        image_bytes,

                    mime_type=
                        mime_type
                )
            )

            images_used.append(
                path
            )

    # --------------------------------------------------------
    # Appel API Gemini
    # --------------------------------------------------------

    try:

        response = (
            active_client.models.generate_content(

                model=
                    active_model,

                contents=
                    contents,

                config=
                    types.GenerateContentConfig(

                        system_instruction=
                            system_prompt,

                        temperature=
                            GEMINI_TEMPERATURE,

                        max_output_tokens=
                            GEMINI_MAX_OUTPUT_TOKENS,
                    )
            )
        )

        answer = (
            getattr(
                response,
                "text",
                None
            )
            or
            ""
        ).strip()

        latency_ms = (
            time.perf_counter()
            -
            start_time
        ) * 1000

        # ----------------------------------------------------
        # Réponse vide
        # ----------------------------------------------------

        if not answer:

            return {
                "success":
                    False,

                "answer":
                    (
                        "Le modèle n'a pas produit "
                        "de réponse exploitable."
                    ),

                "generation_mode":
                    generation_mode,

                "model":
                    active_model,

                "images_used":
                    images_used,

                "latency_ms":
                    latency_ms,

                "error":
                    "empty_response",
            }

        # ----------------------------------------------------
        # Succès
        # ----------------------------------------------------

        return {
            "success":
                True,

            "answer":
                answer,

            "generation_mode":
                generation_mode,

            "model":
                active_model,

            "images_used":
                images_used,

            "latency_ms":
                latency_ms,

            "error":
                None,
        }

    # --------------------------------------------------------
    # Erreur API
    # --------------------------------------------------------

    except Exception as exception:

        latency_ms = (
            time.perf_counter()
            -
            start_time
        ) * 1000

        error_type = (
            classifier_erreur_gemini(
                exception
            )
        )

        return {
            "success":
                False,

            "answer":
                message_erreur_generation(
                    error_type
                ),

            "generation_mode":
                generation_mode,

            "model":
                active_model,

            "images_used":
                images_used,

            "latency_ms":
                latency_ms,

            "error":
                error_type,

            # Diagnostic développement.
            "error_detail":
                str(
                    exception
                )[:500],
        }


# ============================================================
# 16. RÉPONSES STATIQUES
# ============================================================

def construire_reponse_statique(
    agent_result
):
    """
    Réponses ne nécessitant ni Retriever ni Gemini.
    """

    intent = agent_result.get(
        "intent"
    )

    if intent == "greeting":

        return (
            "Bonjour ! Je suis MeteoGPT. "
            "Je peux vous aider à comprendre les prévisions "
            "et informations météorologiques disponibles."
        )

    if intent == "capabilities":

        return (
            "Je peux vous renseigner sur la météo, les prévisions, "
            "les conditions locales, les informations utiles à la pêche "
            "et à la navigation côtière, ainsi qu'expliquer simplement "
            "des phénomènes météorologiques."
        )

    if intent == "personalization":

        return (
            "Vous pouvez personnaliser MeteoGPT en indiquant par exemple "
            "votre localité habituelle, votre activité ou le niveau de "
            "détail que vous préférez."
        )

    return (
        "Je suis prêt à vous aider avec les informations météorologiques."
    )


# ============================================================
# 17. FORMAT STANDARD DE SORTIE
# ============================================================

def construire_sortie_generation(
    *,
    answer,
    generation_mode,
    success=True,
    model=None,
    sources_used=None,
    images_used=None,
    grounded=False,
    latency_ms=0.0,
    error=None,
    error_detail=None
):
    """
    Format standard de sortie de generation.py.
    """

    resultat = {

        "success":
            bool(
                success
            ),

        "answer":
            answer,

        "generation_mode":
            generation_mode,

        "model":
            model,

        "sources_used":
            sources_used or [],

        "images_used":
            images_used or [],

        "grounded":
            bool(
                grounded
            ),

        "latency_ms":
            float(
                latency_ms
            ),

        "error":
            error,
    }

    if error_detail:

        resultat[
            "error_detail"
        ] = error_detail

    return resultat


# ============================================================
# 18. FONCTION PUBLIQUE
# ============================================================

def generate_response(
    agent_result,
    retrieval_result=None,
    client=None
):
    """
    Génère la réponse finale à partir de la décision
    produite par l'Agent.

    Lorsque route == "rag", le Retriever doit avoir
    été exécuté en amont.
    """

    start_total = (
        time.perf_counter()
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not isinstance(
        agent_result,
        dict
    ):

        raise TypeError(
            "agent_result doit être un dictionnaire."
        )

    route = agent_result.get(
        "route"
    )

    # ========================================================
    # STATIC
    # ========================================================

    if route == "static":

        answer = (
            construire_reponse_statique(
                agent_result
            )
        )

        return construire_sortie_generation(

            answer=
                answer,

            generation_mode=
                GENERATION_STATIC,

            grounded=
                False,

            latency_ms=
                (
                    time.perf_counter()
                    -
                    start_total
                ) * 1000
        )

    # ========================================================
    # CLARIFY
    # ========================================================

    if route == "clarify":

        answer = (

            agent_result.get(
                "clarification_message"
            )

            or

            "Pouvez-vous préciser votre demande, notamment la localité "
            "ou la période concernée ?"
        )

        return construire_sortie_generation(

            answer=
                answer,

            generation_mode=
                GENERATION_CLARIFY,

            grounded=
                False,

            latency_ms=
                (
                    time.perf_counter()
                    -
                    start_total
                ) * 1000
        )

    # ========================================================
    # OUT OF SCOPE
    # ========================================================

    if route == "out_of_scope":

        answer = (
            "Cette demande sort du périmètre de MeteoGPT. "
            "Je peux principalement vous aider avec la météo, "
            "les prévisions et les informations météorologiques associées."
        )

        return construire_sortie_generation(

            answer=
                answer,

            generation_mode=
                GENERATION_OUT_OF_SCOPE,

            grounded=
                False,

            latency_ms=
                (
                    time.perf_counter()
                    -
                    start_total
                ) * 1000
        )

    # ========================================================
    # DIRECT LLM
    # ========================================================

    if route == "direct_llm":

        prompt_bundle = (
            construire_prompt_direct_llm(
                agent_result
            )
        )

        resultat_llm = (
            appeler_gemini(

                prompt_bundle=
                    prompt_bundle,

                client=
                    client
            )
        )

        return construire_sortie_generation(

            answer=
                resultat_llm[
                    "answer"
                ],

            generation_mode=
                GENERATION_DIRECT,

            success=
                resultat_llm[
                    "success"
                ],

            model=
                resultat_llm[
                    "model"
                ],

            images_used=
                resultat_llm.get(
                    "images_used",
                    []
                ),

            grounded=
                False,

            latency_ms=
                (
                    time.perf_counter()
                    -
                    start_total
                ) * 1000,

            error=
                resultat_llm[
                    "error"
                ],

            error_detail=
                resultat_llm.get(
                    "error_detail"
                )
        )

    # ========================================================
    # RAG
    # ========================================================

    if route == "rag":

        # ----------------------------------------------------
        # Retriever obligatoire
        # ----------------------------------------------------

        if not isinstance(
            retrieval_result,
            dict
        ):

            return construire_sortie_generation(

                answer=
                    (
                        "Les données météorologiques nécessaires "
                        "n'ont pas pu être récupérées."
                    ),

                generation_mode=
                    GENERATION_RAG_TEXT,

                success=
                    False,

                grounded=
                    False,

                latency_ms=
                    (
                        time.perf_counter()
                        -
                        start_total
                    ) * 1000,

                error=
                    "missing_retrieval"
            )

        # ----------------------------------------------------
        # Construction du contexte
        # ----------------------------------------------------

        contexte_rag = (
            construire_contexte_rag(
                retrieval_result
            )
        )

        # ----------------------------------------------------
        # Aucun contexte exploitable
        # ----------------------------------------------------

        if not contexte_rag[
            "has_context"
        ]:

            return construire_sortie_generation(

                answer=
                    (
                        "Je n'ai pas trouvé suffisamment "
                        "d'informations ANACIM pour répondre "
                        "à cette demande."
                    ),

                generation_mode=
                    GENERATION_RAG_TEXT,

                success=
                    False,

                grounded=
                    False,

                latency_ms=
                    (
                        time.perf_counter()
                        -
                        start_total
                    ) * 1000,

                error=
                    "empty_context"
            )

        # ====================================================
        # RAG MULTIMODAL
        # ====================================================

        if agent_result.get(
            "use_multimodal",
            False
        ):

            multimodal_context = (
                preparer_images_multimodales(

                    agent_result=
                        agent_result,

                    contexte_rag=
                        contexte_rag
                )
            )

            # ------------------------------------------------
            # Image nécessaire mais indisponible
            # ------------------------------------------------

            if not multimodal_context[
                "multimodal_ready"
            ]:

                return construire_sortie_generation(

                    answer=
                        (
                            "Les informations recherchées nécessitent "
                            "l'analyse du bulletin visuel, mais l'image "
                            "correspondante n'est pas disponible."
                        ),

                    generation_mode=
                        GENERATION_RAG_MULTIMODAL,

                    success=
                        False,

                    sources_used=
                        contexte_rag[
                            "sources"
                        ],

                    grounded=
                        False,

                    latency_ms=
                        (
                            time.perf_counter()
                            -
                            start_total
                        ) * 1000,

                    error=
                        "missing_visual_context"
                )

            # ------------------------------------------------
            # Prompt multimodal
            # ------------------------------------------------

            prompt_bundle = (
                construire_prompt_rag(

                    agent_result=
                        agent_result,

                    contexte_rag=
                        contexte_rag,

                    multimodal_context=
                        multimodal_context
                )
            )

            # ------------------------------------------------
            # Génération multimodale
            # ------------------------------------------------

            resultat_llm = (
                appeler_gemini(

                    prompt_bundle=
                        prompt_bundle,

                    multimodal_context=
                        multimodal_context,

                    client=
                        client
                )
            )

            return construire_sortie_generation(

                answer=
                    resultat_llm[
                        "answer"
                    ],

                generation_mode=
                    GENERATION_RAG_MULTIMODAL,

                success=
                    resultat_llm[
                        "success"
                    ],

                model=
                    resultat_llm[
                        "model"
                    ],

                sources_used=
                    contexte_rag[
                        "sources"
                    ],

                images_used=
                    resultat_llm.get(
                        "images_used",
                        []
                    ),

                grounded=
                    bool(
                        resultat_llm[
                            "success"
                        ]
                    ),

                latency_ms=
                    (
                        time.perf_counter()
                        -
                        start_total
                    ) * 1000,

                error=
                    resultat_llm[
                        "error"
                    ],

                error_detail=
                    resultat_llm.get(
                        "error_detail"
                    )
            )

        # ====================================================
        # RAG TEXTE
        # ====================================================

        prompt_bundle = (
            construire_prompt_rag(

                agent_result=
                    agent_result,

                contexte_rag=
                    contexte_rag
            )
        )

        resultat_llm = (
            appeler_gemini(

                prompt_bundle=
                    prompt_bundle,

                client=
                    client
            )
        )

        return construire_sortie_generation(

            answer=
                resultat_llm[
                    "answer"
                ],

            generation_mode=
                GENERATION_RAG_TEXT,

            success=
                resultat_llm[
                    "success"
                ],

            model=
                resultat_llm[
                    "model"
                ],

            sources_used=
                contexte_rag[
                    "sources"
                ],

            images_used=
                resultat_llm.get(
                    "images_used",
                    []
                ),

            grounded=
                bool(
                    resultat_llm[
                        "success"
                    ]
                ),

            latency_ms=
                (
                    time.perf_counter()
                    -
                    start_total
                ) * 1000,

            error=
                resultat_llm[
                    "error"
                ],

            error_detail=
                resultat_llm.get(
                    "error_detail"
                )
        )

    # ========================================================
    # ROUTE INCONNUE
    # ========================================================

    return construire_sortie_generation(

        answer=
            (
                "Je n'ai pas pu déterminer comment traiter "
                "cette demande."
            ),

        generation_mode=
            "unknown",

        success=
            False,

        grounded=
            False,

        latency_ms=
            (
                time.perf_counter()
                -
                start_total
            ) * 1000,

        error=
            "unsupported_route"
    )
