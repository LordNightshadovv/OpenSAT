"""Reject secrets and copyrighted page captures at the persistence boundary."""

from __future__ import annotations

import json
import re
from typing import Any

from ..domain.constants import FORBIDDEN_KEYS


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def ensure_safe_metadata(value: Any, path: str = "payload") -> None:
    """Raise before persistence if a payload contains a prohibited field."""
    if isinstance(value, dict):
        forbidden = {_normalized_key(item) for item in FORBIDDEN_KEYS}
        for key, child in value.items():
            normalized = _normalized_key(str(key))
            if normalized in forbidden:
                raise ValueError(f"Prohibited field at {path}.{key}; store only derived metadata")
            ensure_safe_metadata(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            ensure_safe_metadata(child, f"{path}[{index}]")
    elif isinstance(value, (str, int, float, bool)) or value is None:
        return
    else:
        raise TypeError(f"Unsupported value at {path}: {type(value).__name__}")


def dumps_safe(value: Any) -> str:
    ensure_safe_metadata(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def load_json_object(raw: str, label: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    ensure_safe_metadata(value, label)
    return value
