"""Arize AX tracing. Every branch is a span tree: branch -> LLM turns + shell tool calls -> evals.

If ARIZE_SPACE_ID / ARIZE_API_KEY are missing, tracing is a no-op and the app still runs.
"""

import os

from opentelemetry import trace

PROJECT = os.environ.get("ARIZE_PROJECT_NAME", "ctrlz")
_enabled = False


def setup() -> bool:
    global _enabled
    space_id = os.environ.get("ARIZE_SPACE_ID")
    api_key = os.environ.get("ARIZE_API_KEY") or os.environ.get("ARIZE_AI_API_KEY")
    if not (space_id and api_key):
        print("[ctrlz] Arize tracing disabled: set ARIZE_SPACE_ID and ARIZE_API_KEY")
        return False
    from arize.otel import register
    from openinference.instrumentation.openai import OpenAIInstrumentor

    tp = register(space_id=space_id, api_key=api_key, project_name=PROJECT, verbose=False)
    OpenAIInstrumentor().instrument(tracer_provider=tp)
    _enabled = True
    print(f"[ctrlz] Arize tracing on, project '{PROJECT}'")
    return True


def enabled() -> bool:
    return _enabled


def tracer():
    return trace.get_tracer("ctrlz")
