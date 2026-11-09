"""
Candidate Profile Ingestion and Parsing Module.
Module: ingestion.parser
Feature: F01 (Candidate Profile Data Ingestion)

Authoritative loader converting profile-data.json, arbitrary dicts, or paths into CandidateProfile.
Implements 5-tier path discovery, camelCase/snake_case normalization, error hierarchy,
and embedded fallback resilience.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
    Education,
    KpiMetric,
    RoleCategory,
    SkillsMatrix,
    StepconProfile,
    WorkExperience,
)

logger = logging.getLogger(__name__)

# Search paths for locating profile-data.json
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SEARCH_PATHS = [
    PROJECT_ROOT / "data" / "profile-data.json",
    PROJECT_ROOT / "profile-data.json",
    PROJECT_ROOT / "config" / "profile-data.json",
    PROJECT_ROOT / "ingestion" / "profile-data.json",
    Path("data/profile-data.json"),
    Path("profile-data.json"),
    Path("config/profile-data.json"),
    Path("ingestion/profile-data.json"),
    Path(r"C:\Users\user\Downloads\Nice_Major_Portfolio_and_Automation_Suite\profile-data.json"),
    Path.home() / "Downloads" / "Nice_Major_Portfolio_and_Automation_Suite" / "profile-data.json",
]


# ============================================================================
# 1. Error Hierarchy
# ============================================================================

class ProfileError(Exception):
    """Base exception for all profile ingestion and parsing errors."""


class ProfileNotFoundError(ProfileError, FileNotFoundError):
    """Raised when profile JSON cannot be found across search paths."""


class ProfileParseError(ProfileError, ValueError):
    """Raised when profile JSON is malformed or invalid syntax."""


class ProfileValidationError(ProfileError, ValueError):
    """Raised when profile data violates required schema constraints."""


# ============================================================================
# 2. Path Discovery Hierarchy (5-Tier)
# ============================================================================

def find_profile_data_path(custom_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """
    Locates profile-data.json using the 5-tier search hierarchy:
    Tier 1: Explicit custom_path (file or directory)
    Tier 2: Environment variables CAREER_PROFILE_PATH or CANDIDATE_PROFILE_PATH
    Tier 3: Repository-relative paths (data/, config/, ingestion/)
    Tier 4: Well-known user system downloads path
    Tier 5: None (caller uses embedded default profile)
    """
    # Tier 1: Explicit parameter
    if custom_path:
        p = Path(custom_path)
        if p.is_dir():
            candidate = p / "profile-data.json"
            if candidate.is_file():
                return candidate.resolve()
        elif p.is_file():
            return p.resolve()
        return None

    # Tier 2: Environment variable
    env_path = os.getenv("CAREER_PROFILE_PATH") or os.getenv("CANDIDATE_PROFILE_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            candidate = p / "profile-data.json"
            if candidate.is_file():
                return candidate.resolve()
        elif p.is_file():
            return p.resolve()

    # Tier 3 & Tier 4: Search paths
    for candidate in DEFAULT_SEARCH_PATHS:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except (PermissionError, OSError):
            continue

    return None


# ============================================================================
# 3. Normalization Utilities
# ============================================================================

def _camel_to_snake(name: str) -> str:
    """Convert camelCase identifier to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def normalize_profile_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively transforms dictionary keys to snake_case and fills default fields.
    Handles aliases and assures Stepcon corporate identity defaults.
    """
    if not isinstance(raw, dict):
        raise ProfileValidationError(f"Expected dict at top-level, got {type(raw).__name__}")

    normalized: Dict[str, Any] = {}
    for key, val in raw.items():
        snake_key = _camel_to_snake(key)
        if isinstance(val, dict):
            normalized[snake_key] = normalize_profile_dict(val)
        elif isinstance(val, list):
            normalized[snake_key] = [
                normalize_profile_dict(item) if isinstance(item, dict) else item
                for item in val
            ]
        else:
            normalized[snake_key] = val

    # Candidate field aliases and fallbacks
    cand = normalized.get("candidate", {})
    if isinstance(cand, dict):
        if "full_name" not in cand and "first_name" in cand and "last_name" in cand:
            cand["full_name"] = f"{cand['first_name']} {cand.get('middle_name', '')} {cand['last_name']}".replace("  ", " ").strip()
        if "github" in cand and "github_profile" not in cand:
            cand["github_profile"] = cand["github"]
        if "linkedin" in cand and "linked_in" not in cand:
            cand["linked_in"] = cand["linkedin"]

    # Stepcon Solutions fallback assurance
    if "stepcon_solutions" not in normalized and "stepcon" in normalized:
        normalized["stepcon_solutions"] = normalized["stepcon"]

    if "stepcon_solutions" not in normalized:
        normalized["stepcon_solutions"] = {
            "company_name": "Stepcon Solutions",
            "cac_number": "RC - 8284984",
            "jurisdiction": "Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
            "b2b_consultancy_pitch": (
                "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) "
                "Cloud Architecture, DevSecOps, AI Platform Engineering, and L3 Escalation "
                "Support pods in synchronous CET/UK/EMEA business hours."
            ),
            "hardware_division": (
                "Enterprise & Custom Computing Hardware Division: Procurement, QA diagnostics, "
                "and fulfillment for enterprise workstations and laptops."
            ),
        }

    return normalized


# ============================================================================
# 4. Embedded Authoritative Default Profile (Tier 5)
# ============================================================================

def get_embedded_default_profile() -> Dict[str, Any]:
    """
    Returns the embedded authoritative default profile dictionary for John Victor Aniekwe
    and Stepcon Solutions (RC - 8284984), ensuring zero runtime failure in offline environments.
    """
    return {
        "candidate": {
            "firstName": "John",
            "middleName": "Victor",
            "lastName": "Aniekwe",
            "fullName": "John Victor Aniekwe",
            "email": "aniekwevictor9@gmail.com",
            "phone": "+2348130004114",
            "location": "Lagos, Nigeria (UTC+1 / CET Synchronous)",
            "linkedin": "https://www.linkedin.com/in/victor-aniekwe",
            "githubProfile": "https://github.com/Nice-Major",
            "portfolioUrl": "https://nice-major.github.io/Nice-Major/",
            "timeZone": "UTC+1 / CET Synchronous",
            "mobilityCategories": [
                "Global Remote from Anywhere (Nigeria / UTC+1 / CET / EMEA Synchronous)",
                "Visa-Sponsored Relocation (Canada GTS/LMIA, UK Skilled Worker, EU Blue Card, Spain 20-Day UGE-CE HQP / Digital Nomad Visa)",
                "B2B Corp-to-Corp Contractor via Stepcon Solutions (Nigerian CAC: RC - 8284984)",
            ],
            "education": {
                "degree": "Bachelor of Science (B.Sc.) in Computer Science",
                "institution": "University of Nigeria",
                "period": "2014 – 2018",
                "major": "Computer Science",
            },
            "languages": [
                "English (Professional Fluency — Written & Spoken)"
            ],
            "certifications": [
                {
                    "name": "Kubernetes and Cloud Native Associate (KCNA)",
                    "issuer": "The Linux Foundation / CNCF",
                    "status": "Active",
                    "year": "Active",
                    "verified": True,
                    "tags": ["all", "devops", "architect", "infra", "support"],
                },
                {
                    "name": "AWS Certified Solutions Architect – Associate",
                    "issuer": "Amazon Web Services",
                    "status": "Active",
                    "year": "Active",
                    "verified": True,
                    "tags": ["all", "architect", "devops", "infra", "support"],
                },
                {
                    "name": "AWS Certified Developer – Associate",
                    "issuer": "Amazon Web Services",
                    "status": "Active",
                    "year": "Active",
                    "verified": True,
                    "tags": ["all", "devops", "architect", "support"],
                },
                {
                    "name": "AWS Certified Cloud Practitioner",
                    "issuer": "Amazon Web Services",
                    "status": "Active",
                    "year": "Active",
                    "verified": True,
                    "tags": ["all", "architect", "devops", "infra", "support"],
                },
                {
                    "name": "Kubernetes and Cloud Native Essentials (KCNE)",
                    "issuer": "The Linux Foundation / CNCF",
                    "status": "Active",
                    "year": "Active",
                    "verified": True,
                    "tags": ["all", "devops", "architect", "infra", "support"],
                },
                {
                    "name": "Cisco Certified CyberOps Associate (CBROPS 200-201)",
                    "issuer": "Cisco",
                    "status": "Pursuing / In Progress",
                    "year": "In Progress",
                    "verified": False,
                    "tags": ["all", "devops", "architect", "infra", "support"],
                },
            ],
        },
        "kpiMetrics": [
            {
                "metric": "Enterprise Cloud Uptime SLA",
                "label": "Enterprise Cloud Uptime SLA",
                "value": "99.9%",
                "context": "Sustained across enterprise Microsoft Azure & AWS compute, storage, and networking estates.",
            },
            {
                "metric": "First-Day L3 Issue Resolution",
                "label": "First-Day L3 Issue Resolution",
                "value": "99%",
                "context": "First-day resolution rate for Azure App Service (Linux/OSS & Windows) through structured RCA.",
            },
            {
                "metric": "AI Prediction Engine Accuracy",
                "label": "AI Prediction Engine Accuracy",
                "value": ">60%",
                "context": "Maintained on microservices deployed on Azure OpenAI and AKS pods/nodes.",
            },
            {
                "metric": "IaC Provisioning Reduction",
                "label": "IaC Provisioning Reduction",
                "value": "<15 Min",
                "context": "Reduced multi-environment provisioning and deployment time from hours using Terraform and ARM/Bicep.",
            },
        ],
        "roleCategories": {
            "devops": {
                "title": "Senior DevOps & AI Platform Engineer",
                "categoryTitle": "Dev(Sec)Ops & AI Platform Engineer",
                "level": "Senior",
                "targetTitles": [
                    "DevOps Engineer",
                    "DevSecOps Engineer",
                    "Platform Engineer",
                    "Azure DevOps Engineer",
                    "AWS DevOps Engineer",
                ],
                "headline": "Senior DevOps & AI Platform Engineer | AWS, Azure, Kubernetes (KCNA) & CI/CD Automation",
                "summary": (
                    "Senior DevOps and Platform Engineer with 5+ years of production experience architecting "
                    "cloud infrastructure across AWS and Microsoft Azure. Certified in Kubernetes (KCNA) and AWS (Solutions Architect), "
                    "with deep expertise in Terraform, Docker, GitHub Actions, and production LLM orchestration."
                ),
            },
            "architect": {
                "title": "Cloud Solutions & Platform Architect",
                "categoryTitle": "Cloud Solutions & Platform Architect",
                "level": "Senior",
                "targetTitles": [
                    "Cloud Solutions Architect",
                    "Cloud Architect",
                    "Cloud Engineer",
                    "Platform Architect",
                ],
                "headline": "Cloud Solutions Architect | Enterprise Multi-Cloud, Kubernetes & High-Availability Systems",
                "summary": (
                    "Enterprise Cloud Solutions Architect specializing in resilient, multi-cloud topologies across AWS and Azure. "
                    "Proven track record delivering 99.9% uptime SLAs, scalable Kubernetes container orchestration, and automated governance."
                ),
            },
            "infra": {
                "title": "Cloud Infrastructure & Systems Escalation Engineer",
                "categoryTitle": "Cloud Infrastructure Engineer",
                "level": "Senior",
                "targetTitles": [
                    "Cloud Infrastructure Engineer",
                    "System Administrator",
                    "Infrastructure Engineer",
                    "Systems Administrator",
                ],
                "headline": "Senior Cloud Infrastructure Engineer | Hybrid Systems, Linux/Windows & Infrastructure as Code",
                "summary": (
                    "Senior Cloud Infrastructure and Systems Engineer with 5+ years expertise in automated infrastructure delivery, "
                    "Linux/Ubuntu kernel tuning, Windows Server administration, and enterprise Terraform automation."
                ),
            },
            "support": {
                "title": "Technical Cloud Application Support Engineer (L3)",
                "categoryTitle": "Technical Support Engineer",
                "level": "Senior",
                "targetTitles": [
                    "Technical Support Engineer",
                    "IT Specialist",
                    "IT Specialist / Administrator",
                    "Support Escalation Engineer",
                ],
                "headline": "L3 Technical Support & Cloud Escalation Lead | 99% First-Day RCA Resolution",
                "summary": (
                    "Technical Support and Cloud Escalation Engineer with extensive experience resolving mission-critical "
                    "L3 incidents across enterprise Microsoft Azure App Service environments. Achieved verified 99% same-day RCA resolution rate."
                ),
            },
        },
        "skillsMatrix": [
            {
                "category": "Cloud Platforms (AWS & Azure)",
                "items": [
                    "AWS (EC2, S3, RDS, VPC, CloudWatch, IAM, Route53)",
                    "Microsoft Azure (App Service, Azure Kubernetes Service - AKS, VNets, NSGs, Azure Monitor, Resource Groups)",
                    "Hybrid Cloud Architecture & High-Availability Topologies",
                    "Multi-Region Failover & Disaster Recovery (DR)",
                    "FinOps & Cloud Cost Optimization",
                ],
                "tags": ["architect", "devops", "infra", "support"],
            },
            {
                "category": "AI-Augmented Platform Engineering & DevSecOps",
                "items": [
                    "Azure OpenAI Service & Vector Integrations",
                    "GitHub Copilot Enterprise Integration",
                    "Production LLM Deployment on Kubernetes (AKS)",
                    "Shift-Left Security & IAM Least-Privilege Governance",
                    "Automated Vulnerability Scanning & Secrets Management",
                    "Cisco CyberOps Security Monitoring (SIEM Log Correlation, SOC Alert Triage, NIST SP 800-61 Incident Response, MITRE ATT&CK)",
                    "Network Intrusion & Packet Analysis (IDS/IPS, Wireshark, tcpdump, NetFlow) & Host-Based Forensics / EDR",
                ],
                "tags": ["devops", "architect", "infra", "support"],
            },
            {
                "category": "Containers & Kubernetes Orchestration",
                "items": [
                    "Kubernetes (KCNA Certified — Pods, Deployments, Services, Ingress, HPA, RBAC)",
                    "Azure Kubernetes Service (AKS) & AWS Elastic Kubernetes Service (EKS)",
                    "Docker & Podman Containerization",
                    "Container Registry Management (ACR & ECR)",
                    "Microservices Service Mesh & Traffic Routing",
                ],
                "tags": ["devops", "architect", "infra", "support"],
            },
            {
                "category": "CI/CD & Infrastructure as Code (IaC)",
                "items": [
                    "Terraform (HCL Modules, State Management, Multi-Cloud)",
                    "Azure Resource Manager (ARM) & Bicep",
                    "GitHub Actions Workflow Automation & CI/CD Pipelines",
                    "Azure DevOps Pipelines & Repos",
                    "Bash, Python & PowerShell Infrastructure Scripting",
                ],
                "tags": ["devops", "architect", "infra"],
            },
            {
                "category": "Systems Administration, OS & Networking",
                "items": [
                    "Linux Systems Administration (Ubuntu, Debian, RHEL, CentOS)",
                    "Windows Server Administration & Active Directory",
                    "TCP/IP, DNS, VPNs, Virtual Networks (VNets/VPCs), Subnets, Routing Tables",
                    "Kernel Tuning, Performance Optimization & systemd Service Management",
                    "Patch Compliance & Enterprise Hardening",
                ],
                "tags": ["infra", "support", "devops"],
            },
            {
                "category": "Observability, SRE & Governance",
                "items": [
                    "Azure Monitor, Application Insights & Log Analytics Workspaces",
                    "AWS CloudWatch & Distributed Tracing",
                    "Prometheus & Grafana Dashboarding",
                    "SLI/SLO/SLA Performance Auditing (99.9% Platform SLA)",
                    "Incident Management & Structured Root Cause Analysis (99% Resolution Rate)",
                ],
                "tags": ["support", "devops", "infra", "architect"],
            },
        ],
        "experience": [
            {
                "company": "GVOC",
                "location": "Remote, United Kingdom (UTC+0 / CET Synchronous)",
                "period": "December 2025 – Present",
                "startDate": "December 2025",
                "endDate": "Present",
                "titles": {
                    "devops": "DevOps Engineer / Platform Architect",
                    "architect": "Cloud Solutions & Platform Architect",
                    "infra": "Cloud Infrastructure & Platform Engineer",
                    "support": "Cloud Infrastructure & Operations Support Engineer",
                },
                "bullets": [
                    {
                        "text": "Architected and operationalized Azure OpenAI on Azure Kubernetes Service (AKS), optimizing pod scheduling and resource allocation to sustain >60% AI prediction engine accuracy.",
                        "tags": ["devops", "architect", "infra"],
                    },
                    {
                        "text": "Embedded GitHub Copilot Enterprise across engineering teams, accelerating code delivery and incident triage.",
                        "tags": ["devops", "support"],
                    },
                    {
                        "text": "Developed modular Terraform and ARM/Bicep IaC modules with automated GitHub Actions CI/CD pipelines, cutting environment deployment times from hours to under 15 minutes.",
                        "tags": ["devops", "architect", "infra"],
                    },
                    {
                        "text": "Built ClickUp API automation microservices for operational tracking, eliminating manual status reporting.",
                        "tags": ["devops", "support"],
                    },
                ],
            },
            {
                "company": "TEKNOWLEDGE",
                "location": "Lagos, Nigeria (Hybrid / Synchronous UTC+1 / CET)",
                "period": "October 2021 – November 2025",
                "startDate": "October 2021",
                "endDate": "November 2025",
                "titles": {
                    "devops": "Cloud DevOps & Application Platform Engineer (Azure App Service L3)",
                    "architect": "Cloud Infrastructure & Application Platform Specialist (L3)",
                    "infra": "Cloud Infrastructure & Systems Escalation Engineer (L3)",
                    "support": "Technical Cloud Application Support Engineer – Azure App Service (Dev & OSS) L3",
                },
                "bullets": [
                    {
                        "text": "Designed, managed, and supported enterprise cloud infrastructure across Compute, Storage, Security, and Hybrid Networking (VNets, VPNs, NSGs) for Microsoft Azure customers, sustaining a verified 99.9% platform uptime SLA.",
                        "tags": ["support", "infra", "devops", "architect"],
                    },
                    {
                        "text": "Served as the L3 escalation lead for complex Linux/OSS, container, networking, and application code/configuration incidents, achieving a 99% first-day issue resolution rate through structured root-cause analysis (RCA).",
                        "tags": ["support", "infra", "devops"],
                    },
                    {
                        "text": "Integrated Microsoft Copilot into DfM incident workflows configured with Troubleshooting Guides (TsG) and internal engineering wikis as knowledge sources, accelerating L3 triage and boosting team-wide Customer Satisfaction (CSAT).",
                        "tags": ["support", "devops", "architect", "infra"],
                    },
                    {
                        "text": "Architected automated CI/CD deployment pipelines and reusable IaC templates plus Bash, Python, and PowerShell scripts, reducing multi-environment provisioning and deployment time from hours to minutes.",
                        "tags": ["devops", "architect", "infra", "support"],
                    },
                    {
                        "text": "Implemented comprehensive observability and alerting solutions across Azure Monitor, Application Insights, and AWS CloudWatch by configuring distributed logs, metrics, and traces, and documenting resolutions into a reusable operational knowledge base.",
                        "tags": ["support", "devops", "infra", "architect"],
                    },
                ],
            },
        ],
        "stepconSolutions": {
            "companyName": "Stepcon Solutions",
            "cacNumber": "RC - 8284984",
            "jurisdiction": "Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
            "b2bConsultancyPitch": (
                "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) Cloud Architecture, "
                "DevSecOps, AI Platform Engineering, and L3 Escalation Support pods in synchronous CET/UK/EMEA business "
                "hours—eliminating international payroll tax friction, Employer-of-Record (EOR) markups, and visa lead times."
            ),
            "hardwareDivision": (
                "Enterprise & Custom Computing Hardware Division: Procurement, QA diagnostics, WhatsApp-to-Inventory "
                "catalog automation, and corporate fulfillment for Consumer, Business, High-Performance, and Custom-Built Laptops and Desktops."
            ),
            "serviceOfferings": [
                "Cloud Solutions Architecture (AWS & Microsoft Azure)",
                "DevSecOps & Automated CI/CD Pipelines",
                "Kubernetes & Container Orchestration Pods",
                "L3 Infrastructure & Application Escalation Support",
                "Enterprise & Custom Computing Hardware Commerce",
            ],
            "synchronousHours": "UTC+1 / CET / UK / EMEA Synchronous",
        },
    }


# ============================================================================
# 5. Profile Loaders
# ============================================================================

def load_profile_from_dict(data: Dict[str, Any]) -> CandidateProfile:
    """
    Parses and converts a dictionary into a validated CandidateProfile instance.
    Handles camelCase and snake_case normalization.
    """
    if not isinstance(data, dict):
        raise ProfileValidationError(f"Expected dict at top-level, got {type(data).__name__}")

    # Check for empty dictionary
    if not data:
        raise ProfileValidationError("Profile dictionary is empty.")

    # Check for required candidate block
    if "candidate" not in data and not any(k in data for k in ("fullName", "full_name", "firstName", "first_name")):
        raise ProfileValidationError("Profile dictionary missing required 'candidate' section.")

    normalized = normalize_profile_dict(data)
    return CandidateProfile.from_dict(normalized)


def load_profile_from_file(
    file_path: Union[str, Path],
    allow_fallback: bool = False,
) -> CandidateProfile:
    """
    Reads a candidate profile JSON file from disk and parses into CandidateProfile.
    Handles UTF-8 and UTF-8 BOM encoding.
    """
    p = Path(file_path)
    if not p.is_file():
        if allow_fallback:
            logger.warning("Profile file %s not found. Falling back to embedded profile.", file_path)
            return load_profile_from_dict(get_embedded_default_profile())
        raise ProfileNotFoundError(f"Candidate profile JSON file not found at: {p.resolve()}")

    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            content = f.read().strip()
            if not content:
                raise ProfileValidationError(f"Profile file {p} is empty.")
            data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProfileParseError(
            f"Malformed JSON in profile file {p}: {exc.msg} at line {exc.lineno} col {exc.colno}"
        ) from exc
    except OSError as exc:
        raise ProfileError(f"Could not read profile file {p}: {exc}") from exc

    if not data or not isinstance(data, dict):
        raise ProfileValidationError(f"Expected JSON object in file {p}, got empty or non-dict.")

    if "candidate" not in data and not any(k in data for k in ("fullName", "full_name", "firstName", "first_name")):
        raise ProfileValidationError(f"Profile file {p} missing required 'candidate' section.")

    return load_profile_from_dict(data)


def load_profile(
    source: Optional[Union[str, Path, Dict[str, Any]]] = None,
    allow_fallback: bool = True,
) -> CandidateProfile:
    """
    Universal candidate profile loader.
    Accepts:
    - In-memory dict
    - Path string or Path object (file or directory)
    - None (auto-discovers profile via 5-tier search hierarchy)
    """
    # 1. Direct dictionary
    if isinstance(source, dict):
        return load_profile_from_dict(source)

    # 2. Explicit path parameter
    if isinstance(source, (str, Path)):
        resolved = Path(source)
        if resolved.is_file():
            return load_profile_from_file(resolved, allow_fallback=False)
        if resolved.is_dir():
            sub = resolved / "profile-data.json"
            if sub.is_file():
                return load_profile_from_file(sub, allow_fallback=False)
        raise ProfileNotFoundError(f"Specified profile path does not exist: {resolved.resolve()}")

    # 3. Auto-discovery via search hierarchy
    found_path = find_profile_data_path()
    if found_path and found_path.is_file():
        return load_profile_from_file(found_path, allow_fallback=allow_fallback)

    # 4. Fallback to embedded default
    if allow_fallback:
        logger.info("Using embedded default candidate profile.")
        return load_profile_from_dict(get_embedded_default_profile())

    raise ProfileNotFoundError("Unable to locate profile-data.json across standard search paths.")


# Alias for test harness compatibility
load_source_of_truth = load_profile


# ============================================================================
# 6. Profile Audit & Completeness Validator
# ============================================================================

def validate_profile_completeness(profile: CandidateProfile) -> List[str]:
    """
    Performs integrity audits on the candidate profile.
    Returns a list of warning strings if any recommended fields or verified credentials are absent.
    """
    warnings: List[str] = []
    
    # Candidate contact check
    if not profile.candidate.full_name:
        warnings.append("Missing candidate full_name.")
    if not profile.candidate.email:
        warnings.append("Missing candidate email.")
    if not profile.candidate.certifications:
        warnings.append("No certifications registered.")

    # Verified credentials check
    cert_names = [c.name.lower() for c in profile.candidate.certifications]
    if not any("kubernetes" in c or "kcna" in c for c in cert_names):
        warnings.append("Missing verified Kubernetes certification (KCNA).")
    if not any("solutions architect" in c for c in cert_names):
        warnings.append("Missing verified AWS Solutions Architect credential.")

    # Stepcon CAC registration check
    if profile.stepcon_solutions.cac_number != "RC - 8284984":
        warnings.append(f"Unexpected Stepcon CAC number: {profile.stepcon_solutions.cac_number}")

    return warnings
