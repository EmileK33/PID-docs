"""Ingest Worker package (S2-H).

The Celery-based Ingest Worker performs the pre-ML ingest pipeline for every
uploaded drawing (§1.4 rule 3, §1.11, §1.13 P0):

* post-storage SHA-256 re-verification (second security gate) +
  second blocklist check;
* magic-byte format detection (PDF / DWG);
* DWG→PDF conversion via the ODA File Converter running inside an isolated
  Docker sandbox (``ops/oda-sandbox/Dockerfile``);
* drawing state transitions (``Queued → Scanning``, ``Scanning → Scan_Failed``,
  ``Scanning → Failed``) with synchronous Redis pub/sub event publication;
* scan-job enqueue on the ``scan`` Celery queue.

The Celery task object is :data:`app.workers.ingest.tasks.ingest_task`. It is
imported lazily by consumers (S2-B) to keep this package import side-effect free.
"""
from __future__ import annotations
