from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field

from backend.app.schemas.chat import ChatSource


class AudioTranscriptionResponse(BaseModel):
    """
    Réponse publique d'une transcription audio.
    """

    success: bool

    transcription: str = ""

    model: Optional[str] = None

    mime_type: Optional[str] = None

    latency_ms: float = 0.0

    error: Optional[str] = None


class AudioChatResponse(BaseModel):
    """
    Réponse publique d'une requête audio MeteoGPT.
    """

    success: bool

    thread_id: str

    status: str

    output_mode: Literal[
        "text",
        "audio",
    ]

    transcription: str = ""

    answer: str = ""

    route: Optional[str] = None

    intent: Optional[str] = None

    generation_mode: Optional[str] = None

    grounded: bool = False

    retrieval_executed: bool = False

    use_multimodal: bool = False

    sources: list[ChatSource] = Field(
        default_factory=list
    )

    audio_available: bool = False

    audio_url: Optional[str] = None

    latencies_ms: Dict[
        str,
        float,
    ] = Field(
        default_factory=dict
    )

    error: Optional[str] = None