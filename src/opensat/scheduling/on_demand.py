"""Evidence-to-session recommendations for optional follow-up practice.

Daily Sprints are the planned routine.  These recommendations are a separate,
read-only layer that turns response evidence into a small, specific follow-up
blueprint without silently adding work to the daily budget.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from ..adaptation.difficulty import BAND_BASE_TIER


ACTIONABLE_RESULTS = {
    "incorrect",
    "omitted",
    "correct_uncertain",
    "correct_slow",
    "correct_changed",
}

RESULT_WEIGHT = {
    "incorrect": 5.0,
    "omitted": 5.0,
    "correct_uncertain": 4.0,
    "correct_changed": 3.5,
    "correct_slow": 3.0,
}


def _context(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("abstract_context")
    return value if isinstance(value, dict) else {}


def _skill(event: dict[str, Any]) -> str:
    return str(event.get("provisional_skill") or "unclassified_skill")


def _evidence(event: dict[str, Any]) -> dict[str, Any]:
    context = _context(event)
    silent_danger = (
        event.get("apparent_difficulty") == "routine"
        and event.get("result") in {"incorrect", "omitted"}
        and isinstance(event.get("confidence"), int)
        and event["confidence"] >= 4
    )
    return {
        "event_id": event.get("event_id"),
        "result": event.get("result"),
        "skill": event.get("provisional_skill"),
        "time_seconds": event.get("time_seconds"),
        "confidence": event.get("confidence"),
        "apparent_difficulty": event.get("apparent_difficulty"),
        "silent_danger": silent_danger,
        "answer_changed": bool(event.get("answer_changed")),
        "help_used": bool(context.get("help_used")),
        "intended_difficulty": context.get("intended_difficulty"),
        "provenance_type": event.get("provenance_type"),
        "assessment_source": event.get("assessment_source"),
        "assessment_taken_at": event.get("assessment_taken_at"),
    }


def _band_material_guidance(band: str, session_type: str) -> dict[str, Any]:
    difficulty = BAND_BASE_TIER.get(band, "medium")
    if band == "600-640":
        support = "Use an annotated worked example, explicit hints, then fade one support before a near-transfer item."
    elif band == "650-690":
        support = "Begin with retrieval, show a worked example only when needed, then use targeted practice and guided fading."
    elif band == "700-740":
        support = "Use contrastive distractors, interleaving, and changed surface forms; keep support brief."
    else:
        support = "Use hard items and precision-oriented distractors; add a lower-tier item only as an explicit calibration or scaffold."

    if session_type == "mistake_autopsy_worked_example":
        material = "One mechanism-matched worked example, followed by two targeted items and one near-transfer item."
    elif session_type == "timed_precision_and_retrieval":
        material = "A short timed precision cluster using the same skill in varied contexts, preceded by one retrieval prompt."
    elif session_type == "confidence_calibration_and_contrast":
        material = "Near-neighbor options where the learner predicts confidence, identifies the discriminating evidence, and revisits one fragile choice."
    else:
        material = "A delayed retrieval item followed by near or mid transfer selected from the review evidence."

    return {
        "difficulty_center": difficulty,
        "support_mode": support,
        "material_design": material,
        "simulated_content_rule": "Generated items must be labeled as simulated and must target the observed skill or provisional mechanism.",
    }


def _session_shape(session_type: str, *, recurrence: int) -> dict[str, Any]:
    if session_type == "mistake_autopsy_worked_example":
        activities = [
            {
                "activity_type": "retrieval_check",
                "minutes": 2,
                "purpose": "State what the question was asking and the evidence threshold before seeing help.",
                "success_criterion": "Name the task and one guardrail in the learner's own words.",
                "exit_condition": "Proceed after retrieval, or record the missing cue for the worked example.",
            },
            {
                "activity_type": "worked_example",
                "minutes": 4,
                "purpose": "Make the suspected mechanism and strongest distractor visible.",
                "success_criterion": "Explain why the correct option performs the requested task and why the strongest distractor does not.",
                "exit_condition": "Fade one annotation or hint before independent practice.",
            },
            {
                "activity_type": "targeted_practice",
                "minutes": 4,
                "purpose": "Practice the same mechanism in a changed but nearby context.",
                "success_criterion": "Meet the item-level evidence threshold without copying the example.",
                "exit_condition": "Stop after usable evidence is recorded, not after a fixed question count.",
            },
            {
                "activity_type": "transfer_check",
                "minutes": 3,
                "purpose": "Check near transfer before declaring the issue resolved.",
                "success_criterion": "Select and justify the answer on a changed surface form.",
                "exit_condition": "Escalate to another near scaffold if transfer fails.",
            },
        ]
        diagnostic_boundary = "The response supports a mechanism hypothesis; it is not a confirmed recurring signature until recurrence is established."
    elif session_type == "timed_precision_and_retrieval":
        activities = [
            {
                "activity_type": "retrieval_check",
                "minutes": 2,
                "purpose": "Recover the decision rule before timed work.",
                "success_criterion": "State the rule and the condition that makes the item slow or fragile.",
                "exit_condition": "Start timed practice after the rule is stated or the gap is recorded.",
            },
            {
                "activity_type": "timed_precision_cluster",
                "minutes": 7,
                "purpose": "Test whether the skill can be executed efficiently without lowering the evidence threshold.",
                "success_criterion": "Maintain accuracy while recording time and confidence on each item.",
                "exit_condition": "Stop at the planned time and preserve slow-correct evidence.",
            },
            {
                "activity_type": "near_miss_review",
                "minutes": 3,
                "purpose": "Inspect slow, uncertain, or changed responses rather than treating them as clean mastery.",
                "success_criterion": "Name one guardrail that would reduce decision time without encouraging rushing.",
                "exit_condition": "Finish with a concrete next transfer condition.",
            },
        ]
        diagnostic_boundary = "Slow or fragile correctness is evidence for a precision intervention, not proof of a content weakness."
    elif session_type == "confidence_calibration_and_contrast":
        activities = [
            {
                "activity_type": "calibration_check",
                "minutes": 2,
                "purpose": "Predict confidence and identify the evidence needed before committing.",
                "success_criterion": "State the evidence threshold before answer reveal.",
                "exit_condition": "Continue after the prediction is recorded.",
            },
            {
                "activity_type": "interleaved_practice",
                "minutes": 6,
                "purpose": "Compare near-neighbor options or methods and make the discriminating feature explicit.",
                "success_criterion": "Reject the attractive distractor for a specific reason, not a general impression.",
                "exit_condition": "Stop when the response mechanism is explainable.",
            },
            {
                "activity_type": "transfer_check",
                "minutes": 4,
                "purpose": "Test calibration on a changed context.",
                "success_criterion": "Confidence tracks evidence quality on the transfer item.",
                "exit_condition": "Schedule another near check when confidence and result diverge.",
            },
        ]
        diagnostic_boundary = "Uncertainty, answer changes, and confidence gaps identify a calibration target; they do not by themselves identify the underlying content mechanism."
    else:
        transfer = "mid" if recurrence >= 2 else "near"
        activities = [
            {
                "activity_type": "delayed_review",
                "minutes": 4,
                "purpose": "Retrieve the prior guardrail after a delay.",
                "success_criterion": "Recover the rule without copying the previous explanation.",
                "exit_condition": "Proceed once retrieval is stated and confidence is recorded.",
            },
            {
                "activity_type": "transfer_check",
                "minutes": 7,
                "purpose": f"Apply the guardrail at {transfer} transfer distance.",
                "success_criterion": "Use the method on a changed surface form and justify the choice.",
                "exit_condition": "Return to near transfer if the changed form fails.",
            },
            {
                "activity_type": "reflection",
                "minutes": 1,
                "purpose": "Record what remains uncertain and the next review condition.",
                "success_criterion": "Name one observed fact and one next action.",
                "exit_condition": "Finish when both are recorded.",
            },
        ]
        diagnostic_boundary = "This is a delayed review recommendation; continued recurrence is needed before treating the issue as confirmed."

    return {
        "planned_minutes": sum(item["minutes"] for item in activities),
        "activities": activities,
        "transfer_distance": "near" if session_type != "delayed_retrieval_and_transfer" else ("mid" if recurrence >= 2 else "near"),
        "diagnostic_boundary": diagnostic_boundary,
        "workload_rule": "Optional and user-initiated; this recommendation does not extend or mutate the daily sprint.",
    }


def _choose_session_type(signals: list[dict[str, Any]]) -> str:
    results = {signal.get("result") for signal in signals}
    if results.intersection({"incorrect", "omitted"}):
        return "mistake_autopsy_worked_example"
    if "correct_slow" in results:
        return "timed_precision_and_retrieval"
    if results.intersection({"correct_uncertain", "correct_changed"}):
        return "confidence_calibration_and_contrast"
    return "delayed_retrieval_and_transfer"


def recommend_on_demand_sessions(
    band: str,
    events: Iterable[dict[str, Any]],
    review_queue: Iterable[dict[str, Any]] = (),
    *,
    signatures: Iterable[dict[str, Any]] = (),
    limit: int = 3,
) -> dict[str, Any]:
    """Return specific optional follow-up sessions from response evidence.

    High accuracy does not suppress a recommendation when correctness is slow,
    uncertain, changed, or overconfident.  A clean, fast, calibrated response
    produces no issue-specific session because there is no observed issue to
    solve.  Recommendations stay provisional until autopsy and recurrence
    provide enough evidence.
    """

    if band not in BAND_BASE_TIER:
        raise ValueError(f"Unknown instructional band: {band}")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5:
        raise ValueError("limit must be an integer between 1 and 5")

    all_events = list(events)
    event_list = [event for event in all_events if event.get("result") in ACTIONABLE_RESULTS]
    clean_events = [event for event in all_events if event.get("result") == "correct"]
    review_list = [review for review in review_queue if review.get("status", "open") == "open"]
    signature_by_code = {str(item.get("code")): item for item in signatures if item.get("code")}
    signature_by_event: dict[str, dict[str, Any]] = {}
    for signature in signature_by_code.values():
        evidence_event_ids = signature.get("evidence_event_ids", [])
        if isinstance(evidence_event_ids, list):
            for event_id in evidence_event_ids:
                if isinstance(event_id, str):
                    signature_by_event[event_id] = signature
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in event_list:
        groups[_skill(event)].append(event)

    event_by_id = {event.get("event_id"): event for event in event_list if event.get("event_id")}
    for review in review_list:
        event = event_by_id.get(review.get("event_id"))
        skill = str(review.get("skill") or (event and _skill(event)) or "unclassified_skill")
        if event is None:
            groups[skill].append({
                "event_id": review.get("event_id"),
                "result": "review_due",
                "provisional_skill": review.get("skill"),
                "review_only": True,
            })

    candidates: list[tuple[float, str, list[dict[str, Any]]]] = []
    for skill, signals in groups.items():
        actionable_signals = [signal for signal in signals if signal.get("result") in ACTIONABLE_RESULTS]
        review_signals = [signal for signal in signals if signal.get("result") == "review_due"]
        latest_actionable = max(
            (str(signal.get("created_at")) for signal in actionable_signals if signal.get("created_at")),
            default=None,
        )
        latest_clean = max(
            (
                str(signal.get("created_at"))
                for signal in clean_events
                if _skill(signal) == skill and signal.get("created_at")
            ),
            default=None,
        )
        has_confirmed_signature = any(
            signature_by_event.get(signal.get("event_id"), {}).get("status") == "confirmed"
            for signal in actionable_signals
        )
        if (
            latest_clean is not None
            and latest_actionable is not None
            and latest_clean > latest_actionable
            and not review_signals
            and not has_confirmed_signature
        ):
            continue
        score = sum(RESULT_WEIGHT.get(signal.get("result"), 1.0) for signal in actionable_signals)
        score += 1.5 * len(review_signals)
        if len(actionable_signals) >= 2:
            score += 1.0
        for signal in actionable_signals:
            if (
                signal.get("result") in {"incorrect", "omitted"}
                and isinstance(signal.get("confidence"), int)
                and signal["confidence"] >= 4
            ):
                score += 1.0
                if signal.get("apparent_difficulty") == "routine":
                    score += 1.5
            context = _context(signal)
            if context.get("help_used"):
                score += 0.5
        if score > 0:
            candidates.append((score, skill, signals))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    recommendations: list[dict[str, Any]] = []
    for rank, (score, skill, signals) in enumerate(candidates[:limit], start=1):
        actionable_signals = [signal for signal in signals if signal.get("result") in ACTIONABLE_RESULTS]
        session_type = _choose_session_type(actionable_signals) if actionable_signals else "delayed_retrieval_and_transfer"
        recurrence = max(1, len(actionable_signals))
        shape = _session_shape(session_type, recurrence=recurrence)
        target_signature = next(
            (
                _context(signal).get("target_error_signature") or signature_by_event.get(signal.get("event_id"), {}).get("code")
                for signal in actionable_signals
                if _context(signal).get("target_error_signature") or signal.get("event_id") in signature_by_event
            ),
            None,
        )
        confirmed = bool(
            target_signature
            and signature_by_code.get(str(target_signature), {}).get("status") == "confirmed"
        )
        evidence = [_evidence(signal) for signal in actionable_signals]
        silent_danger = any(item.get("silent_danger") for item in evidence)
        evidence.extend(
            {
                "event_id": signal.get("event_id"),
                "result": "review_due",
                "skill": skill,
            }
            for signal in signals
            if signal.get("result") == "review_due"
        )
        if session_type == "mistake_autopsy_worked_example":
            title = f"{skill}: mistake autopsy and worked example"
        elif session_type == "timed_precision_and_retrieval":
            title = f"{skill}: slow-correct precision session"
        elif session_type == "confidence_calibration_and_contrast":
            title = f"{skill}: confidence calibration and contrast"
        else:
            title = f"{skill}: delayed retrieval and transfer"
        recommendations.append({
            "recommendation_id": f"on_demand:{skill}:{session_type}",
            "rank": rank,
            "title": title,
            "session_type": session_type,
            "priority_score": round(score, 2),
            "target_skill": None if skill == "unclassified_skill" else skill,
            "target_error_signature": target_signature,
            "diagnostic_status": "confirmed" if confirmed else ("provisional" if actionable_signals else "review_due"),
            "evidence": evidence,
            "material_guidance": _band_material_guidance(band, session_type),
            "session_blueprint": shape,
            "selection_reason": (
                "A routine-looking high-confidence miss created a silent-danger signal; prioritize calibration and the exact discriminating evidence."
                if silent_danger
                else "Accuracy is not the only signal: this skill has slow, uncertain, changed, incorrect, omitted, or due-review evidence."
                if actionable_signals
                else "An open review is due even though no recent issue-specific response is available."
            ),
            "confirmed_issue_note": (
                "A confirmed signature exists; keep the session targeted and verify transfer after completion."
                if confirmed
                else "No confirmed underlying issue is stored; complete the smallest autopsy needed before generalizing."
            ),
        })

    return {
        "policy_version": "1.0",
        "band_prior": band,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "selection_rule": "Use recent issue-specific evidence and open reviews; do not suppress follow-up solely because overall accuracy is high.",
        "no_issue_message": (
            None
            if recommendations
            else "No issue-specific on-demand session is currently warranted. Continue the next planned sprint and collect calibrated evidence."
        ),
        "caveat": "These are optional practice blueprints, not score predictions or proof that a single session resolves an issue.",
    }
