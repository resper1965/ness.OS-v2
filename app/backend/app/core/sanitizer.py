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
from typing import Final

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
    # Passwords em key=value ou key:value
    (
        re.compile(
            r"(?i)(password|passwd|pwd|pass|db_pass|db_password)"
            r"\s*[=:]\s*\S+",
        ),
        r"\1=[REDACTED]",
    ),
    # API keys, tokens, secrets em key=value
    (
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token"
            r"|bearer[_-]?token|client[_-]?secret|private[_-]?key)"
            r"\s*[=:]\s*\S+",
        ),
        r"\1=[REDACTED]",
    ),
    # Bearer tokens em headers
    (
        re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-/+=]{8,}"),
        "Bearer [REDACTED]",
    ),
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
    sensitive_keys = {"password", "passwd", "pwd", "secret", "api_key", "token", "private_key"}
    result: dict = {}
    for key, value in data.items():
        is_sensitive = any(sk in key.lower() for sk in sensitive_keys)

        if isinstance(value, str):
            if is_sensitive:
                result[key] = "[REDACTED]"
            else:
                result[key] = sanitize(value)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            if is_sensitive:
                result[key] = ["[REDACTED]" if isinstance(v, str) else v for v in value]
            else:
                result[key] = [
                    sanitize(v) if isinstance(v, str) else v for v in value
                ]
        else:
            if is_sensitive and value is not None:
                result[key] = "[REDACTED]"
            else:
                result[key] = value
    return result
