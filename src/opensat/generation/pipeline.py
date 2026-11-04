"""Provider-neutral candidate-item gates; no official content is copied."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.metadata import version
from statistics import mean, median
from typing import Any

from wordfreq import zipf_frequency

from ..domain.constants import SIMULATED_LABEL
from ..privacy.redaction import ensure_safe_metadata


_TOKEN_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*|\d+(?:\.\d+)?%?")
_NUMERIC_CELL_RE = re.compile(
    r"[+-]?(?:\d+(?:,\d{3})*|\d*\.\d+)(?:\s*(?:%|°[CF]|mm|cm|kg|g|s|ms|days?))?",
    re.IGNORECASE,
)
_UNIT_LABEL_RE = re.compile(
    r"%|°|\([^)]*(?:mm|cm|kg|grams?|seconds?|days?|dollars?|fahrenheit|celsius|[FC])[^)]*\)",
    re.IGNORECASE,
)
_FUNCTION_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "because", "been", "being", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "hers", "him", "his", "how", "if", "in", "into", "is", "it", "its",
    "may", "might", "more", "most", "must", "no", "nor", "not", "of", "on", "or",
    "our", "ours", "shall", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "then", "there", "these", "they", "this",
    "those", "through", "to", "under", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "whose", "why", "will", "with", "would", "you",
    "your", "yours",
})
_SUBORDINATION_CUES = frozenset({
    "although", "because", "despite", "if", "unless", "whereas", "while",
    "which", "who", "whose", "that",
})
_NEGATION_CUES = frozenset({"no", "not", "neither", "nor", "never", "without"})
_WORDFREQ_VERSION = version("wordfreq")


@dataclass(frozen=True)
class ItemSpecification:
    domain: str
    skill: str
    question_type: str
    stem_family: str
    score_band: str
    difficulty: str
    cognitive_operation: str
    target_error_signature: str | None
    stimulus_constraints: dict[str, Any]
    correct_answer_rationale: str
    distractor_mechanisms: list[str]
    difficulty_mechanisms: list[str]
    style_reference_ids: list[str]
    timing_expectation_seconds: int
    transfer_distance: str
    fidelity_targets: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _token_counts(text: str) -> dict[str, int]:
    tokens = _TOKEN_RE.findall(text)
    content_tokens = [
        token for token in tokens
        if token[0].isalpha() and token.lower() not in _FUNCTION_WORDS
    ]
    return {"total_tokens": len(tokens), "content_tokens": len(content_tokens)}


def _reading_features(text: str) -> dict[str, Any]:
    """Cheap local language proxies; no model inference or difficulty label."""
    words = [token for token in _TOKEN_RE.findall(text) if token[0].isalpha()]
    sentences = [
        part for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())
        if part.strip()
    ]
    content_words = [word for word in words if word.lower() not in _FUNCTION_WORDS]
    frequencies = [zipf_frequency(word.lower(), "en") for word in content_words]
    lengths = [len(_TOKEN_RE.findall(sentence)) for sentence in sentences]
    # ARI is a conventional length-based readability formula. It is unstable on short SAT passages.
    ari = None
    if words and sentences:
        ari = (
            4.71 * sum(len(word) for word in words) / len(words)
            + 0.5 * len(words) / len(sentences)
            - 21.43
        )
    return {
        "method": f"wordfreq-{_WORDFREQ_VERSION} + deterministic surface cues",
        "lexical": {
            "content_words": len(content_words),
            "mean_zipf_frequency": round(mean(frequencies), 2) if frequencies else None,
            "median_zipf_frequency": round(median(frequencies), 2) if frequencies else None,
            "share_below_zipf_3": (
                round(sum(value < 3 for value in frequencies) / len(frequencies), 3)
                if frequencies else None
            ),
            "zero_frequency_words": sum(value == 0 for value in frequencies),
        },
        "syntax_cues": {
            "mean_words_per_sentence": round(mean(lengths), 2) if lengths else None,
            "longest_sentence_words": max(lengths, default=0),
            "commas": text.count(","),
            "semicolons": text.count(";"),
            "subordination_cues": sum(word.lower() in _SUBORDINATION_CUES for word in words),
            "negation_cues": sum(word.lower() in _NEGATION_CUES for word in words),
        },
        "readability": {
            "automated_readability_index": round(ari, 2) if ari is not None else None,
            "short_text_caution": len(words) < 100,
        },
    }


def profile_surface_load(
    body_text: str,
    table: list[list[Any]] | None,
    options: list[str],
    stimulus_text: str | None = None,
) -> dict[str, Any]:
    """Return reproducible surface-load proxies without claiming comprehension difficulty."""
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("body_text must be a non-empty string")
    if stimulus_text is not None and (not isinstance(stimulus_text, str) or not stimulus_text.strip()):
        raise ValueError("stimulus_text must be nonempty text when supplied")
    if not isinstance(options, list) or len(options) != 4 or any(
        not isinstance(option, str) or not option.strip() for option in options
    ):
        raise ValueError("options must contain four non-empty strings")
    body = _token_counts(body_text)
    body["sentences"] = len([
        segment
        for segment in re.split(r"(?<=[.!?])\s+(?=[A-Z])", body_text.strip())
        if segment.strip()
    ])
    body["reading_features"] = _reading_features(stimulus_text if stimulus_text is not None else body_text)
    body["reading_features"]["text_scope"] = "stimulus_only" if stimulus_text is not None else "body_including_stem"

    rows = table or []
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError("table must be a list of rows")
    widths = [len(row) for row in rows]
    columns = max(widths, default=0)
    flattened = [str(cell).strip() for row in rows for cell in row]
    table_profile = {
        "rows": len(rows),
        "header_rows": 1 if rows else 0,
        "data_rows": max(0, len(rows) - 1),
        "columns": columns,
        "cells": len(rows) * columns,
        "nonempty_cells": sum(bool(cell) for cell in flattened),
        "numeric_cells": sum(bool(_NUMERIC_CELL_RE.fullmatch(cell)) for cell in flattened),
        "unit_label_cells": sum(bool(_UNIT_LABEL_RE.search(cell)) for cell in flattened),
        "rectangular": bool(rows) and all(width == columns for width in widths),
    }
    table_counts = _token_counts(" ".join(flattened))
    table_profile.update(table_counts)
    option_counts = [_token_counts(option) for option in options]
    content_lengths = [counts["content_tokens"] for counts in option_counts]
    return {
        "proxy_notice": "surface-load proxies; not comprehension difficulty",
        "body": body,
        "table": table_profile,
        "options": {
            "count": len(options),
            "total_tokens": [counts["total_tokens"] for counts in option_counts],
            "content_tokens": content_lengths,
            "max_to_min_content_ratio": (
                max(content_lengths) / min(content_lengths)
                if content_lengths and min(content_lengths) > 0
                else None
            ),
        },
        "displayed_total_tokens": body["total_tokens"] + table_counts["total_tokens"] + sum(counts["total_tokens"] for counts in option_counts),
        "displayed_content_tokens": body["content_tokens"] + table_counts["content_tokens"] + sum(counts["content_tokens"] for counts in option_counts),
    }


def _profile_value(profile: dict[str, Any], path: str) -> Any:
    value: Any = profile
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _fidelity_failures(
    profile: dict[str, Any],
    targets: dict[str, Any],
) -> list[str]:
    if not isinstance(targets, dict):
        raise ValueError("fidelity_targets must be an object")
    calibration_id = targets.get("calibration_id")
    source_count = targets.get("reviewed_source_count")
    rules = targets.get("metrics")
    if not isinstance(calibration_id, str) or not calibration_id.strip():
        raise ValueError("fidelity_targets require a calibration_id")
    if isinstance(source_count, bool) or not isinstance(source_count, int) or source_count < 3:
        raise ValueError("fidelity calibration requires at least three reviewed source items")
    if not isinstance(rules, dict) or not rules:
        raise ValueError("fidelity_targets require metric rules")
    if not isinstance(profile, dict):
        raise ValueError("fidelity_profile must be an object")

    failures: list[str] = []
    for path, rule in rules.items():
        if not isinstance(path, str) or not path.strip() or not isinstance(rule, dict):
            raise ValueError("each fidelity metric needs a dotted path and rule object")
        if not set(rule).issubset({"min", "max", "exact"}) or not rule:
            raise ValueError(f"unsupported fidelity rule for {path}")
        value = _profile_value(profile, path)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            failures.append(path)
            continue
        for boundary in rule.values():
            if isinstance(boundary, bool) or not isinstance(boundary, (int, float)):
                raise ValueError(f"fidelity boundary for {path} must be numeric")
        if "min" in rule and value < rule["min"]:
            failures.append(path)
        elif "max" in rule and value > rule["max"]:
            failures.append(path)
        elif "exact" in rule and value != rule["exact"]:
            failures.append(path)
    return failures


def validate_candidate(candidate: dict[str, Any], specification: ItemSpecification) -> dict[str, Any]:
    """Require explicit validation evidence before an item can be approved."""
    ensure_safe_metadata(candidate)
    if not specification.question_type.strip() or not specification.stem_family.strip():
        raise ValueError("Reading and Writing candidates need a question type and public stem family")
    if not specification.difficulty_mechanisms:
        raise ValueError("State at least one substantive difficulty mechanism")
    if not specification.style_reference_ids:
        raise ValueError("State at least one public style-reference identifier")
    required = {
        "options",
        "proposed_key",
        "independent_solution",
        "option_defensibility",
        "shortcut_check",
        "wording_check",
        "difficulty_check",
        "college_board_style_check",
        "difficulty_mechanism_check",
        "originality_check",
    }
    if specification.skill == "rhetorical_synthesis":
        required.add("rhetorical_synthesis_scenario_check")
    missing = sorted(required.difference(candidate))
    if missing:
        raise ValueError(f"Candidate is missing validation stages: {', '.join(missing)}")
    options = candidate["options"]
    defensibility = candidate["option_defensibility"]
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("Synthetic SAT-style candidate must contain four options")
    if not isinstance(defensibility, dict) or len(defensibility) != 4:
        raise ValueError("Inspect every distractor before approval")
    if candidate.get("proposed_key") not in {"A", "B", "C", "D"}:
        raise ValueError("proposed_key must be A, B, C, or D")
    fidelity_failures: list[str] = []
    if specification.fidelity_targets is not None:
        if "fidelity_profile" not in candidate:
            raise ValueError("fidelity-calibrated candidates require a fidelity_profile")
        fidelity_failures = _fidelity_failures(
            candidate["fidelity_profile"],
            specification.fidelity_targets,
        )
    checks = [candidate[key] for key in required if key.endswith("_check") or key == "originality_check"]
    if not all(check is True for check in checks) or fidelity_failures:
        return {
            "status": "needs_revision",
            "simulated_label": SIMULATED_LABEL,
            "specification": specification.as_dict(),
            "fidelity_failures": fidelity_failures,
        }
    return {
        "status": "approved",
        "simulated_label": SIMULATED_LABEL,
        "specification": specification.as_dict(),
        "proposed_key": candidate["proposed_key"],
    }


def validate_purpose_groups(
    groups: list[dict[str, Any]],
    *,
    minimum_groups: int = 1,
    maximum_groups: int = 4,
    maximum_questions_per_group: int = 4,
) -> dict[str, Any]:
    """Validate UI grouping without turning presentation labels into activities."""
    limits = (minimum_groups, maximum_groups, maximum_questions_per_group)
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in limits):
        raise ValueError("Purpose-group limits must be integers")
    if not 1 <= minimum_groups <= maximum_groups <= 4:
        raise ValueError("Purpose-group count must stay between one and four")
    if not 1 <= maximum_questions_per_group <= 4:
        raise ValueError("A purpose group must contain fewer than five questions")
    if not isinstance(groups, list) or not minimum_groups <= len(groups) <= maximum_groups:
        raise ValueError(f"Expected {minimum_groups} to {maximum_groups} purpose groups")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"Purpose group {index + 1} must be an object")
        purpose = group.get("purpose")
        item_ids = group.get("item_ids")
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError(f"Purpose group {index + 1} needs a shared purpose")
        if not isinstance(item_ids, list) or not 1 <= len(item_ids) <= maximum_questions_per_group:
            raise ValueError(f"Purpose group {index + 1} must contain one to {maximum_questions_per_group} item ids")
        if any(not isinstance(item_id, str) or not item_id.strip() for item_id in item_ids):
            raise ValueError(f"Purpose group {index + 1} contains an invalid item id")
        duplicates = seen.intersection(item_ids)
        if duplicates:
            raise ValueError(f"Item ids cannot appear in multiple purpose groups: {', '.join(sorted(duplicates))}")
        seen.update(item_ids)
        normalized.append({"purpose": purpose.strip(), "item_ids": list(item_ids)})
    return {
        "groups": normalized,
        "group_count": len(normalized),
        "question_count": len(seen),
        "presentation_only": True,
    }
