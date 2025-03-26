"""Tests for the exponential_backoff decorator."""

import time

import pytest

from custom_components.google_keep_sync.exponential_backoff import exponential_backoff


@pytest.mark.asyncio
async def test_success_on_first_try():
    """Test that no backoff occurs when function succeeds immediately."""

    @exponential_backoff(max_retries=3)
    async def successful_function():
        return "Success"

    start = time.time()
    result = await successful_function()
    duration = time.time() - start

    assert result == "Success"

    maximum_expected_function_duration = 1.0
    assert (
        duration < maximum_expected_function_duration
    )  # Should not wait if it succeeds immediately


@pytest.mark.asyncio
async def test_fails_then_succeeds():
    """Test backoff occurs for function that fails first, then succeeds."""
    attempts = {"count": 0}
    max_attemps = 2

    @exponential_backoff(max_retries=4, base_delay=0.5)
    async def flaky_function():
        if attempts["count"] < max_attemps:
            attempts["count"] += 1
            raise ConnectionError("Simulated failure")
        return "Recovered"

    result = await flaky_function()
    assert result == "Recovered"
    assert attempts["count"] == max_attemps


@pytest.mark.asyncio
async def test_all_attempts_fail():
    """Test exception is raised if all attempts fail."""

    @exponential_backoff(max_retries=2, base_delay=0.1)
    async def always_fail():
        raise ValueError("Never succeeds")

    with pytest.raises(ValueError):
        await always_fail()
