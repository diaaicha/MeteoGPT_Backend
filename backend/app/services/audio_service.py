from uuid import uuid4

from backend.app.core.log_context import (
    get_request_id,
    thread_id_context,
)

from backend.app.core.logging import (
    get_logger,
)

from backend.app.schemas.audio import (
    AudioChatResponse,
    AudioTranscriptionResponse,
)

from backend.app.schemas.chat import (
    ChatSource,
)


logger = get_logger("audio")


# ============================================================
# LAZY LOADERS
# ============================================================

def _load_transcribe_audio():
    """
    Charge le STT uniquement lorsqu'une transcription
    est réellement demandée.
    """

    from speech import transcribe_audio

    return transcribe_audio


def _load_process_audio_request():
    """
    Charge le pipeline audio complet uniquement lorsqu'une
    requête audio MeteoGPT doit être traitée.

    Cela évite de charger E5, Qdrant et le pipeline RAG au
    simple démarrage de FastAPI / Swagger.
    """

    from rag_pipeline import process_audio_request

    return process_audio_request


# ============================================================
# SOURCES
# ============================================================

def _normalize_sources(
    raw_sources,
) -> list[ChatSource]:

    if not isinstance(
        raw_sources,
        list,
    ):
        return []

    sources = []

    for source in raw_sources:

        if not isinstance(
            source,
            dict,
        ):
            continue

        sources.append(
            ChatSource(
                rank=source.get("rank"),
                chunk_id=source.get("chunk_id"),
                chunk_type=source.get("chunk_type"),
                source_file=source.get("source_file"),
                category=source.get("category"),
                page=source.get("page"),
                localite=source.get("localite"),
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
# STT SEUL
# ============================================================

def transcribe_audio_file(
    *,
    audio_path,
    speech_client=None,
) -> AudioTranscriptionResponse:
    """
    Transcrit un fichier audio sans lancer le pipeline RAG.
    """

    transcribe_audio = (
        _load_transcribe_audio()
    )

    result = transcribe_audio(
        audio_path,
        client=speech_client,
    )

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError(
            "Le module Speech a retourné "
            "un résultat STT invalide."
        )

    success = bool(
        result.get(
            "success",
            False,
        )
    )

    logger.info(
        "Audio transcription processed | "
        "request_id=%s | "
        "success=%s | "
        "model=%s | "
        "mime_type=%s | "
        "latency_ms=%.2f | "
        "error=%s",
        get_request_id(),
        success,
        result.get("model"),
        result.get("mime_type"),
        float(
            result.get(
                "latency_ms",
                0.0,
            )
            or 0.0
        ),
        result.get("error"),
    )

    return AudioTranscriptionResponse(
        success=success,

        transcription=(
            result.get("transcription")
            or result.get("text")
            or ""
        ),

        model=result.get("model"),

        mime_type=result.get(
            "mime_type"
        ),

        latency_ms=float(
            result.get(
                "latency_ms",
                0.0,
            )
            or 0.0
        ),

        error=result.get("error"),
    )


# ============================================================
# AUDIO -> METEOGPT
# ============================================================

def process_audio_chat(
    *,
    audio_path,
    output_mode: str = "text",
    thread_id: str | None = None,
    user_preferences=None,
    generation_client=None,
    speech_client=None,
    audio_output_path=None,
) -> AudioChatResponse:
    """
    Exécute une requête audio MeteoGPT.

    Flux :
        audio
        -> STT
        -> RAG
        -> réponse texte
        -> TTS éventuel
    """

    active_thread_id = (
        thread_id
        or str(
            uuid4()
        )
    )

    thread_token = (
        thread_id_context.set(
            active_thread_id
        )
    )

    try:

        process_audio_request = (
            _load_process_audio_request()
        )

        result = process_audio_request(
            audio_path,
            output_mode=output_mode,
            thread_id=active_thread_id,
            user_preferences=user_preferences,
            generation_client=generation_client,
            speech_client=speech_client,
            audio_output_path=audio_output_path,
        )

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Le pipeline audio MeteoGPT "
                "a retourné un résultat invalide."
            )

        pipeline_result = (
            result.get(
                "pipeline_result"
            )
            or {}
        )

        if not isinstance(
            pipeline_result,
            dict,
        ):
            pipeline_result = {}

        raw_sources = (
            pipeline_result.get(
                "sources"
            )
            or []
        )

        generated_audio_path = (
            result.get(
                "audio_output_path"
            )
        )

        success = bool(
            result.get(
                "success",
                False,
            )
        )

        logger.info(
            "Audio chat processed | "
            "request_id=%s | "
            "thread_id=%s | "
            "success=%s | "
            "status=%s | "
            "output_mode=%s | "
            "route=%s | "
            "intent=%s | "
            "grounded=%s | "
            "audio_available=%s | "
            "error=%s",
            get_request_id(),
            active_thread_id,
            success,
            result.get("status"),
            output_mode,
            pipeline_result.get("route"),
            pipeline_result.get("intent"),
            bool(
                pipeline_result.get(
                    "grounded",
                    False,
                )
            ),
            bool(
                generated_audio_path
            ),
            result.get("error"),
        )

        return AudioChatResponse(
            success=success,

            thread_id=active_thread_id,

            status=(
                result.get("status")
                or (
                    "ok"
                    if success
                    else "error"
                )
            ),

            output_mode=output_mode,

            transcription=(
                result.get(
                    "transcription"
                )
                or ""
            ),

            answer=(
                result.get(
                    "answer"
                )
                or ""
            ),

            route=pipeline_result.get(
                "route"
            ),

            intent=pipeline_result.get(
                "intent"
            ),

            generation_mode=(
                pipeline_result.get(
                    "generation_mode"
                )
            ),

            grounded=bool(
                pipeline_result.get(
                    "grounded",
                    False,
                )
            ),

            retrieval_executed=bool(
                pipeline_result.get(
                    "retrieval_executed",
                    False,
                )
            ),

            use_multimodal=bool(
                pipeline_result.get(
                    "use_multimodal",
                    False,
                )
            ),

            sources=_normalize_sources(
                raw_sources
            ),

            audio_available=bool(
                generated_audio_path
            ),

            audio_url=None,

            latencies_ms={
                key: float(
                    value or 0.0
                )
                for key, value in (
                    result.get(
                        "latencies_ms",
                        {}
                    )
                    or {}
                ).items()
            },

            error=result.get(
                "error"
            ),
        )

    finally:

        thread_id_context.reset(
            thread_token
        )