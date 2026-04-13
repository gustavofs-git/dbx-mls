"""
Platform routing configuration for the Riot Games API.

Riot uses two host namespaces:
  - Platform hosts  (e.g. kr.api.riotgames.com)  — League-Exp-V4, Summoner-V4
  - Regional hosts  (e.g. asia.api.riotgames.com) — Match-V5, Account-V1

NEVER use a platform host for Match-V5 or Account-V1 calls — returns 404.
"""
from src.common.exceptions import ConfigError
from src.common.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Routing constants
# ---------------------------------------------------------------------------

PLATFORM_TO_REGION: dict[str, str] = {
    # Asia
    "KR": "asia",
    "JP1": "asia",
    # Americas
    "NA1": "americas",
    "BR1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    # Europe
    "EUW1": "europe",
    "EUN1": "europe",
    "TR1": "europe",
    "RU": "europe",
    "ME1": "europe",
    # Southeast Asia
    "OC1": "sea",
    "PH2": "sea",
    "SG2": "sea",
    "TH2": "sea",
    "TW2": "sea",
    "VN2": "sea",
}

RANKED_QUEUE: str = "RANKED_SOLO_5x5"

# Max match IDs fetched per PUUID (Riot API max is 100; use 20 for dev key quota)
DEFAULT_MATCH_COUNT: int = 20

# 4-hour timeout — cold KR Challenger run is 2–3.5 h at dev key rate (100 req/2min)
JOB_TIMEOUT_SECONDS: int = 14400

# ---------------------------------------------------------------------------
# Host resolution
# ---------------------------------------------------------------------------


def get_platform_host(platform: str) -> str:
    """Return the platform-specific API host.

    Used by: League-Exp-V4, Summoner-V4.
    Example: get_platform_host("KR") → "kr.api.riotgames.com"
    """
    return f"{platform.lower()}.api.riotgames.com"


def get_region_host(platform: str) -> str:
    """Return the regional API host for the given platform.

    Used by: Match-V5, Account-V1.
    Example: get_region_host("KR") → "asia.api.riotgames.com"

    Raises ConfigError for unknown platforms.
    """
    region = PLATFORM_TO_REGION.get(platform.upper())
    if region is None:
        raise ConfigError(
            f"Unknown platform '{platform}'. "
            f"Known platforms: {sorted(PLATFORM_TO_REGION.keys())}"
        )
    return f"{region}.api.riotgames.com"


# ---------------------------------------------------------------------------
# Job parameter reader
# ---------------------------------------------------------------------------


def get_job_params(dbutils) -> dict:
    """Read job parameters from Databricks widget parameters.

    Parameters (set via DAB job definition defaults or runtime override):
      region  — Riot platform code, e.g. "KR", "NA1"  (default: KR)
      tier    — League tier, e.g. "CHALLENGER", "DIAMOND"  (default: CHALLENGER)

    Returns: {"region": str, "tier": str}
    Raises ConfigError if region is not a known Riot platform.
    """
    region = dbutils.widgets.get("region")
    tier = dbutils.widgets.get("tier")

    if region.upper() not in PLATFORM_TO_REGION:
        raise ConfigError(
            f"Job parameter 'region={region}' is not a known Riot platform. "
            f"Known platforms: {sorted(PLATFORM_TO_REGION.keys())}"
        )

    logger.info(f"Job params: region={region} tier={tier}")
    return {"region": region.upper(), "tier": tier.upper()}
