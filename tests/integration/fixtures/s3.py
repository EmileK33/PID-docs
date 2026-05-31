"""S3 (MinIO) client helper for the integration harness.

MinIO is S3-API compatible. Path-style addressing + s3v4 signing is required
for the local endpoint (no DNS-based virtual-hosted buckets).
"""

import boto3
from botocore.client import Config


def make_s3_client(*, endpoint_url: str, region_name: str, access_key: str, secret_key: str):
    """Build a boto3 S3 client pointed at the MinIO fixture."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
