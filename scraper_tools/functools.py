import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from functools import wraps


def timeout[**P, R](duration: timedelta):
    """
    Adds a timeout to an async function
    """

    def decorator(func: Callable[P, Awaitable[R]]):
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with asyncio.timeout(duration.total_seconds()):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


def retry[**P, R](
    attempts: int,
    delay: float = 0,
    timeout_duration: timedelta | None = None,
):
    """
    Retries an async function a number of times with a delay between each attempt, with an optional timeout
    """

    def decorator(func: Callable[P, Awaitable[R]]):
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            while True:
                attempt = 0
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < attempts - 1:
                        if delay:
                            await asyncio.sleep(delay)
                        attempt += 1
                    else:
                        raise e

        if timeout_duration:
            wrapper = timeout(timeout_duration)(wrapper)

        return wrapper

    return decorator
