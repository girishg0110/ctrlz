"""LLM access through Fireworks AI's OpenAI-compatible endpoint."""

import os

from openai import OpenAI

BASE_URL = os.environ.get("CTRLZ_LLM_BASE_URL", "https://api.fireworks.ai/inference/v1")
AGENT_MODEL = os.environ.get("CTRLZ_MODEL", "accounts/fireworks/routers/kimi-k3-fast")
JUDGE_MODEL = os.environ.get("CTRLZ_JUDGE_MODEL", AGENT_MODEL)


def client() -> OpenAI:
    key = os.environ.get("FIREWORKS_AI_API_KEY") or os.environ.get("FIREWORKS_API_KEY")
    if not key:
        raise RuntimeError("set FIREWORKS_AI_API_KEY (or run with CTRLZ_AGENT=scripted)")
    return OpenAI(base_url=BASE_URL, api_key=key, timeout=180, max_retries=2)


def short(model: str) -> str:
    return model.rsplit("/", 1)[-1]
