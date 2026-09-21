from uuid import uuid4

from backend.app.schemas.chat import (
    ChatResponse,
    ChatSource,
)


from backend.app.core.log_context import (
    get_request_id,
    thread_id_context,
)
from backend.app.core.logging import (
    get_logger,
)

logger = get_logger("chat")
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

    thread_token = thread_id_context.set(
        active_thread_id
    )

    try:

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

        success = bool(
            result.get(
                "success",
                False
            )
        )

        log_function = (
            logger.info
            if success
            else logger.warning
        )

        log_function(
            "Chat request processed | "
            "request_id=%s | "
            "thread_id=%s | "
            "route=%s | "
            "intent=%s | "
            "generation_mode=%s | "
            "retrieval=%s | "
            "multimodal=%s | "
            "grounded=%s | "
            "agent_ms=%.2f | "
            "retrieval_ms=%.2f | "
            "generation_ms=%.2f | "
            "total_ms=%.2f | "
            "error=%s",
            get_request_id(),
            active_thread_id,
            result.get("route"),
            result.get("intent"),
            result.get("generation_mode"),
            bool(
                result.get(
                    "retrieval_executed",
                    False
                )
            ),
            bool(
                result.get(
                    "use_multimodal",
                    False
                )
            ),
            bool(
                result.get(
                    "grounded",
                    False
                )
            ),
            float(
                latencies.get(
                    "agent",
                    0.0
                )
                or 0.0
            ),
            float(
                latencies.get(
                    "retrieval",
                    0.0
                )
                or 0.0
            ),
            float(
                latencies.get(
                    "generation",
                    0.0
                )
                or 0.0
            ),
            float(
                latencies.get(
                    "total",
                    0.0
                )
                or 0.0
            ),
            result.get(
                "error"
            ),
        )

        return ChatResponse(
            success=success,

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

    except Exception:

        logger.exception(
            "Chat request failed | "
            "request_id=%s | "
            "thread_id=%s",
            get_request_id(),
            active_thread_id,
        )

        raise

    finally:

        thread_id_context.reset(
            thread_token
        )