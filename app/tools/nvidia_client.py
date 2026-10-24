"""NVIDIA Nemotron client (OpenAI-style chat API), standard library only.

Settings (put them in .env, never in code):
  NVIDIA_API_KEY    key starting with nvapi-  (build.nvidia.com, or the organisers' credits)
  NVIDIA_MODEL      exact model name copied from build.nvidia.com (no default on purpose)
  NVIDIA_BASE_URL   default https://integrate.api.nvidia.com/v1 (any OpenAI-style gateway works, including a Meterless one)
"""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"


class NvidiaError(RuntimeError):
    pass


def available():
    return bool(os.environ.get("NVIDIA_API_KEY", "").strip() and os.environ.get("NVIDIA_MODEL", "").strip())


def chat(messages, model=None, temperature=0, max_tokens=400, timeout=60):
    """Send one chat request. Returns {text, model, tokens, prompt_tokens, completion_tokens, latency_s}."""
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        raise NvidiaError("NVIDIA_API_KEY is not set. Put it in .env (see .env.example).")
    model = model or os.environ.get("NVIDIA_MODEL", "").strip()
    if not model:
        raise NvidiaError("NVIDIA_MODEL is not set. Copy the exact model name from build.nvidia.com into .env.")
    base = os.environ.get("NVIDIA_BASE_URL", DEFAULT_BASE).rstrip("/")
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode()
    req = Request(base + "/chat/completions", data=body, method="POST",
                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        detail = e.read(300).decode(errors="replace")
        hint = {401: "The key was rejected: create a fresh key.", 403: "This key cannot use that model.",
                404: "Wrong model name or base URL.", 429: "Rate limit or credits used up: wait, or use a smaller model."}.get(e.code, "")
        raise NvidiaError(f"HTTP {e.code} from the model API. {hint} {detail}") from e
    except (URLError, OSError) as e:
        raise NvidiaError(f"Cannot reach {base}: {getattr(e, 'reason', e)}") from e
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise NvidiaError("Unexpected response shape from the model API.") from e
    u = data.get("usage") or {}
    return {"text": text, "model": data.get("model", model), "latency_s": round(time.time() - t0, 2),
            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"), "tokens": u.get("total_tokens")}
