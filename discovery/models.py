"""
Domain entities and data models for Job Discovery Engine.
Module: discovery.models
Feature: F08 (Opportunity Discovery Engine)
Milestone: M3 (Opportunity Discovery, Geo-Filtering & Verification)
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class JobOpportunity:
    """
    Unified representation of a discovered career or consultancy opportunity.
    Supports attribute access, dict subscripting (__getitem__), and bidirectional contract aliases.
    """
    id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    source: str = "synthetic"
    posted_date: str = ""
    is_remote: bool = True
    nigeria_eligible: bool = False
    visa_sponsored: bool = False
    contract_type: str = "full-time"  # "full-time", "contract", "c2c", "b2b", "consultancy"
    is_active: bool = True
    salary_range: str = ""
    tags: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Auto-generate deterministic ID if empty
        if not self.id:
            fp_raw = f"{self.company.strip().lower()}|{self.title.strip().lower()}|{self.url.strip().lower()}"
            self.id = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()[:16]

    # -------------------------------------------------------------------------
    # Bidirectional Interface Contract Aliases (PROJECT.md line 117)
    # -------------------------------------------------------------------------
    @property
    def remote_eligible_nigeria(self) -> bool:
        """Alias for nigeria_eligible (PROJECT.md contract)."""
        return self.nigeria_eligible

    @remote_eligible_nigeria.setter
    def remote_eligible_nigeria(self, value: bool) -> None:
        self.nigeria_eligible = bool(value)

    @property
    def visa_sponsorship(self) -> bool:
        """Alias for visa_sponsored (PROJECT.md contract)."""
        return self.visa_sponsored

    @visa_sponsorship.setter
    def visa_sponsorship(self, value: bool) -> None:
        self.visa_sponsored = bool(value)

    @property
    def contract_b2b(self) -> bool:
        """Alias for contract_type B2B / C2C check (PROJECT.md contract)."""
        ct = (self.contract_type or "").lower().strip()
        return ct in ("b2b", "c2c", "contract", "consultancy")

    @contract_b2b.setter
    def contract_b2b(self, value: bool) -> None:
        if value:
            if (self.contract_type or "").lower().strip() not in ("b2b", "c2c", "contract", "consultancy"):
                self.contract_type = "b2b"
        else:
            if (self.contract_type or "").lower().strip() in ("b2b", "c2c", "contract", "consultancy"):
                self.contract_type = "full-time"

    @property
    def verified_active(self) -> bool:
        """Alias for is_active (PROJECT.md contract)."""
        return self.is_active

    @verified_active.setter
    def verified_active(self, value: bool) -> None:
        self.is_active = bool(value)

    # -------------------------------------------------------------------------
    # Subscript & Dict-like Access Protocols
    # -------------------------------------------------------------------------
    def __getitem__(self, item: str) -> Any:
        """Supports dict-style access for all fields and contract aliases."""
        alias_map = {
            "remote_eligible_nigeria": "nigeria_eligible",
            "remoteEligibleNigeria": "nigeria_eligible",
            "visa_sponsorship": "visa_sponsored",
            "visaSponsorship": "visa_sponsored",
            "contract_b2b": "contract_b2b",
            "contractB2B": "contract_b2b",
            "verified_active": "is_active",
            "verifiedActive": "is_active",
            "isRemote": "is_remote",
            "postedDate": "posted_date",
            "contractType": "contract_type",
            "salaryRange": "salary_range",
            "rawData": "raw_data",
        }
        target_key = alias_map.get(item, item)
        if hasattr(self, target_key):
            return getattr(self, target_key)
        if item in self.raw_data:
            return self.raw_data[item]
        raise KeyError(f"Key '{item}' not found in JobOpportunity")

    def __setitem__(self, key: str, value: Any) -> None:
        alias_map = {
            "remote_eligible_nigeria": "nigeria_eligible",
            "remoteEligibleNigeria": "nigeria_eligible",
            "visa_sponsorship": "visa_sponsored",
            "visaSponsorship": "visa_sponsored",
            "contract_b2b": "contract_b2b",
            "verified_active": "is_active",
            "verifiedActive": "is_active",
            "isRemote": "is_remote",
            "postedDate": "posted_date",
            "contractType": "contract_type",
            "salaryRange": "salary_range",
            "rawData": "raw_data",
        }
        target_key = alias_map.get(key, key)
        if hasattr(self, target_key):
            setattr(self, target_key, value)
        else:
            self.raw_data[key] = value

    def __contains__(self, item: str) -> bool:
        alias_map = {
            "remote_eligible_nigeria", "remoteEligibleNigeria",
            "visa_sponsorship", "visaSponsorship",
            "contract_b2b", "contractB2B",
            "verified_active", "verifiedActive",
            "isRemote", "postedDate", "contractType", "salaryRange", "rawData"
        }
        return hasattr(self, item) or item in alias_map or item in self.raw_data

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    # -------------------------------------------------------------------------
    # Serialization and Deserialization
    # -------------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        Exports opportunity as a clean dictionary including both canonical keys
        and PROJECT.md contract alias keys.
        """
        d = asdict(self)
        # Inject contract aliases explicitly
        d["remote_eligible_nigeria"] = self.nigeria_eligible
        d["visa_sponsorship"] = self.visa_sponsored
        d["contract_b2b"] = self.contract_b2b
        d["verified_active"] = self.is_active
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JobOpportunity:
        """
        Constructs JobOpportunity from a dictionary, safely mapping
        raw external API fields or contract alias fields.
        """
        if not data or not isinstance(data, dict):
            return cls()

        is_rem = data.get("is_remote", data.get("isRemote", True))
        nig_elig = data.get("nigeria_eligible", data.get("remote_eligible_nigeria", False))
        visa_spon = data.get("visa_sponsored", data.get("visa_sponsorship", False))
        ct = data.get("contract_type", data.get("contractType", "full-time"))
        if "contract_b2b" in data and not data.get("contract_type"):
            ct = "b2b" if data["contract_b2b"] else "full-time"

        active = data.get("is_active", data.get("verified_active", True))

        tags_val = data.get("tags", [])
        if not isinstance(tags_val, list):
            tags_val = [str(tags_val)]

        raw_val = data.get("raw_data", data.get("raw", {}))
        if not isinstance(raw_val, dict):
            raw_val = {"raw": raw_val}

        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            company=str(data.get("company", "")),
            location=str(data.get("location", "")),
            description=str(data.get("description", "")),
            url=str(data.get("url", data.get("link", ""))),
            source=str(data.get("source", "synthetic")),
            posted_date=str(data.get("posted_date", data.get("postedDate", data.get("date", "")))),
            is_remote=bool(is_rem),
            nigeria_eligible=bool(nig_elig),
            visa_sponsored=bool(visa_spon),
            contract_type=str(ct),
            is_active=bool(active),
            salary_range=str(data.get("salary_range", data.get("salary", ""))),
            tags=list(tags_val),
            raw_data=dict(raw_val),
        )


# Module-level contract alias for PROJECT.md line 117
Opportunity = JobOpportunity


@dataclass
class JobQueryParams:
    """Structured query filters for job opportunity searches."""
    query_roles: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    location: str = ""
    remote_only: bool = True
    sources: List[str] = field(default_factory=list)
    limit: int = 20
    dry_run: bool = True
    simulate_timeout: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> JobQueryParams:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            query_roles=list(data.get("query_roles", data.get("roles", []))),
            keywords=list(data.get("keywords", data.get("tags", []))),
            location=str(data.get("location", "")),
            remote_only=bool(data.get("remote_only", True)),
            sources=list(data.get("sources", [])),
            limit=int(data.get("limit", 20)),
            dry_run=bool(data.get("dry_run", True)),
            simulate_timeout=bool(data.get("simulate_timeout", False)),
        )
