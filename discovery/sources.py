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
import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import settings
from discovery.models import JobOpportunity, JobQueryParams, Opportunity

logger = logging.getLogger(__name__)

USER_AGENT: str = "CareerAutomation/1.0 (+https://nice-major.github.io/Nice-Major/; OpportunityDiscovery)"

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

    def fetch_url(self, url: str, timeout: int = 5) -> Tuple[int, bytes]:
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
                body = response.read(524288)  # Read up to 512KB
                return status, body
        except HTTPError as e:
            return e.code, b""
        except (URLError, Exception) as e:
            logger.debug(f"Source adapter fetch failed for {url}: {e}")
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
                if len(opportunities) >= limit:
                    break
            return opportunities
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

                    opp = JobOpportunity(
                        title=title,
                        company=company or "Remote Company",
                        location="Remote - Worldwide",
                        description=description,
                        url=link,
                        source=self.source_id,
                        posted_date=pub_date,
                        is_remote=True,
                    )
                    opportunities.append(opp)
                    if len(opportunities) >= limit:
                        return opportunities
            except Exception as e:
                logger.debug(f"WWR feed parsing error: {e}")
                continue
        return opportunities


class JobicyAdapter(BaseSourceAdapter):
    """Adapter for Jobicy public remote jobs API."""
    source_id = "jobicy"
    name = "Jobicy Remote Jobs"
    BASE_URL = "https://jobicy.com/api/v2/remote-jobs?count=20"

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
            data = json.loads(body.decode("utf-8"))
            jobs = data.get("jobs", [])
            opportunities: List[JobOpportunity] = []
            for item in jobs:
                opp = JobOpportunity(
                    id=str(item.get("id", "")),
                    title=str(item.get("jobTitle", "")),
                    company=str(item.get("companyName", "")),
                    location=str(item.get("jobGeo", "Remote")),
                    description=str(item.get("jobDescription", "")),
                    url=str(item.get("url", "")),
                    source=self.source_id,
                    posted_date=str(item.get("pubDate", "")).split("T")[0],
                    is_remote=True,
                    salary_range=str(item.get("annualSalaryMin", "")),
                    raw_data=item,
                )
                opportunities.append(opp)
                if len(opportunities) >= limit:
                    break
            return opportunities
        except Exception as e:
            logger.debug(f"Jobicy API parsing error: {e}")
            return []


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
            return opportunities
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

    # Live discovery execution across registered source adapters
    results: List[JobOpportunity] = []
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
            results.extend(found)
        except Exception as e:
            logger.warning(f"Adapter '{adapter.name}' failed during fetch: {e}")

    # Fall back to synthetic if live search returned nothing or on unknown sources
    if not results:
        results = get_synthetic_opportunities(query_roles=roles_to_query)

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
