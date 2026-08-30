"""Typed boundary objects for read-only Chrome observations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ..domain.constants import QUESTION_RESULTS
from ..privacy.redaction import ensure_safe_metadata
from .security import ScopeViolation, ensure_no_credential_bearing_url


_ALLOWED_AUTH_KEYS = {
    "approved_hosts",
    "approved_path_prefixes",
    "user_confirmed",
    "source",
    "active_test",
    "max_pages",
    "bridge_name",
}
_ALLOWED_PAGE_KEYS = {
    "url",
    "title",
    "visible_text",
    "attempt",
    "questions",
    "page_index",
    "has_more",
}
_HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


def _bounded_string(value: Any, field_name: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    value = value.strip()
    if not value or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field_name} is invalid")
    return value


def _normalize_host(value: Any) -> str:
    host = _bounded_string(value, "approved host", maximum=253).lower().rstrip(".")
    if "://" in host or "/" in host or not _HOST_RE.fullmatch(host):
        raise ValueError("approved hosts must be bare DNS hostnames")
    if host != "collegeboard.org" and not host.endswith(".collegeboard.org"):
        raise ValueError("approved hosts must be College Board domains")
    return host


def _normalize_path_prefix(value: Any) -> str:
    prefix = _bounded_string(value, "approved path prefix", maximum=300)
    if not prefix.startswith("/") or ".." in prefix or "?" in prefix or "#" in prefix:
        raise ValueError("approved path prefixes must be absolute, query-free paths")
    return prefix.rstrip("/") or "/"


@dataclass(frozen=True)
class ChromeScanAuthorization:
    """Explicit user permission for a narrow, read-only Chrome inspection."""

    approved_hosts: tuple[str, ...]
    approved_path_prefixes: tuple[str, ...]
    user_confirmed: bool
    source: str = "college-board"
    active_test: bool = False
    max_pages: int = 25
    bridge_name: str = "chrome-read-only"

    @classmethod
    def from_value(cls, value: "ChromeScanAuthorization | dict[str, Any]") -> "ChromeScanAuthorization":
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("authorization must be an object")
        ensure_safe_metadata(value)
        unknown = set(value) - _ALLOWED_AUTH_KEYS
        if unknown:
            raise ValueError("authorization contains unsupported fields")
        hosts = tuple(dict.fromkeys(_normalize_host(item) for item in value.get("approved_hosts", [])))
        prefixes = tuple(dict.fromkeys(_normalize_path_prefix(item) for item in value.get("approved_path_prefixes", [])))
        if not hosts or not prefixes:
            raise ValueError("authorization must name approved hosts and paths")
        source = value.get("source", "college-board")
        if source not in {"college-board", "bluebook"}:
            raise ValueError("authorization source must be college-board or bluebook")
        max_pages = value.get("max_pages", 25)
        if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        bridge_name = _bounded_string(value.get("bridge_name", "chrome-read-only"), "bridge_name", maximum=80)
        return cls(
            approved_hosts=hosts,
            approved_path_prefixes=prefixes,
            user_confirmed=value.get("user_confirmed") is True,
            source=source,
            active_test=value.get("active_test") is True,
            max_pages=max_pages,
            bridge_name=bridge_name,
        )

    def require_user_confirmation(self) -> None:
        if not self.user_confirmed:
            raise ValueError("explicit user authorization is required before Chrome inspection")
        if self.active_test:
            raise ScopeViolation("active_test_detected")

    def validate_url(self, url: str) -> str:
        url = _bounded_string(url, "page url", maximum=2048)
        parsed = urlparse(url)
        ensure_no_credential_bearing_url(url)
        if parsed.username is not None or parsed.password is not None:
            raise ScopeViolation("credential_exposure_detected")
        host = (parsed.hostname or "").lower().rstrip(".")
        path = parsed.path or "/"
        if parsed.scheme != "https" or not host:
            raise ScopeViolation("https_college_board_page_required")
        if not any(host == approved or host.endswith(f".{approved}") for approved in self.approved_hosts):
            raise ScopeViolation("domain_not_user_approved")
        if not any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.approved_path_prefixes):
            raise ScopeViolation("path_not_user_approved")
        return host


@dataclass
class ChromePageSnapshot:
    """Transient data supplied by a user-authorized Chrome bridge.

    The adapter copies only the structured fields it needs.  ``discard`` is
    called in every scan path and clears this object so page text is not kept
    after the observation boundary returns.
    """

    url: str
    title: str = ""
    visible_text: str = ""
    attempt: dict[str, Any] = field(default_factory=dict)
    questions: list[dict[str, Any]] = field(default_factory=list)
    page_index: int = 0
    has_more: bool = False
    discarded: bool = False

    @classmethod
    def from_value(cls, value: "ChromePageSnapshot | dict[str, Any]") -> "ChromePageSnapshot":
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise ValueError("page snapshot must be an object")
        ensure_safe_metadata(value)
        unknown = set(value) - _ALLOWED_PAGE_KEYS
        if unknown:
            raise ValueError("page snapshot contains unsupported fields")
        url = _bounded_string(value.get("url"), "page url", maximum=2048)
        title = value.get("title", "")
        visible_text = value.get("visible_text", "")
        if not isinstance(title, str) or not isinstance(visible_text, str):
            raise ValueError("page title and visible_text must be strings")
        if len(title) > 4000 or len(visible_text) > 300_000:
            raise ValueError("transient page text exceeds the safety limit")
        attempt = value.get("attempt", {})
        questions = value.get("questions", [])
        if not isinstance(attempt, dict) or not isinstance(questions, list):
            raise ValueError("attempt must be an object and questions must be an array")
        if len(questions) > 200:
            raise ValueError("a page may contain at most 200 question observations")
        if not all(isinstance(item, dict) for item in questions):
            raise ValueError("question observations must be objects")
        page_index = value.get("page_index", 0)
        if not isinstance(page_index, int) or isinstance(page_index, bool) or not 0 <= page_index <= 100:
            raise ValueError("page_index must be between 0 and 100")
        has_more = value.get("has_more", False)
        if not isinstance(has_more, bool):
            raise ValueError("has_more must be boolean")
        return cls(
            url=url,
            title=title,
            visible_text=visible_text,
            attempt=dict(attempt),
            questions=[dict(item) for item in questions],
            page_index=page_index,
            has_more=has_more,
        )

    def discard(self) -> None:
        """Clear transient page text and structured page material in place."""

        self.url = ""
        self.title = ""
        self.visible_text = ""
        self.attempt.clear()
        for question in self.questions:
            question.clear()
        self.questions.clear()
        self.page_index = 0
        self.has_more = False
        self.discarded = True


def validate_result(value: Any) -> str:
    result = _bounded_string(value, "result", maximum=32)
    if result not in QUESTION_RESULTS:
        raise ValueError(f"result must be one of {QUESTION_RESULTS}")
    return result


def validate_identifier(value: Any, field_name: str) -> str:
    value = _bounded_string(value, field_name, maximum=200)
    if not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field_name} contains unsupported characters")
    return value
