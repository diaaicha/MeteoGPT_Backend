import logging
from logging.handlers import RotatingFileHandler


from backend.app.core.config import get_settings


# ============================================================
# CONSTANTES
# ============================================================

LOGGER_NAME = "meteogpt"

LOG_FILENAME = "meteogpt_backend.log"


# ============================================================
# CONFIGURATION DU LOGGING
# ============================================================

def configure_logging() -> logging.Logger:
    """
    Configure le système de logging centralisé de MeteoGPT.

    Les logs sont envoyés :
    - dans la console ;
    - dans un fichier rotatif local.

    Cette fonction est idempotente :
    elle n'ajoute pas plusieurs fois les mêmes handlers.
    """

    settings = get_settings()

    log_dir = settings.absolute_log_dir

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = logging.getLogger(
        LOGGER_NAME
    )

    logger.setLevel(
        getattr(
            logging,
            settings.log_level.upper(),
            logging.INFO,
        )
    )

    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )

    # --------------------------------------------------------
    # CONSOLE
    # --------------------------------------------------------

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    # --------------------------------------------------------
    # FICHIER
    # --------------------------------------------------------

    file_handler = RotatingFileHandler(
        log_dir / LOG_FILENAME,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        formatter
    )

    # --------------------------------------------------------
    # HANDLERS
    # --------------------------------------------------------

    logger.addHandler(
        console_handler
    )

    logger.addHandler(
        file_handler
    )

    return logger


# ============================================================
# LOGGER ENFANT
# ============================================================

def get_logger(
    name: str
) -> logging.Logger:
    """
    Retourne un logger enfant du logger MeteoGPT.
    """

    return logging.getLogger(
        f"{LOGGER_NAME}.{name}"
    )