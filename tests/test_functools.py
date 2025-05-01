import asyncio
from contextlib import AbstractContextManager, nullcontext
from datetime import timedelta

import pytest

from scraper_tools.functools import retry, timeout

cases = [
    pytest.param(timedelta(seconds=1), timedelta(seconds=0.01), nullcontext()),
    pytest.param(
        timedelta(milliseconds=10),
        timedelta(milliseconds=100),
        pytest.raises(asyncio.TimeoutError),
    ),
]


@pytest.mark.parametrize(
    "timeout_duration, work_duration, expectation",
    cases,
)
async def test_timeout_decorator(
    timeout_duration: timedelta,
    work_duration: timedelta,
    expectation: AbstractContextManager,
):
    @timeout(timeout_duration)
    async def f():
        await asyncio.sleep(work_duration.total_seconds())

    with expectation:
        await f()


async def test_retry_success_first_try():
    call_count = 0

    @retry(attempts=3)
    async def succeed_first_time():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await succeed_first_time()
    assert result == "success"
    assert call_count == 1


async def test_retry_success_after_failure():
    call_count = 0

    @retry(attempts=3)
    async def fail_then_succeed():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ValueError("Temporary failure")
        return "success"

    result = await fail_then_succeed()
    assert result == "success"
    assert call_count == 2


async def test_retry_failure_all_attempts():
    call_count = 0

    @retry(attempts=3)
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise Exception("Persistent failure")

    with pytest.raises(Exception, match="Persistent failure"):
        await always_fail()
    assert call_count == 3


async def test_retry_with_timeout_raises_timeout():
    call_count = 0

    @retry(attempts=5, delay=0.1, timeout_duration=timedelta(milliseconds=150))
    async def slow_fail():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # Each attempt takes 50ms, delay is 100ms
        raise ValueError("Trying...")

    # Expected timeline:
    # 0ms:   Attempt 1 starts
    # 50ms:  Attempt 1 fails, sleep(0.1) starts
    # 150ms: Timeout occurs during sleep before Attempt 2

    with pytest.raises(asyncio.TimeoutError):
        await slow_fail()

    # Only the first attempt runs before timeout
    assert call_count == 1


async def test_retry_with_timeout_success_within_timeout():
    call_count = 0

    @retry(attempts=3, delay=0.05, timeout_duration=timedelta(milliseconds=200))
    async def fail_then_succeed_with_timeout():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        if call_count < 2:
            raise ValueError("Temporary failure")
        return "success"

    # Expected timeline:
    # 0ms:   Attempt 1 starts
    # 10ms:  Attempt 1 fails, sleep(0.05) starts
    # 60ms:  Attempt 2 starts
    # 70ms:  Attempt 2 succeeds
    # Total time ~70ms < 200ms timeout

    result = await fail_then_succeed_with_timeout()
    assert result == "success"
    assert call_count == 2


async def test_retry_with_timeout_failure_within_timeout():
    call_count = 0

    @retry(attempts=2, delay=0.05, timeout_duration=timedelta(milliseconds=200))
    async def always_fail_with_timeout():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Simulate work
        raise ValueError("Persistent failure")

    # Expected timeline:
    # 0ms:   Attempt 1 starts
    # 10ms:  Attempt 1 fails, sleep(0.05) starts
    # 60ms:  Attempt 2 starts
    # 70ms:  Attempt 2 fails (max attempts reached)
    # Total time ~70ms < 200ms timeout

    with pytest.raises(ValueError, match="Persistent failure"):
        await always_fail_with_timeout()
    assert call_count == 2
