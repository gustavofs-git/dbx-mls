"""
Riot API client: dual-bucket token bucket rate limiter and API call function.

Implements the 20 req/sec + 100 req/2min dual-bucket constraint from the Riot
Developer Portal (development key limits). All API calls must pass through
call_riot_api() which calls limiter.acquire() before every requests.get().

Decision D-01: All API calls execute on the Spark driver in plain Python for loops.
The RiotRateLimiter singleton is shared naturally within the driver process.
"""

import random
import threading
import time

import requests

from src.common.exceptions import RiotApiError
from src.common.logger import get_logger

logger = get_logger(__name__)


class RiotRateLimiter:
    """Thread-safe dual-bucket token bucket rate limiter.

    Enforces both Riot API development key limits simultaneously:
    - Bucket 1: 20 requests per second
    - Bucket 2: 100 requests per 2 minutes (120 seconds)

    Instantiate once per driver process and pass the instance to every
    call_riot_api() call. Do NOT instantiate inside call_riot_api().
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Bucket 1: 20 req/sec
        self._sec_tokens = 20
        self._sec_capacity = 20
        self._sec_refill_rate = 20.0  # tokens per second
        # Bucket 2: 100 req/2min
        self._min_tokens = 100
        self._min_capacity = 100
        self._min_refill_rate = 100 / 120.0  # tokens per second
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        """Compute elapsed time and add proportional tokens to both buckets.

        Must be called inside the lock. Uses time.monotonic() for monotonic
        wall-clock elapsed time, immune to system clock adjustments.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._sec_tokens = min(
            self._sec_capacity,
            self._sec_tokens + elapsed * self._sec_refill_rate,
        )
        self._min_tokens = min(
            self._min_capacity,
            self._min_tokens + elapsed * self._min_refill_rate,
        )

    def acquire(self) -> None:
        """Block until both buckets have a token, then consume one from each.

        The token bucket IS the primary throttle. The time.sleep(0.05) here is
        a lock-release wait between bucket-check loop iterations only — it is
        NOT the primary throttle mechanism.
        """
        while True:
            with self._lock:
                self._refill()
                if self._sec_tokens >= 1 and self._min_tokens >= 1:
                    self._sec_tokens -= 1
                    self._min_tokens -= 1
                    return
            time.sleep(0.05)  # release lock between checks (NOT the primary throttle)


def call_riot_api(
    url: str,
    headers: dict,
    limiter: RiotRateLimiter,
    params: dict | None = None,
    timeout: int = 10,
) -> dict:
    """Call a Riot API endpoint with rate limiting and 429 handling.

    Rate limiting:
        limiter.acquire() is called before every requests.get() to enforce the
        dual-bucket constraint. The limiter is passed in — never instantiated here.

    429 handling:
        - X-Rate-Limit-Type: application or method → sleep Retry-After seconds, retry
        - X-Rate-Limit-Type: service               → exponential backoff with jitter, retry

    Error handling:
        - 404 → raises RiotApiError(404, url) (not bare HTTPError)
        - Other 4xx/5xx → raises via response.raise_for_status()

    Args:
        url: Full Riot API endpoint URL including routing host.
        headers: Request headers dict (must include X-Riot-Token).
        limiter: RiotRateLimiter instance shared across all calls.
        params: Optional query string parameters.
        timeout: requests.get() timeout in seconds.

    Returns:
        Parsed JSON response as a Python dict.

    Raises:
        RiotApiError: On 404 or other non-retried HTTP errors.
    """
    limiter.acquire()
    response = requests.get(url, headers=headers, params=params, timeout=timeout)

    # Log rate limit usage on every response for observability
    rate_count = response.headers.get("X-App-Rate-Limit-Count", "unknown")
    logger.info(
        f"Riot API call: status={response.status_code} rate_count={rate_count} url={url}"
    )

    if response.status_code == 429:
        rate_limit_type = response.headers.get("X-Rate-Limit-Type", "service")
        if rate_limit_type in ("application", "method"):
            # App/method limit: Riot tells us exactly how long to wait
            retry_after = int(response.headers.get("Retry-After", 1))
            time.sleep(retry_after)
            return call_riot_api(url, headers, limiter, params, timeout)
        else:
            # Service-level limit: exponential backoff with jitter
            time.sleep(2 + random.uniform(0, 1))
            return call_riot_api(url, headers, limiter, params, timeout)

    if response.status_code == 404:
        raise RiotApiError(404, url)

    response.raise_for_status()
    return response.json()
