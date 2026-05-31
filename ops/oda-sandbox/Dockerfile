# ODA File Converter sandbox — isolated DWG-to-raster/PDF conversion.
#
# SECURITY POSTURE (§1.8 — runtime enforcement is infra-time, documented here):
#   * NO NETWORK EGRESS AT RUNTIME — enforced by the ECS task definition
#     `networkMode: none` in production (and `--network none` for local
#     `docker run`). The converter must never make outbound connections.
#   * READ-ONLY ROOT FILESYSTEM AT RUNTIME — enforced by
#     `readOnlyRootFilesystem: true` in the ECS task definition. The only
#     writable path is the bind-mounted/tmpfs work directory below.
#   * NON-ROOT — the container runs as USER 1000:1000 (declared below).
#
# This Dockerfile establishes the image; the no-egress and read-only guarantees
# are applied by the orchestrator at run time, not bakeable into the image.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Minimal runtime libraries the ODA File Converter needs (headless Qt/X libs).
# The proprietary, license-restricted ODAFileConverter binary is injected at
# deploy time (it cannot be redistributed in this image) into /opt/oda.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglu1-mesa libxrender1 libxi6 libsm6 libxext6 fontconfig \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/oda /work \
    && chown -R 1000:1000 /work

# Dedicated unprivileged user. No shell login, no home writes needed.
RUN useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin odauser

# Writable scratch space; the rest of the filesystem is read-only at runtime.
VOLUME ["/work"]
WORKDIR /work

# NON-ROOT runtime (defence in depth — also enforced by the task definition).
USER 1000:1000

# Entry command is supplied by the ingest worker at invocation time. The image
# itself runs nothing privileged.
CMD ["/usr/sbin/nologin"]
