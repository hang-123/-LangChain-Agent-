"""
Retry helpers adapted from the upstream BettaFish project.
They centralize retry/backoff behavior so both QueryEngine and InsightEngine
can share the same posture when calling external services.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Iterable, Tuple

import requests

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retry_on: Tuple[type[BaseException], ...] = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.HTTPError,
        requests.exceptions.RequestException,
        ConnectionError,
        TimeoutError,
        Exception,
    )


def _sleep(delay: float) -> None:
    try:
        time.sleep(delay)
    except Exception:  # pragma: no cover
        pass


def with_retry(config: RetryConfig | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that retries the wrapped call and re-raises the last exception
    if all attempts fail.
    """

    cfg = config or RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: BaseException | None = None
            for attempt in range(cfg.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.retry_on as exc:  # type: ignore[arg-type]
                    last_error = exc
                    if attempt >= cfg.max_retries:
                        logger.error("Function %s failed after %s attempts", func.__name__, attempt + 1)
                        raise
                    delay = min(cfg.initial_delay * (cfg.backoff_factor**attempt), cfg.max_delay)
                    logger.warning(
                        "Function %s failed on attempt %s: %s. Retrying in %.1fs",
                        func.__name__,
                        attempt + 1,
                        exc,
                        delay,
                    )
                    _sleep(delay)
            if last_error:
                raise last_error
            raise RuntimeError("Retry loop exited without result")

        return wrapper

    return decorator


def with_graceful_retry(
    config: RetryConfig | None = None, *, default_return: Any = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Similar to with_retry but returns a default value instead of raising.
    Suitable for non-critical network calls.
    """

    cfg = config or RetryConfig()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(cfg.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except cfg.retry_on as exc:  # type: ignore[arg-type]
                    if attempt >= cfg.max_retries:
                        logger.warning(
                            "Function %s failed after %s attempts, returning default. Error: %s",
                            func.__name__,
                            attempt + 1,
                            exc,
                        )
                        return default_return
                    delay = min(cfg.initial_delay * (cfg.backoff_factor**attempt), cfg.max_delay)
                    logger.warning(
                        "Function %s failed on attempt %s: %s. Retrying in %.1fs",
                        func.__name__,
                        attempt + 1,
                        exc,
                        delay,
                    )
                    _sleep(delay)
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "Function %s raised non-retryable error %s. Returning default value.",
                        func.__name__,
                        exc,
                    )
                    return default_return
            return default_return

        return wrapper

    return decorator


LLM_RETRY_CONFIG = RetryConfig(
    max_retries=6,
    initial_delay=60.0,
    backoff_factor=2.0,
    max_delay=600.0,
)

SEARCH_API_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    initial_delay=2.0,
    backoff_factor=1.6,
    max_delay=25.0,
)

DB_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    initial_delay=1.0,
    backoff_factor=1.5,
    max_delay=10.0,
)

