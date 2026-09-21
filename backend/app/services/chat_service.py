from uuid import uuid4

from backend.app.schemas.chat import (
    ChatResponse,
    ChatSource,
)


# ============================================================
# CHARGEMENT LAZY DU PIPELINE
# ============================================================

def _load_process_text_request():
    """
    Charge le pipeline RAG uniquement lorsqu'une requête Chat
    doit réellement être traitée.

    Cela évite de charger E5, Qdrant et Gemini lors du simple
    démarrage de FastAPI ou pendant les tests API mockés.
    """

    from rag_pipeline import process_text_request

    return process_text_request


# ============================================================
# NORMALISATION DES SOURCES
# ============================================================

def _normalize_sources(
    raw_sources
) -> list[ChatSource]:
    """
    Convertit les sources internes du pipeline en sources
    publiques simplifiées.
    """

    if not isinstance(
        raw_sources,
        list
    ):
        return []

    sources = []

    for source in raw_sources:

        if not isinstance(
            source,
            dict
        ):
            continue

        sources.append(
            ChatSource(
                rank=source.get(
                    "rank"
                ),
                chunk_id=source.get(
                    "chunk_id"
                ),
                chunk_type=source.get(
                    "chunk_type"
                ),
                source_file=source.get(
                    "source_file"
                ),
                category=source.get(
                    "category"
                ),
                page=source.get(
                    "page"
                ),
                localite=source.get(
                    "localite"
                ),
                date_publication=source.get(
                    "date_publication"
                ),
                date_debut_validite=source.get(
                    "date_debut_validite"
                ),
                date_fin_validite=source.get(
                    "date_fin_validite"
                ),
            )
        )

    return sources


# ============================================================
# SERVICE CHAT
# ============================================================

def process_chat(
    *,
    query: str,
    thread_id: str | None = None,
    user_preferences=None,
) -> ChatResponse:
    """
    Exécute une requête Chat MeteoGPT et transforme la sortie
    interne du pipeline en réponse API.
    """

    active_thread_id = (
        thread_id
        or str(
            uuid4()
        )
    )

    process_text_request = (
        _load_process_text_request()
    )

    result = process_text_request(
        query,
        thread_id=active_thread_id,
        user_preferences=user_preferences,
    )

    if not isinstance(
        result,
        dict
    ):
        raise RuntimeError(
            "Le pipeline MeteoGPT a retourné "
            "un résultat invalide."
        )

    latencies = result.get(
        "latencies_ms",
        {}
    )

    if not isinstance(
        latencies,
        dict
    ):
        latencies = {}

    return ChatResponse(
        success=bool(
            result.get(
                "success",
                False
            )
        ),

        thread_id=
            active_thread_id,

        answer=
            result.get(
                "answer",
                ""
            )
            or "",

        route=
            result.get(
                "route"
            ),

        intent=
            result.get(
                "intent"
            ),

        generation_mode=
            result.get(
                "generation_mode"
            ),

        grounded=bool(
            result.get(
                "grounded",
                False
            )
        ),

        retrieval_executed=bool(
            result.get(
                "retrieval_executed",
                False
            )
        ),

        use_multimodal=bool(
            result.get(
                "use_multimodal",
                False
            )
        ),

        sources=_normalize_sources(
            result.get(
                "sources_used",
                []
            )
        ),

        latency_ms=
            latencies.get(
                "total"
            ),

        error=
            result.get(
                "error"
            ),
    )