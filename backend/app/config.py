"""Application configuration (§1.12 Environment Variable Schema).

Loads every environment variable from §1.12 via a Pydantic v2 ``BaseSettings``
model and applies the documented startup behaviour:

* **Refuse to start** (``sys.exit(1)``) when a REQUIRED variable is absent or
  invalid. The error message names the offending variable(s).
* **Warn / use default** for optional variables.

LOAD-BEARING export: ``settings`` singleton — consumed by S1-A..S1-E and every
S2-* session. Do not rename fields without updating those consumers.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("pid.config")

# Defaults documented in §1.12.
_DEFAULT_POSTHOG_HOST = "https://app.posthog.com"
_DEFAULT_MAX_UPLOAD_SIZE_BYTES = 104_857_600  # 100 MB
_DEFAULT_PRESIGNED_URL_EXPIRY_SECONDS = 900  # 15 min
_DEFAULT_ML_JOB_TIMEOUT_SECONDS = 1200  # 20 min
_DEFAULT_DATA_REGION = "eu-central-1"
_DEFAULT_ENVIRONMENT = "production"


class Settings(BaseSettings):
    """Typed view over §1.12. REQUIRED fields have no default → missing them
    raises ``ValidationError`` which is converted to ``sys.exit(1)`` below."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- REQUIRED: Refuse to start if absent or invalid ---
    DATABASE_URL: str
    REDIS_URL: str
    S3_BUCKET_NAME: str
    S3_REGION: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_RS256_PUBLIC_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    SENDGRID_API_KEY: str
    HMAC_SERVER_SECRET: str
    ML_MODEL_S3_KEY: str
    ODA_CONVERTER_PATH: str

    # --- OPTIONAL: warn / use IAM role if absent ---
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None

    # --- Stripe price→tier mapping (S2-E). Not in §1.12. ---
    # Required to translate a Stripe price ID into a TierId inside the webhook
    # handler / checkout session creation. Declared OPTIONAL (warn-if-absent)
    # rather than "Refuse to start": making them hard-required would break the
    # sibling integration suite, whose conftest (owned by S0-B, not editable
    # here) seeds only the §1.12 subset of REQUIRED vars and would then
    # sys.exit(1) on `import app.config`. Presence is enforced at the point of
    # use in app.services.stripe_client (ConfigurationError → HTTP 500), so a
    # misconfigured deployment still fails loudly the first time Stripe is hit.
    STRIPE_PRO_PRICE_ID: Optional[str] = None
    STRIPE_TEAM_PRICE_ID: Optional[str] = None

    # --- OPTIONAL: analytics disabled if absent (log warning) ---
    POSTHOG_API_KEY: Optional[str] = None
    POSTHOG_HOST: str = _DEFAULT_POSTHOG_HOST

    # --- OPTIONAL: log warning if absent ---
    ML_MODEL_VERSION: Optional[str] = None
    ODA_LICENSE_EXPIRY_DATE: Optional[str] = None

    # --- OPTIONAL: typed defaults ---
    MAX_UPLOAD_SIZE_BYTES: int = _DEFAULT_MAX_UPLOAD_SIZE_BYTES
    PRESIGNED_URL_EXPIRY_SECONDS: int = _DEFAULT_PRESIGNED_URL_EXPIRY_SECONDS
    ML_JOB_TIMEOUT_SECONDS: int = _DEFAULT_ML_JOB_TIMEOUT_SECONDS

    # CELERY_BROKER_URL falls back to REDIS_URL when absent (see validator).
    CELERY_BROKER_URL: Optional[str] = None

    DATA_REGION: str = _DEFAULT_DATA_REGION
    ENVIRONMENT: str = _DEFAULT_ENVIRONMENT

    @field_validator("DATA_REGION")
    @classmethod
    def _validate_data_region(cls, v: str) -> str:
        # §1.12: invalid DATA_REGION → "Refuse to start".
        allowed = {"eu-central-1", "us-east-1"}
        if v not in allowed:
            raise ValueError(f"DATA_REGION must be one of {sorted(allowed)}, got {v!r}")
        return v

    @field_validator("STRIPE_SECRET_KEY")
    @classmethod
    def _validate_stripe_secret(cls, v: str) -> str:
        if not (v.startswith("sk_live_") or v.startswith("sk_test_")):
            raise ValueError("STRIPE_SECRET_KEY must start with 'sk_live_' or 'sk_test_'")
        return v

    @field_validator("STRIPE_WEBHOOK_SECRET")
    @classmethod
    def _validate_stripe_webhook(cls, v: str) -> str:
        if not v.startswith("whsec_"):
            raise ValueError("STRIPE_WEBHOOK_SECRET must start with 'whsec_'")
        return v

    @model_validator(mode="after")
    def _apply_fallbacks_and_warnings(self) -> "Settings":
        # CELERY_BROKER_URL falls back to REDIS_URL (§1.12).
        if not self.CELERY_BROKER_URL:
            object.__setattr__(self, "CELERY_BROKER_URL", self.REDIS_URL)

        # ENVIRONMENT: invalid → warn + use 'production' default.
        if self.ENVIRONMENT not in {"development", "staging", "production"}:
            logger.warning(
                "ENVIRONMENT=%r invalid; falling back to 'production'", self.ENVIRONMENT
            )
            object.__setattr__(self, "ENVIRONMENT", _DEFAULT_ENVIRONMENT)

        # Optional-but-warn variables.
        if not self.POSTHOG_API_KEY:
            logger.warning("POSTHOG_API_KEY absent; analytics disabled.")
        if not self.ML_MODEL_VERSION:
            logger.warning("ML_MODEL_VERSION absent; will use latest model in bucket.")
        if not self.STRIPE_PRO_PRICE_ID or not self.STRIPE_TEAM_PRICE_ID:
            logger.warning(
                "STRIPE_PRO_PRICE_ID / STRIPE_TEAM_PRICE_ID absent; Stripe "
                "checkout and tier resolution will fail until they are set "
                "(see app.services.stripe_client)."
            )
        if not self.ODA_LICENSE_EXPIRY_DATE:
            logger.warning("ODA_LICENSE_EXPIRY_DATE absent; 30-day expiry alerting disabled.")
        if not self.AWS_ACCESS_KEY_ID or not self.AWS_SECRET_ACCESS_KEY:
            logger.info("AWS static credentials absent; using IAM role.")
        return self


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_or_invalid = sorted({str(err["loc"][0]) for err in exc.errors() if err.get("loc")})
        print(
            "FATAL: invalid or missing required environment variable(s): "
            + ", ".join(missing_or_invalid)
            + "\nRefusing to start (see §1.12 Environment Variable Schema).\n"
            + f"Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


# LOAD-BEARING singleton. Importing this module with a REQUIRED var missing
# terminates the process with exit code 1.
settings = _load_settings()
