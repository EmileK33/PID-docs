"""Redis client helper for the integration harness."""

import redis


def make_redis_client(redis_url: str) -> "redis.Redis":
    """Build a Redis client from the harness REDIS_URL."""
    return redis.Redis.from_url(redis_url, decode_responses=True)
