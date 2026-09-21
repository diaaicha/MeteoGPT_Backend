from typing import Any, Dict, Optional

from pydantic import BaseModel


class UpdateRequest(BaseModel):
    """
    Paramètres d'une actualisation ANACIM.
    """

    dry_run: bool = True


class UpdateResponse(BaseModel):
    """
    Résultat public du service d'actualisation.
    """

    status: str
    dry_run: bool

    update: Optional[
        Dict[str, Any]
    ] = None

    bm25_refresh: Optional[
        Dict[str, Any]
    ] = None

    error: Optional[str] = None