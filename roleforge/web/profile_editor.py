from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ALLOWED_TOP_LEVEL_KEYS = {
    "intent",
    "hard_filters",
    "weights",
    "min_score",
    "keywords",
    "skills",
    "preferred_companies",
    "delivery_mode",
}

ALLOWED_WEIGHT_KEYS = {"title_match", "company_match", "location_match", "keyword_bonus"}

ALLOWED_HARD_FILTER_KEYS = {"locations", "exclude_companies", "exclude_titles", "min_parse_confidence"}

ALLOWED_DELIVERY_MODE_KEYS = {
    "alert_enabled",
    "immediate_threshold",
    "batch_enabled",
    "batch_threshold",
    "batch_interval_minutes",
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str
    config: dict[str, Any] | None = None


def _is_list_of_strings(value: Any, *, max_items: int = 200, max_len: int = 200) -> bool:
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    if len(value) > max_items:
        return False
    for item in value:
        if not isinstance(item, str):
            return False
        if len(item) > max_len:
            return False
    return True


def validate_profile_config(raw_json: str, *, max_bytes: int = 25_000) -> ValidationResult:
    if raw_json is None:
        return ValidationResult(False, "missing config")
    if len(raw_json.encode("utf-8")) > max_bytes:
        return ValidationResult(False, f"config too large (>{max_bytes} bytes)")
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return ValidationResult(False, f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return ValidationResult(False, "config must be a JSON object")

    unknown = sorted(set(data.keys()) - ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        return ValidationResult(False, f"unknown top-level keys: {', '.join(unknown)}")

    hard = data.get("hard_filters", {})
    if hard is None:
        hard = {}
    if not isinstance(hard, dict):
        return ValidationResult(False, "hard_filters must be an object")
    hard_unknown = sorted(set(hard.keys()) - ALLOWED_HARD_FILTER_KEYS)
    if hard_unknown:
        return ValidationResult(False, f"unknown hard_filters keys: {', '.join(hard_unknown)}")
    if not _is_list_of_strings(hard.get("locations")):
        return ValidationResult(False, "hard_filters.locations must be a list of strings")
    if not _is_list_of_strings(hard.get("exclude_companies")):
        return ValidationResult(False, "hard_filters.exclude_companies must be a list of strings")
    if not _is_list_of_strings(hard.get("exclude_titles")):
        return ValidationResult(False, "hard_filters.exclude_titles must be a list of strings")
    mpc = hard.get("min_parse_confidence")
    if mpc is not None:
        try:
            mpc_f = float(mpc)
        except (TypeError, ValueError):
            return ValidationResult(False, "hard_filters.min_parse_confidence must be numeric")
        if not (0.0 <= mpc_f <= 1.0):
            return ValidationResult(False, "hard_filters.min_parse_confidence must be between 0 and 1")

    weights = data.get("weights", {})
    if weights is None:
        weights = {}
    if not isinstance(weights, dict):
        return ValidationResult(False, "weights must be an object")
    weights_unknown = sorted(set(weights.keys()) - ALLOWED_WEIGHT_KEYS)
    if weights_unknown:
        return ValidationResult(False, f"unknown weights keys: {', '.join(weights_unknown)}")
    for k, v in weights.items():
        try:
            float(v)
        except (TypeError, ValueError):
            return ValidationResult(False, f"weights.{k} must be numeric")

    if data.get("keywords") is not None and not _is_list_of_strings(data.get("keywords"), max_items=200, max_len=80):
        return ValidationResult(False, "keywords must be a list of short strings")
    if data.get("skills") is not None and not _is_list_of_strings(data.get("skills"), max_items=200, max_len=80):
        return ValidationResult(False, "skills must be a list of short strings")
    if data.get("preferred_companies") is not None and not _is_list_of_strings(
        data.get("preferred_companies"), max_items=500, max_len=120
    ):
        return ValidationResult(False, "preferred_companies must be a list of strings")

    ms = data.get("min_score")
    if ms is not None:
        try:
            ms_f = float(ms)
        except (TypeError, ValueError):
            return ValidationResult(False, "min_score must be numeric or null")
        if not (0.0 <= ms_f <= 1.0):
            return ValidationResult(False, "min_score must be between 0 and 1")

    dm = data.get("delivery_mode")
    if dm is not None:
        if not isinstance(dm, dict):
            return ValidationResult(False, "delivery_mode must be an object")
        dm_unknown = sorted(set(dm.keys()) - ALLOWED_DELIVERY_MODE_KEYS)
        if dm_unknown:
            return ValidationResult(False, f"unknown delivery_mode keys: {', '.join(dm_unknown)}")
        for bkey in ("alert_enabled", "batch_enabled"):
            if bkey in dm and not isinstance(dm[bkey], bool):
                return ValidationResult(False, f"delivery_mode.{bkey} must be boolean")
        for nkey in ("immediate_threshold", "batch_threshold"):
            if nkey in dm and dm[nkey] is not None:
                try:
                    v = float(dm[nkey])
                except (TypeError, ValueError):
                    return ValidationResult(False, f"delivery_mode.{nkey} must be numeric")
                if not (0.0 <= v <= 1.0):
                    return ValidationResult(False, f"delivery_mode.{nkey} must be between 0 and 1")
        if "batch_interval_minutes" in dm and dm["batch_interval_minutes"] is not None:
            try:
                iv = int(dm["batch_interval_minutes"])
            except (TypeError, ValueError):
                return ValidationResult(False, "delivery_mode.batch_interval_minutes must be integer")
            if iv < 1 or iv > 24 * 60:
                return ValidationResult(False, "delivery_mode.batch_interval_minutes must be between 1 and 1440")

    intent = data.get("intent")
    if intent is not None and (not isinstance(intent, str) or len(intent) > 400):
        return ValidationResult(False, "intent must be a short string")

    return ValidationResult(True, "ok", config=data)


def diff_top_level_keys(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for k in sorted(ALLOWED_TOP_LEVEL_KEYS):
        if old.get(k) != new.get(k):
            changed.append(k)
    return changed


def update_profile_config(conn: Any, *, profile_id: Any, new_config: dict[str, Any]) -> None:
    import json as _json

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE profiles SET config = %s::jsonb WHERE id = %s",
            (_json.dumps(new_config), profile_id),
        )
    conn.commit()

