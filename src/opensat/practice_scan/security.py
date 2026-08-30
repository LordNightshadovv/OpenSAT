"""Security gates for the user-authorized, read-only practice scanner.

The scanner treats every browser string as hostile input.  These helpers never
return matched page text; callers receive only stable reason codes so a page
cannot smuggle its own instructions into logs, previews, or tool errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlparse


class ScanBlocked(ValueError):
    """Raised when a scan must stop before reading or persisting page data."""

    def __init__(self, code: str, *, reasons: tuple[str, ...] = ()) -> None:
        self.code = code
        self.reasons = reasons or (code,)
        super().__init__(f"Chrome practice scan blocked: {code}")


class ScopeViolation(ScanBlocked):
    """Raised when a page is outside the user-approved read-only scope."""


class CursorError(ValueError):
    """Raised for a malformed, stale, or mismatched resumable cursor."""


class ConfirmationRequired(ValueError):
    """Raised when derived data has not received explicit user confirmation."""


@dataclass(frozen=True)
class PromptInspection:
    """Page-safety result containing codes only, never a text excerpt."""

    safe: bool
    reasons: tuple[str, ...] = ()


_PROMPT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|override|forget|bypass)\b.{0,100}\b(?:previous|prior|system|developer|assistant|instructions?|rules?|policy)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "model_directive",
        re.compile(
            r"\b(?:system|developer|assistant)\s+(?:prompt|message|instruction)\b|\bprompt\s+injection\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential_request",
        re.compile(
            r"\b(?:reveal|show|send|enter|share|provide|copy|paste|save)\b.{0,100}\b(?:password|passcode|cookie|token|api\s*key|secret|credential|verification\s*code)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "tool_action_request",
        re.compile(
            r"\b(?:click|submit|navigate|open|visit|download|upload|change|modify)\b.{0,100}\b(?:account|settings?|profile|payment|external|another\s+(?:site|domain)|form)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "scope_expansion",
        re.compile(
            r"\b(?:leave|go\s+outside|expand|broaden|change)\b.{0,100}\b(?:approved|allowed|college\s*board|domain|scope|page)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "active_test_detected",
        re.compile(
            r"\b(?:active|live|current)\s+(?:SAT|test|exam|assessment)\b|\bdo\s+not\s+leave\s+this\s+test\b|\btesting\s+session\b",
            re.IGNORECASE,
        ),
    ),
)

_URL_SECRET_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "accesstoken",
    "refreshtoken",
    "apikey",
    "api_key",
    "cookie",
    "auth",
    "authorization",
    "code",
    "session",
}


def inspect_untrusted_page(*, title: str, visible_text: str) -> PromptInspection:
    """Return safety codes for untrusted page text without exposing matches."""

    haystack = f"{title}\n{visible_text}"
    reasons = tuple(code for code, pattern in _PROMPT_PATTERNS if pattern.search(haystack))
    return PromptInspection(safe=not reasons, reasons=reasons)


def ensure_no_credential_bearing_url(url: str) -> None:
    """Reject URLs containing common credential or session query parameters."""

    parsed = urlparse(url)
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if re.sub(r"[^a-z0-9_]", "", key.lower()) in _URL_SECRET_KEYS:
            raise ScanBlocked("credential_exposure_detected")


def raise_for_unsafe_page(*, title: str, visible_text: str) -> None:
    """Stop on prompt injection, credential requests, scope changes, or live tests."""

    inspection = inspect_untrusted_page(title=title, visible_text=visible_text)
    if not inspection.safe:
        raise ScanBlocked("untrusted_page_instruction", reasons=inspection.reasons)
