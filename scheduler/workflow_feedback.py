"""Explicit candidate feedback used for bounded, transparent role ranking adjustments."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from discovery.sources import CANONICAL_TARGET_ROLES

FEEDBACK_OUTCOMES = (
    "interested",
    "not_interested",
    "applied",
    "interview",
    "rejected",
    "offer",
)


def _canonical_role(role: str) -> str:
    for known_role in CANONICAL_TARGET_ROLES:
        if known_role.casefold() == role.strip().casefold():
            return known_role
    raise ValueError(f"Unknown role '{role}'. Choose one of: {', '.join(CANONICAL_TARGET_ROLES)}")


def load_role_feedback(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "roles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read candidate feedback {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("roles"), dict):
        raise ValueError(f"Invalid candidate feedback format in {path}")
    for role, counts in data["roles"].items():
        if not isinstance(counts, dict) or any(
            not isinstance(count, int) or count < 0 for count in counts.values()
        ):
            raise ValueError(f"Invalid feedback counts for role '{role}' in {path}")
    return data


def record_role_feedback(path: Path, role: str, outcome: str) -> Dict[str, Any]:
    canonical_role = _canonical_role(role)
    normalized_outcome = outcome.strip().lower()
    if normalized_outcome not in FEEDBACK_OUTCOMES:
        raise ValueError(f"Unknown outcome '{outcome}'. Choose one of: {', '.join(FEEDBACK_OUTCOMES)}")

    data = load_role_feedback(path)
    role_counts = data["roles"].setdefault(canonical_role, {})
    role_counts[normalized_outcome] = role_counts.get(normalized_outcome, 0) + 1
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
    return data


def role_preference_adjustments(feedback: Dict[str, Any], minimum_votes: int = 3) -> Dict[str, float]:
    """Returns a maximum +/-5 ranking-only adjustment after three explicit interest votes."""
    adjustments: Dict[str, float] = {}
    for role, counts in feedback.get("roles", {}).items():
        interested = counts.get("interested", 0)
        not_interested = counts.get("not_interested", 0)
        votes = interested + not_interested
        if votes >= minimum_votes:
            adjustments[role] = round(max(-5.0, min(5.0, 10.0 * (interested / votes - 0.5))), 1)
    return adjustments


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record explicit candidate role feedback.")
    parser.add_argument("--role", required=True, choices=CANONICAL_TARGET_ROLES)
    parser.add_argument("--outcome", required=True, choices=FEEDBACK_OUTCOMES)
    parser.add_argument("--state-file", type=Path, default=Path("output/state/role_feedback.json"))
    args = parser.parse_args(argv)
    data = record_role_feedback(args.state_file, args.role, args.outcome)
    print(json.dumps({"role": args.role, "outcome": args.outcome, "feedback": data["roles"][args.role]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
