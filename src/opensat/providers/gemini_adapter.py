"""Future module-level Gemini adapter boundary; deliberately not live."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GeminiModuleRequest:
    module_goal: str
    score_band: str
    provider_label: str = "gemini-princeton-review-module"


class GeminiModuleProvider:
    """Stub that documents the module-level contract without making network calls."""

    live = False

    def request_module(self, request: GeminiModuleRequest) -> dict[str, Any]:
        return {
            "status": "deferred",
            "provider": request.provider_label,
            "scope": "module-level assessment or practice provider",
            "reason": "Live Gemini integration is intentionally deferred from the first local slice.",
        }
