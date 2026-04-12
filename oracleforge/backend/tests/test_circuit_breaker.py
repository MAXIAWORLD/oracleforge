"""TDD tests for services/circuit_breaker.py."""

from services.circuit_breaker import CircuitBreaker, State


class TestCircuitBreaker:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(threshold=3)
        assert cb.state == State.CLOSED
        assert not cb.is_open

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(threshold=2, ttl=60)
        cb.record_failure("err1")
        assert not cb.is_open
        cb.record_failure("err2")
        assert cb.is_open
        assert cb.last_error == "err2"

    def test_success_resets(self) -> None:
        cb = CircuitBreaker(threshold=2, ttl=60)
        cb.record_failure("err1")
        cb.record_success()
        cb.record_failure("err2")
        assert not cb.is_open  # reset to 1 failure

    def test_half_open_after_ttl(self) -> None:
        cb = CircuitBreaker(threshold=1, ttl=0)  # instant TTL
        cb.record_failure("err")
        import time
        time.sleep(0.01)
        assert cb.state == State.HALF_OPEN

    def test_status_dict(self) -> None:
        cb = CircuitBreaker(threshold=3, ttl=60)
        status = cb.get_status()
        assert status["state"] == "closed"
        assert status["failures"] == 0
        assert status["threshold"] == 3
