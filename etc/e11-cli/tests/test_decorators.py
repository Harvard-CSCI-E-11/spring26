"""Tests for e11.e11core.decorators module."""
import time

import pytest

from e11.e11core.decorators import retry, timeout


class TestTimeout:
    """Test cases for timeout decorator."""

    def test_timeout_function_completes(self):
        """Test that function completes normally when it finishes before timeout."""
        @timeout(5)
        def fast_function():
            return "success"

        result = fast_function()
        assert result == "success"

    def test_timeout_function_times_out(self):
        """Test that function raises TimeoutError when it exceeds timeout."""
        @timeout(1)
        def slow_function():
            time.sleep(2)
            return "should not reach here"

        with pytest.raises(TimeoutError, match="timed out after 1s"):
            slow_function()

    def test_timeout_with_arguments(self):
        """Test timeout decorator works with functions that take arguments."""
        @timeout(2)
        def function_with_args(x, y):
            return x + y

        result = function_with_args(3, 4)
        assert result == 7

    def test_timeout_with_keyword_arguments(self):
        """Test timeout decorator works with keyword arguments."""
        @timeout(2)
        def function_with_kwargs(x, y=10):
            return x + y

        result = function_with_kwargs(5, y=20)
        assert result == 25

    def test_timeout_preserves_function_metadata(self):
        """Test that timeout decorator preserves function metadata."""
        @timeout(2)
        def documented_function():
            """This is a test function."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a test function."


class TestRetry:
    """Test cases for retry decorator."""

    def test_retry_succeeds_first_try(self):
        """Test that function succeeds on first try without retrying."""
        call_count = 0

        @retry(times=3)
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()
        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_retries(self):
        """Test that function succeeds after initial failures."""
        call_count = 0

        @retry(times=3, backoff=0.1)
        def eventually_successful_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Not yet")
            return "success"

        result = eventually_successful_function()
        assert result == "success"
        assert call_count == 2

    def test_retry_fails_after_all_attempts(self):
        """Test that function raises exception after all retries exhausted."""
        call_count = 0

        @retry(times=3, backoff=0.1)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_failing_function()

        assert call_count == 3

    def test_retry_with_default_parameters(self):
        """Test retry decorator with default parameters."""
        call_count = 0

        @retry()
        def function_with_defaults():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Retry needed")
            return "success"

        result = function_with_defaults()
        assert result == "success"
        assert call_count == 3

    def test_retry_exponential_backoff(self):
        """Test that retry uses exponential backoff."""
        call_times = []
        expected_delays = [0.1, 0.2]  # 0.1 * 2^0, 0.1 * 2^1

        @retry(times=3, backoff=0.1)
        def function_with_backoff():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Retry")
            return "success"

        result = function_with_backoff()

        assert result == "success"
        assert len(call_times) == 3

        # Check that delays between calls follow exponential backoff pattern
        # Allow some tolerance for timing variations
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        assert 0.05 <= delay1 <= 0.15  # Allow 50ms tolerance
        assert 0.15 <= delay2 <= 0.25  # Allow 50ms tolerance

    def test_retry_different_exception_types(self):
        """Test that retry catches and retries different exception types."""
        call_count = 0

        @retry(times=3, backoff=0.1)
        def function_with_various_exceptions():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First failure")
            if call_count == 2:
                raise RuntimeError("Second failure")
            return "success"

        result = function_with_various_exceptions()
        assert result == "success"
        assert call_count == 3

    def test_retry_with_function_arguments(self):
        """Test retry decorator works with function arguments."""
        @retry(times=2, backoff=0.1)
        def function_with_args(x, y):
            return x * y

        result = function_with_args(5, 6)
        assert result == 30

    def test_retry_with_keyword_arguments(self):
        """Test retry decorator works with keyword arguments."""
        @retry(times=2, backoff=0.1)
        def function_with_kwargs(x, y=10):
            return x + y

        result = function_with_kwargs(5, y=20)
        assert result == 25

    def test_retry_preserves_function_metadata(self):
        """Test that retry decorator preserves function metadata."""
        @retry(times=3)
        def documented_function():
            """This is a test function."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a test function."

    def test_retry_single_attempt(self):
        """Test retry with times=1 (no actual retries)."""
        call_count = 0

        @retry(times=1, backoff=0.1)
        def single_attempt_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Fails")

        with pytest.raises(ValueError, match="Fails"):
            single_attempt_function()

        assert call_count == 1

    def test_retry_no_backoff_on_last_attempt(self):
        """Test that no backoff occurs after the last failed attempt."""
        call_times = []

        @retry(times=2, backoff=0.2)
        def function_no_backoff_after_last():
            call_times.append(time.time())
            raise ValueError("Always fails")

        start = time.time()
        with pytest.raises(ValueError):
            function_no_backoff_after_last()
        end = time.time()

        # Should have 2 calls, with backoff only between first and second
        assert len(call_times) == 2
        # Total time should be approximately one backoff period (0.2s)
        # Allow tolerance for timing
        assert (end - start) < 0.5

