# ClamAV malware-scanning sidecar for the ingest worker (§1.8).
# Based on the official clamav image; bundles freshclam for signature updates.
FROM clamav/clamav:1.3

# Refresh virus definitions at build time so a fresh container can scan
# immediately (freshclam also runs on a schedule inside the official image).
# Failure to reach the mirror at build time is non-fatal; the daemon refreshes
# on first start.
RUN freshclam --quiet || true

# clamd listens on 3310 (TCP). The ingest worker connects over this socket.
EXPOSE 3310
