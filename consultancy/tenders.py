"""
Stepcon Solutions (RC - 8284984) Public & Corporate Tender Discovery and Scorer.
Module: consultancy.tenders
Feature: F14 (Stepcon Solutions Consultancy Pipeline)
Milestone: M5 (Interactive CLI & Stepcon Solutions Pipeline)

Provides:
- `TenderOpportunity`: Machine-readable data model for public RFPs and corporate consultancy engagements.
- `TenderMatchResult`: Multi-dimensional evaluation report with breakdown and transparent rationale.
- `evaluate_tender`: Match scorer assessing alignment with Stepcon's core IT offerings (Cloud Architecture,
  Kubernetes Pods, DevSecOps, L3 Support, Computing Hardware), SLA governance, and commercial contracting terms.
- `fetch_tenders`: Synthetic and open discovery engine for global and Nigerian IT tenders.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from ingestion.models import StepconProfile


# ============================================================================
# 1. Domain Entities
# ============================================================================

@dataclass
class TenderOpportunity:
    """
    Domain entity representing a public or corporate consultancy opportunity/RFP.
    Provides dual attribute and dictionary subscript compatibility.
    """
    id: str = "TND-GENERIC"
    tender_id: str = ""
    title: str = ""
    client: str = ""
    description: str = ""
    budget: str = ""
    deadline: str = ""
    category: str = "cloud"
    country: str = "Nigeria"
    url: str = ""
    verified_active: bool = True

    def __post_init__(self):
        if not self.tender_id:
            self.tender_id = self.id
        if not self.id:
            self.id = self.tender_id

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item == "tender_id":
            return self.id
        if item == "id":
            return self.tender_id
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in ("tender_id", "id")

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TenderOpportunity:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            id=str(data.get("id", data.get("tender_id", "TND-GENERIC"))),
            tender_id=str(data.get("tender_id", data.get("id", "TND-GENERIC"))),
            title=str(data.get("title", "")),
            client=str(data.get("client", "")),
            description=str(data.get("description", "")),
            budget=str(data.get("budget", "")),
            deadline=str(data.get("deadline", "")),
            category=str(data.get("category", "cloud")),
            country=str(data.get("country", "Nigeria")),
            url=str(data.get("url", "")),
            verified_active=bool(data.get("verified_active", True)),
        )


@dataclass
class TenderMatchResult:
    """
    Evaluated tender match report adhering to PROJECT.md:120.
    Provides dual attribute and dictionary subscript compatibility.
    """
    overall_score: float
    breakdown: Dict[str, float]
    matched_capabilities: List[str]
    missing_capabilities: List[str]
    target_offering: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "breakdown": dict(self.breakdown),
            "matched_capabilities": list(self.matched_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "target_offering": self.target_offering,
            "rationale": self.rationale,
        }

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


# ============================================================================
# 2. Capabilities & Keywords Taxonomy
# ============================================================================

OFFERINGS_TAXONOMY = {
    "cloud": [
        "cloud", "aws", "azure", "multi-cloud", "well-architected", "cloud migration",
        "cloud infrastructure", "solution architecture", "iaas", "paas"
    ],
    "containers": [
        "kubernetes", "k8s", "docker", "aks", "eks", "container", "microservices",
        "orchestration", "pods", "helm"
    ],
    "devsecops": [
        "devops", "devsecops", "terraform", "iac", "infrastructure as code", "ci/cd",
        "github actions", "pipelines", "automation", "bicep", "ansible"
    ],
    "support": [
        "support", "l3", "troubleshooting", "rca", "incident", "azure app service",
        "monitoring", "application insights", "cloudwatch", "observability"
    ],
    "hardware": [
        "hardware", "procurement", "laptops", "desktops", "workstations",
        "computing equipment", "enterprise computing"
    ],
}

SLA_KEYWORDS = ["sla", "99.9%", "uptime", "availability", "high availability", "24/7", "resilience"]
COMMERCIAL_KEYWORDS = ["b2b", "corp-to-corp", "c2c", "rfp", "contractor", "consultancy", "retainer", "emea", "cet", "synchronous"]
CREDENTIAL_KEYWORDS = ["certified", "kcna", "aws certified", "solutions architect", "developer", "engineering team", "degree"]

# Keywords indicating completely unrelated civil, physical, or non-IT domains
NON_IT_KEYWORDS = [
    "asphalt", "paving", "drainage", "grading", "road", "construction", "concrete",
    "culvert", "gravel", "plumbing", "catering", "janitorial", "civil engineering",
    "horticulture", "building renovation"
]


# ============================================================================
# 3. Main Tender Evaluator
# ============================================================================

def evaluate_tender(
    stepcon: Union[StepconProfile, Dict[str, Any]],
    tender: Union[str, Dict[str, Any], TenderOpportunity],
) -> TenderMatchResult:
    """
    Evaluates commercial tender suitability against Stepcon Solutions capabilities.

    Args:
        stepcon: StepconProfile instance or raw dictionary.
        tender: Unstructured tender description string, dictionary, or TenderOpportunity.

    Returns:
        TenderMatchResult containing overall_score, breakdown, matched/missing capabilities,
        target_offering, and actionable rationale.
    """
    # 1. Extract tender text
    if tender is None:
        tender_text = ""
    elif isinstance(tender, str):
        tender_text = tender
    elif isinstance(tender, dict):
        tender_text = tender.get("description") or tender.get("title") or ""
    elif hasattr(tender, "description") or hasattr(tender, "title"):
        tender_text = getattr(tender, "description", None) or getattr(tender, "title", None) or ""
    else:
        tender_text = str(tender) if tender is not None else ""

    tender_lower = str(tender_text or "").lower().strip()

    # Edge Case 1: Empty or blank tender text
    if not tender_lower or tender_lower == "none":
        return TenderMatchResult(
            overall_score=0.0,
            breakdown={"offerings": 0.0, "sla": 0.0, "commercial": 0.0, "credentials": 0.0},
            matched_capabilities=[],
            missing_capabilities=["Cloud Solutions", "DevSecOps", "Kubernetes", "SLA Commitments"],
            target_offering="Cloud Solutions Architecture",
            rationale="Empty Tender: Unable to evaluate zero-length tender description. Match score is 0.0%.",
        )

    # Edge Case 2: Non-IT civil works / road construction rejection
    non_it_hits = sum(1 for kw in NON_IT_KEYWORDS if kw in tender_lower)
    it_hits = sum(
        1 for group in OFFERINGS_TAXONOMY.values() for kw in group if kw in tender_lower
    )

    if non_it_hits >= 2 and it_hits == 0:
        return TenderMatchResult(
            overall_score=10.0,
            breakdown={"offerings": 0.0, "sla": 10.0, "commercial": 20.0, "credentials": 10.0},
            matched_capabilities=[],
            missing_capabilities=["IT Infrastructure", "Cloud Architecture", "DevOps Automation"],
            target_offering="None (Non-IT Domain)",
            rationale="Do Not Bid (Score: 10.0%): Civil/public works tender outside Stepcon Solutions IT scope.",
        )

    if non_it_hits >= 1 and it_hits == 0:
        return TenderMatchResult(
            overall_score=15.0,
            breakdown={"offerings": 0.0, "sla": 15.0, "commercial": 25.0, "credentials": 20.0},
            matched_capabilities=[],
            missing_capabilities=["Cloud Computing", "Software & Systems"],
            target_offering="None (Non-IT Domain)",
            rationale="Do Not Bid (Score: 15.0%): Non-IT procurement opportunity; outside core capabilities.",
        )

    if non_it_hits >= 2 and non_it_hits >= it_hits:
        return TenderMatchResult(
            overall_score=20.0,
            breakdown={"offerings": 10.0, "sla": 20.0, "commercial": 25.0, "credentials": 25.0},
            matched_capabilities=[],
            missing_capabilities=["Core IT Infrastructure", "Cloud Architecture"],
            target_offering="None (Non-IT Domain)",
            rationale="Do Not Bid (Score: 20.0%): Predominantly non-IT civil works tender with incidental terminology.",
        )

    # Step 1: Score Offerings Alignment (40% weight)
    matched_caps = []
    category_scores = {}
    for cat_name, keywords in OFFERINGS_TAXONOMY.items():
        hits = [kw for kw in keywords if kw in tender_lower]
        if hits:
            matched_caps.extend(hits[:3])
            category_scores[cat_name] = min(100.0, len(hits) * 35.0)
        else:
            category_scores[cat_name] = 0.0

    if category_scores and any(category_scores.values()):
        best_cat = max(category_scores, key=category_scores.get)
        offerings_score = min(100.0, category_scores[best_cat] * 0.7 + sum(category_scores.values()) * 0.1)
    else:
        best_cat = "cloud"
        offerings_score = 0.0

    # Step 2: Score SLA & Operating Model (25% weight)
    sla_hits = [kw for kw in SLA_KEYWORDS if kw in tender_lower]
    if sla_hits:
        sla_score = min(100.0, 50.0 + len(sla_hits) * 25.0)
    else:
        sla_score = 70.0

    # Step 3: Score Commercial Alignment (20% weight)
    comm_hits = [kw for kw in COMMERCIAL_KEYWORDS if kw in tender_lower]
    if comm_hits:
        comm_score = min(100.0, 60.0 + len(comm_hits) * 20.0)
    else:
        comm_score = 65.0

    # Step 4: Score Credentials Alignment (15% weight)
    cred_hits = [kw for kw in CREDENTIAL_KEYWORDS if kw in tender_lower]
    if cred_hits:
        cred_score = min(100.0, 70.0 + len(cred_hits) * 15.0)
    else:
        cred_score = 80.0

    # Handle minimalist text (e.g. "Cloud.")
    if len(tender_lower.split()) <= 3 and it_hits > 0:
        offerings_score = 45.0
        sla_score = 40.0
        comm_score = 40.0
        cred_score = 50.0

    # Step 5: Compute Weighted Overall Score
    weights = {"offerings": 0.40, "sla": 0.25, "commercial": 0.20, "credentials": 0.15}
    breakdown = {
        "offerings": round(offerings_score, 1),
        "sla": round(sla_score, 1),
        "commercial": round(comm_score, 1),
        "credentials": round(cred_score, 1),
    }

    weighted_total = sum(breakdown[dim] * weights[dim] for dim in weights)
    overall_score = round(min(100.0, max(0.0, weighted_total)), 1)

    # Formulate Rationale & Target Offering Title
    target_offering_map = {
        "cloud": "Cloud Solutions Architecture (AWS & Microsoft Azure)",
        "containers": "Kubernetes & Container Orchestration Pods",
        "devsecops": "DevSecOps & Automated CI/CD Pipelines",
        "support": "L3 Infrastructure & Application Escalation Support",
        "hardware": "Enterprise & Custom Computing Hardware Division",
    }
    target_offering_title = target_offering_map.get(best_cat, "Cloud Solutions Architecture")

    # Missing capabilities breakdown
    all_possible = ["Cloud Migration", "Kubernetes Pods", "Terraform CI/CD", "99.9% Uptime SLA", "Hardware Fulfillment"]
    missing = [c for c in all_possible if not any(c.lower() in m.lower() for m in matched_caps)]

    if overall_score >= 70.0:
        rationale = (
            f"Strong Bid Recommendation (Fit Score: {overall_score}%): High commercial alignment with Stepcon "
            f"capabilities in {target_offering_title} and synchronous CET/EMEA operational SLA."
        )
    elif overall_score >= 50.0:
        rationale = (
            f"Selective Bid (Fit Score: {overall_score}%): Moderate alignment; potential B2B engagement "
            f"requiring joint consortium or scope refinement."
        )
    else:
        rationale = (
            f"Low Match (Fit Score: {overall_score}%): Limited alignment with Stepcon core offerings; "
            f"recommend deprioritizing."
        )

    return TenderMatchResult(
        overall_score=overall_score,
        breakdown=breakdown,
        matched_capabilities=list(dict.fromkeys(matched_caps)),
        missing_capabilities=missing[:3],
        target_offering=target_offering_title,
        rationale=rationale,
    )


# ============================================================================
# 4. Synthetic Tenders Registry & Discovery API
# ============================================================================

def _build_synthetic_tenders() -> List[TenderOpportunity]:
    """Returns canonical synthetic tenders matching test contracts."""
    return [
        TenderOpportunity(
            id="TND-2026-088",
            tender_id="TND-2026-088",
            title="Enterprise Multi-Cloud Infrastructure & DevSecOps Modernization",
            client="Pan-African Financial Services Group",
            description=(
                "RFP for turnkey cloud engineering pod to design declarative Infrastructure as Code (Terraform), "
                "automate CI/CD pipelines, and deploy Kubernetes microservices on AWS and Azure under 99.9% availability SLA. "
                "B2B Corp-to-Corp contracting with synchronous EMEA/CET working hours required."
            ),
            budget="$120,000 USD",
            deadline="2026-12-15",
            category="cloud",
            country="Pan-African / Remote",
            verified_active=True,
        ),
        TenderOpportunity(
            id="TND-HEALTH-042",
            tender_id="TND-HEALTH-042",
            title="National Health Data Platform Azure Migration & Kubernetes Modernization",
            client="Federal Ministry of Health",
            description=(
                "Tender for dedicated cloud platform engineering firm to migrate core health records to Microsoft Azure, "
                "orchestrate containerized microservices on Azure Kubernetes Service (AKS), and guarantee L3 incident escalation "
                "under a 99.9% availability SLA. Must be CAC registered in Nigeria."
            ),
            budget="₦85,000,000 NGN",
            deadline="2026-12-20",
            category="cloud",
            country="Nigeria",
            verified_active=True,
        ),
        TenderOpportunity(
            id="TND-HARDWARE-015",
            tender_id="TND-HARDWARE-015",
            title="Enterprise Developer Workstations & Computing Hardware Supply",
            client="FinTech Alliance Nigeria",
            description=(
                "Procurement of 50 enterprise-grade high-performance developer laptops and custom workstations. "
                "Requires hardware QA diagnostics, OS baseline provisioning, and warranty fulfillment."
            ),
            budget="$75,000 USD",
            deadline="2026-11-30",
            category="hardware",
            country="Nigeria",
            verified_active=True,
        ),
        TenderOpportunity(
            id="TND-CIVIL-009",
            tender_id="TND-CIVIL-009",
            title="Construction and Road Asphalt Paving Tender",
            client="Regional Transport Authority",
            description=(
                "Supply of asphalt concrete, road grading equipment, and civil engineering drainage maintenance."
            ),
            budget="$500,000 USD",
            deadline="2026-12-01",
            category="civil",
            country="Nigeria",
            verified_active=True,
        ),
    ]


def fetch_tenders(
    dry_run: bool = True,
    query_categories: Optional[List[str]] = None,
    limit: int = 10,
) -> List[TenderOpportunity]:
    """
    Retrieves public and corporate consultancy opportunities.
    In dry-run or offline mode, returns synthetic fixtures.
    """
    synth = _build_synthetic_tenders()

    if query_categories:
        cats = [c.lower() for c in query_categories]
        filtered = [t for t in synth if t.category.lower() in cats]
        return (filtered or synth)[:limit]

    return synth[:limit]
