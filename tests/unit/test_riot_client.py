"""
Unit tests for src/riot_client.py — RiotRateLimiter and call_riot_api().

Tests use mocked HTTP responses and time functions; no live API key required.
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.riot_client import RiotRateLimiter, call_riot_api
from src.common.exceptions import RiotApiError


# ---------------------------------------------------------------------------
# RiotRateLimiter tests
# ---------------------------------------------------------------------------

class TestRiotRateLimiterInit:
    def test_initial_sec_tokens(self):
        limiter = RiotRateLimiter()
        assert limiter._sec_tokens == 20

    def test_initial_min_tokens(self):
        limiter = RiotRateLimiter()
        assert limiter._min_tokens == 100

    def test_sec_capacity(self):
        limiter = RiotRateLimiter()
        assert limiter._sec_capacity == 20

    def test_min_capacity(self):
        limiter = RiotRateLimiter()
        assert limiter._min_capacity == 100

    def test_min_refill_rate(self):
        limiter = RiotRateLimiter()
        assert abs(limiter._min_refill_rate - (100 / 120.0)) < 1e-9

    def test_has_lock(self):
        limiter = RiotRateLimiter()
        assert limiter._lock is not None


class TestRiotRateLimiterAcquire:
    def test_acquire_returns_when_tokens_available(self):
        """acquire() returns immediately when both buckets have tokens."""
        limiter = RiotRateLimiter()
        # Fresh limiter has full tokens — should return without sleeping
        with patch("time.sleep") as mock_sleep:
            limiter.acquire()
        mock_sleep.assert_not_called()

    def test_acquire_consumes_one_sec_token(self):
        limiter = RiotRateLimiter()
        initial = limiter._sec_tokens
        limiter.acquire()
        assert limiter._sec_tokens == initial - 1

    def test_acquire_consumes_one_min_token(self):
        limiter = RiotRateLimiter()
        initial = limiter._min_tokens
        limiter.acquire()
        assert limiter._min_tokens == initial - 1

    def test_acquire_blocks_when_sec_bucket_empty(self):
        """acquire() calls time.sleep(0.05) when sec bucket is empty."""
        limiter = RiotRateLimiter()
        limiter._sec_tokens = 0.5  # below 1

        call_count = 0

        def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            # After first sleep, refill sec tokens so acquire() can proceed
            limiter._sec_tokens = 20.0

        with patch("time.sleep", side_effect=fake_sleep):
            limiter.acquire()

        assert call_count >= 1

    def test_acquire_blocks_when_min_bucket_empty(self):
        """acquire() calls time.sleep(0.05) when min bucket is empty."""
        limiter = RiotRateLimiter()
        limiter._min_tokens = 0.5  # below 1

        call_count = 0

        def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            limiter._min_tokens = 100.0

        with patch("time.sleep", side_effect=fake_sleep):
            limiter.acquire()

        assert call_count >= 1


# ---------------------------------------------------------------------------
# call_riot_api() tests
# ---------------------------------------------------------------------------

class TestCallRiotApi:
    def _make_response(self, status_code, json_data=None, headers=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or {}
        mock_resp.headers = headers or {}
        if status_code < 400:
            mock_resp.raise_for_status.return_value = None
        else:
            mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return mock_resp

    def test_returns_json_on_200(self):
        limiter = RiotRateLimiter()
        resp_data = {"gameId": 123, "winner": "blue"}
        mock_resp = self._make_response(200, json_data=resp_data)

        with patch("requests.get", return_value=mock_resp):
            result = call_riot_api("http://test/api", {"X-Riot-Token": "key"}, limiter)

        assert result == resp_data

    def test_calls_limiter_acquire_before_get(self):
        limiter = MagicMock(spec=RiotRateLimiter)
        mock_resp = self._make_response(200, json_data={})

        acquire_called_before_get = []

        def track_get(*args, **kwargs):
            acquire_called_before_get.append(limiter.acquire.called)
            return mock_resp

        with patch("requests.get", side_effect=track_get):
            call_riot_api("http://test/api", {}, limiter)

        limiter.acquire.assert_called_once()
        assert acquire_called_before_get[0] is True, "acquire() must be called before requests.get()"

    def test_raises_riot_api_error_on_404(self):
        limiter = RiotRateLimiter()
        mock_resp = self._make_response(404, headers={"X-App-Rate-Limit-Count": "1:1"})
        mock_resp.raise_for_status.side_effect = None  # 404 handled explicitly before raise_for_status

        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(RiotApiError) as exc_info:
                call_riot_api("http://test/summoner/unknown", {}, limiter)

        assert exc_info.value.status_code == 404
        assert "http://test/summoner/unknown" in exc_info.value.url

    def test_429_application_limit_sleeps_retry_after(self):
        """On 429 application/method limit, sleeps Retry-After seconds then retries."""
        limiter = RiotRateLimiter()
        mock_429 = self._make_response(
            429,
            headers={
                "X-Rate-Limit-Type": "application",
                "Retry-After": "5",
                "X-App-Rate-Limit-Count": "20:1",
            },
        )
        mock_200 = self._make_response(200, json_data={"ok": True})
        sleep_durations = []

        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep", side_effect=lambda d: sleep_durations.append(d)):
                result = call_riot_api("http://test/api", {}, limiter)

        assert result == {"ok": True}
        assert 5 in sleep_durations, f"Expected sleep(5) for Retry-After=5. Got: {sleep_durations}"

    def test_429_method_limit_sleeps_retry_after(self):
        """On 429 method limit, sleeps Retry-After seconds then retries."""
        limiter = RiotRateLimiter()
        mock_429 = self._make_response(
            429,
            headers={
                "X-Rate-Limit-Type": "method",
                "Retry-After": "3",
                "X-App-Rate-Limit-Count": "5:10",
            },
        )
        mock_200 = self._make_response(200, json_data={"result": "data"})
        sleep_durations = []

        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep", side_effect=lambda d: sleep_durations.append(d)):
                result = call_riot_api("http://test/api", {}, limiter)

        assert result == {"result": "data"}
        assert 3 in sleep_durations

    def test_429_service_limit_uses_backoff(self):
        """On 429 service limit, uses exponential backoff with jitter (sleep called with value != Retry-After)."""
        limiter = RiotRateLimiter()
        mock_429 = self._make_response(
            429,
            headers={
                "X-Rate-Limit-Type": "service",
                "X-App-Rate-Limit-Count": "0:0",
            },
        )
        mock_200 = self._make_response(200, json_data={"data": "ok"})
        sleep_durations = []

        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep", side_effect=lambda d: sleep_durations.append(d)):
                result = call_riot_api("http://test/api", {}, limiter)

        assert result == {"data": "ok"}
        # Service backoff: sleep with value >= 2 (base is 2 + jitter)
        non_bucket_sleeps = [d for d in sleep_durations if d != 0.05]
        assert len(non_bucket_sleeps) >= 1
        assert non_bucket_sleeps[0] >= 2, f"Expected service backoff >= 2s, got: {non_bucket_sleeps}"

    def test_x_app_rate_limit_count_logged(self, caplog):
        """call_riot_api() logs the X-App-Rate-Limit-Count header."""
        import logging
        limiter = RiotRateLimiter()
        mock_resp = self._make_response(
            200,
            json_data={},
            headers={"X-App-Rate-Limit-Count": "5:20,3:100"},
        )

        with patch("requests.get", return_value=mock_resp):
            with caplog.at_level(logging.INFO, logger="src.riot_client"):
                call_riot_api("http://test/api", {}, limiter)

        assert any("5:20,3:100" in r.message for r in caplog.records), (
            "Expected X-App-Rate-Limit-Count value in log records"
        )
