"""Free-tier monthly drawing counter (§1.4 rule 8, US-018).

Free-tier users may initiate processing of at most ``FREE_TIER_MONTHLY_LIMIT``
(3) drawings per calendar month. The counter is incremented at *enqueue time*
(``upload-complete``), not at completion, so concurrent uploads cannot bypass
the cap (§1.4 rule 8 / US-018 AC-5).

Atomicity (US-018 AC-2): the check-and-increment relies on Redis ``INCR``
returning the post-increment value atomically. Two concurrent callers therefore
observe two distinct values — they can never both read the same pre-increment
count and both proceed. When the post-increment value exceeds the limit the key
is immediately ``DECR``-ed back, so a rejected attempt does not consume quota.

Key format (load-bearing within this session): ``free_tier_counter:{user_id}:
{YYYY-MM}`` scoped to the current UTC calendar month. The key's TTL is set on
first increment to expire shortly after month-end, so a user who hits the cap in
January can upload again in February (US-018 AC-4).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional

# §1.3 TIER_FEATURE_GATES — free tier allows 3 drawings/month.
FREE_TIER_MONTHLY_LIMIT = 3

_KEY_PREFIX = "free_tier_counter:"


@dataclass(frozen=True)
class FreeCounterResult:
    """Outcome of a check-and-increment attempt.

    * ``allowed`` — ``True`` when the increment stayed within ``limit`` (the
      caller may enqueue); ``False`` when the limit would be exceeded (the
      caller must NOT enqueue and should fire ``free_limit_reached``).
    * ``count`` — the effective count of enqueued drawings this month *after*
      this call (rejected attempts are rolled back, so this never exceeds
      ``limit``).
    * ``limit`` — the limit that was applied.
    """

    allowed: bool
    count: int
    limit: int


def _month_key(user_id: str, now: datetime.datetime) -> str:
    return f"{_KEY_PREFIX}{user_id}:{now:%Y-%m}"


def _seconds_until_month_end(now: datetime.datetime) -> int:
    """Seconds from ``now`` until 1 day past the end of the current UTC month."""
    if now.month == 12:
        next_month = now.replace(
            year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        next_month = now.replace(
            month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    # +1 day of slack so a clock skew never expires the window early.
    expiry = next_month + datetime.timedelta(days=1)
    return int((expiry - now).total_seconds())


async def check_and_increment(
    user_id: str,
    db: Any,
    redis: Any,
    *,
    limit: int = FREE_TIER_MONTHLY_LIMIT,
    now: Optional[datetime.datetime] = None,
) -> FreeCounterResult:
    """Atomically increment this month's counter and report whether it is within
    ``limit``.

    ``db`` is accepted for the documented internal contract (and to allow a
    future DB-backed fallback) but the count itself is held in Redis so the
    increment is atomic across processes. ``now`` is injectable for tests; it
    defaults to the current UTC time.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    key = _month_key(user_id, now)

    count = int(await redis.incr(key))
    if count == 1:
        # Set the month-scoped TTL only when the key is first created so the
        # window is not extended by later increments.
        await redis.expire(key, _seconds_until_month_end(now))

    if count > limit:
        # Roll the rejected attempt back so it does not consume quota.
        await redis.decr(key)
        return FreeCounterResult(allowed=False, count=limit, limit=limit)

    return FreeCounterResult(allowed=True, count=count, limit=limit)


__all__ = ["FREE_TIER_MONTHLY_LIMIT", "FreeCounterResult", "check_and_increment"]
