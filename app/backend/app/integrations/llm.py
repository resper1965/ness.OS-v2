# LLM client: OpenAI-compatible chat completions (OpenRouter by default).
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()


class LLMNotConfigured(httpx.HTTPError):
    """No API key: callers already fall back on httpx.HTTPError."""


class LLMBadResponse(httpx.HTTPError):
    """Unusable 200 body (non-JSON, no choices, null content)."""


def _json_schema(node: Any) -> Any:
    """Gemini schema (OBJECT/STRING/...) -> strict JSON Schema."""
    if isinstance(node, list):
        return [_json_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {k: _json_schema(v) for k, v in node.items()}
    if isinstance(out.get("type"), str):
        out["type"] = out["type"].lower()
    if out.get("type") == "object":
        out["additionalProperties"] = False
        out["required"] = list(out.get("properties", {}))  # strict: all required
    return out


def _request(system, user, json_schema, temperature, max_tokens):
    if not settings.llm_api_key:
        raise LLMNotConfigured("llm_api_key not configured")
    body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": {"data_collection": "deny"},
    }
    if json_schema:
        # else OpenRouter treats response_format as a soft hint
        body["provider"]["require_parameters"] = True
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "strict": True,
                "schema": _json_schema(json_schema),
            },
        }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "HTTP-Referer": "https://hub.ness.com.br",
        "X-Title": "ness.OS",
    }
    return f"{settings.llm_base_url.rstrip('/')}/chat/completions", body, headers


def _parse(response: httpx.Response) -> tuple[str, dict[str, Any]]:
    response.raise_for_status()
    try:
        result = response.json()
        text = ((result.get("choices") or [{}])[0].get("message") or {}).get("content")
    except (ValueError, AttributeError) as exc:
        raise LLMBadResponse("invalid LLM response body") from exc
    if not text:  # 200 with {"error":...}, empty choices or null content
        raise LLMBadResponse("empty LLM completion")
    return text, result.get("usage") or {}


def chat_completion(
    system, user, *, json_schema=None, temperature=0.2, max_tokens=2048, timeout=None
) -> tuple[str, dict[str, Any]]:
    url, body, headers = _request(system, user, json_schema, temperature, max_tokens)
    with httpx.Client(timeout=timeout) as client:
        return _parse(client.post(url, json=body, headers=headers))


async def achat_completion(
    system, user, *, json_schema=None, temperature=0.2, max_tokens=2048, timeout=None
) -> tuple[str, dict[str, Any]]:
    url, body, headers = _request(system, user, json_schema, temperature, max_tokens)
    async with httpx.AsyncClient(timeout=timeout) as client:
        return _parse(await client.post(url, json=body, headers=headers))
