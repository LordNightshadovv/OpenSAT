"""Pure functions for representing a short mistake autopsy."""

from __future__ import annotations

from typing import Any

from .taxonomy import minimal_autopsy_prompts


def build_autopsy(event: dict[str, Any]) -> dict[str, Any]:
    prompts = minimal_autopsy_prompts(
        result=event.get("result", "incorrect"),
        confidence=event.get("confidence"),
        time_seconds=event.get("time_seconds"),
        answer_changed=bool(event.get("answer_changed")),
    )
    return {
        "event_id": event.get("event_id"),
        "observed_fact": {
            "result": event.get("result"),
            "provisional_skill": event.get("provisional_skill"),
            "time_seconds": event.get("time_seconds"),
            "confidence": event.get("confidence"),
        },
        "prompts": prompts,
        "diagnostic_ceiling": "provisional until recurring evidence supports a pattern",
    }
