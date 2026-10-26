"""Fail-closed asynchronous transactional email transport for the ness.OS Hub."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("nessops.integrations.email")

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EmailDeliveryError(RuntimeError):
    """Raised when Resend does not accept a transactional email."""


class EmailDisabledError(EmailDeliveryError):
    """Raised when a caller tries to send while the runtime gate is closed."""


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    email_id: str
    attempts: int


@dataclass(slots=True)
class EmailDeliveryMetrics:
    requested: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    blocked: int = 0


class ResendEmailClient:
    """Small Resend API adapter with retries and provider idempotency."""

    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str,
        sender: str,
        api_url: str = "https://api.resend.com",
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        metrics: EmailDeliveryMetrics | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")

        self.enabled = enabled
        self.api_key = api_key.strip()
        self.sender = sender.strip()
        self.api_url = api_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_attempts = max_attempts
        self.transport = transport
        self.metrics = metrics or EmailDeliveryMetrics()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ResendEmailClient:
        current = settings or get_settings()
        return cls(
            enabled=current.transactional_email_enabled,
            api_key=current.resend_api_key,
            sender=current.transactional_email_from,
            api_url=current.resend_api_url,
            timeout_seconds=current.email_timeout_seconds,
            max_attempts=current.email_max_attempts,
        )

    async def send(
        self,
        *,
        to: list[str],
        subject: str,
        idempotency_key: str,
        html: str | None = None,
        text: str | None = None,
    ) -> EmailDeliveryResult:
        """Send one message without logging recipients, subjects, or content."""
        self.metrics.requested += 1
        self._validate_message(to, subject, idempotency_key, html, text)

        if not self.enabled:
            self.metrics.blocked += 1
            raise EmailDisabledError("transactional email is disabled")
        if not self.api_key or not self.sender:
            self.metrics.failed += 1
            raise EmailDeliveryError("transactional email runtime is incomplete")

        payload: dict[str, object] = {
            "from": self.sender,
            "to": to,
            "subject": subject,
        }
        if html is not None:
            payload["html"] = html
        if text is not None:
            payload["text"] = text

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        correlation = hashlib.sha256(idempotency_key.encode()).hexdigest()[:12]

        async with httpx.AsyncClient(
            base_url=self.api_url,
            timeout=self.timeout,
            transport=self.transport,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await client.post(
                        "/emails", json=payload, headers=headers
                    )
                    if response.is_success:
                        email_id = response.json().get("id", "")
                        if not isinstance(email_id, str) or not email_id:
                            self.metrics.failed += 1
                            raise EmailDeliveryError(
                                "Resend success response did not include an email id"
                            )
                        self.metrics.succeeded += 1
                        logger.info(
                            "Transactional email accepted | correlation=%s attempts=%d",
                            correlation,
                            attempt,
                        )
                        return EmailDeliveryResult(email_id=email_id, attempts=attempt)

                    if response.status_code not in _RETRYABLE_STATUS_CODES:
                        self.metrics.failed += 1
                        raise EmailDeliveryError(
                            "Resend rejected the request with status "
                            f"{response.status_code}"
                        )

                    retry_after = response.headers.get("Retry-After")
                except httpx.TransportError as exc:
                    retry_after = None
                    if attempt == self.max_attempts:
                        self.metrics.failed += 1
                        raise EmailDeliveryError(
                            "Resend transport failed after all attempts"
                        ) from exc

                if attempt == self.max_attempts:
                    self.metrics.failed += 1
                    raise EmailDeliveryError(
                        "Resend did not accept the request after all attempts"
                    )

                self.metrics.retried += 1
                delay = self._retry_delay(attempt, retry_after)
                logger.warning(
                    "Retrying transactional email | correlation=%s attempt=%d",
                    correlation,
                    attempt + 1,
                )
                await asyncio.sleep(delay)

        raise AssertionError("unreachable")

    @staticmethod
    def _validate_message(
        to: list[str],
        subject: str,
        idempotency_key: str,
        html: str | None,
        text: str | None,
    ) -> None:
        if not to or any(not address.strip() for address in to):
            raise ValueError("at least one recipient is required")
        if not subject.strip():
            raise ValueError("subject is required")
        if not html and not text:
            raise ValueError("html or text content is required")
        if not idempotency_key or len(idempotency_key) > 256:
            raise ValueError("idempotency_key must contain 1 to 256 characters")

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                pass
        return min(float(2 ** (attempt - 1)), 30.0)
