from contextvars import ContextVar


# ============================================================
# CONTEXTE DES LOGS
# ============================================================

request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)

thread_id_context: ContextVar[str] = ContextVar(
    "thread_id",
    default="-",
)


def get_request_id() -> str:
    """
    Retourne l'identifiant de la requête HTTP courante.
    """

    return request_id_context.get()


def get_thread_id() -> str:
    """
    Retourne l'identifiant de conversation courant.
    """

    return thread_id_context.get()