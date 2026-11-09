"""
Domain Entities and Data Models for Career Automation & Stepcon Pipeline.
Module: ingestion.models
Feature: F02 (Profile Representation & Schema Modeling)

Complies with Python 3.10+, zero external dependencies, strict ATS guidelines,
and statutory CAC RC - 8284984 validation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union


# ============================================================================
# 1. Core Component Entities
# ============================================================================

@dataclass
class Education:
    """Educational qualification credential."""
    degree: str = ""
    institution: str = ""
    period: str = ""
    major: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Education:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            degree=str(data.get("degree", "")),
            institution=str(data.get("institution", "")),
            period=str(data.get("period", "")),
            major=str(data.get("major", "")),
        )


@dataclass
class Certification:
    """Formal professional certification credential."""
    name: str = ""
    issuer: str = ""
    year: str = "Active"
    verified: bool = True
    status: str = "Active"
    credly_tracker_link_policy: str = "no_external_tracker_links"
    tags: List[str] = field(default_factory=list)
    credential_id: str = ""
    verification_url: str = ""

    def __init__(
        self,
        name: str = "",
        issuer: str = "",
        year: str = "Active",
        verified: bool = True,
        status: str = "Active",
        credly_tracker_link_policy: str = "no_external_tracker_links",
        tags: Optional[List[str]] = None,
        credential_id: str = "",
        verification_url: str = "",
        **kwargs: Any,
    ):
        self.name = str(kwargs.get("name", name))
        self.issuer = str(kwargs.get("issuer", issuer))
        self.status = str(kwargs.get("status", status))
        self.year = str(kwargs.get("year", kwargs.get("issueDate", year)))
        
        # Determine verified flag
        if "verified" in kwargs:
            self.verified = bool(kwargs["verified"])
        else:
            self.verified = verified if verified is not None else (self.status.lower() == "active")

        self.credly_tracker_link_policy = str(
            kwargs.get("credlyTrackerLinkPolicy", kwargs.get("credly_tracker_link_policy", credly_tracker_link_policy))
        )
        self.tags = list(kwargs.get("tags", tags or []))
        self.credential_id = str(kwargs.get("credentialId", kwargs.get("credential_id", credential_id)))
        self.verification_url = str(kwargs.get("verificationUrl", kwargs.get("verification_url", verification_url)))

    @property
    def is_active(self) -> bool:
        return self.status.lower() == "active"

    @property
    def credlyTrackerLinkPolicy(self) -> str:
        return self.credly_tracker_link_policy

    @property
    def credentialId(self) -> str:
        return self.credential_id

    @property
    def verificationUrl(self) -> str:
        return self.verification_url

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "issuer": self.issuer,
            "year": self.year,
            "verified": self.verified,
            "status": self.status,
            "credlyTrackerLinkPolicy": self.credly_tracker_link_policy,
            "tags": self.tags,
            "credentialId": self.credential_id,
            "verificationUrl": self.verification_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Certification:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(**data)


@dataclass
class KpiMetric:
    """Empirical production performance accomplishment."""
    metric: str = ""
    value: str = ""
    context: str = ""

    def __init__(
        self,
        metric: str = "",
        value: str = "",
        context: str = "",
        label: Optional[str] = None,
        **kwargs: Any,
    ):
        self.value = str(kwargs.get("value", value))
        self.metric = str(kwargs.get("metric", kwargs.get("label", label or metric)))
        ctx = str(kwargs.get("context", context))
        # Supply sensible default context for canonical metrics if missing
        if not ctx:
            if "99.9%" in self.value:
                ctx = "Sustained enterprise uptime across AWS and Azure estates"
            elif "99%" in self.value:
                ctx = "First-day L3 issue resolution rate for Azure App Service"
            elif "60%" in self.value:
                ctx = "AI prediction engine accuracy on AKS pods/nodes"
            elif "15" in self.value:
                ctx = "Terraform and ARM/Bicep IaC provisioning reduced from hours"
        self.context = ctx

    @property
    def label(self) -> str:
        return self.metric

    @label.setter
    def label(self, val: str) -> None:
        self.metric = val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "label": self.metric,
            "value": self.value,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KpiMetric:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(**data)


@dataclass
class RoleCategory:
    """Architectural persona lens definition."""
    title: str = ""
    level: str = "Senior"
    summary: str = ""
    core_keywords: List[str] = field(default_factory=list)
    headline: str = ""
    target_titles: List[str] = field(default_factory=list)
    key: str = ""

    def __init__(
        self,
        title: str = "",
        level: str = "Senior",
        summary: str = "",
        core_keywords: Optional[List[str]] = None,
        headline: str = "",
        target_titles: Optional[List[str]] = None,
        key: str = "",
        category_title: Optional[str] = None,
        categoryTitle: Optional[str] = None,
        **kwargs: Any,
    ):
        self.title = str(categoryTitle or category_title or kwargs.get("title", title))
        self.level = str(kwargs.get("level", level))
        self.summary = str(kwargs.get("summary", summary))
        
        raw_targets = kwargs.get("targetTitles", kwargs.get("target_titles", target_titles or []))
        self.target_titles = list(raw_targets)

        raw_keywords = kwargs.get("coreKeywords", kwargs.get("core_keywords", core_keywords or []))
        self.core_keywords = list(raw_keywords) if raw_keywords else list(self.target_titles)

        self.headline = str(kwargs.get("headline", headline))
        self.key = str(kwargs.get("key", key))

    @property
    def category_title(self) -> str:
        return self.title

    @property
    def categoryTitle(self) -> str:
        return self.title

    @property
    def coreKeywords(self) -> List[str]:
        return self.core_keywords

    @property
    def targetTitles(self) -> List[str]:
        return self.target_titles

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "categoryTitle": self.title,
            "level": self.level,
            "summary": self.summary,
            "coreKeywords": self.core_keywords,
            "targetTitles": self.target_titles,
            "headline": self.headline,
            "key": self.key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], key: str = "") -> RoleCategory:
        if not data or not isinstance(data, dict):
            return cls(key=key)
        data_copy = dict(data)
        resolved_key = key or str(data_copy.pop("key", ""))
        data_copy.pop("key", None)
        return cls(key=resolved_key, **data_copy)


@dataclass
class BulletPoint:
    """Individual achievement statement with role tags and metrics."""
    text: str = ""
    tags: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> BulletPoint:
        if isinstance(data, str):
            return cls(text=data, tags=["all"])
        if isinstance(data, dict):
            return cls(
                text=str(data.get("text", "")),
                tags=list(data.get("tags", [])),
                metrics=list(data.get("metrics", [])),
            )
        return cls()


@dataclass
class WorkExperience:
    """Employment tenure with role lenses and tagged achievements."""
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    bullets: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    period: str = ""
    titles: Dict[str, str] = field(default_factory=dict)
    raw_bullets: List[BulletPoint] = field(default_factory=list)

    def __init__(
        self,
        company: str = "",
        role: str = "",
        start_date: str = "",
        end_date: str = "",
        location: str = "",
        bullets: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        period: str = "",
        titles: Optional[Dict[str, str]] = None,
        raw_bullets: Optional[List[BulletPoint]] = None,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None,
        **kwargs: Any,
    ):
        self.company = str(kwargs.get("company", company))
        self.location = str(kwargs.get("location", location))
        self.period = str(kwargs.get("period", period))
        
        s_date = str(startDate or kwargs.get("start_date", start_date))
        e_date = str(endDate or kwargs.get("end_date", end_date))

        # Derive start and end dates from period if empty
        if self.period and not s_date and ("–" in self.period or "-" in self.period):
            parts = re.split(r"\s*[–-]\s*", self.period)
            if len(parts) >= 2:
                s_date = parts[0].strip()
                e_date = parts[1].strip()

        self.start_date = s_date
        self.end_date = e_date

        self.titles = dict(kwargs.get("titles", titles or {}))
        
        # Primary role resolution
        p_role = str(kwargs.get("role", role))
        if not p_role and self.titles:
            p_role = self.titles.get("devops", next(iter(self.titles.values())))
        self.role = p_role

        # Process bullets
        in_bullets = kwargs.get("bullets", bullets or [])
        flat_b: List[str] = []
        parsed_raw: List[BulletPoint] = []
        tags_set = set(kwargs.get("tags", tags or []))

        for b_entry in in_bullets:
            if isinstance(b_entry, BulletPoint):
                parsed_raw.append(b_entry)
                flat_b.append(b_entry.text)
                for t in b_entry.tags:
                    tags_set.add(t)
            elif isinstance(b_entry, dict):
                bp = BulletPoint.from_dict(b_entry)
                parsed_raw.append(bp)
                flat_b.append(bp.text)
                for t in bp.tags:
                    tags_set.add(t)
            elif isinstance(b_entry, str):
                bp = BulletPoint(text=b_entry, tags=["all"])
                parsed_raw.append(bp)
                flat_b.append(b_entry)

        self.bullets = flat_b
        self.raw_bullets = raw_bullets or parsed_raw
        self.tags = list(tags_set)

    @property
    def startDate(self) -> str:
        return self.start_date

    @property
    def endDate(self) -> str:
        return self.end_date

    def get_title_for_role(self, role_key: str) -> str:
        """Returns role-lens customized title, falling back to primary role."""
        rk = role_key.lower().strip()
        if rk in self.titles:
            return self.titles[rk]
        for k, v in self.titles.items():
            if k in rk or rk in k:
                return v
        return self.role

    def get_bullets_for_role(self, role_key: str) -> List[str]:
        """Filters bullets matching role_key or tagged 'all'."""
        rk = role_key.lower().strip()
        filtered = []
        for b in self.raw_bullets:
            if not b.tags or "all" in b.tags or rk in b.tags:
                filtered.append(b.text)
        return filtered or self.bullets

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "role": self.role,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "period": self.period,
            "location": self.location,
            "bullets": [b.to_dict() for b in self.raw_bullets] if self.raw_bullets else self.bullets,
            "tags": self.tags,
            "titles": self.titles,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkExperience:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(**data)


# ============================================================================
# 2. Skills Matrix (6 Domains)
# ============================================================================

@dataclass
class SkillsMatrix:
    """
    Candidate technical competency matrix divided across the 6 canonical domains:
    1. Cloud Architecture (AWS / Microsoft Azure)
    2. DevSecOps & AI Platform Engineering
    3. IaC & Automation (Terraform, Bicep, CI/CD)
    4. Systems Administration (Linux/Windows Systems & Networking)
    5. Containerization & Orchestration (Kubernetes KCNA, AKS, Docker)
    6. Observability, SRE & Governance (SLO, Azure Monitor, CloudWatch)
    """
    cloud_architecture: List[str] = field(default_factory=list)
    dev_sec_ops: List[str] = field(default_factory=list)
    iac_automation: List[str] = field(default_factory=list)
    systems_linux_windows: List[str] = field(default_factory=list)
    containerization_kubernetes: List[str] = field(default_factory=list)
    observability_monitoring: List[str] = field(default_factory=list)
    raw_categories: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def cloudArchitecture(self) -> List[str]:
        return self.cloud_architecture

    @property
    def devSecOps(self) -> List[str]:
        return self.dev_sec_ops

    @property
    def iacAutomation(self) -> List[str]:
        return self.iac_automation

    @property
    def systemsLinuxWindows(self) -> List[str]:
        return self.systems_linux_windows

    @property
    def containerizationKubernetes(self) -> List[str]:
        return self.containerization_kubernetes

    @property
    def observabilityMonitoring(self) -> List[str]:
        return self.observability_monitoring

    def get_skills_flat(self) -> List[str]:
        """Returns a flat, deduplicated list of all technical skill items across all 6 domains."""
        seen = set()
        flat_list: List[str] = []
        all_domains = [
            self.cloud_architecture,
            self.dev_sec_ops,
            self.iac_automation,
            self.systems_linux_windows,
            self.containerization_kubernetes,
            self.observability_monitoring,
        ]
        for domain in all_domains:
            for item in domain:
                clean_item = str(item).strip()
                if clean_item and clean_item.lower() not in seen:
                    seen.add(clean_item.lower())
                    flat_list.append(clean_item)
        return flat_list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cloudArchitecture": self.cloud_architecture,
            "devSecOps": self.dev_sec_ops,
            "iacAutomation": self.iac_automation,
            "systemsLinuxWindows": self.systems_linux_windows,
            "containerizationKubernetes": self.containerization_kubernetes,
            "observabilityMonitoring": self.observability_monitoring,
            "rawCategories": self.raw_categories,
        }

    def _domain_dict(self) -> Dict[str, List[str]]:
        """Canonical 6-domain dictionary mapping."""
        return {
            "cloud_architecture": self.cloud_architecture,
            "dev_sec_ops": self.dev_sec_ops,
            "iac_automation": self.iac_automation,
            "systems_linux_windows": self.systems_linux_windows,
            "containerization_kubernetes": self.containerization_kubernetes,
            "observability_monitoring": self.observability_monitoring,
        }

    def items(self):
        return self._domain_dict().items()

    def keys(self):
        return self._domain_dict().keys()

    def values(self):
        return self._domain_dict().values()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        return iter(self._domain_dict())

    def __len__(self) -> int:
        return 6

    def __contains__(self, key: str) -> bool:
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __getitem__(self, item: str) -> List[str]:
        mapping = {
            "cloudArchitecture": self.cloud_architecture,
            "cloud_architecture": self.cloud_architecture,
            "devSecOps": self.dev_sec_ops,
            "dev_sec_ops": self.dev_sec_ops,
            "iacAutomation": self.iac_automation,
            "iac_automation": self.iac_automation,
            "systemsLinuxWindows": self.systems_linux_windows,
            "systems_linux_windows": self.systems_linux_windows,
            "containerizationKubernetes": self.containerization_kubernetes,
            "containerization_kubernetes": self.containerization_kubernetes,
            "observabilityMonitoring": self.observability_monitoring,
            "observability_monitoring": self.observability_monitoring,
        }
        if item in mapping:
            return mapping[item]
        raise KeyError(f"Domain '{item}' not found in SkillsMatrix")

    @classmethod
    def from_dict(cls, data: Any) -> SkillsMatrix:
        if isinstance(data, list):
            # Parse from profile-data.json array format
            cloud_arch: List[str] = []
            devsecops: List[str] = []
            iac: List[str] = []
            sys_linux: List[str] = []
            containers: List[str] = []
            obs: List[str] = []
            for entry in data:
                cat_name = str(entry.get("category", ""))
                items = list(entry.get("items", []))
                cat_lower = cat_name.lower()
                # Observability & SRE must be checked before devsecops because Category 6 is
                # 'Observability, SRE & DevSecOps Governance'
                if "observability" in cat_lower or "sre" in cat_lower or "monitor" in cat_lower:
                    obs.extend(items)
                elif "cloud platform" in cat_lower or "architect" in cat_lower:
                    cloud_arch.extend(items)
                elif "container" in cat_lower or "orchestration" in cat_lower or "kubernetes" in cat_lower:
                    containers.extend(items)
                elif "ci/cd" in cat_lower or "iac" in cat_lower or "scripting" in cat_lower:
                    iac.extend(items)
                elif "linux" in cat_lower or "windows" in cat_lower or "networking" in cat_lower or "system" in cat_lower:
                    sys_linux.extend(items)
                elif "ai-augmented" in cat_lower or "mlops" in cat_lower or "devsecops" in cat_lower or "devops" in cat_lower:
                    devsecops.extend(items)
                elif "governance" in cat_lower:
                    obs.extend(items)
                else:
                    # Generic fallback
                    cloud_arch.extend(items)

            return cls(
                cloud_architecture=cloud_arch,
                dev_sec_ops=devsecops,
                iac_automation=iac,
                systems_linux_windows=sys_linux,
                containerization_kubernetes=containers,
                observability_monitoring=obs,
                raw_categories=data,
            )
        elif isinstance(data, dict):
            return cls(
                cloud_architecture=list(data.get("cloudArchitecture", data.get("cloud_architecture", []))),
                dev_sec_ops=list(data.get("devSecOps", data.get("dev_sec_ops", []))),
                iac_automation=list(data.get("iacAutomation", data.get("iac_automation", []))),
                systems_linux_windows=list(data.get("systemsLinuxWindows", data.get("systems_linux_windows", []))),
                containerization_kubernetes=list(data.get("containerizationKubernetes", data.get("containerization_kubernetes", []))),
                observability_monitoring=list(data.get("observabilityMonitoring", data.get("observability_monitoring", []))),
                raw_categories=list(data.get("rawCategories", data.get("raw_categories", []))),
            )
        return cls()


# ============================================================================
# 3. Candidate Info & Stepcon Profile Entities
# ============================================================================

@dataclass
class CandidateInfo:
    """Biographical contact data and profile metadata."""
    full_name: str = "John Victor Aniekwe"
    email: str = "aniekwevictor9@gmail.com"
    phone: str = "+2348130004114"
    location: str = "Lagos, Nigeria (UTC+1 / CET Synchronous)"
    linked_in: str = "https://www.linkedin.com/in/victor-aniekwe"
    github: str = "https://github.com/Nice-Major"
    portfolio: str = "https://nice-major.github.io/Nice-Major/"
    commitment: str = "Full-time / C2C Consultancy / Synchronous CET (UTC+1)"
    first_name: str = "John"
    middle_name: str = "Victor"
    last_name: str = "Aniekwe"
    time_zone: str = "UTC+1 / CET Synchronous"
    mobility_categories: List[str] = field(default_factory=list)
    education: Optional[Education] = None
    languages: List[str] = field(default_factory=lambda: ["English (Professional Fluency)"])
    certifications: List[Certification] = field(default_factory=list)

    def __init__(
        self,
        full_name: Optional[str] = None,
        email: str = "aniekwevictor9@gmail.com",
        phone: str = "+2348130004114",
        location: str = "Lagos, Nigeria (UTC+1 / CET Synchronous)",
        linked_in: Optional[str] = None,
        github: Optional[str] = None,
        portfolio: Optional[str] = None,
        commitment: str = "Full-time / C2C Consultancy / Synchronous CET (UTC+1)",
        first_name: str = "John",
        middle_name: str = "Victor",
        last_name: str = "Aniekwe",
        time_zone: str = "UTC+1 / CET Synchronous",
        mobility_categories: Optional[List[str]] = None,
        education: Optional[Union[Education, Dict[str, Any]]] = None,
        languages: Optional[List[str]] = None,
        certifications: Optional[List[Union[Certification, Dict[str, Any]]]] = None,
        fullName: Optional[str] = None,
        firstName: Optional[str] = None,
        middleName: Optional[str] = None,
        lastName: Optional[str] = None,
        githubProfile: Optional[str] = None,
        portfolioUrl: Optional[str] = None,
        mobilityCategories: Optional[List[str]] = None,
        timeZone: Optional[str] = None,
        linkedin: Optional[str] = None,
        linkedIn: Optional[str] = None,
        **kwargs: Any,
    ):
        self.first_name = str(firstName or kwargs.get("first_name", first_name))
        self.middle_name = str(middleName or kwargs.get("middle_name", middle_name))
        self.last_name = str(lastName or kwargs.get("last_name", last_name))
        
        f_name = fullName or full_name or kwargs.get("full_name")
        if not f_name:
            f_name = f"{self.first_name} {self.middle_name} {self.last_name}".replace("  ", " ").strip()
        self.full_name = str(f_name)

        self.email = str(kwargs.get("email", email))
        self.phone = str(kwargs.get("phone", phone))
        self.location = str(kwargs.get("location", location))
        self.time_zone = str(timeZone or kwargs.get("time_zone", time_zone))

        self.linked_in = str(linkedIn or linkedin or linked_in or kwargs.get("linkedin", "https://www.linkedin.com/in/victor-aniekwe"))
        self.github = str(githubProfile or github or kwargs.get("github_profile", "https://github.com/Nice-Major"))
        self.portfolio = str(portfolioUrl or portfolio or kwargs.get("portfolio_url", "https://nice-major.github.io/Nice-Major/"))

        self.mobility_categories = list(mobilityCategories or mobility_categories or kwargs.get("mobility_categories", []))
        self.commitment = str(commitment or ("; ".join(self.mobility_categories) if self.mobility_categories else "Full-time"))

        if isinstance(education, dict):
            self.education = Education.from_dict(education)
        else:
            self.education = education

        self.languages = list(languages or kwargs.get("languages", ["English (Professional Fluency)"]))

        # Parse certifications if passed here
        raw_certs = certifications or kwargs.get("certifications", [])
        parsed_certs: List[Certification] = []
        for c in raw_certs:
            if isinstance(c, Certification):
                parsed_certs.append(c)
            elif isinstance(c, dict):
                parsed_certs.append(Certification.from_dict(c))
        self.certifications = parsed_certs

    @property
    def fullName(self) -> str:
        return self.full_name

    @property
    def linkedIn(self) -> str:
        return self.linked_in

    @property
    def gitHub(self) -> str:
        return self.github

    @property
    def githubProfile(self) -> str:
        return self.github

    @property
    def portfolioUrl(self) -> str:
        return self.portfolio

    @property
    def mobilityCategories(self) -> List[str]:
        return self.mobility_categories

    @property
    def timeZone(self) -> str:
        return self.time_zone

    @property
    def firstName(self) -> str:
        return self.first_name

    @property
    def middleName(self) -> str:
        return self.middle_name

    @property
    def lastName(self) -> str:
        return self.last_name

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "firstName": self.first_name,
            "middleName": self.middle_name,
            "lastName": self.last_name,
            "fullName": self.full_name,
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "timeZone": self.time_zone,
            "time_zone": self.time_zone,
            "linkedin": self.linked_in,
            "linkedIn": self.linked_in,
            "linked_in": self.linked_in,
            "githubProfile": self.github,
            "github": self.github,
            "portfolioUrl": self.portfolio,
            "portfolio": self.portfolio,
            "mobilityCategories": self.mobility_categories,
            "mobility_categories": self.mobility_categories,
            "commitment": self.commitment,
            "education": self.education.to_dict() if self.education else {},
            "languages": self.languages,
            "certifications": [c.to_dict() for c in self.certifications],
        }
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateInfo:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(**data)


@dataclass
class StepconProfile:
    """Stepcon Solutions (RC - 8284984) statutory registration and business pitch."""
    company_name: str = "Stepcon Solutions"
    cac_number: str = "RC - 8284984"
    jurisdiction: str = "Corporate Affairs Commission (CAC), Federal Republic of Nigeria"
    offerings: List[str] = field(default_factory=lambda: [
        "Cloud Solutions Architecture (AWS & Microsoft Azure)",
        "DevSecOps & Automated CI/CD Pipelines",
        "Kubernetes & Container Orchestration Pods",
        "L3 Infrastructure & Application Escalation Support",
        "Enterprise & Custom Computing Hardware Commerce",
    ])
    synchronous_hours: str = "UTC+1 / CET / UK / EMEA Synchronous"
    b2b_consultancy_pitch: str = (
        "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) Cloud Architecture, "
        "DevSecOps, AI Platform Engineering, and L3 Escalation Support pods in synchronous CET/UK/EMEA business "
        "hours—eliminating international payroll tax friction, Employer-of-Record (EOR) markups, and visa lead times."
    )
    hardware_division: str = (
        "Enterprise & Custom Computing Hardware Division: Procurement, QA diagnostics, WhatsApp-to-Inventory "
        "catalog automation, and corporate fulfillment for Consumer, Business, High-Performance, and Custom-Built "
        "Laptops and Desktops."
    )
    proposal_terms: Dict[str, Any] = field(default_factory=lambda: {
        "engagementModel": "Corp-to-Corp (C2C) Monthly Retainer / Fixed-Milestone SOW",
        "timeZone": "UTC+1 / CET Synchronous",
        "currencyOptions": ["USD ($)", "GBP (£)", "EUR (€)", "NGN (₦)"],
        "paymentTerms": "Net 15 / Net 30 corporate wire",
    })

    def __init__(
        self,
        company_name: str = "Stepcon Solutions",
        cac_number: str = "RC - 8284984",
        jurisdiction: str = "Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
        offerings: Optional[List[str]] = None,
        synchronous_hours: str = "UTC+1 / CET / UK / EMEA Synchronous",
        b2b_consultancy_pitch: Optional[str] = None,
        hardware_division: Optional[str] = None,
        proposal_terms: Optional[Dict[str, Any]] = None,
        companyName: Optional[str] = None,
        cacNumber: Optional[str] = None,
        b2bConsultancyPitch: Optional[str] = None,
        hardwareDivision: Optional[str] = None,
        proposalTerms: Optional[Dict[str, Any]] = None,
        entity_name: Optional[str] = None,
        entityName: Optional[str] = None,
        registrationAuthority: Optional[str] = None,
        registration_authority: Optional[str] = None,
        synchronousHours: Optional[str] = None,
        services: Optional[List[str]] = None,
        legal_status: Optional[str] = None,
        legalStatus: Optional[str] = None,
        **kwargs: Any,
    ):
        self.company_name = str(companyName or entityName or entity_name or kwargs.get("company_name", company_name))
        
        raw_cac = cacNumber or kwargs.get("cac_number", cac_number)
        self.cac_number = str(raw_cac)
        
        # Enforce CAC statutory registration validation
        if "RC - 8284984" not in self.cac_number and "8284984" not in self.cac_number:
            raise ValueError(f"Invalid CAC registration number: '{self.cac_number}'. Expected 'RC - 8284984'")

        raw_jurisdiction = (
            legal_status
            or legalStatus
            or registrationAuthority
            or registration_authority
            or kwargs.get("legal_status", kwargs.get("legalStatus", kwargs.get("jurisdiction", jurisdiction)))
        )
        self.jurisdiction = str(raw_jurisdiction)

        raw_offerings = (
            services
            or offerings
            or kwargs.get("services", kwargs.get("offerings"))
        )
        self.offerings = list(raw_offerings) if raw_offerings is not None else [
            "Cloud Solutions Architecture (AWS & Microsoft Azure)",
            "DevSecOps & Automated CI/CD Pipelines",
            "Kubernetes & Container Orchestration Pods",
            "L3 Infrastructure & Application Escalation Support",
            "Enterprise & Custom Computing Hardware Commerce",
        ]
        self.synchronous_hours = str(synchronousHours or kwargs.get("synchronous_hours", synchronous_hours))
        
        default_pitch = (
            "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) Cloud Architecture, "
            "DevSecOps, AI Platform Engineering, and L3 Escalation Support pods in synchronous CET/UK/EMEA business "
            "hours—eliminating international payroll tax friction, Employer-of-Record (EOR) markups, and visa lead times."
        )
        self.b2b_consultancy_pitch = str(b2bConsultancyPitch or b2b_consultancy_pitch or kwargs.get("b2b_consultancy_pitch", default_pitch))

        default_hw = (
            "Enterprise & Custom Computing Hardware Division: Procurement, QA diagnostics, WhatsApp-to-Inventory "
            "catalog automation, and corporate fulfillment for Consumer, Business, High-Performance, and Custom-Built "
            "Laptops and Desktops."
        )
        self.hardware_division = str(hardwareDivision or hardware_division or kwargs.get("hardware_division", default_hw))

        self.proposal_terms = dict(proposalTerms or proposal_terms or kwargs.get("proposal_terms", {
            "engagementModel": "Corp-to-Corp (C2C) Monthly Retainer / Fixed-Milestone SOW",
            "timeZone": "UTC+1 / CET Synchronous",
            "currencyOptions": ["USD ($)", "GBP (£)", "EUR (€)", "NGN (₦)"],
            "paymentTerms": "Net 15 / Net 30 corporate wire",
        }))

    @property
    def services(self) -> List[str]:
        """Contractual alias for offerings per PROJECT.md line 105."""
        return self.offerings

    @services.setter
    def services(self, val: List[str]) -> None:
        self.offerings = list(val)

    @property
    def legal_status(self) -> str:
        """Contractual alias for jurisdiction per PROJECT.md line 105."""
        return self.jurisdiction

    @legal_status.setter
    def legal_status(self, val: str) -> None:
        self.jurisdiction = str(val)

    @property
    def legalStatus(self) -> str:
        return self.jurisdiction

    @legalStatus.setter
    def legalStatus(self, val: str) -> None:
        self.jurisdiction = str(val)

    @property
    def entity_name(self) -> str:
        return self.company_name

    @property
    def entityName(self) -> str:
        return self.company_name

    @property
    def companyName(self) -> str:
        return self.company_name

    @property
    def cacNumber(self) -> str:
        return self.cac_number

    @property
    def registration_authority(self) -> str:
        return self.jurisdiction

    @property
    def registrationAuthority(self) -> str:
        return self.jurisdiction

    @property
    def synchronousHours(self) -> str:
        return self.synchronous_hours

    @property
    def b2bConsultancyPitch(self) -> str:
        return self.b2b_consultancy_pitch

    @property
    def hardwareDivision(self) -> str:
        return self.hardware_division

    def to_dict(self) -> Dict[str, Any]:
        return {
            "companyName": self.company_name,
            "company_name": self.company_name,
            "entityName": self.company_name,
            "entity_name": self.company_name,
            "cacNumber": self.cac_number,
            "cac_number": self.cac_number,
            "registrationAuthority": self.jurisdiction,
            "registration_authority": self.jurisdiction,
            "jurisdiction": self.jurisdiction,
            "legal_status": self.jurisdiction,
            "legalStatus": self.jurisdiction,
            "offerings": self.offerings,
            "services": self.offerings,
            "synchronousHours": self.synchronous_hours,
            "synchronous_hours": self.synchronous_hours,
            "b2bConsultancyPitch": self.b2b_consultancy_pitch,
            "b2b_consultancy_pitch": self.b2b_consultancy_pitch,
            "hardwareDivision": self.hardware_division,
            "hardware_division": self.hardware_division,
            "proposalTerms": self.proposal_terms,
            "proposal_terms": self.proposal_terms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StepconProfile:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(**data)


# ============================================================================
# 4. RoleLens Helper & Aggregator
# ============================================================================

class RoleLens(dict):
    """
    Role lens view projected from candidate profile.
    Provides dual dictionary-subscript and attribute-access compatibility.
    """
    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)
        self.__dict__.update(data)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'RoleLens' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value
        self.__dict__[name] = value


# ============================================================================
# 5. Master Candidate Profile Model (Aggregator)
# ============================================================================

@dataclass
class CandidateProfile:
    """
    Authoritative Master Container encapsulating Candidate Info, Certifications,
    KPI Metrics, 4 Role Lenses, 6-Domain Skills Matrix, Work Experience, and Stepcon Profile.
    """
    candidate: CandidateInfo = field(default_factory=CandidateInfo)
    certifications: List[Certification] = field(default_factory=list)
    kpi_metrics: List[KpiMetric] = field(default_factory=list)
    role_categories: Dict[str, RoleCategory] = field(default_factory=dict)
    skills_matrix: SkillsMatrix = field(default_factory=SkillsMatrix)
    experience: List[WorkExperience] = field(default_factory=list)
    stepcon_solutions: StepconProfile = field(default_factory=StepconProfile)
    education: Optional[Education] = None
    projects: List[Dict[str, Any]] = field(default_factory=list)

    def __init__(
        self,
        candidate: Optional[Union[CandidateInfo, Dict[str, Any]]] = None,
        certifications: Optional[List[Union[Certification, Dict[str, Any]]]] = None,
        kpi_metrics: Optional[List[Union[KpiMetric, Dict[str, Any]]]] = None,
        role_categories: Optional[Dict[str, Union[RoleCategory, Dict[str, Any]]]] = None,
        skills_matrix: Optional[Union[SkillsMatrix, List[Any], Dict[str, Any]]] = None,
        experience: Optional[List[Union[WorkExperience, Dict[str, Any]]]] = None,
        stepcon_solutions: Optional[Union[StepconProfile, Dict[str, Any]]] = None,
        education: Optional[Union[Education, Dict[str, Any]]] = None,
        projects: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        # Handle case where CandidateProfile is initialized directly with candidate dict kwargs
        # (e.g. CandidateProfile(**canonical_profile_data["candidate"]))
        if candidate is None:
            # Check if kwargs contain candidate-like fields
            if any(k in kwargs for k in ("fullName", "full_name", "firstName", "first_name", "email")):
                cand_info = CandidateInfo(**kwargs)
            else:
                cand_info = CandidateInfo()
        elif isinstance(candidate, dict):
            cand_info = CandidateInfo.from_dict(candidate)
        else:
            cand_info = candidate

        self.candidate = cand_info

        # Certifications
        raw_certs = certifications if certifications is not None else kwargs.get("certifications", self.candidate.certifications)
        parsed_certs: List[Certification] = []
        for c in raw_certs:
            if isinstance(c, Certification):
                parsed_certs.append(c)
            elif isinstance(c, dict):
                parsed_certs.append(Certification.from_dict(c))
        self.certifications = parsed_certs
        if not self.candidate.certifications and self.certifications:
            self.candidate.certifications = self.certifications
        elif self.candidate.certifications and not self.certifications:
            self.certifications = self.candidate.certifications

        # KPI Metrics
        raw_kpis = kpi_metrics if kpi_metrics is not None else kwargs.get("kpiMetrics", kwargs.get("kpi_metrics", []))
        parsed_kpis: List[KpiMetric] = []
        for m in raw_kpis:
            if isinstance(m, KpiMetric):
                parsed_kpis.append(m)
            elif isinstance(m, dict):
                parsed_kpis.append(KpiMetric.from_dict(m))
        self.kpi_metrics = parsed_kpis

        # Role Categories
        raw_roles = role_categories if role_categories is not None else kwargs.get("roleCategories", kwargs.get("role_categories", {}))
        parsed_roles: Dict[str, RoleCategory] = {}
        if isinstance(raw_roles, dict):
            for k, v in raw_roles.items():
                if isinstance(v, RoleCategory):
                    parsed_roles[k] = v
                elif isinstance(v, dict):
                    parsed_roles[k] = RoleCategory.from_dict(v, key=k)
        self.role_categories = parsed_roles

        # Skills Matrix
        raw_skills = skills_matrix if skills_matrix is not None else kwargs.get("skillsMatrix", kwargs.get("skills_matrix", []))
        if isinstance(raw_skills, SkillsMatrix):
            self.skills_matrix = raw_skills
        else:
            self.skills_matrix = SkillsMatrix.from_dict(raw_skills)

        # Experience
        raw_exp = experience if experience is not None else kwargs.get("experience", [])
        parsed_exp: List[WorkExperience] = []
        for e in raw_exp:
            if isinstance(e, WorkExperience):
                parsed_exp.append(e)
            elif isinstance(e, dict):
                parsed_exp.append(WorkExperience.from_dict(e))
        self.experience = parsed_exp

        # Stepcon Solutions
        raw_stepcon = stepcon_solutions if stepcon_solutions is not None else kwargs.get("stepconSolutions", kwargs.get("stepcon_solutions", {}))
        if isinstance(raw_stepcon, StepconProfile):
            self.stepcon_solutions = raw_stepcon
        elif isinstance(raw_stepcon, dict) and raw_stepcon:
            self.stepcon_solutions = StepconProfile.from_dict(raw_stepcon)
        else:
            self.stepcon_solutions = StepconProfile()

        # Education
        raw_edu = education if education is not None else kwargs.get("education", self.candidate.education)
        if isinstance(raw_edu, Education):
            self.education = raw_edu
        elif isinstance(raw_edu, dict):
            self.education = Education.from_dict(raw_edu)
        else:
            self.education = self.candidate.education

        self.projects = list(projects or kwargs.get("projects", []))

    # Candidate field property delegations
    @property
    def full_name(self) -> str:
        return self.candidate.full_name if self.candidate else ""

    @full_name.setter
    def full_name(self, value: str) -> None:
        if self.candidate:
            self.candidate.full_name = value

    @property
    def fullName(self) -> str:
        return self.full_name

    @property
    def email(self) -> str:
        return self.candidate.email if self.candidate else ""

    @email.setter
    def email(self, value: str) -> None:
        if self.candidate:
            self.candidate.email = value

    @property
    def phone(self) -> str:
        return self.candidate.phone if self.candidate else ""

    @property
    def location(self) -> str:
        return self.candidate.location if self.candidate else ""

    @property
    def linked_in(self) -> str:
        return self.candidate.linked_in if self.candidate else ""

    @property
    def github(self) -> str:
        return self.candidate.github if self.candidate else ""

    def get_skills_flat(self) -> List[str]:
        """Returns flat, deduplicated list of candidate technical skills across 6 domains."""
        return self.skills_matrix.get_skills_flat()

    def get_role_lens(self, role_key: str) -> RoleLens:
        """
        Projects a role-tailored view for CV generation and ATS alignment.
        Maps any of the 8 target titles or 4 lens keys ('devops', 'architect', 'infra', 'support').
        """
        normalized_key = re.sub(r"\s*/\s*", "/", role_key.lower().strip())
        normalized_key = re.sub(r"\s+", " ", normalized_key)
        role_map = {
            # DevOps Lens
            "devops": "devops",
            "devops engineer": "devops",
            "devsecops": "devops",
            "devsecops engineer": "devops",
            "dev(sec)ops": "devops",
            "dev(sec)ops engineer": "devops",
            "azure/aws devops engineer": "devops",
            "azure devops engineer": "devops",
            "aws devops engineer": "devops",
            "platform engineer": "devops",
            "site reliability engineer": "devops",
            "sre": "devops",
            # Architect Lens
            "architect": "architect",
            "cloud solutions architect": "architect",
            "cloud architect": "architect",
            "cloud engineer": "architect",
            "multi-cloud platform architect": "architect",
            "ai cloud architect": "architect",
            # Infrastructure & SysAdmin Lens
            "infra": "infra",
            "cloud infrastructure engineer": "infra",
            "system administrator": "infra",
            "systems administrator": "infra",
            "sysadmin": "infra",
            "linux systems engineer": "infra",
            "hybrid cloud administrator": "infra",
            # Support & IT Specialist Lens
            "support": "support",
            "technical support engineer": "support",
            "technical support engineer (l3)": "support",
            "cloud support engineer": "support",
            "it specialist": "support",
            "it administrator": "support",
            "it specialist/administrator": "support",
            "it support specialist": "support",
            "application support engineer": "support",
        }
        canonical_lens = role_map.get(normalized_key, "devops")
        cat = self.role_categories.get(canonical_lens, self.role_categories.get("devops"))

        # Tailor work experience
        tailored_exp = []
        for exp in self.experience:
            tailored_exp.append({
                "company": exp.company,
                "role": exp.get_title_for_role(canonical_lens),
                "period": exp.period,
                "startDate": exp.start_date,
                "endDate": exp.end_date,
                "location": exp.location,
                "bullets": exp.get_bullets_for_role(canonical_lens),
            })

        # Filter certifications matching lens or tagged 'all'
        rel_certs = [
            c for c in self.certifications
            if not c.tags or "all" in c.tags or canonical_lens in c.tags
        ]

        title = cat.title if cat else "Senior Engineer"
        headline = cat.headline if cat else ""
        summary = cat.summary if cat else ""
        level = cat.level if cat else "Senior"
        target_titles = cat.target_titles if cat else []

        data: Dict[str, Any] = {
            "role_key": canonical_lens,
            "title": title,
            "category_title": title,
            "categoryTitle": title,
            "headline": headline,
            "summary": summary,
            "level": level,
            "target_titles": target_titles,
            "experience": tailored_exp,
            "certifications": rel_certs,
            "kpi_metrics": self.kpi_metrics,
            "skills": self.skills_matrix.to_dict(),
        }
        return RoleLens(data)

    def to_dict(self) -> Dict[str, Any]:
        """Converts entire candidate profile to a JSON-compatible dictionary."""
        return {
            "candidate": self.candidate.to_dict(),
            "certifications": [c.to_dict() for c in self.certifications],
            "kpiMetrics": [m.to_dict() for m in self.kpi_metrics],
            "kpi_metrics": [m.to_dict() for m in self.kpi_metrics],
            "roleCategories": {k: v.to_dict() for k, v in self.role_categories.items()},
            "role_categories": {k: v.to_dict() for k, v in self.role_categories.items()},
            "skillsMatrix": self.skills_matrix.to_dict(),
            "skills_matrix": self.skills_matrix.to_dict(),
            "experience": [e.to_dict() for e in self.experience],
            "stepconSolutions": self.stepcon_solutions.to_dict(),
            "stepcon_solutions": self.stepcon_solutions.to_dict(),
            "education": self.education.to_dict() if self.education else {},
            "projects": self.projects,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateProfile:
        """Instantiates full CandidateProfile from profile dictionary."""
        if not data or not isinstance(data, dict):
            return cls()

        cand_data = data.get("candidate", {})
        cand_info = CandidateInfo.from_dict(cand_data)

        # Parse certifications
        raw_certs = data.get("certifications") or cand_data.get("certifications") or []
        certs = [Certification.from_dict(c) for c in raw_certs]

        # Parse KPI metrics
        raw_kpis = data.get("kpiMetrics", data.get("kpi_metrics", []))
        kpi_metrics = [KpiMetric.from_dict(m) for m in raw_kpis]

        # Parse Role Categories
        raw_roles = data.get("roleCategories", data.get("role_categories", {}))
        roles: Dict[str, RoleCategory] = {}
        if isinstance(raw_roles, dict):
            for k, v in raw_roles.items():
                if isinstance(v, RoleCategory):
                    roles[k] = v
                elif isinstance(v, dict):
                    roles[k] = RoleCategory.from_dict(v, key=k)

        # Parse Skills Matrix
        raw_skills = data.get("skillsMatrix", data.get("skills_matrix", []))
        skills_matrix = SkillsMatrix.from_dict(raw_skills)

        # Parse Work Experience
        raw_exp = data.get("experience", [])
        experience = [WorkExperience.from_dict(e) for e in raw_exp]

        # Parse Stepcon Profile
        raw_stepcon = data.get("stepconSolutions", data.get("stepcon_solutions", {}))
        stepcon = StepconProfile.from_dict(raw_stepcon)

        # Education
        edu_data = cand_data.get("education", data.get("education"))
        edu = Education.from_dict(edu_data) if isinstance(edu_data, dict) else cand_info.education

        return cls(
            candidate=cand_info,
            certifications=certs,
            kpi_metrics=kpi_metrics,
            role_categories=roles,
            skills_matrix=skills_matrix,
            experience=experience,
            stepcon_solutions=stepcon,
            education=edu,
            projects=list(data.get("projects", [])),
        )

    @classmethod
    def from_json(cls, json_str: str) -> CandidateProfile:
        return cls.from_dict(json.loads(json_str))
