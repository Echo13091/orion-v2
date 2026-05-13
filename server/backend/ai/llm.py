from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")

EDGE_MODE = os.getenv("ORION_EDGE_MODE", "1").strip().lower() in {"1", "true", "yes", "on"}
LLM_ENABLED = os.getenv("ORION_LLM_ENABLED", "0" if EDGE_MODE else "1").strip().lower() in {"1", "true", "yes", "on"}
CODE_LLM_ENABLED = os.getenv("ORION_CODE_LLM_ENABLED", "0" if EDGE_MODE else "1").strip().lower() in {"1", "true", "yes", "on"}

MODELS = {
    # TinyLlama is the lowest-friction RPi-friendly default. Override with
    # ORION_MODEL_DEFAULT=phi3:mini if your Pi/mini-PC has enough RAM.
    "default": os.getenv("ORION_MODEL_DEFAULT", "mistral"),
    "code": os.getenv("ORION_MODEL_CODE", "deepseek-coder:6.7b"),
}

DEFAULT_TIMEOUT_SECONDS = float(os.getenv("ORION_LLM_TIMEOUT_SECONDS", "60"))
DEFAULT_NUM_PREDICT = int(os.getenv("ORION_LLM_NUM_PREDICT", "180"))
DEFAULT_NUM_CTX = int(os.getenv("ORION_LLM_NUM_CTX", "1024"))


def _model_enabled(mode: str) -> bool:
    if mode == "code":
        return CODE_LLM_ENABLED
    return LLM_ENABLED


def _fallback_response(prompt: str | None, mode: str = "default") -> str:
    if mode == "code":
        return (
            "Code model is disabled in Orion edge mode. Enable it with "
            "ORION_CODE_LLM_ENABLED=1 when you need local coding help."
        )

    return (
        "Orion is running in edge mode, so general LLM chat is disabled. "
        "I can still answer live home-system questions, explain weather, summarize "
        "sprinkler/thermostat state, and run safe device commands using fast rules. "
        "Enable ORION_LLM_ENABLED=1 for optional free-form chat."
    )


def _options() -> dict[str, Any]:
    return {
        "temperature": 0.1,
        "num_ctx": DEFAULT_NUM_CTX,
        "num_predict": DEFAULT_NUM_PREDICT,
        # Ollama ignores unsupported options on many builds/models; keep this low.
        "num_gpu": int(os.getenv("ORION_LLM_NUM_GPU", "1" if EDGE_MODE else "1")),
    }


# -------------------------
# STANDARD BLOCKING
# -------------------------
def run_llm(prompt: str, mode: str = "default") -> str:
    if not _model_enabled(mode):
        return _fallback_response(prompt, mode)

    model = MODELS.get(mode, MODELS["default"])

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": _options(),
            },
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return f"ERROR: HTTP {response.status_code} - {response.text[:500]}"

        data = response.json()
        return str(data.get("response", "")).strip()

    except requests.exceptions.Timeout:
        return "ERROR: Model timed out"

    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama not running"

    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


# -------------------------
# STREAMING
# -------------------------
def stream_llm(prompt: str, mode: str = "default") -> Iterator[str]:
    if not _model_enabled(mode):
        yield _fallback_response(prompt, mode)
        return

    model = MODELS.get(mode, MODELS["default"])

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": _options(),
            },
            stream=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            yield f"ERROR: HTTP {response.status_code} - {response.text[:500]}"
            return

        for line in response.iter_lines():
            if not line:
                continue

            try:
                data = json.loads(line.decode("utf-8"))
            except Exception:
                continue

            if "response" in data:
                yield str(data["response"])

            if data.get("done"):
                break

    except Exception as exc:  # noqa: BLE001
        yield f"ERROR: {exc}"


# -------------------------
# WARM MODELS
# -------------------------
def warm_model(mode: str = "default") -> None:
    # Warming large models on a Raspberry Pi wastes boot time and memory.
    if not os.getenv("ORION_WARM_MODELS", "0").strip().lower() in {"1", "true", "yes", "on"}:
        print(f"[LLM] Warm skipped for {mode} (edge mode)")
        return

    if not _model_enabled(mode):
        print(f"[LLM] Warm skipped for {mode} (model disabled)")
        return

    model = MODELS.get(mode, MODELS["default"])

    try:
        requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": "hello",
                "stream": False,
                "options": {"num_predict": 8, "num_ctx": 256},
            },
            timeout=min(DEFAULT_TIMEOUT_SECONDS, 20),
        )
        print(f"[LLM] {model} warmed up")

    except Exception as exc:  # noqa: BLE001
        print(f"[LLM] Failed to warm {model}: {exc}")
