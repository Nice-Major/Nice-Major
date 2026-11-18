"""Persistent, content-minimal history for opportunities already dispatched."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _field(opportunity: Any, name: str) -> str:
    if isinstance(opportunity, dict):
        value = opportunity.get(name, "")
    else:
        value = getattr(opportunity, name, "")
    return str(value or "").strip()


def _canonical_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    tracking_names = {"ref", "referrer", "source", "campaign", "tracking"}
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking_names
    ]
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, urlencode(sorted(query)), "")
    )


def opportunity_fingerprint(opportunity: Any) -> Optional[str]:
    """Returns a stable SHA-256 key without storing job text or URLs in state."""
    url = _canonical_url(_field(opportunity, "url"))
    if url:
        identity = f"url:{url}"
    else:
        company = re.sub(r"\s+", " ", _field(opportunity, "company")).casefold()
        title = re.sub(r"\s+", " ", _field(opportunity, "title")).casefold()
        description = re.sub(r"\s+", " ", _field(opportunity, "description")).casefold()
        provider_id = _field(opportunity, "id")
        identity = f"job:{company}|{title}|{provider_id or description}"
    if identity == "job:||":
        return None
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def load_opportunity_history(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "dispatched": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read opportunity history {path}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or not isinstance(data.get("dispatched"), dict)
    ):
        raise ValueError(f"Invalid opportunity history format in {path}")
    return data


def filter_new_opportunities(
    opportunities: Iterable[Any],
    history_path: Path,
) -> Tuple[list[Any], int]:
    """Filters postings previously delivered and duplicates within the current batch."""
    history = load_opportunity_history(history_path)
    dispatched = history["dispatched"]
    new_opportunities = []
    seen_in_batch = set()
    suppressed = 0
    for opportunity in opportunities:
        fingerprint = opportunity_fingerprint(opportunity)
        if fingerprint is None:
            new_opportunities.append(opportunity)
        elif fingerprint in dispatched or fingerprint in seen_in_batch:
            suppressed += 1
        else:
            seen_in_batch.add(fingerprint)
            new_opportunities.append(opportunity)
    return new_opportunities, suppressed


def record_dispatched_opportunities(
    opportunities: Iterable[Any],
    history_path: Path,
    dispatched_date: Optional[str] = None,
) -> int:
    """Records fingerprints only after successful dispatch; no posting data is retained."""
    history = load_opportunity_history(history_path)
    dispatched = history["dispatched"]
    active_date = dispatched_date or date.today().isoformat()
    added = 0
    for opportunity in opportunities:
        fingerprint = opportunity_fingerprint(opportunity)
        if fingerprint and fingerprint not in dispatched:
            dispatched[fingerprint] = active_date
            added += 1

    if added:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = history_path.with_suffix(history_path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(history_path)
    return added
