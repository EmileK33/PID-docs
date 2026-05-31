"""ML inference execution (US-011).

Runs the cached detection model over the downloaded drawing bytes and returns the
§1.1 :class:`MLInferenceResult`. This is the single seam the integration tests
patch (``mock_inference_engine`` / ``mock_inference_raises_once`` /
``mock_inference_always_raises``).

No ``user_id`` is read here — the result is keyed only by ``drawing_id`` (§1.4
rule 5: the worker never resolves ``user_id`` from anything but the job payload,
and inference has no business with it at all).

Scope note: the concrete detection engine (ONNX/torch runtime + page raster +
post-processing) is an external model artifact wired in at deploy time. S2-J owns
the *orchestration* — download, cache, run, atomic persist, state machine — so
this function delegates the actual prediction to the loaded model object via a
``predict`` interface. When the deployed artifact does not expose that interface
the call raises a clear error, which flows into the task's retry/``Failed`` path.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.schemas.contracts import MLInferenceResult

logger = logging.getLogger("pid.workers.ml.inference")


def run_inference(
    model: Any,
    file_bytes: bytes,
    drawing_id: str,
    page_range: Optional[tuple[int, int]] = None,
) -> MLInferenceResult:
    """Execute symbol + table detection over ``file_bytes``.

    Returns a fully-typed :class:`MLInferenceResult`. ``page_range`` (1-based,
    inclusive) is forwarded to the model so it can restrict the pages it rasters;
    the final authoritative page filter is applied again at persistence time
    (US-011 AC-5) so a model that ignores the hint cannot leak out-of-range rows.
    """
    logger.info(
        "Running ML inference for drawing %s (page_range=%s, model=%r)",
        drawing_id,
        page_range,
        getattr(model, "version", model),
    )

    predict = getattr(model, "predict", None)
    if not callable(predict):
        # The orchestration is complete; only the concrete model artifact is
        # pluggable. Surface a clear error so the task's retry/Failed path runs
        # rather than silently persisting an empty result.
        raise NotImplementedError(
            "Loaded ML model exposes no callable 'predict'; the detection engine "
            "artifact must be wired in at deploy time (S2-J owns orchestration only)."
        )

    result = predict(file_bytes, drawing_id=drawing_id, page_range=page_range)

    # Accept either a ready MLInferenceResult or a dict the model emitted.
    if isinstance(result, MLInferenceResult):
        return result
    return MLInferenceResult.model_validate(result)


__all__ = ["run_inference"]
