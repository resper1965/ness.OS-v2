# -------------------------------------------------------
# NessOps — Sanitização de dados sensíveis (CISO-Mindset)
# -------------------------------------------------------
"""
Limpa PII, credenciais e tokens antes que qualquer string seja:
  1. Persistida no banco de vetores (pgvector).
  2. Enviada para a API do Gemini (RCA).
  3. Exibida no dashboard ou ChatOps.

Roda ANTES da serialização, nunca depois.
"""

from __future__ import annotations

import re
from typing import Any, Final

# --- Padrões compilados (uma vez, no import) ---

_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # IPs internos (RFC 1918) e qualquer IPv4
    (
        re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        "[IP_REDACTED]",
    ),
    # Connection strings (mysql://, postgres://, redis://, mongodb://, amqp://)
    (
        re.compile(
            r"(mysql|postgres(?:ql)?|redis|mongodb|amqp|mariadb)"
            r"(?:\+[a-zA-Z0-9_]+)?://[^\s\"'<>]+",
            re.IGNORECASE,
        ),
        "[CONN_STRING_REDACTED]",
    ),
    # Credenciais em URL (scheme://user:pass@host)
    (
        re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*)://[^\s/:@]+:[^\s/@]+@"),
        r"\1://[REDACTED]@",
    ),
    # Passwords em key=value ou key:value (inclui JSON: "password":"x")
    (
        re.compile(
            r"(?i)(?<![A-Za-z0-9])(password|passwd|pwd|pass|db_pass|db_password)"
            r"[\"']?\s*[=:]\s*[\"']?\S+",
        ),
        r"\1=[REDACTED]",
    ),
    # API keys, tokens, secrets em key=value (inclui JSON)
    (
        re.compile(
            r"(?i)(?<![A-Za-z0-9])(api[_-]?key|secret|token|private[_-]?key)"
            r"[\"']?\s*[=:]\s*[\"']?\S+",
        ),
        r"\1=[REDACTED]",
    ),
    # Bearer/Basic em headers
    (
        re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._\-/+=]{8,}"),
        r"\1 [REDACTED]",
    ),
    # Google API keys e JWTs
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "[GOOGLE_KEY_REDACTED]"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "[JWT_REDACTED]"),
    # AWS-style keys (AKIA...)
    (
        re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"),
        "[AWS_KEY_REDACTED]",
    ),
    # Hashes hexadecimais longos (possíveis tokens/secrets, >=32 chars)
    (
        re.compile(r"\b[0-9a-fA-F]{32,}\b"),
        "[HEX_TOKEN_REDACTED]",
    ),
]


def sanitize(text: str) -> str:
    """Aplica todos os padrões de sanitização sequencialmente.

    Args:
        text: String bruta (trigger description, log, etc.)

    Returns:
        String limpa com dados sensíveis mascarados.
    """
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_dict(data: dict) -> dict:
    """Sanitiza recursivamente todos os valores string de um dict, redigindo chaves sensíveis."""
    sensitive_keys = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "token",
        "private_key",
        "authorization",
        "cookie",
        "apikey",
    }
    result: dict = {}
    for key, value in data.items():
        normalized_key = key.lower().replace("-", "_")
        is_sensitive = any(sk in normalized_key for sk in sensitive_keys)
        result[key] = (
            "[REDACTED]"
            if is_sensitive and value is not None
            else sanitize_value(value)
        )
    return result


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, dict):
        return sanitize_dict(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value
