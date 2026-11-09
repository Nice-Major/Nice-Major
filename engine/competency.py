"""
Role Competency Taxonomy and Keyword Extraction Engine.
Module: engine.competency
Feature: F04 (Role Competency & Keyword Extraction)

Provides:
- 8-role technical competency taxonomy mapping skills, weights, and certifications.
- High-performance keyword and technical requirement extractor with HTML/DOM sanitization.
- Required certification parser and target role detector.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================================
# 1. 8-Role Competency Taxonomy Definitions
# ============================================================================

@dataclass
class RoleTaxonomyEntry:
    """Defines competency mapping, weights, and keywords for a target role."""
    title: str
    role_key: str
    parent_lens: str  # devops, architect, infra, support
    headline: str
    summary: str
    core_technologies: List[str]
    secondary_technologies: List[str]
    required_certifications: List[str]
    domain_weights: Dict[str, float]
    aliases: List[str] = field(default_factory=list)

    @property
    def core_skills(self) -> List[str]:
        return self.core_technologies

    @property
    def skills(self) -> List[str]:
        return self.core_technologies

    @property
    def certifications(self) -> List[str]:
        return self.required_certifications

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "role_key": self.role_key,
            "parent_lens": self.parent_lens,
            "headline": self.headline,
            "summary": self.summary,
            "core_technologies": list(self.core_technologies),
            "core_skills": list(self.core_technologies),
            "skills": list(self.core_technologies),
            "secondary_technologies": list(self.secondary_technologies),
            "required_certifications": list(self.required_certifications),
            "certifications": list(self.required_certifications),
            "domain_weights": dict(self.domain_weights),
            "aliases": list(self.aliases),
        }


ROLE_ENTRIES: List[RoleTaxonomyEntry] = [
    RoleTaxonomyEntry(
        title="Cloud Solutions Architect",
        role_key="cloud_solutions_architect",
        parent_lens="architect",
        headline="Cloud Solutions Architect & Multi-Cloud Platform Specialist",
        summary="Cloud Solutions Architect with 5+ years experience designing enterprise multi-cloud architectures across AWS and Azure.",
        core_technologies=[
            "AWS", "Microsoft Azure", "Multi-Cloud", "Well-Architected Framework",
            "Microservices", "Terraform", "Kubernetes", "AKS", "EKS", "FinOps",
            "High Availability", "Disaster Recovery", "Private Endpoints"
        ],
        secondary_technologies=["ARM", "Bicep", "Docker", "Python", "CloudWatch", "Azure Monitor"],
        required_certifications=["AWS Certified Solutions Architect", "AWS Certified Cloud Practitioner", "Bachelor of Science in Computer Science"],
        domain_weights={
            "cloud_architecture": 0.35,
            "containerization_kubernetes": 0.20,
            "iac_automation": 0.20,
            "observability_monitoring": 0.15,
            "systems_linux_windows": 0.10,
        },
        aliases=[
            "cloud solutions architect", "cloud architect", "enterprise cloud architect",
            "multi-cloud architect", "solutions architect", "ai cloud platform architect",
            "principal cloud architect", "principal cloud solutions architect",
            "ai fellow", "ai solutions architect"
        ],
    ),
    RoleTaxonomyEntry(
        title="Cloud Infrastructure Engineer",
        role_key="cloud_infrastructure_engineer",
        parent_lens="infra",
        headline="Cloud Infrastructure Engineer & Hybrid Systems Specialist",
        summary="Infrastructure Engineer with 5+ years experience administering Linux/Windows systems, enterprise networks, and cloud compute.",
        core_technologies=[
            "AWS", "Microsoft Azure", "Linux", "Ubuntu Server", "Windows Server",
            "Terraform", "Bash", "PowerShell", "VPN Gateway", "VNet Peering",
            "Network Security Groups", "Virtualization", "Patch Management"
        ],
        secondary_technologies=["Docker", "Active Directory", "CloudWatch", "Azure Monitor", "Storage Accounts"],
        required_certifications=["AWS Certified Solutions Architect", "AWS Certified Cloud Practitioner"],
        domain_weights={
            "cloud_architecture": 0.30,
            "systems_linux_windows": 0.30,
            "iac_automation": 0.20,
            "observability_monitoring": 0.10,
            "containerization_kubernetes": 0.10,
        },
        aliases=[
            "cloud infrastructure engineer", "infrastructure engineer", "cloud systems engineer",
            "cloud systems administrator", "hybrid cloud administrator", "cloud infra engineer",
            "senior cloud infrastructure engineer"
        ],
    ),
    RoleTaxonomyEntry(
        title="Cloud Engineer",
        role_key="cloud_engineer",
        parent_lens="architect",
        headline="Cloud Engineer & Platform Operations Specialist",
        summary="Cloud Engineer with 5+ years experience deploying, automating, and operating cloud workloads across AWS and Microsoft Azure.",
        core_technologies=[
            "AWS", "Microsoft Azure", "Docker", "Kubernetes", "Terraform",
            "CI/CD", "GitHub Actions", "Azure DevOps", "Azure App Service", "CloudWatch"
        ],
        secondary_technologies=["Bash", "Python", "PowerShell", "Azure Monitor", "Linux"],
        required_certifications=["AWS Certified Cloud Practitioner", "AWS Certified Solutions Architect"],
        domain_weights={
            "cloud_architecture": 0.30,
            "iac_automation": 0.25,
            "dev_sec_ops": 0.20,
            "containerization_kubernetes": 0.15,
            "observability_monitoring": 0.10,
        },
        aliases=[
            "cloud engineer", "associate cloud engineer", "senior cloud engineer",
            "cloud operations engineer", "cloud platform engineer"
        ],
    ),
    RoleTaxonomyEntry(
        title="Dev(Sec)Ops Engineer",
        role_key="devsecops_engineer",
        parent_lens="devops",
        headline="Dev(Sec)Ops Engineer & AI Platform Architect",
        summary="DevOps Engineer with 5+ years experience specializing in Kubernetes orchestration, declarative IaC, and automated DevSecOps CI/CD pipelines.",
        core_technologies=[
            "Kubernetes", "Docker", "Terraform", "CI/CD", "GitHub Actions",
            "Azure DevOps", "DevSecOps", "Podman", "Bicep", "ARM",
            "Static Analysis", "Vulnerability Scanning", "Zero Downtime"
        ],
        secondary_technologies=["Jenkins", "Helm", "GitOps", "Python", "Bash", "Prometheus", "Grafana"],
        required_certifications=["KCNA", "Kubernetes and Cloud Native Associate", "AWS Certified Developer"],
        domain_weights={
            "dev_sec_ops": 0.30,
            "containerization_kubernetes": 0.25,
            "iac_automation": 0.25,
            "observability_monitoring": 0.10,
            "cloud_architecture": 0.10,
        },
        aliases=[
            "devops engineer", "devsecops engineer", "dev(sec)ops engineer",
            "dev(sec)ops", "platform engineer", "site reliability engineer", "sre",
            "senior devops engineer", "senior devsecops engineer", "senior devops & platform engineer"
        ],
    ),
    RoleTaxonomyEntry(
        title="System Administrator",
        role_key="system_administrator",
        parent_lens="infra",
        headline="Systems Administrator (Linux / Windows)",
        summary="Systems Administrator with 5+ years experience managing Linux and Windows server fleets, kernel performance tuning, and access control.",
        core_technologies=[
            "Linux", "Ubuntu Server", "RHEL", "Windows Server", "Bash",
            "PowerShell", "Active Directory", "SSH", "systemd", "cron",
            "OS Patching", "System Hardening", "Disaster Recovery"
        ],
        secondary_technologies=["Networking", "DNS", "DHCP", "NFS", "Hyper-V", "AWS EC2", "Azure VMs"],
        required_certifications=["AWS Certified Cloud Practitioner", "ITIL Foundation"],
        domain_weights={
            "systems_linux_windows": 0.40,
            "iac_automation": 0.20,
            "observability_monitoring": 0.20,
            "cloud_architecture": 0.15,
            "dev_sec_ops": 0.05,
        },
        aliases=[
            "system administrator", "systems administrator", "sysadmin",
            "linux system administrator", "windows system administrator", "linux systems engineer",
            "linux & windows systems administrator"
        ],
    ),
    RoleTaxonomyEntry(
        title="IT Specialist/Administrator",
        role_key="it_specialist_administrator",
        parent_lens="support",
        headline="IT Specialist / Enterprise Systems Administrator",
        summary="IT Specialist with 5+ years experience managing corporate IT infrastructure, identity systems, and hardware logistics.",
        core_technologies=[
            "Active Directory", "Azure AD", "Entra ID", "Microsoft 365",
            "ITSM", "ITIL", "Hardware Diagnostics", "Network Routing",
            "Helpdesk", "User Lifecycle", "SOP Documentation"
        ],
        secondary_technologies=["PowerShell", "Windows 11", "Ubuntu Desktop", "VPN", "MFA", "Asset Management"],
        required_certifications=["ITIL Foundation"],
        domain_weights={
            "systems_linux_windows": 0.35,
            "observability_monitoring": 0.25,
            "cloud_architecture": 0.20,
            "iac_automation": 0.15,
            "dev_sec_ops": 0.05,
        },
        aliases=[
            "it specialist", "it administrator", "it specialist/administrator",
            "it systems specialist", "corporate it administrator", "it support specialist",
            "senior it specialist & systems administrator"
        ],
    ),
    RoleTaxonomyEntry(
        title="Technical Support Engineer",
        role_key="technical_support_engineer",
        parent_lens="support",
        headline="L3 Technical Cloud Support Engineer & Diagnostics Lead",
        summary="L3 Technical Support Engineer achieving a verified 99% first-day resolution rate on Microsoft Azure App Service and distributed cloud workloads.",
        core_technologies=[
            "Azure App Service", "L3 Support", "Root-Cause Analysis", "RCA",
            "Distributed Tracing", "Telemetry", "Azure Monitor", "Application Insights",
            "CloudWatch", "CSAT", "TsG", "SLA Adherence"
        ],
        secondary_technologies=["Bash", "PowerShell", "HTTP/REST", "SQL", "Log Analytics", "Kusto"],
        required_certifications=["AWS Certified Developer", "AWS Certified Solutions Architect", "ITIL Foundation"],
        domain_weights={
            "observability_monitoring": 0.35,
            "cloud_architecture": 0.30,
            "systems_linux_windows": 0.20,
            "iac_automation": 0.15,
        },
        aliases=[
            "technical support engineer", "l3 technical support engineer",
            "cloud support engineer", "l3 cloud escalation engineer",
            "application support engineer", "support engineer",
            "l3 technical cloud support engineer"
        ],
    ),
    RoleTaxonomyEntry(
        title="Azure/AWS DevOps Engineer",
        role_key="azure_aws_devops_engineer",
        parent_lens="devops",
        headline="Multi-Cloud DevOps Engineer (Azure & AWS)",
        summary="DevOps Engineer with 5+ years experience building unified automation pipelines across both Microsoft Azure and Amazon Web Services estates.",
        core_technologies=[
            "Azure DevOps", "AWS", "Microsoft Azure", "GitHub Actions",
            "Kubernetes", "AKS", "EKS", "Terraform", "Bicep", "ARM",
            "AWS CodePipeline", "CloudWatch", "Azure Monitor"
        ],
        secondary_technologies=["Docker", "Bash", "Python", "PowerShell", "IAM", "RBAC", "Helm"],
        required_certifications=["KCNA", "AWS Certified Solutions Architect", "AWS Certified Developer"],
        domain_weights={
            "dev_sec_ops": 0.30,
            "cloud_architecture": 0.30,
            "containerization_kubernetes": 0.20,
            "iac_automation": 0.20,
        },
        aliases=[
            "azure/aws devops engineer", "aws/azure devops engineer",
            "multi-cloud devops engineer", "azure devops engineer", "aws devops engineer"
        ],
    ),
]

ROLE_TAXONOMY: Dict[str, RoleTaxonomyEntry] = {entry.title: entry for entry in ROLE_ENTRIES}


def get_role_taxonomy() -> Dict[str, Any]:
    """
    Returns the full 8-role technical competency taxonomy dictionary.
    Includes entries keyed by canonical title, role_key, and normalized name.
    """
    tax: Dict[str, Any] = {}
    for entry in ROLE_ENTRIES:
        # Title key e.g. "Cloud Solutions Architect"
        tax[entry.title] = entry
        # Snake-case key e.g. "cloud_solutions_architect"
        tax[entry.role_key] = entry
        # Normalized key without parentheses/slashes e.g. "devsecops engineer"
        norm_key = entry.title.lower().replace("(", "").replace(")", "").replace("/", " ")
        if norm_key not in tax:
            tax[norm_key] = entry
    return tax


# ============================================================================
# 2. Canonical Keywords & Terminology Map
# ============================================================================

# Maps lowercase variants and acronyms to canonical presentation names
CANONICAL_TECH_MAP: Dict[str, str] = {
    # Containers & Kubernetes
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "kcna": "KCNA",
    "docker": "Docker",
    "podman": "Podman",
    "helm": "Helm",
    "container": "Container",
    "containers": "Container",
    "containerization": "Container",
    "aks": "AKS",
    "eks": "EKS",

    # Cloud Platforms
    "aws": "AWS",
    "amazon web services": "AWS",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "multi-cloud": "Multi-Cloud",
    "multicloud": "Multi-Cloud",
    "hybrid cloud": "Hybrid Cloud",
    "azure app service": "Azure App Service",
    "app service": "Azure App Service",
    "ec2": "EC2",
    "s3": "S3",
    "vpc": "VPC",
    "vnet": "VNet",
    "iam": "IAM",
    "finops": "FinOps",
    "well-architected": "Well-Architected",
    "well-architected framework": "Well-Architected",
    "microservices": "Microservices",

    # IaC & Automation
    "terraform": "Terraform",
    "iac": "IaC",
    "infrastructure as code": "IaC",
    "bicep": "Bicep",
    "arm": "ARM",
    "arm/bicep": "ARM/Bicep",

    # CI/CD & DevSecOps
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "github actions": "GitHub Actions",
    "azure devops": "Azure DevOps",
    "jenkins": "Jenkins",
    "gitops": "GitOps",
    "devops": "DevOps",
    "devsecops": "DevSecOps",
    "shift-left": "Shift-Left",
    "vulnerability scanning": "Vulnerability Scanning",
    "static analysis": "Static Analysis",
    "zero downtime": "Zero Downtime",

    # Systems, Scripting & Languages
    "linux": "Linux",
    "ubuntu": "Ubuntu",
    "ubuntu server": "Ubuntu Server",
    "rhel": "RHEL",
    "windows": "Windows",
    "windows server": "Windows Server",
    "bash": "Bash",
    "powershell": "PowerShell",
    "python": "Python",
    "golang": "Golang",
    "rust": "Rust",
    "ansible": "Ansible",
    "gcp": "Google Cloud Platform (GCP)",
    "google cloud": "Google Cloud Platform (GCP)",
    "active directory": "Active Directory",
    "azure ad": "Azure AD",
    "entra id": "Entra ID",
    "ssh": "SSH",
    "systemd": "systemd",

    # Observability, Reliability & Support
    "azure monitor": "Azure Monitor",
    "cloudwatch": "CloudWatch",
    "application insights": "Application Insights",
    "prometheus": "Prometheus",
    "grafana": "Grafana",
    "sla": "SLA",
    "uptime": "Uptime",
    "rca": "RCA",
    "root cause": "RCA",
    "root cause analysis": "RCA",
    "root-cause analysis": "RCA",
    "csat": "CSAT",
    "tsg": "TsG",
    "telemetry": "Telemetry",
    "support": "Support",
    "incident management": "Incident Management",

    # AI, ML & Data Engineering
    "azure openai": "Azure OpenAI",
    "openai": "Azure OpenAI",
    "llm": "Large Language Models (LLMs)",
    "llms": "Large Language Models (LLMs)",
    "large language models": "Large Language Models (LLMs)",
    "language models": "Large Language Models (LLMs)",
    "machine learning": "Machine Learning (ML)",
    "predictive analytics": "Predictive Analytics",
    "data pipelines": "Data Pipelines",
    "data engineering": "Data Pipelines",
    "retrieval": "RAG & Knowledge Retrieval",
    "version control": "Git & Version Control",
    "software engineering": "Software Engineering",
    "decision-support": "AI Decision-Support Systems",
    "decision support": "AI Decision-Support Systems",
    "databricks": "Azure Databricks",
    "copilot": "Microsoft Copilot",
    "fine-tuning": "LLM Fine-Tuning",
    "statistical modeling": "Statistical Modeling",

    # CyberOps, Security Monitoring & SOC Operations
    "cyberops": "Cisco CyberOps",
    "cbrops": "Cisco CyberOps",
    "siem": "SIEM & Security Monitoring",
    "soc": "SOC Operations",
    "nist 800-61": "NIST SP 800-61 Incident Response",
    "incident response": "Incident Response (NIST 800-61)",
    "mitre att&ck": "MITRE ATT&CK",
    "ids/ips": "IDS/IPS Intrusion Analysis",
    "wireshark": "Packet Analysis (Wireshark/tcpdump)",
    "tcpdump": "Packet Analysis (Wireshark/tcpdump)",
    "netflow": "NetFlow Telemetry",
    "edr": "Endpoint Detection & Response (EDR)",
    "threat intelligence": "Threat Intelligence",
}

# Certifications lookup
CERT_SYNONYMS: Dict[str, str] = {
    "kcna": "Kubernetes and Cloud Native Associate (KCNA)",
    "kubernetes and cloud native associate": "Kubernetes and Cloud Native Associate (KCNA)",
    "cka": "Certified Kubernetes Administrator (CKA)",
    "ckad": "Certified Kubernetes Application Developer (CKAD)",
    "aws solutions architect": "AWS Certified Solutions Architect",
    "aws certified solutions architect": "AWS Certified Solutions Architect",
    "aws developer": "AWS Certified Developer",
    "aws certified developer": "AWS Certified Developer",
    "aws cloud practitioner": "AWS Certified Cloud Practitioner",
    "aws certified cloud practitioner": "AWS Certified Cloud Practitioner",
    "itil": "ITIL Foundation",
    "itil foundation": "ITIL Foundation",
    "itil v4": "ITIL Foundation",
    "cyberops": "Cisco Certified CyberOps Associate",
    "cisco cyberops": "Cisco Certified CyberOps Associate",
    "cbrops": "Cisco Certified CyberOps Associate",
    "200-201": "Cisco Certified CyberOps Associate",
    "b.sc.": "Bachelor of Science (B.Sc.) in Computer Science",
    "bsc": "Bachelor of Science (B.Sc.) in Computer Science",
    "bachelor": "Bachelor of Science (B.Sc.) in Computer Science",
    "degree in computer science": "Bachelor of Science (B.Sc.) in Computer Science",
    "az-104": "Microsoft Certified: Azure Administrator Associate",
    "az-305": "Microsoft Certified: Azure Solutions Architect Expert",
    "az-400": "Microsoft Certified: DevOps Engineer Expert",
}


# ============================================================================
# 3. Extraction & Classification Functions
# ============================================================================

def clean_html(text: str) -> str:
    """Strips HTML/DOM tags and decodes entities safely."""
    if not text:
        return ""
    unescaped = html.unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", unescaped)
    return cleaned


# Precompile regex patterns for performance on repeated queries
_REGEX_CACHE: Dict[str, re.Pattern] = {}

def _get_boundary_regex(term: str) -> re.Pattern:
    if term not in _REGEX_CACHE:
        # If term has non-word chars like "ci/cd", word boundaries need special handling
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(term) + r"(?![a-zA-Z0-9])"
        _REGEX_CACHE[term] = re.compile(pattern, re.IGNORECASE)
    return _REGEX_CACHE[term]


def extract_keywords(text: str) -> List[str]:
    """
    Extracts normalized technical keywords from arbitrary job description text.
    Handles HTML tags, acronyms, case-insensitivity, and deduplication.

    Guarantees:
    - Empty input returns empty list [].
    - Robust against noise, HTML, and long repetitive strings.
    - Preserves canonical presentation format.
    """
    if not text or not text.strip():
        return []

    cleaned_text = clean_html(text)
    if not cleaned_text.strip():
        return []

    lower_text = cleaned_text.lower()

    # Sort terms by length descending to match longer phrases first (e.g. "azure app service" before "azure")
    sorted_terms = sorted(CANONICAL_TECH_MAP.keys(), key=len, reverse=True)

    found_keywords: List[str] = []
    seen: Set[str] = set()

    for raw_term in sorted_terms:
        canonical = CANONICAL_TECH_MAP[raw_term]
        if canonical in seen:
            continue
        if raw_term not in lower_text:
            continue
        pattern = _get_boundary_regex(raw_term)
        if pattern.search(lower_text):
            seen.add(canonical)
            found_keywords.append(canonical)

    return found_keywords


def extract_certifications(text: str) -> List[str]:
    """Extracts certified credentials mentioned in the job description."""
    if not text or not text.strip():
        return []

    cleaned_text = clean_html(text)
    if not cleaned_text.strip():
        return []

    lower_text = cleaned_text.lower()

    certs: List[str] = []
    seen: Set[str] = set()

    for pattern_key, canonical_cert in CERT_SYNONYMS.items():
        if canonical_cert in seen:
            continue
        if pattern_key not in lower_text:
            continue
        pattern = _get_boundary_regex(pattern_key)
        if pattern.search(lower_text):
            seen.add(canonical_cert)
            certs.append(canonical_cert)

    return certs


extract_required_certifications = extract_certifications


def classify_target_role(text: str) -> str:
    """
    Classifies job title or description text into 1 of the 8 canonical target roles.
    Returns canonical title (e.g. 'Dev(Sec)Ops Engineer').
    """
    if not text or not text.strip():
        return "Dev(Sec)Ops Engineer"

    cleaned = clean_html(text)
    first_lines = "\n".join(cleaned.splitlines()[:5]).lower()
    full_lower = cleaned.lower()

    # 1. Check title lines first against aliases
    for role_entry in ROLE_ENTRIES:
        for alias in role_entry.aliases:
            if alias in first_lines and _get_boundary_regex(alias).search(first_lines):
                return role_entry.title

    # 2. Check full text for explicit role aliases
    for role_entry in ROLE_ENTRIES:
        for alias in role_entry.aliases:
            if alias in full_lower and _get_boundary_regex(alias).search(full_lower):
                return role_entry.title

    # 3. Frequency-based scoring across role core technologies
    best_role = "Dev(Sec)Ops Engineer"
    highest_score = -1

    for role_entry in ROLE_ENTRIES:
        match_count = sum(
            1 for tech in role_entry.core_technologies
            if tech.lower() in full_lower and _get_boundary_regex(tech.lower()).search(full_lower)
        )
        if match_count > highest_score:
            highest_score = match_count
            best_role = role_entry.title

    return best_role


detect_target_role = classify_target_role
