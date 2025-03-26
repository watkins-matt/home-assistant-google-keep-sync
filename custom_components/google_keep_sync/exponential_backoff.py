"""Exponential backoff decorator for Python asynchronous functions."""

import asyncio
import functools
import logging
from typing import Any, Awaitable, Callable

_LOGGER = logging.getLogger(__name__)


def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Return a decorator that applies exponential backoff to an async function.

    Args:
    ----
      max_retries: Maximum number of retries before failing
      base_delay: Starting delay in seconds before retrying
      backoff_factor: Factor by which the delay is multiplied
      exceptions: Tuple of exceptions that trigger a retry

    Returns:
    -------
      A decorator for an async function, implementing exponential backoff

    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Apply exponential backoff to the function."""

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Implement the retry logic with exponential backoff."""
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (backoff_factor**attempt)
                        _LOGGER.warning(
                            "Attempt %d for %s failed: %s. Retrying in %.2f seconds",
                            attempt + 1,
                            func.__name__,
                            e,
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        _LOGGER.error(
                            "All %d attempts for %s failed: %s",
                            max_retries,
                            func.__name__,
                            e,
                        )
                        raise

        return wrapper

    return decorator
