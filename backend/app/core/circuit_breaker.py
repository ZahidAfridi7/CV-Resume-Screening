"""Simple in-memory circuit breaker for external calls (e.g. OpenAI)."""
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

# Default: open after 5 failures, try again after 60s
FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT_SECONDS = 60


class CircuitBreaker:
    """Thread-safe circuit breaker. State: closed -> (failures) -> open -> (timeout) -> half-open -> closed."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = FAILURE_THRESHOLD,
        recovery_timeout: float = RECOVERY_TIMEOUT_SECONDS,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._last_failure_time: float | None = None
        self._state = "closed"  # closed | open | half_open
        self._lock = Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return False
            if self._state == "open":
                if self._last_failure_time and (time.monotonic() - self._last_failure_time) >= self.recovery_timeout:
                    self._state = "half_open"
                    logger.info("Circuit %s: half-open (trial)", self.name)
                    return False
                return True
            # half_open: allow one call
            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures = 0
                logger.info("Circuit %s: closed (recovered)", self.name)
            elif self._state == "closed":
                self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.monotonic()
            if self._state == "half_open":
                self._state = "open"
                logger.warning("Circuit %s: open again (trial failed)", self.name)
            elif self._state == "closed" and self._failures >= self.failure_threshold:
                self._state = "open"
                logger.warning("Circuit %s: open after %s failures", self.name, self._failures)


# Singleton for OpenAI embedding calls (shared across async workers in same process)
_embedding_circuit: CircuitBreaker | None = None


def get_embedding_circuit() -> CircuitBreaker:
    global _embedding_circuit
    if _embedding_circuit is None:
        _embedding_circuit = CircuitBreaker(name="openai_embedding")
    return _embedding_circuit
