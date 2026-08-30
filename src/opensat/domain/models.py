"""Small immutable models shared by the scheduling and service layers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Activity:
    activity_type: str
    minutes: int
    purpose: str
    success_criterion: str
    exit_condition: str


@dataclass(frozen=True)
class DailySessionPlan:
    band: str
    planned_minutes: int
    activities: tuple[Activity, ...]
    rationale: str

    def as_dict(self) -> dict:
        return {
            "band": self.band,
            "planned_minutes": self.planned_minutes,
            "activities": [activity.__dict__ for activity in self.activities],
            "rationale": self.rationale,
        }
