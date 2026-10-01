"""In-cluster inference: the preconfigured E5 and ELSER endpoints.

Elasticsearch 8.16+ ships inference endpoints that download and deploy their
model on first use. That takes from seconds to minutes (a first request may
answer 408 "waiting for trained model deployment"), so `warm()` sends a tiny
request until the endpoint answers, before any bulk load or query needs it.
"""

from __future__ import annotations

import time
from typing import Callable

from search.connection import Client, EsError

E5 = ".multilingual-e5-small-elasticsearch"  # text_embedding, 384 dims, multilingual
ELSER = ".elser-2-elasticsearch"  # sparse_embedding, English
E5_DIMS = 384
TASKS = {E5: "text_embedding", ELSER: "sparse_embedding"}


class InferenceNotReady(RuntimeError):
    """An inference endpoint did not answer within the warm-up timeout."""


def warm(
    client: Client,
    endpoint: str,
    timeout: float = 900,
    interval: float = 10,
    progress: Callable[[str], None] = print,
) -> float:
    """Wait until `endpoint` answers an inference request; returns the seconds it took."""
    started = time.monotonic()
    last = ""
    while True:
        try:
            client.post(
                f"/_inference/{TASKS[endpoint]}/{endpoint}",
                {"input": ["warm up"]},
                timeout=120,
            )
            return time.monotonic() - started
        except EsError as exc:
            if exc.status == 404:
                raise InferenceNotReady(
                    f"inference endpoint {endpoint} does not exist on this cluster"
                ) from exc
            last = exc.describe()
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            raise InferenceNotReady(
                f"{endpoint} not ready after {elapsed:.0f}s: {last}"
            )
        progress(
            f"Waiting for {endpoint} (model download/deployment, {elapsed:.0f}s): {last[:120]}"
        )
        time.sleep(interval)


def e5_pipeline(input_field: str, output_field: str) -> dict:
    """Ingest pipeline that embeds `input_field` into `output_field` with E5."""
    return {
        "description": f"E5 embeddings of {input_field} ({E5})",
        "processors": [
            {
                "inference": {
                    "model_id": E5,
                    "input_output": {
                        "input_field": input_field,
                        "output_field": output_field,
                    },
                }
            },
            # The inference processor also records the model id in every document.
            {"remove": {"field": "model_id", "ignore_missing": True}},
        ],
    }
