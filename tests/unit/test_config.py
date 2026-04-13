"""
Unit tests for src/config.py — platform routing, host resolvers, job parameter reader.
"""
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# PLATFORM_TO_REGION — coverage
# ---------------------------------------------------------------------------

class TestPlatformToRegion:
    def test_has_exactly_17_entries(self):
        from src.config import PLATFORM_TO_REGION
        assert len(PLATFORM_TO_REGION) == 17, (
            f"Expected 17 platforms, got {len(PLATFORM_TO_REGION)}: "
            f"{sorted(PLATFORM_TO_REGION.keys())}"
        )

    def test_kr_maps_to_asia(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["KR"] == "asia"

    def test_jp1_maps_to_asia(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["JP1"] == "asia"

    def test_na1_maps_to_americas(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["NA1"] == "americas"

    def test_br1_maps_to_americas(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["BR1"] == "americas"

    def test_la1_maps_to_americas(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["LA1"] == "americas"

    def test_la2_maps_to_americas(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["LA2"] == "americas"

    def test_euw1_maps_to_europe(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["EUW1"] == "europe"

    def test_eun1_maps_to_europe(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["EUN1"] == "europe"

    def test_tr1_maps_to_europe(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["TR1"] == "europe"

    def test_ru_maps_to_europe(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["RU"] == "europe"

    def test_me1_maps_to_europe(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["ME1"] == "europe"

    def test_oc1_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["OC1"] == "sea"

    def test_ph2_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["PH2"] == "sea"

    def test_sg2_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["SG2"] == "sea"

    def test_th2_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["TH2"] == "sea"

    def test_tw2_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["TW2"] == "sea"

    def test_vn2_maps_to_sea(self):
        from src.config import PLATFORM_TO_REGION
        assert PLATFORM_TO_REGION["VN2"] == "sea"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_ranked_queue_value(self):
        from src.config import RANKED_QUEUE
        assert RANKED_QUEUE == "RANKED_SOLO_5x5"

    def test_default_match_count(self):
        from src.config import DEFAULT_MATCH_COUNT
        assert DEFAULT_MATCH_COUNT == 20

    def test_job_timeout_seconds(self):
        from src.config import JOB_TIMEOUT_SECONDS
        assert JOB_TIMEOUT_SECONDS == 14400


# ---------------------------------------------------------------------------
# get_platform_host
# ---------------------------------------------------------------------------

class TestGetPlatformHost:
    def test_kr_returns_platform_host(self):
        from src.config import get_platform_host
        assert get_platform_host("KR") == "kr.api.riotgames.com"

    def test_na1_returns_platform_host(self):
        from src.config import get_platform_host
        assert get_platform_host("NA1") == "na1.api.riotgames.com"

    def test_euw1_returns_platform_host(self):
        from src.config import get_platform_host
        assert get_platform_host("EUW1") == "euw1.api.riotgames.com"

    def test_lowercase_input_normalized(self):
        from src.config import get_platform_host
        assert get_platform_host("kr") == "kr.api.riotgames.com"


# ---------------------------------------------------------------------------
# get_region_host
# ---------------------------------------------------------------------------

class TestGetRegionHost:
    def test_kr_returns_asia_host(self):
        from src.config import get_region_host
        assert get_region_host("KR") == "asia.api.riotgames.com"

    def test_na1_returns_americas_host(self):
        from src.config import get_region_host
        assert get_region_host("NA1") == "americas.api.riotgames.com"

    def test_euw1_returns_europe_host(self):
        from src.config import get_region_host
        assert get_region_host("EUW1") == "europe.api.riotgames.com"

    def test_oc1_returns_sea_host(self):
        from src.config import get_region_host
        assert get_region_host("OC1") == "sea.api.riotgames.com"

    def test_unknown_platform_raises_config_error(self):
        from src.config import get_region_host
        from src.common.exceptions import ConfigError
        with pytest.raises(ConfigError):
            get_region_host("UNKNOWN_PLATFORM")

    def test_fake_raises_config_error(self):
        from src.config import get_region_host
        from src.common.exceptions import ConfigError
        with pytest.raises(ConfigError):
            get_region_host("FAKE")

    def test_lowercase_kr_works(self):
        from src.config import get_region_host
        assert get_region_host("kr") == "asia.api.riotgames.com"


# ---------------------------------------------------------------------------
# get_job_params
# ---------------------------------------------------------------------------

class TestGetJobParams:
    def _make_dbutils(self, region: str, tier: str) -> MagicMock:
        dbutils = MagicMock()
        dbutils.widgets.get.side_effect = lambda key: {"region": region, "tier": tier}[key]
        return dbutils

    def test_returns_dict_with_region_and_tier(self):
        from src.config import get_job_params
        dbutils = self._make_dbutils("KR", "CHALLENGER")
        result = get_job_params(dbutils)
        assert result == {"region": "KR", "tier": "CHALLENGER"}

    def test_normalizes_region_to_uppercase(self):
        from src.config import get_job_params
        dbutils = self._make_dbutils("kr", "challenger")
        result = get_job_params(dbutils)
        assert result["region"] == "KR"
        assert result["tier"] == "CHALLENGER"

    def test_invalid_region_raises_config_error(self):
        from src.config import get_job_params
        from src.common.exceptions import ConfigError
        dbutils = self._make_dbutils("INVALID_REGION", "CHALLENGER")
        with pytest.raises(ConfigError):
            get_job_params(dbutils)

    def test_reads_from_widgets_not_hardcoded(self):
        """Verify that dbutils.widgets.get is called for both region and tier."""
        from src.config import get_job_params
        dbutils = self._make_dbutils("NA1", "GRANDMASTER")
        result = get_job_params(dbutils)
        assert result == {"region": "NA1", "tier": "GRANDMASTER"}
        # Confirm widget reads happened
        calls = [call.args[0] for call in dbutils.widgets.get.call_args_list]
        assert "region" in calls
        assert "tier" in calls
