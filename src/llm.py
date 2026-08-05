"""Client LLM toi thieu (stdlib, khong dependency ngoai).

Model duoc khai bao trong src/config.py theo yeu cau de bai:
Groq llama-3.1-8b-instant (8B parameters, thoa rang buoc <= 10B).
API key doc tu .env va KHONG duoc commit.
"""

import json
import time
import urllib.error
import urllib.request

from . import config

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

_ENV_CACHE: dict | None = None


def load_env() -> dict:
    """Doc .env thu cong de khong phu thuoc python-dotenv."""
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE

    env: dict[str, str] = {}
    env_path = config.ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    _ENV_CACHE = env
    return env


def api_key() -> str | None:
    import os

    return load_env().get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")


def is_available() -> bool:
    return bool(api_key())


class LLMError(RuntimeError):
    pass


def complete_json(system_prompt: str, user_prompt: str) -> tuple[dict, dict]:
    """Goi LLM va ep tra ve JSON. Tra (parsed_json, meta)."""
    key = api_key()
    if not key:
        raise LLMError("GROQ_API_KEY not configured")

    payload = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    body = json.dumps(payload).encode("utf-8")

    last_error = None
    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        request = urllib.request.Request(
            GROQ_ENDPOINT,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(
                request, timeout=config.LLM_TIMEOUT_S
            ) as response:
                raw = json.loads(response.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"]
            meta = {
                "model": raw.get("model", config.LLM_MODEL),
                "latency_s": round(time.time() - started, 3),
                "attempt": attempt,
                "usage": raw.get("usage", {}),
            }
            return json.loads(content), meta
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            last_error = exc
            if attempt < config.LLM_MAX_RETRIES:
                time.sleep(1.5 * attempt)  # backoff tuyen tinh cho rate limit

    raise LLMError(f"LLM call failed after {config.LLM_MAX_RETRIES} attempts: {last_error}")
