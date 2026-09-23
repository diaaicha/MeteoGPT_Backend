from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from backend.app.core.config import (
    get_settings,
)

from backend.app.schemas.audio import (
    AudioChatResponse,
    AudioTranscriptionResponse,
)

from backend.app.services import (
    audio_service,
)


router = APIRouter(
    prefix="/audio",
    tags=["Audio"],
)


# ============================================================
# TRANSCRIPTION AUDIO
# ============================================================

@router.post(
    "/transcribe",
    response_model=AudioTranscriptionResponse,
    summary="Transcrire un fichier audio",
)
async def transcribe_audio(
    file: UploadFile = File(...),
) -> AudioTranscriptionResponse:
    """
    Reçoit un fichier audio et retourne sa transcription.

    Le fichier temporaire local est supprimé après traitement.
    """

    settings = get_settings()

    if not settings.enable_speech:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service audio est désactivé.",
        )

    suffix = Path(
        file.filename or "audio.wav"
    ).suffix

    if not suffix:
        suffix = ".wav"

    temp_path = None

    try:

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier audio est vide.",
            )

        with NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
        ) as temp_file:

            temp_file.write(content)

            temp_path = Path(
                temp_file.name
            )

        result = (
            audio_service.transcribe_audio_file(
                audio_path=temp_path,
            )
        )

        return result

    finally:

        await file.close()

        if (
            temp_path is not None
            and temp_path.exists()
        ):
            try:
                temp_path.unlink()
            except OSError:
                pass


# ============================================================
# AUDIO -> STT -> RAG -> TEXTE
# ============================================================

@router.post(
    "/chat",
    response_model=AudioChatResponse,
    summary="Interroger MeteoGPT avec un fichier audio",
)
async def audio_chat(
    file: UploadFile = File(...),
    thread_id: str | None = Form(default=None),
) -> AudioChatResponse:
    """
    Reçoit une question vocale et retourne la réponse
    textuelle de MeteoGPT.

    Flux :
        audio
        -> STT
        -> pipeline RAG
        -> réponse texte
    """

    settings = get_settings()

    if not settings.enable_speech:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service audio est désactivé.",
        )

    suffix = Path(
        file.filename or "audio.wav"
    ).suffix

    if not suffix:
        suffix = ".wav"

    temp_path = None

    try:

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier audio est vide.",
            )

        with NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
        ) as temp_file:

            temp_file.write(content)

            temp_path = Path(
                temp_file.name
            )

        result = (
            audio_service.process_audio_chat(
                audio_path=temp_path,
                output_mode="text",
                thread_id=thread_id,
            )
        )

        return result

    finally:

        await file.close()

        if (
            temp_path is not None
            and temp_path.exists()
        ):
            try:
                temp_path.unlink()
            except OSError:
                pass