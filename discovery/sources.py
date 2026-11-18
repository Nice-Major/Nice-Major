"""
Multi-Source Job Discovery Engine & Feed Adapters.
Module: discovery.sources
Feature: F08 (Opportunity Discovery Engine)
Milestone: M3 (Opportunity Discovery, Geo-Filtering & Verification)

Provides pluggable adapters for public remote job boards, RSS feeds, and company career pages,
with robust zero-network synthetic fallback when running in dry-run or offline mode.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import load_dotenv_file, settings
from discovery.models import JobOpportunity, JobQueryParams, Opportunity

logger = logging.getLogger(__name__)

USER_AGENT: str = "CareerAutomation/1.0 (+https://nice-major.github.io/Nice-Major/; OpportunityDiscovery)"
DEFAULT_MAX_RESPONSE_BYTES = 512 * 1024
ARBEITNOW_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
JOBICY_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
COMPANY_BOARD_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_COMPANY_BOARDS_PER_SOURCE = 20
COMPANY_BOARD_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "company-boards.json"
LEVER_COUNTRY_NAMES = {
    "fr": "France",
    "ng": "Nigeria",
    "gb": "United Kingdom",
    "us": "United States",
}

CANONICAL_TARGET_ROLES: List[str] = [
    "Cloud Solutions Architect",
    "Cloud Infrastructure Engineer",
    "Cloud Engineer",
    "Dev(Sec)Ops Engineer",
    "System Administrator",
    "IT Specialist/Administrator",
    "Technical Support Engineer",
    "Azure/AWS DevOps Engineer",
]


def _source_setting(name: str) -> str:
    """Resolve provider configuration from the environment or local .env file."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    return load_dotenv_file().get(name, "").strip()


def load_curated_board_entries(source_id: str) -> List[Dict[str, str]]:
    """Load validated public board identifiers from the repository's curated catalog."""
    try:
        with COMPANY_BOARD_CATALOG_PATH.open("r", encoding="utf-8") as catalog_file:
            catalog = json.load(catalog_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Unable to read curated company-board catalog at {COMPANY_BOARD_CATALOG_PATH}: {exc}"
        ) from exc

    sources = catalog.get("sources") if isinstance(catalog, dict) else None
    entries = sources.get(source_id) if isinstance(sources, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"Company-board catalog must define a list for source '{source_id}'.")

    validated: List[Dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Company-board catalog entry for '{source_id}' must be an object.")
        board = str(entry.get("board", "")).strip()
        company = str(entry.get("company", "")).strip()
        if not board or not re.fullmatch(r"[A-Za-z0-9._-]+", board) or not company:
            raise ValueError(f"Invalid board or company name in '{source_id}' company-board catalog.")
        validated.append({"board": board, "company": company})
    return validated


# ============================================================================
# 1. Deterministic Synthetic Opportunities Dataset
# ============================================================================

def _build_synthetic_dataset() -> List[JobOpportunity]:
    """
    Constructs the canonical deterministic synthetic opportunities matching
    candidate John Victor Aniekwe's 8 target roles and pipeline test fixtures.
    """
    return [
        JobOpportunity(
            id="synth-devops-101",
            title="Senior DevOps & Platform Engineer",
            company="Global Cloud Corp",
            location="Remote - Worldwide (EMEA / UTC+1)",
            description=(
                "We are seeking a Senior DevOps Engineer to lead our Kubernetes and Terraform automation. "
                "Must have strong experience in container orchestration (Kubernetes, Docker), Infrastructure as Code "
                "(Terraform), CI/CD pipelines (GitHub Actions), and AWS/Azure cloud platforms. Candidate must ensure "
                "enterprise 99.9% uptime SLAs and integrate DevSecOps controls."
            ),
            url="https://careers.globalcloud.example/jobs/devops-101",
            source="synthetic",
            posted_date="2026-11-01",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$95,000 - $130,000 USD",
            tags=["devops", "kubernetes", "terraform", "aws", "azure", "ci/cd"],
        ),
        JobOpportunity(
            id="synth-csa-202",
            title="Senior Cloud Solutions Architect",
            company="Enterprise Horizons Ltd",
            location="Worldwide Remote / CET Synchronous",
            description=(
                "Looking for a Cloud Solutions Architect to design scalable multi-cloud microservices on Azure and AWS. "
                "Must apply the Well-Architected Framework, architect AKS/EKS clusters, configure private endpoints, "
                "and optimize FinOps cost governance."
            ),
            url="https://careers.enterprisehorizons.example/jobs/csa-202",
            source="synthetic",
            posted_date="2026-11-03",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$110,000 - $150,000 USD",
            tags=["architect", "cloud", "aws", "azure", "aks", "finops"],
        ),
        JobOpportunity(
            id="synth-infra-102",
            title="Lead Cloud Infrastructure Engineer",
            company="Hybrid Systems International",
            location="Remote - Worldwide (EMEA / UTC+1)",
            description=(
                "Hybrid Systems International is hiring a Lead Cloud Infrastructure Engineer. You will manage "
                "hybrid Linux/Windows server fleets, automate cloud provisioning using Terraform, implement VNet "
                "peering and network security groups across AWS and Azure, sustaining 99.9% enterprise uptime."
            ),
            url="https://careers.hybridsystems.example/jobs/infra-102",
            source="synthetic",
            posted_date="2026-11-02",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$90,000 - $125,000 USD",
            tags=["infrastructure", "linux", "windows", "terraform", "networking", "aws", "azure"],
        ),
        JobOpportunity(
            id="synth-cloud-505",
            title="Senior Cloud Platform Engineer",
            company="CloudScale Innovations",
            location="Remote (EMEA / Worldwide)",
            description=(
                "Join CloudScale Innovations as a Senior Cloud Engineer managing cloud infrastructure and Kubernetes "
                "clusters. Responsibilities include building containerized microservices (Docker, Kubernetes), writing "
                "modular Terraform configurations, and maintaining CI/CD deployment pipelines."
            ),
            url="https://careers.cloudscale.example/jobs/cloud-505",
            source="synthetic",
            posted_date="2026-11-04",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$85,000 - $120,000 USD",
            tags=["cloud", "kubernetes", "docker", "terraform", "ci/cd"],
        ),
        JobOpportunity(
            id="synth-sysadmin-401",
            title="Senior Systems Administrator (Linux/Windows)",
            company="Apex Infrastructure Group",
            location="Worldwide Remote (UTC+1 Synchronous)",
            description=(
                "Apex Infrastructure Group seeks an experienced Systems Administrator to maintain enterprise server "
                "environments. Must have deep expertise in Linux (Ubuntu, RHEL) and Windows Server administration, "
                "Active Directory management, PowerShell/Bash scripting, system hardening, and backup recovery protocols."
            ),
            url="https://careers.apexinfra.example/jobs/sysadmin-401",
            source="synthetic",
            posted_date="2026-11-02",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$75,000 - $105,000 USD",
            tags=["sysadmin", "linux", "windows", "active directory", "powershell", "bash"],
        ),
        JobOpportunity(
            id="synth-itadmin-707",
            title="Enterprise IT Specialist / Administrator",
            company="FinTech Alliance Global",
            location="Remote (Anywhere / CET)",
            description=(
                "FinTech Alliance Global is hiring an Enterprise IT Specialist / Administrator. You will configure and "
                "administer Microsoft 365, Azure Active Directory / Entra ID, identity access controls, endpoint management, "
                "hardware diagnostics, and ITIL/ITSM service request fulfillment."
            ),
            url="https://careers.fintechalliance.example/jobs/it-admin-707",
            source="synthetic",
            posted_date="2026-11-03",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$70,000 - $95,000 USD",
            tags=["it specialist", "azure ad", "entra id", "microsoft 365", "itil", "support"],
        ),
        JobOpportunity(
            id="synth-supp-303",
            title="L3 Technical Cloud Support Engineer",
            company="CloudCare Global",
            location="Remote (Anywhere)",
            description=(
                "Seeking an L3 Technical Cloud Support Engineer for production incident escalation on Microsoft Azure App Service. "
                "Deep root-cause analysis (RCA), logs, metrics, distributed traces, and TsG authoring. High CSAT and SLA adherence required."
            ),
            url="https://careers.cloudcare.example/jobs/supp-303",
            source="synthetic",
            posted_date="2026-11-04",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$75,000 - $105,000 USD",
            tags=["support", "azure", "incident escalation", "rca", "troubleshooting"],
        ),
        JobOpportunity(
            id="synth-azure-aws-808",
            title="Multi-Cloud DevOps Engineer (Azure & AWS)",
            company="MultiCloud Solutions Corp",
            location="Remote - Worldwide (EMEA)",
            description=(
                "We are seeking a Multi-Cloud DevOps Engineer proficient in both Azure DevOps and AWS tooling. "
                "Hands-on experience with Terraform, ARM/Bicep, Kubernetes (AKS/EKS), container registries, "
                "automated test gates, and continuous deployment workflows required."
            ),
            url="https://careers.multicloud.example/jobs/azure-aws-808",
            source="synthetic",
            posted_date="2026-11-05",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
            salary_range="$100,000 - $135,000 USD",
            tags=["devops", "azure", "aws", "terraform", "kubernetes", "ci/cd"],
        ),
        # Boundary & Test Fixtures
        JobOpportunity(
            id="synth-visa-uk-909",
            title="Senior Cloud Architect (UK Visa Sponsorship)",
            company="Metropolitan Cloud Partners UK",
            location="London, UK (Relocation & Visa Sponsorship)",
            description=(
                "We offer UK Skilled Worker visa sponsorship and comprehensive relocation assistance to London. "
                "Looking for a Senior Cloud Solutions Architect to lead enterprise migration initiatives."
            ),
            url="https://careers.metropolitancloud.example/jobs/uk-visa-909",
            source="synthetic",
            posted_date="2026-11-04",
            is_remote=False,
            nigeria_eligible=False,
            visa_sponsored=True,
            contract_type="full-time",
            is_active=True,
            salary_range="£85,000 - £110,000 GBP",
            tags=["architect", "cloud", "visa sponsorship", "relocation", "uk"],
        ),
        JobOpportunity(
            id="synth-us-defense-404",
            title="DevOps Engineer (US Defense)",
            company="American Defense Systems",
            location="Remote - US",
            description=(
                "Must be a US Citizen residing in the continental United States. Requires active Secret Clearance. "
                "W2 Only. Candidates outside the US will not be considered."
            ),
            url="https://careers.usdefense.example/jobs/us-404",
            source="synthetic",
            posted_date="2026-11-02",
            is_remote=False,
            nigeria_eligible=False,
            visa_sponsored=False,
            contract_type="w2",
            is_active=True,
            salary_range="$120,000 - $150,000 USD",
            tags=["us only", "secret clearance", "w2 only"],
        ),
        JobOpportunity(
            id="synth-stale-505",
            title="Infrastructure Engineer (Legacy Systems)",
            company="Legacy Tech Ltd",
            location="Worldwide",
            description="Maintain legacy Linux servers. Closed listing.",
            url="https://careers.legacytech.example/jobs/stale-505",
            source="synthetic",
            posted_date="2026-08-01",  # Older than 30 days relative to 2026-11-07
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=False,
            tags=["legacy", "stale"],
        ),
        JobOpportunity(
            id="synth-closed-606",
            title="Cloud Operations Engineer",
            company="QuickFill Inc",
            location="Remote Worldwide",
            description="This position has been filled. Applications are now closed.",
            url="https://careers.quickfill.example/jobs/closed-606",
            source="synthetic",
            posted_date="2026-11-05",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=False,
            tags=["closed", "filled"],
        ),
        JobOpportunity(
            id="synth-tender-b2b-088",
            title="Enterprise Multi-Cloud Infrastructure & DevSecOps Lead (B2B Consultancy)",
            company="Pan-African Financial Services Group",
            location="Worldwide / CET Synchronous",
            description=(
                "RFP for turnkey cloud engineering pod to design declarative Infrastructure as Code (Terraform), "
                "automate CI/CD pipelines, and deploy Kubernetes microservices on AWS and Azure under 99.9% availability SLA. "
                "B2B Corp-to-Corp contracting with synchronous EMEA/CET working hours required."
            ),
            url="https://tenders.panafricanfin.example/tnd-2026-088",
            source="synthetic",
            posted_date="2026-11-05",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="b2b",
            is_active=True,
            salary_range="$120,000 USD Contract",
            tags=["b2b", "c2c", "consultancy", "devops", "cloud", "terraform"],
        ),
    ]


# ============================================================================
# 2. Public Filtering, Normalization & Deduplication Functions
# ============================================================================

def get_synthetic_opportunities(
    query_roles: Optional[List[str]] = None,
) -> List[JobOpportunity]:
    """
    Returns deterministic synthetic opportunities matching candidate's 8 target roles
    and test fixtures. Guaranteed to have >= 8 items when unfiltered and >= 1 when filtered by role.
    """
    all_opps = _build_synthetic_dataset()
    if not query_roles:
        return all_opps

    # Filter by query_roles
    normalized_queries = [r.strip().lower() for r in query_roles if r and r.strip()]
    if not normalized_queries:
        return all_opps

    filtered = []
    for opp in all_opps:
        title_lower = opp.title.lower()
        desc_lower = opp.description.lower()
        tags_lower = [t.lower() for t in opp.tags]

        for q in normalized_queries:
            # Check if query matches title, tags, or description
            if q in title_lower or any(q in t for t in tags_lower) or q in desc_lower:
                filtered.append(opp)
                break

    # If role filter produced nothing, return all non-boundary synthetic jobs as fallback
    if not filtered:
        return [op for op in all_opps if op.is_active and not op.id.startswith("synth-us-")]

    return filtered


def normalize_opportunities(raw_items: List[Any]) -> List[JobOpportunity]:
    """
    Normalizes a list of dictionary or object items into valid JobOpportunity instances.
    Filters out corrupted or incomplete items (must contain valid non-empty title, company, and url).
    Fulfills test_f08_b3_malformed_api_item_filtered_out.
    """
    normalized: List[JobOpportunity] = []
    if not raw_items or not isinstance(raw_items, (list, tuple)):
        return normalized

    for item in raw_items:
        if not item or not isinstance(item, (dict, JobOpportunity)):
            continue

        if isinstance(item, JobOpportunity):
            t = str(getattr(item, "title", "") or "").strip()
            c = str(getattr(item, "company", "") or "").strip()
            u = str(getattr(item, "url", "") or "").strip()
            if t and c and u and t.lower() != "none" and c.lower() != "none" and u.lower() != "none":
                normalized.append(item)
            continue

        # Item is a dict
        raw_title = item.get("title")
        raw_company = item.get("company")
        raw_url = item.get("url") if item.get("url") is not None else item.get("link")

        # Reject None fields
        if raw_title is None or raw_company is None or raw_url is None:
            continue

        title = str(raw_title).strip()
        company = str(raw_company).strip()
        url = str(raw_url).strip()

        # Reject empty or literal 'none' strings
        if not title or not company or not url or title.lower() == "none" or company.lower() == "none" or url.lower() == "none":
            continue

        # Construct JobOpportunity
        opp = JobOpportunity.from_dict(item)
        normalized.append(opp)

    return normalized


def deduplicate_opportunities(opportunities: List[Any]) -> List[Any]:
    """
    Deduplicates opportunities based on SHA-256 fingerprint of (company, title)
    or unique application URL.
    Preserves the first occurrence and drops duplicates while maintaining original item type.
    Fulfills test_f08_b4_duplicate_jobs_merged.
    """
    if not opportunities or not isinstance(opportunities, (list, tuple)):
        return []

    from discovery.verifier import generate_fingerprint

    seen_fingerprints: Set[str] = set()
    seen_urls: Set[str] = set()
    seen_ids: Set[str] = set()
    deduped: List[Any] = []

    for opp in opportunities:
        if opp is None:
            continue

        if isinstance(opp, dict):
            company = str(opp.get("company", "") or "").strip()
            title = str(opp.get("title", "") or "").strip()
            url = str(opp.get("url", opp.get("link", "")) or "").strip().lower()
            opp_id = str(opp.get("id", "") or "").strip()
        else:
            company = str(getattr(opp, "company", "") or "").strip()
            title = str(getattr(opp, "title", "") or "").strip()
            url = str(getattr(opp, "url", "") or "").strip().lower()
            opp_id = str(getattr(opp, "id", "") or "").strip()

        # Compute fingerprint with internal whitespace normalization
        # Guard against empty company/title collisions (only fingerprint when company and title exist)
        has_text_ident = bool(company and title)
        fp = generate_fingerprint(company, title) if has_text_ident else None

        if (fp and fp in seen_fingerprints) or (url and url in seen_urls) or (not has_text_ident and not url and opp_id and opp_id in seen_ids):
            continue

        if not has_text_ident and not url and not opp_id:
            raw_repr = str(sorted(opp.items(), key=lambda kv: (str(kv[0]), type(kv[0]).__name__))) if isinstance(opp, dict) else str(opp)
            if raw_repr in seen_urls:
                continue
            seen_urls.add(raw_repr)

        if fp:
            seen_fingerprints.add(fp)
        if url:
            seen_urls.add(url)
        if opp_id:
            seen_ids.add(opp_id)
        deduped.append(opp)

    return deduped


# ============================================================================
# 3. Base & Concrete Source Adapters
# ============================================================================

class BaseSourceAdapter(ABC):
    """Abstract base class for all recruitment platform adapters."""
    source_id: str = "base"
    name: str = "Base Source Adapter"

    def fetch_url(
        self,
        url: str,
        timeout: int = 5,
        max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> Tuple[int, bytes]:
        """Safely fetch HTTP endpoint using Python standard urllib with legitimate User-Agent."""
        req = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/xml, text/html, */*",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read(max_bytes)
                return status, body
        except HTTPError as e:
            return e.code, b""
        except (URLError, Exception) as e:
            logger.debug("Source adapter fetch failed for %s: %s", url, e)
            return 0, b""

    @abstractmethod
    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        """Fetches and parses job opportunities from the source."""
        pass


class RemoteOKAdapter(BaseSourceAdapter):
    """Adapter for RemoteOK public API."""
    source_id = "remoteok"
    name = "RemoteOK API"
    BASE_URL = "https://remoteok.com/api"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        status, body = self.fetch_url(self.BASE_URL, timeout=timeout)
        if status != 200 or not body:
            return []

        try:
            items = json.loads(body.decode("utf-8"))
            if not isinstance(items, list):
                return []
            opportunities: List[JobOpportunity] = []
            for item in items:
                # RemoteOK first element is usually a legal notice
                if not isinstance(item, dict) or "position" not in item:
                    continue
                opp = JobOpportunity(
                    id=str(item.get("id", "")),
                    title=str(item.get("position", "")),
                    company=str(item.get("company", "")),
                    location=str(item.get("location", "Remote - Worldwide")),
                    description=str(item.get("description", "")),
                    url=str(item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id', '')}")),
                    source=self.source_id,
                    posted_date=str(item.get("date", "")).split("T")[0],
                    is_remote=True,
                    tags=list(item.get("tags", [])),
                    raw_data=item,
                )
                opportunities.append(opp)
            return _filter_roles(opportunities, query_roles)[:limit]
        except Exception as e:
            logger.debug(f"RemoteOK parsing error: {e}")
            return []


class WeWorkRemotelyAdapter(BaseSourceAdapter):
    """Adapter for WeWorkRemotely public RSS feeds."""
    source_id = "weworkremotely"
    name = "We Work Remotely RSS"
    FEED_URLS = [
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    ]

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        opportunities: List[JobOpportunity] = []
        for feed_url in self.FEED_URLS:
            status, body = self.fetch_url(feed_url, timeout=timeout)
            if status != 200 or not body:
                continue
            try:
                root = ET.fromstring(body)
                for item in root.findall(".//item"):
                    raw_title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    description = item.findtext("description", "")
                    pub_date = item.findtext("pubDate", "")

                    # Extract company and title: "Company: Job Title"
                    company = ""
                    title = raw_title
                    if ":" in raw_title:
                        parts = raw_title.split(":", 1)
                        company = parts[0].strip()
                        title = parts[1].strip()
                    restricted_remote = re.search(
                        r"\bremote\s+(?:eligible|available)\s+in\s+([A-Za-z][A-Za-z -]*?)(?=\s*(?:[)\],.;:]|$))",
                        f"{raw_title} {description}",
                        flags=re.IGNORECASE,
                    )
                    location = (
                        f"Remote - {restricted_remote.group(1).strip()}"
                        if restricted_remote
                        else "Remote - Worldwide"
                    )

                    opp = JobOpportunity(
                        title=title,
                        company=company or "Remote Company",
                        location=location,
                        description=description,
                        url=link,
                        source=self.source_id,
                        posted_date=pub_date,
                        is_remote=True,
                    )
                    opportunities.append(opp)
            except Exception as e:
                logger.debug(f"WWR feed parsing error: {e}")
                continue
        return _filter_roles(opportunities, query_roles)[:limit]


class JobicyAdapter(BaseSourceAdapter):
    """Adapter for Jobicy public remote jobs API."""
    source_id = "jobicy"
    name = "Jobicy Remote Jobs"
    BASE_URL = "https://jobicy.com/api/jobs"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        count = min(max(limit, 1), 100)
        status, body = self.fetch_url(
            f"{self.BASE_URL}?count={count}",
            timeout=timeout,
            max_bytes=JOBICY_MAX_RESPONSE_BYTES,
        )
        if status != 200 or not body:
            return []
        try:
            data = json.loads(body.decode("utf-8"))
            jobs = data.get("jobs", []) if isinstance(data, dict) else []
            if not isinstance(jobs, list):
                logger.warning("Jobicy response did not contain a jobs list.")
                return []
            opportunities: List[JobOpportunity] = []
            for item in jobs:
                if not isinstance(item, dict):
                    continue
                geography = str(item.get("jobGeo", "") or "").strip()
                location = (
                    f"Remote - {geography}"
                    if geography and geography.casefold() not in {"remote", "n/a", "not specified"}
                    else "Remote"
                )
                opp = JobOpportunity(
                    id=str(item.get("id", "")),
                    title=str(item.get("jobTitle", "")),
                    company=str(item.get("companyName", "")),
                    location=location,
                    description=str(item.get("jobDescription", "")),
                    url=str(item.get("url", "")),
                    source=self.source_id,
                    posted_date=str(
                        item.get("publishedAt")
                        or item.get("pubDate")
                        or item.get("publicationDate")
                        or ""
                    ).split("T")[0],
                    is_remote=True,
                    salary_range=str(item.get("salaryRange") or item.get("annualSalaryMin") or ""),
                    raw_data=item,
                )
                opportunities.append(opp)
            return _filter_roles(opportunities, query_roles)[:limit]
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Jobicy response parsing failed: %s", exc)
            return []


class RemotiveAdapter(BaseSourceAdapter):
    """Single-request daily adapter for Remotive's public remote-jobs API."""
    source_id = "remotive"
    name = "Remotive Remote Jobs"
    BASE_URL = "https://remotive.com/api/remote-jobs?limit=100"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        status, body = self.fetch_url(self.BASE_URL, timeout=timeout)
        if status != 200 or not body:
            return []
        try:
            jobs = json.loads(body.decode("utf-8")).get("jobs", [])
            opportunities = []
            for item in jobs:
                if not isinstance(item, dict):
                    continue
                opportunities.append(JobOpportunity(
                    id=str(item.get("id", "")),
                    title=str(item.get("title", "")),
                    company=str(item.get("company_name", "")),
                    location=str(item.get("candidate_required_location", "Remote")),
                    description=str(item.get("description", "")),
                    url=str(item.get("url", "")),
                    source=self.source_id,
                    posted_date=str(item.get("publication_date", "")).split("T")[0],
                    is_remote=True,
                    tags=[str(item.get("category", ""))] + [
                        str(tag) for tag in item.get("tags", [])
                    ],
                    raw_data=item,
                ))
            return _filter_roles(opportunities, query_roles)[:limit]
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Remotive response parsing failed: %s", exc)
            return []


class ArbeitnowAdapter(BaseSourceAdapter):
    """Adapter for Arbeitnow's public job-board API."""
    source_id = "arbeitnow"
    name = "Arbeitnow Job Board"
    BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        status, body = self.fetch_url(
            self.BASE_URL,
            timeout=timeout,
            max_bytes=ARBEITNOW_MAX_RESPONSE_BYTES,
        )
        if status != 200 or not body:
            return []
        try:
            jobs = json.loads(body.decode("utf-8")).get("data", [])
            opportunities = []
            for item in jobs:
                if not isinstance(item, dict):
                    continue
                opportunities.append(JobOpportunity(
                    id=str(item.get("slug", "")),
                    title=str(item.get("title", "")),
                    company=str(item.get("company_name", "")),
                    location=str(item.get("location", "")),
                    description=str(item.get("description", "")),
                    url=str(item.get("url", "")),
                    source=self.source_id,
                    posted_date=str(item.get("created_at", ""))[:10],
                    is_remote=bool(item.get("remote", False)),
                    tags=[str(tag) for tag in item.get("tags", [])],
                    raw_data=item,
                ))
            return _filter_roles(opportunities, query_roles)[:limit]
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Arbeitnow response parsing failed: %s", exc)
            return []


class CompanyBoardAdapter(BaseSourceAdapter):
    """Public job listings from explicitly configured Greenhouse, Lever, or Ashby boards."""

    def __init__(self, source_id: str, name: str, env_var: str):
        self.source_id = source_id
        self.name = name
        self.env_var = env_var

    def _board_url(self, board: str) -> str:
        if self.source_id == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
        if self.source_id == "lever":
            is_eu = board.casefold().startswith("eu:")
            site_name = board[3:] if is_eu else board
            api_host = "api.eu.lever.co" if is_eu else "api.lever.co"
            return f"https://{api_host}/v0/postings/{site_name}?mode=json"
        return f"https://api.ashbyhq.com/posting-api/job-board/{board}"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        if limit <= 0:
            return []
        boards = load_curated_board_entries(self.source_id)
        seen_boards = {entry["board"].casefold() for entry in boards}
        for configured_board in _source_setting(self.env_var).split(","):
            board = configured_board.strip()
            board_name = board[3:] if self.source_id == "lever" and board.casefold().startswith("eu:") else board
            if re.fullmatch(r"[A-Za-z0-9._-]+", board_name) and board.casefold() not in seen_boards:
                boards.append({"board": board, "company": board_name})
                seen_boards.add(board.casefold())
        if not boards:
            logger.info("%s adapter has no configured board identifiers (%s).", self.name, self.env_var)
            return []
        if len(boards) > MAX_COMPANY_BOARDS_PER_SOURCE:
            logger.warning(
                "%s has %d configured boards; limiting this run to %d.",
                self.name,
                len(boards),
                MAX_COMPANY_BOARDS_PER_SOURCE,
            )
            boards = boards[:MAX_COMPANY_BOARDS_PER_SOURCE]

        opportunities_by_board: List[List[JobOpportunity]] = []
        for board_entry in boards:
            board = board_entry["board"]
            board_company = board_entry["company"]
            status, body = self.fetch_url(
                self._board_url(board),
                timeout=timeout,
                max_bytes=COMPANY_BOARD_MAX_RESPONSE_BYTES,
            )
            if status != 200 or not body:
                if status:
                    logger.warning("%s board '%s' returned HTTP %d.", self.name, board, status)
                continue
            try:
                payload = json.loads(body.decode("utf-8"))
                if self.source_id == "greenhouse":
                    postings = payload.get("jobs", [])
                elif self.source_id == "lever":
                    postings = payload if isinstance(payload, list) else []
                else:
                    postings = payload.get("jobs", [])
                board_opportunities: List[JobOpportunity] = []
                for item in postings:
                    if not isinstance(item, dict):
                        continue
                    categories = item.get("categories")
                    if not isinstance(categories, dict):
                        categories = {}
                    if self.source_id == "lever":
                        title = item.get("text", item.get("title", ""))
                        location_value = categories.get("location", item.get("location", ""))
                        description = (
                            item.get("descriptionPlain")
                            or item.get("description")
                            or item.get("openingPlain")
                            or ""
                        )
                        posting_url = item.get("hostedUrl", item.get("applyUrl", ""))
                        is_remote = str(item.get("workplaceType", "")).casefold() == "remote"
                        country = item.get("country")
                        if isinstance(country, dict):
                            country = country.get("name") or country.get("code")
                        country = str(country or "").strip()
                        if country and is_remote:
                            country_name = LEVER_COUNTRY_NAMES.get(country.casefold(), country)
                            location_text = str(location_value or "").strip()
                            if not re.search(r"\b(?:worldwide|anywhere|global)\b", location_text, re.IGNORECASE):
                                location_value = f"Remote - {country_name}"
                        posted_date = item.get("createdAt", item.get("updatedAt", ""))
                    else:
                        title = item.get("title", "")
                        location_value = item.get("location", categories.get("location", ""))
                        description = item.get(
                            "content",
                            item.get("descriptionPlain", item.get("description", "")),
                        )
                        posting_url = item.get(
                            "absolute_url",
                            item.get("hostedUrl", item.get("jobUrl", "")),
                        )
                        is_remote = bool(item.get("isRemote", False))
                        posted_date = item.get("updatedAt", item.get("createdAt", ""))
                    if isinstance(location_value, dict):
                        location_value = location_value.get("name", "")
                    if isinstance(description, dict):
                        description = description.get("text", "")
                    company = item.get("companyName", board_company)
                    board_opportunities.append(JobOpportunity(
                        id=str(item.get("id", "")),
                        title=str(title),
                        company=str(company or board_company),
                        location=str(location_value or ""),
                        description=str(description or ""),
                        url=str(posting_url),
                        source=self.source_id,
                        posted_date=str(posted_date)[:10],
                        is_remote=is_remote,
                        raw_data=item,
                    ))
                opportunities_by_board.append(_filter_roles(board_opportunities, query_roles))
            except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("%s board '%s' response parsing failed: %s", self.name, board, exc)
        diversified: List[JobOpportunity] = []
        for posting_index in range(max((len(jobs) for jobs in opportunities_by_board), default=0)):
            for board_jobs in opportunities_by_board:
                if posting_index < len(board_jobs):
                    diversified.append(board_jobs[posting_index])
                    if len(diversified) >= limit:
                        return diversified
        return diversified


def _filter_roles(
    opportunities: List[JobOpportunity],
    query_roles: Optional[List[str]],
) -> List[JobOpportunity]:
    if not query_roles:
        return opportunities
    terms = set()
    for role in query_roles:
        normalized = role.casefold()
        if any(keyword in normalized for keyword in ("devops", "dev(sec)ops")):
            terms.update(("devops", "devsecops", "platform", "site reliability", "sre"))
        if "cloud" in normalized:
            terms.add("cloud")
        if any(keyword in normalized for keyword in ("system", "infrastructure")):
            terms.update(("system", "infrastructure", "administrator", "linux"))
        if any(keyword in normalized for keyword in ("support", "specialist")):
            terms.update(("support", "specialist", "it administrator"))
        if not terms:
            terms.update(re.findall(r"[a-z0-9]+", normalized))
    return [
        opportunity
        for opportunity in opportunities
        if any(
            term in f"{opportunity.title} {' '.join(opportunity.tags)}".casefold()
            for term in terms
        )
    ]


class RssFeedAdapter(BaseSourceAdapter):
    """Adapter for arbitrary generic RSS/Atom feeds."""
    source_id = "rss_feed"
    name = "Generic RSS/Atom Feed"

    def __init__(self, feed_url: str = ""):
        self.feed_url = feed_url

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        if not self.feed_url:
            return []
        status, body = self.fetch_url(self.feed_url, timeout=timeout)
        if status != 200 or not body:
            return []
        try:
            root = ET.fromstring(body)
            opportunities: List[JobOpportunity] = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                opp = JobOpportunity(
                    title=title,
                    company="Feed Sponsor",
                    location="Remote",
                    description=description,
                    url=link,
                    source=self.source_id,
                    posted_date=pub_date,
                    is_remote=True,
                )
                opportunities.append(opp)
                if len(opportunities) >= limit:
                    break
            return _filter_roles(opportunities, query_roles)[:limit]
        except Exception as e:
            logger.debug(f"Generic RSS feed parse error: {e}")
            return []


class CompanyCareerPageAdapter(BaseSourceAdapter):
    """Adapter for scraping career portals and structured schema.org JobPosting JSON-LD."""
    source_id = "career_page"
    name = "Company Career Portal"

    def __init__(self, page_url: str = ""):
        self.page_url = page_url

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        if not self.page_url:
            return []
        status, body = self.fetch_url(self.page_url, timeout=timeout)
        if status != 200 or not body:
            return []
        try:
            html_text = body.decode("utf-8", errors="replace")
            # Look for JSON-LD JobPosting
            json_ld_matches = re.findall(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html_text,
                re.DOTALL | re.IGNORECASE,
            )
            opportunities: List[JobOpportunity] = []
            for block in json_ld_matches:
                try:
                    data = json.loads(block.strip())
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        opp = JobOpportunity(
                            title=str(data.get("title", "")),
                            company=str(data.get("hiringOrganization", {}).get("name", "")),
                            location=str(data.get("jobLocation", {}).get("address", {}).get("addressLocality", "Remote")),
                            description=str(data.get("description", "")),
                            url=str(data.get("url", self.page_url)),
                            source=self.source_id,
                            posted_date=str(data.get("datePosted", "")),
                            is_remote=True,
                        )
                        opportunities.append(opp)
                except Exception:
                    continue
            return opportunities[:limit]
        except Exception as e:
            logger.debug(f"Career page parsing error: {e}")
            return []


class SyntheticSourceAdapter(BaseSourceAdapter):
    """Deterministic zero-network synthetic adapter returning canonical candidate opportunities."""
    source_id = "synthetic"
    name = "Synthetic Offline Generator"

    def fetch(
        self,
        query_roles: Optional[List[str]] = None,
        limit: int = 20,
        timeout: int = 5,
    ) -> List[JobOpportunity]:
        synth = get_synthetic_opportunities(query_roles=query_roles)
        return synth[:limit]


# ============================================================================
# 4. Adapter Registry
# ============================================================================

class AdapterRegistry:
    """Registry maintaining active and pluggable discovery adapters."""
    def __init__(self) -> None:
        self._adapters: Dict[str, BaseSourceAdapter] = {}
        # Register standard built-in adapters
        self.register(SyntheticSourceAdapter())
        self.register(RemoteOKAdapter())
        self.register(WeWorkRemotelyAdapter())
        self.register(JobicyAdapter())
        self.register(RemotiveAdapter())
        self.register(ArbeitnowAdapter())
        self.register(CompanyBoardAdapter("greenhouse", "Greenhouse Public Job Boards", "GREENHOUSE_BOARD_TOKENS"))
        self.register(CompanyBoardAdapter("lever", "Lever Public Job Boards", "LEVER_SITE_NAMES"))
        self.register(CompanyBoardAdapter("ashby", "Ashby Public Job Boards", "ASHBY_BOARD_NAMES"))

    def register(self, adapter: BaseSourceAdapter) -> None:
        self._adapters[adapter.source_id.lower()] = adapter

    def get(self, source_id: str) -> Optional[BaseSourceAdapter]:
        return self._adapters.get(source_id.lower())

    def get_all(self) -> List[BaseSourceAdapter]:
        return list(self._adapters.values())

    def list_sources(self) -> List[str]:
        return list(self._adapters.keys())


registry = AdapterRegistry()


# ============================================================================
# 5. Core Discovery Engine Interfaces
# ============================================================================

def fetch_opportunities(
    query_roles: Optional[List[str]] = None,
    dry_run: bool = True,
    simulate_timeout: bool = False,
    sources: Optional[List[str]] = None,
    limit: int = 20,
    offline_mode: Optional[bool] = None,
    **kwargs: Any,
) -> List[JobOpportunity]:
    """
    Primary interface function required by PROJECT.md (line 116) and E2E test suite.

    Behavior:
    1. If simulate_timeout=True: Immediately triggers offline synthetic fallback.
    2. If settings.offline_mode or dry_run: Returns deterministic synthetic opportunities.
    3. If query_roles is None or empty ([]): Defaults to all canonical target roles.
    4. If sources specified: Filters active adapters; falls back safely on unknown source names.
    5. Normalizes and deduplicates results.
    6. Returns list of JobOpportunity objects.
    """
    # Boundary defense: empty list defaults to all target roles
    roles_to_query = query_roles
    if roles_to_query is not None and len(roles_to_query) == 0:
        roles_to_query = None

    # Determine offline / dry-run posture
    is_offline = (
        offline_mode
        if offline_mode is not None
        else (getattr(settings, "offline_mode", True) or getattr(settings, "dry_run", True) or dry_run)
    )

    # Simulated timeout or offline mode -> synthetic fallback immediately
    if simulate_timeout or is_offline:
        raw_synth = get_synthetic_opportunities(query_roles=roles_to_query)
        normalized = normalize_opportunities(raw_synth)
        deduped = deduplicate_opportunities(normalized)
        return deduped[:limit]

    # Live discovery execution across registered source adapters.
    # Preserve per-source batches so a large feed cannot consume the global limit
    # before the remaining providers have contributed.
    source_batches: List[List[JobOpportunity]] = []
    adapters_to_use: List[BaseSourceAdapter] = []

    if sources:
        for s in sources:
            adapter = registry.get(s)
            if adapter:
                adapters_to_use.append(adapter)
            else:
                logger.warning(f"Unknown source provider '{s}', skipping.")
    else:
        adapters_to_use = [
            a for a in registry.get_all() if not isinstance(a, SyntheticSourceAdapter)
        ]

    for adapter in adapters_to_use:
        try:
            found = adapter.fetch(query_roles=roles_to_query, limit=limit)
            normalized_source = normalize_opportunities(found)
            source_batches.append(normalized_source)
            logger.info("Discovery source %s returned %d valid postings.", adapter.source_id, len(normalized_source))
        except Exception as e:
            logger.warning(f"Adapter '{adapter.name}' failed during fetch: {e}")

    if not any(source_batches):
        logger.warning(
            "Live discovery returned no postings from configured sources; synthetic opportunities are not used in live mode."
        )

    results: List[JobOpportunity] = []
    for index in range(max((len(batch) for batch in source_batches), default=0)):
        for batch in source_batches:
            if index < len(batch):
                results.append(batch[index])

    normalized = normalize_opportunities(results)
    deduped = deduplicate_opportunities(normalized)
    return deduped[:limit]


def search_opportunities(
    query_params: Optional[Union[JobQueryParams, Dict[str, Any]]] = None,
    limit: int = 20,
) -> List[JobOpportunity]:
    """
    Search opportunities using a query dictionary or JobQueryParams object.
    Extracts roles, keywords, remote flags, and execution modes.
    """
    if query_params is None:
        params = JobQueryParams()
    elif isinstance(query_params, dict):
        params = JobQueryParams.from_dict(query_params)
    elif isinstance(query_params, JobQueryParams):
        params = query_params
    else:
        params = JobQueryParams()

    return fetch_opportunities(
        query_roles=params.query_roles,
        dry_run=params.dry_run,
        simulate_timeout=params.simulate_timeout,
        sources=params.sources if params.sources else None,
        limit=params.limit or limit,
    )
