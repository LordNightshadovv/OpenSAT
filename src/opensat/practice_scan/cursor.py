"""Opaque, content-free cursors for resumable practice scans."""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from dataclasses import dataclass

from .security import CursorError


_PREFIX = "opensat1."


@dataclass(frozen=True)
class ScanCursor:
    """A resume token containing only import identity and progress counters.

    The database stores the exact current token.  A caller must present that
    exact value, so editing or replaying an older token fails even though the
    token is intentionally not a bearer credential and contains no page text.
    """

    import_id: str
    next_page_index: int
    observation_count: int
    nonce: str

    @classmethod
    def new(cls, *, import_id: str, next_page_index: int, observation_count: int) -> "ScanCursor":
        if not import_id or not 0 <= next_page_index <= 100 or not 0 <= observation_count <= 10_000:
            raise CursorError("cursor_progress_invalid")
        return cls(import_id, next_page_index, observation_count, secrets.token_urlsafe(18))

    def encode(self) -> str:
        payload = {
            "v": 1,
            "i": self.import_id,
            "p": self.next_page_index,
            "n": self.observation_count,
            "r": self.nonce,
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return _PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def decode(cls, value: str) -> "ScanCursor":
        if not isinstance(value, str) or not value.startswith(_PREFIX):
            raise CursorError("cursor_format_invalid")
        encoded = value[len(_PREFIX) :]
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error):
            raise CursorError("cursor_format_invalid") from None
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise CursorError("cursor_version_invalid")
        import_id = payload.get("i")
        nonce = payload.get("r")
        next_page_index = payload.get("p")
        observation_count = payload.get("n")
        if (
            not isinstance(import_id, str)
            or not import_id
            or not isinstance(nonce, str)
            or len(nonce) < 16
            or not isinstance(next_page_index, int)
            or isinstance(next_page_index, bool)
            or not 0 <= next_page_index <= 100
            or not isinstance(observation_count, int)
            or isinstance(observation_count, bool)
            or not 0 <= observation_count <= 10_000
        ):
            raise CursorError("cursor_payload_invalid")
        return cls(import_id, next_page_index, observation_count, nonce)
