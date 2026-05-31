"""Canonical tier seed data (§1.3 ``TIER_FEATURE_GATES``).

[LOAD-BEARING] ``TIER_SEED_DATA`` is the source-of-truth list of tier rows. The
``0001_initial_schema`` migration INSERTs these rows so a fresh ``alembic upgrade
head`` is fully populated; downstream test fixtures and S2-E import this list
directly. Keep it in sync with the migration's bulk insert.
"""
from __future__ import annotations

# free: 3 drawings/month, no team features, no API.
# pro:  unlimited drawings, no team features, no API.
# team: unlimited drawings, team features on, no API.
TIER_SEED_DATA: list[dict] = [
    {
        "id": "free",
        "name": "Free",
        "monthly_drawing_limit": 3,
        "team_features": False,
        "api_access": False,
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly_drawing_limit": None,
        "team_features": False,
        "api_access": False,
    },
    {
        "id": "team",
        "name": "Team",
        "monthly_drawing_limit": None,
        "team_features": True,
        "api_access": False,
    },
]

__all__ = ["TIER_SEED_DATA"]
