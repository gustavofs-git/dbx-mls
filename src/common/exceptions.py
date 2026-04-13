"""
Typed exception hierarchy for the Riot API client and ingestion pipeline.
"""


class ConfigError(Exception):
    """Raised when an unknown platform is looked up in PLATFORM_TO_REGION."""

    pass


class RiotApiError(Exception):
    """Raised on any non-retried 4xx/5xx from the Riot API."""

    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        self.url = url
        super().__init__(f"Riot API error {status_code} for {url}")


class RateLimitError(RiotApiError):
    """Raised when rate limit handling exhausts retries (future use)."""

    pass
