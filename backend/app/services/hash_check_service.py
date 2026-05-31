"""Hash-check gate — the first of the two upload gates (§1.4 rules 1 & 2).

Flow:

1. Client calls ``POST /drawings/hash-check`` with ``{sha256_hash, filename,
   size_bytes}``. :func:`run_hash_check` probes ``file_hash_blocklist`` (S1-C
   ``is_hash_blocked``). A present hash means *blocked* → the endpoint returns
   ``409`` and NO Drawing / NO pre-signed URL is created. An absent hash is
   recorded as a *pass* in Redis under ``hash_check_passed:{user_id}:{hash}``
   with a 30-minute TTL.
2. ``POST /drawings`` must find that pass key (:func:`has_passed_hash_check`);
   its absence means the mandatory pre-check was skipped or expired → ``400``.

Hashes are normalised to lowercase (matching S1-C's blocklist normalisation) so
the pass key written here and read by ``drawing_service`` always agree
regardless of client casing.
"""
from __future__ import annotations

from typing import Any

from app.schemas.contracts import HashCheckRequest, HashCheckResponse
from app.storage.blocklist import is_hash_blocked

# Pass-tracking key (§ critical implementation notes): 30-minute TTL.
HASH_CHECK_PASS_PREFIX = "hash_check_passed:"
HASH_CHECK_PASS_TTL_SECONDS = 1800  # 30 minutes


def _normalize(sha256_hash: str) -> str:
    return sha256_hash.strip().lower()


def pass_key(user_id: str, sha256_hash: str) -> str:
    """Redis key recording that ``user_id`` passed hash-check for this hash."""
    return f"{HASH_CHECK_PASS_PREFIX}{user_id}:{_normalize(sha256_hash)}"


async def run_hash_check(
    user_id: str,
    request: HashCheckRequest,
    db: Any,
    redis: Any,
) -> HashCheckResponse:
    """Run the blocklist gate. Returns a :class:`HashCheckResponse`.

    Returns ``allowed=False`` when the hash is blocklisted (the endpoint maps
    this to ``409`` — never ``200 {allowed:false}``). On a pass, records the
    30-minute Redis pass key and returns ``allowed=True``. No Drawing record or
    pre-signed URL is created here under any path.
    """
    if is_hash_blocked(request.sha256_hash, db):
        return HashCheckResponse(allowed=False)

    await redis.set(
        pass_key(user_id, request.sha256_hash),
        "1",
        ex=HASH_CHECK_PASS_TTL_SECONDS,
    )
    return HashCheckResponse(allowed=True)


async def has_passed_hash_check(user_id: str, sha256_hash: str, redis: Any) -> bool:
    """Return ``True`` iff a non-expired hash-check pass exists for this hash."""
    return bool(await redis.get(pass_key(user_id, sha256_hash)))


__all__ = [
    "HASH_CHECK_PASS_PREFIX",
    "HASH_CHECK_PASS_TTL_SECONDS",
    "pass_key",
    "run_hash_check",
    "has_passed_hash_check",
]
