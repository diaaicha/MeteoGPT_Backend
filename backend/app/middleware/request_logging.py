from time import perf_counter
from uuid import uuid4

from fastapi import Request

from backend.app.core.log_context import (
    request_id_context,
)
from backend.app.core.logging import (
    get_logger,
)


logger = get_logger("http")


async def request_logging_middleware(
    request: Request,
    call_next,
):
    """
    Associe un request_id unique à chaque requête HTTP
    et journalise son exécution.
    """

    request_id = str(uuid4())

    token = request_id_context.set(
        request_id
    )

    start_time = perf_counter()

    try:

        response = await call_next(
            request
        )

        latency_ms = (
            perf_counter() - start_time
        ) * 1000

        if response.status_code >= 500:
            log_function = logger.error

        elif response.status_code >= 400:
            log_function = logger.warning

        else:
            log_function = logger.info


        log_function(
            "HTTP request completed | "
            "request_id=%s | "
            "method=%s | "
            "path=%s | "
            "status=%s | "
            "latency_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )

        response.headers[
            "X-Request-ID"
        ] = request_id

        return response

    except Exception:

        latency_ms = (
            perf_counter() - start_time
        ) * 1000

        logger.exception(
            "HTTP request failed | "
            "request_id=%s | "
            "method=%s | "
            "path=%s | "
            "latency_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            latency_ms,
        )

        raise

    finally:

        request_id_context.reset(
            token
        )