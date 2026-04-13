"""Shared pytest fixtures for Phase 2 unit tests."""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_dbutils():
    """Mock Databricks dbutils.widgets for get_job_params() tests."""
    dbutils = MagicMock()
    dbutils.widgets.get.side_effect = lambda key: {"region": "KR", "tier": "CHALLENGER"}[key]
    return dbutils


@pytest.fixture
def mock_response_200(mocker):
    """Factory fixture for a successful 200 Riot API response."""
    def _make(payload: dict):
        mock = mocker.Mock()
        mock.status_code = 200
        mock.json.return_value = payload
        mock.headers = {"X-App-Rate-Limit-Count": "1:20,1:100"}
        mock.raise_for_status.return_value = None
        return mock
    return _make


@pytest.fixture
def mock_response_429(mocker):
    """Factory fixture for a 429 rate-limit response."""
    def _make(rate_limit_type: str = "application", retry_after: str = "1"):
        mock = mocker.Mock()
        mock.status_code = 429
        mock.headers = {
            "X-Rate-Limit-Type": rate_limit_type,
            "Retry-After": retry_after,
        }
        return mock
    return _make
