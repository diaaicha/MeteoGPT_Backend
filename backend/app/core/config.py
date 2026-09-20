from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ============================================================
# SETTINGS
# ============================================================

class Settings(BaseSettings):
    """
    Configuration centralisée du backend MeteoGPT.

    Les valeurs sont chargées depuis :
    - les variables d'environnement ;
    - le fichier .env local.

    Aucun secret ne doit être codé directement dans le code.
    """

    # --------------------------------------------------------
    # APPLICATION
    # --------------------------------------------------------

    app_name: str = "MeteoGPT Backend"

    app_env: Literal[
        "development",
        "test",
        "production",
    ] = "development"

    debug: bool = True

    api_v1_prefix: str = "/api/v1"


    # --------------------------------------------------------
    # PATHS
    # --------------------------------------------------------

    data_dir: Path = Path("data")

    log_dir: Path = Path("logs")


    # --------------------------------------------------------
    # QDRANT
    # --------------------------------------------------------

    qdrant_collection: str = "meteogpt_api_chunks"

    qdrant_path: Path = Path("data/qdrant")


    # --------------------------------------------------------
    # ANACIM
    # --------------------------------------------------------

    anacim_api_url: str = (
        "http://213.154.77.59:8000/mat/api_meteo.php"
    )


    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    gemini_api_key: str | None = None


    # --------------------------------------------------------
    # WHATSAPP CLOUD API
    # --------------------------------------------------------

    whatsapp_access_token: str | None = None

    whatsapp_phone_number_id: str | None = None

    whatsapp_verify_token: str | None = None

    whatsapp_api_version: str = "v23.0"


    # --------------------------------------------------------
    # FEATURES
    # --------------------------------------------------------

    enable_speech: bool = True

    enable_admin_update: bool = True

    enable_whatsapp: bool = False


    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )


    # --------------------------------------------------------
    # PYDANTIC SETTINGS
    # --------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


    # --------------------------------------------------------
    # ABSOLUTE PATHS
    # --------------------------------------------------------

    @property
    def absolute_data_dir(self) -> Path:
        return (
            self.data_dir
            if self.data_dir.is_absolute()
            else PROJECT_ROOT / self.data_dir
        )


    @property
    def absolute_log_dir(self) -> Path:
        return (
            self.log_dir
            if self.log_dir.is_absolute()
            else PROJECT_ROOT / self.log_dir
        )


    @property
    def absolute_qdrant_path(self) -> Path:
        return (
            self.qdrant_path
            if self.qdrant_path.is_absolute()
            else PROJECT_ROOT / self.qdrant_path
        )


# ============================================================
# SINGLETON SETTINGS
# ============================================================

@lru_cache
def get_settings() -> Settings:
    return Settings()