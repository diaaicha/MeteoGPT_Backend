from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# REQUEST
# ============================================================

class ChatRequest(BaseModel):
    """
    Requête textuelle envoyée à MeteoGPT.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Question ou message envoyé à MeteoGPT.",
    )

    thread_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Identifiant de conversation. "
            "S'il est absent, le backend en génère un."
        ),
    )

    user_preferences: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Préférences utilisateur facultatives "
            "transmises à l'Agent MeteoGPT."
        ),
    )


# ============================================================
# SOURCE
# ============================================================

class ChatSource(BaseModel):
    """
    Source documentaire simplifiée exposée par l'API.
    """

    rank: int | None = None

    chunk_id: str | None = None

    chunk_type: str | None = None

    source_file: str | None = None

    category: str | None = None

    page: int | None = None

    localite: str | None = None

    date_publication: str | None = None

    date_debut_validite: str | None = None

    date_fin_validite: str | None = None


# ============================================================
# RESPONSE
# ============================================================

class ChatResponse(BaseModel):
    """
    Réponse publique de l'endpoint Chat.
    """

    success: bool

    thread_id: str

    answer: str

    route: str | None = None

    intent: str | None = None

    generation_mode: str | None = None

    grounded: bool = False

    retrieval_executed: bool = False

    use_multimodal: bool = False

    sources: list[ChatSource] = Field(
        default_factory=list
    )

    latency_ms: float | None = None

    error: str | None = None