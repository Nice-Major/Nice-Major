"""
STAR Methodology Cover Letter Tailoring Engine.
Module: tailoring.letter_tailor
Feature: F06 (Cover Letter Tailoring Engine)

Generates tailored, high-impact cover letters structured around the STAR
(Situation, Task, Action, Result) methodology. Conforms strictly to global
technical recruitment standards:
- Dynamic alignment with target role, hiring company, and job description keywords.
- Grounded strictly in candidate John Victor Aniekwe's verified empirical metrics
  (99.9% uptime SLA, 99% first-day L3 RCA resolution, >60% AI prediction accuracy, <15m IaC).
- Multi-format output: Markdown (.md), clean print-ready semantic HTML (.html),
  and ATS-friendly plain text (.txt).
- Multi-tone adaptation: professional (default), technical, executive, results-oriented.
- Zero buzzwords/fluff (prohibits "rockstar", "ninja", "guru", "wizard").
- Zero external tracker / Credly links.
- Typographic safety via sanitize_ligatures and clean_ats_text.
"""

from __future__ import annotations

import datetime
import html
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
    Education,
    KpiMetric,
    RoleCategory,
    WorkExperience,
)
from ingestion.parser import get_embedded_default_profile, load_profile_from_dict
from ingestion.text_utils import (
    clean_ats_text,
    extract_clean_words,
    safe_filename,
    sanitize_ligatures,
    strip_markdown,
)


# ============================================================================
# 1. Constants & Lexicons
# ============================================================================

SUPPORTED_FORMATS: Tuple[str, ...] = ("md", "html", "txt")

SUPPORTED_TONES: Tuple[str, ...] = (
    "professional",
    "technical",
    "executive",
    "results_oriented",
)

BANNED_BUZZWORDS: Tuple[str, ...] = (
    "rockstar",
    "rock star",
    "ninja",
    "guru",
    "wizard",
    "passionate evangelist",
    "unicorn",
    "10x engineer",
)

# Canonical 8 Target Roles mapped to primary lens
ROLE_LENS_MAP: Dict[str, str] = {
    "cloud solutions architect": "architect",
    "cloud architect": "architect",
    "enterprise cloud architect": "architect",
    "solutions architect": "architect",
    "cloud infrastructure engineer": "infra",
    "cloud infrastructure": "infra",
    "cloud engineer": "architect",
    "dev(sec)ops engineer": "devops",
    "devops engineer": "devops",
    "devsecops engineer": "devops",
    "devops": "devops",
    "devsecops": "devops",
    "azure/aws devops engineer": "devops",
    "azure devops engineer": "devops",
    "aws devops engineer": "devops",
    "system administrator": "infra",
    "systems administrator": "infra",
    "sysadmin": "infra",
    "linux systems administrator": "infra",
    "it specialist/administrator": "support",
    "it specialist": "support",
    "it administrator": "support",
    "technical support engineer": "support",
    "technical support engineer (l3)": "support",
    "l3 technical support engineer": "support",
    "l3 cloud escalation engineer": "support",
}

# Verified Empirical Metrics
VERIFIED_METRICS = {
    "uptime": "99.9% infrastructure uptime SLA",
    "rca": "99% first-day L3 issue resolution rate",
    "ai_accuracy": ">60% AI prediction accuracy",
    "iac_speed": "<15-minute automated provisioning time",
}

# Common high-value technical keywords by lens
LENS_TECH_KEYWORDS: Dict[str, List[str]] = {
    "devops": [
        "Kubernetes (KCNA)", "Terraform", "Docker", "CI/CD Pipelines",
        "GitHub Actions", "Azure DevOps", "AWS", "Microsoft Azure",
        "Helm", "ArgoCD", "DevSecOps", "Prometheus", "Grafana"
    ],
    "architect": [
        "Cloud Solutions Architecture", "AWS", "Microsoft Azure", "Terraform",
        "Well-Architected Framework", "Kubernetes (AKS/EKS)", "Microservices",
        "Private Endpoints", "FinOps", "Disaster Recovery", "Zero-Trust Security"
    ],
    "infra": [
        "Linux (Ubuntu/RHEL)", "Windows Server", "Hybrid Cloud Networking",
        "Terraform", "AWS EC2/VPC", "Azure VMs/VNets", "Bash & PowerShell",
        "Patch Management", "System Hardening", "Virtualization"
    ],
    "support": [
        "Microsoft Azure App Service", "L3 Production Escalation", "Root-Cause Analysis (RCA)",
        "Azure Monitor & App Insights", "AWS CloudWatch", "Distributed Tracing",
        "Microsoft Copilot in DfM", "Troubleshooting Guides (TsG)", "SLA & CSAT Delivery"
    ],
}


# ============================================================================
# 2. Candidate Ingestion & Extraction Helpers
# ============================================================================

def _resolve_candidate_profile(candidate: Any) -> CandidateProfile:
    """
    Normalizes candidate input into an authoritative CandidateProfile instance.
    Accepts CandidateProfile, dict representation, or None.
    """
    if isinstance(candidate, CandidateProfile):
        return candidate
    if isinstance(candidate, dict):
        if "candidate" in candidate:
            return load_profile_from_dict(candidate)
        return CandidateProfile(candidate=CandidateInfo.from_dict(candidate))
    # Embedded default fallback
    try:
        return load_profile_from_dict(get_embedded_default_profile())
    except Exception:
        return CandidateProfile(candidate=CandidateInfo())


def _resolve_target_role(target_role: str, job_text: str = "") -> str:
    """Resolves standardized target role title from parameter or job text."""
    if target_role and target_role.strip():
        return target_role.strip()

    jt_lower = job_text.lower()
    for role_name in ROLE_LENS_MAP:
        if role_name in jt_lower:
            return role_name.title()

    return "DevOps Engineer"


def _extract_matched_technologies(candidate: CandidateProfile, job_text: str, target_role: str) -> List[str]:
    """
    Identifies candidate technical skills matching the target job description.
    Falls back to canonical lens skills if job_text is minimal or empty.
    """
    role_key = ROLE_LENS_MAP.get(target_role.lower().strip(), "devops")
    all_candidate_skills = candidate.get_skills_flat()
    if not all_candidate_skills:
        all_candidate_skills = LENS_TECH_KEYWORDS.get(role_key, LENS_TECH_KEYWORDS["devops"])

    if not job_text or not job_text.strip():
        return LENS_TECH_KEYWORDS.get(role_key, LENS_TECH_KEYWORDS["devops"])[:6]

    clean_words = set(extract_clean_words(job_text))
    matched: List[str] = []

    for skill in all_candidate_skills:
        skill_lower = skill.lower()
        if skill_lower in job_text.lower():
            matched.append(skill)
        elif any(part in clean_words for part in re.split(r"[\s/,-]+", skill_lower) if len(part) >= 3):
            matched.append(skill)

    # Augment with role-lens competencies if few matches
    if len(matched) < 4:
        for fallback_skill in LENS_TECH_KEYWORDS.get(role_key, []):
            if fallback_skill not in matched:
                matched.append(fallback_skill)
            if len(matched) >= 6:
                break

    return matched[:8]


# ============================================================================
# 3. STAR Content Synthesis Engine
# ============================================================================

def _build_salutation(company_name: str) -> str:
    """Constructs a professional salutation incorporating hiring entity."""
    clean_company = company_name.strip() if company_name else ""
    if clean_company:
        return f"Dear Hiring Team at {clean_company},"
    return "Dear Hiring Manager,"


def _build_opening_paragraph(
    candidate: CandidateProfile,
    target_role: str,
    company_name: str,
    tone: str,
) -> str:
    """Constructs the opening hook establishing candidacy, credentials, and authority."""
    company_phrase = f" at {company_name.strip()}" if company_name and company_name.strip() else ""
    degree_info = "Bachelor of Science (B.Sc.) in Computer Science from the University of Nigeria"
    if candidate.candidate and candidate.candidate.education and candidate.candidate.education.degree:
        edu = candidate.candidate.education
        degree_info = f"{edu.degree} from {edu.institution or 'the University of Nigeria'}"

    if tone == "technical":
        return (
            f"I am writing to express my strong interest in the {target_role} position{company_phrase}. "
            f"With over 5 years of production engineering experience architecting, automating, and securing "
            f"mission-critical cloud infrastructure across AWS and Microsoft Azure—backed by a {degree_info} "
            f"and active Kubernetes (KCNA) and AWS certifications—I specialize in building fault-tolerant systems "
            f"that guarantee high availability and operational excellence."
        )
    elif tone == "executive":
        return (
            f"I am pleased to present my application for the {target_role} role{company_phrase}. "
            f"Bringing 5+ years of demonstrable success in cloud infrastructure leadership, enterprise SLA governance, "
            f"and high-impact platform engineering, I have consistently aligned technical operations with strategic "
            f"business objectives. Holding a {degree_info} alongside formal certifications in AWS and Kubernetes (KCNA), "
            f"I deliver scalable platforms that balance rigorous reliability, security, and capital efficiency."
        )
    elif tone in ("results_oriented", "results-oriented"):
        return (
            f"I am writing to apply for the {target_role} position{company_phrase}. "
            f"Throughout 5+ years of enterprise cloud engineering, my track record is defined by quantifiable operational "
            f"outcomes: sustaining a 99.9% infrastructure uptime SLA across hybrid estates, attaining a 99% first-day "
            f"L3 incident resolution rate, and slashing environment provisioning times from hours to <15 minutes. "
            f"Supported by a {degree_info} and AWS and KCNA certifications, I offer immediate engineering rigor."
        )
    else:  # professional (default)
        return (
            f"I am writing to formally submit my application for the {target_role} position{company_phrase}. "
            f"As a Senior Cloud and Platform Engineer with 5+ years of verified production experience across Amazon "
            f"Web Services (AWS) and Microsoft Azure, I have dedicated my career to designing high-availability systems, "
            f"automating declarative pipelines, and resolving complex infrastructure escalations. I hold a {degree_info}, "
            f"as well as industry credentials including Kubernetes and Cloud Native Associate (KCNA) and AWS Certified "
            f"Solutions Architect."
        )


def _build_star_body_paragraphs(
    candidate: CandidateProfile,
    target_role: str,
    company_name: str,
    matched_skills: List[str],
    tone: str,
) -> List[str]:
    """Constructs the 3 STAR-methodology core body paragraphs."""
    company_ref = company_name.strip() if company_name and company_name.strip() else "your organization"
    tech_str = ", ".join(matched_skills[:5]) if matched_skills else "Kubernetes, Terraform, AWS, Azure, and CI/CD"

    # Paragraph 1: STAR Situation & Task (Cloud Scale & Reliability)
    if tone == "technical":
        p1 = (
            f"In my production engineering roles, I have spearheaded the design and lifecycle management of "
            f"distributed multi-cloud estates spanning AWS and Microsoft Azure. Tasked with ensuring zero-downtime "
            f"deployments and robust security perimeters, I engineered declarative Infrastructure as Code (IaC) "
            f"modules utilizing Terraform and ARM/Bicep, containerized workloads deployed to Kubernetes (AKS/EKS), "
            f"and established automated CI/CD pipelines through GitHub Actions. By implementing shift-left DevSecOps "
            f"controls, private network endpoints, and comprehensive telemetry via Azure Monitor and AWS CloudWatch, "
            f"I sustained an uncompromising 99.9% infrastructure uptime SLA while reducing multi-tier environment "
            f"provisioning cycles from hours to under 15 minutes."
        )
    elif tone == "executive":
        p1 = (
            f"At the enterprise level, my focus centers on transforming infrastructure into a competitive advantage. "
            f"Faced with rapidly scaling systems and the operational necessity for 24/7 reliability, I directed "
            f"the modernization of multi-cloud architectures across AWS and Azure. Through standardizing declarative "
            f"IaC workflows with Terraform, enforcing FinOps cost governance, and orchestrating containerized microservices "
            f"on Kubernetes, I secured continuous 99.9% enterprise uptime SLAs. This automated governance accelerated product "
            f"delivery timelines while eliminating configuration drift and significantly decreasing infrastructure spend."
        )
    else:  # professional & results_oriented
        p1 = (
            f"Throughout my production tenure at GVOC and enterprise engagements, I have maintained end-to-end "
            f"ownership of mission-critical cloud and platform infrastructure. When tasked with supporting distributed "
            f"enterprise workloads across AWS and Microsoft Azure, I engineered automated Infrastructure as Code using "
            f"Terraform and ARM/Bicep, managed containerized microservices on Kubernetes (KCNA certified), and established "
            f"hardened CI/CD release pipelines with GitHub Actions. Through proactive capacity planning and resilient "
            f"network architecture, I consistently delivered a 99.9% infrastructure uptime SLA and compressed environment "
            f"deployment times from hours to under 15 minutes."
        )

    # Paragraph 2: STAR Action & Result (Incident Escalation, SRE & AI Workloads)
    if tone == "technical":
        p2 = (
            f"Beyond core infrastructure provisioning, I bring proven L3 escalation expertise in distributed systems "
            f"and AI platform engineering. Serving as L3 Escalation Lead for Microsoft Azure App Service, I executed "
            f"deep-dive root-cause analysis (RCA) across complex microservices by dissecting distributed traces, "
            f"memory dumps, and network metrics, utilizing Microsoft Copilot in DfM alongside custom troubleshooting guides. "
            f"This rigorous diagnostic methodology resulted in a verified 99% first-day L3 issue resolution rate. "
            f"Furthermore, at GVOC I architected and deployed containerized Azure OpenAI microservices on Kubernetes "
            f"pods and nodes, achieving over 60% AI prediction accuracy under strict production performance constraints."
        )
    elif tone == "executive":
        p2 = (
            f"High-reliability operations demand both strategic vision and rapid incident resolution. As L3 Escalation "
            f"Lead for Azure App Service environments, I instituted systematic root-cause mitigation protocols that "
            f"achieved a 99% first-day resolution rate, safeguarding client SLA commitments and elevating customer satisfaction. "
            f"In parallel, I spearheaded cutting-edge platform innovation by productionizing Azure OpenAI microservices "
            f"on Kubernetes clusters, successfully powering AI prediction engines with >60% accuracy while maintaining "
            f"strict cost boundaries and audit readiness."
        )
    else:  # professional & results_oriented
        p2 = (
            f"In addition to platform architecture, I possess extensive experience resolving complex production incidents "
            f"and delivering next-generation AI workloads. As an L3 Cloud Escalation Lead for Microsoft Azure App Service, "
            f"I conducted deep root-cause analysis using Application Insights, Azure Monitor, and CloudWatch telemetry, "
            f"attaining a verified 99% first-day issue resolution rate. Moreover, I successfully architected and deployed "
            f"Azure OpenAI workloads on Kubernetes infrastructure at GVOC, powering predictive AI platforms that achieved "
            f"over 60% prediction accuracy while adhering to enterprise security baselines."
        )

    # Paragraph 3: Dynamic Alignment with Job & Company
    p3 = (
        f"The technical scope of the {target_role} role at {company_ref} aligns directly with my core competencies "
        f"in {tech_str}. Operating synchronously within UTC+1 / CET business hours from Lagos, Nigeria, I collaborate "
        f"seamlessly with international engineering teams across the UK, Europe, and North America. Whether integrated "
        f"as an agile full-time engineering team member or engaged via frictionless Corp-to-Corp (C2C) contracting "
        f"through Stepcon Solutions (CAC Registration: RC - 8284984), I am prepared to deliver immediate, measurable "
        f"value to your cloud engineering initiatives."
    )

    return [p1, p2, p3]


def _build_closing_paragraph(company_name: str, tone: str) -> str:
    """Constructs a confident, professional call to action and closing."""
    company_ref = f" {company_name.strip()}" if company_name and company_name.strip() else ""
    return (
        f"I welcome the opportunity to discuss how my technical expertise, certified engineering disciplines, "
        f"and proven record of production uptime can contribute to the continued success of{company_ref}. "
        f"Thank you for your time and consideration."
    )


def _build_signoff(candidate: CandidateProfile) -> Tuple[str, str, str]:
    """Returns sign-off salutation, full name, and contact details."""
    full_name = candidate.full_name or "John Victor Aniekwe"
    phone_str = candidate.phone or "+2348130004114"
    email_str = candidate.email or "aniekwevictor9@gmail.com"
    portfolio_str = candidate.candidate.portfolio if (candidate.candidate and candidate.candidate.portfolio) else "https://nice-major.github.io/Nice-Major/"

    contact_parts = [p for p in [email_str, phone_str] if p and str(p).strip() and str(p).strip().lower() != "none"]
    contact_line = " | ".join(contact_parts)
    portfolio_line = f"Portfolio: {portfolio_str}" if portfolio_str and portfolio_str.lower() != "none" else ""

    signoff_block = "\n".join([line for line in [contact_line, portfolio_line] if line.strip()])
    return "Sincerely,", full_name, signoff_block


# ============================================================================
# 4. Multi-Format Renderers (Markdown, HTML, Plain Text)
# ============================================================================

def _render_markdown(
    header_block: Dict[str, str],
    salutation: str,
    paragraphs: List[str],
    closing_valediction: str,
    full_name: str,
    signoff_details: str,
) -> str:
    """Renders tailored cover letter in clean, structured Markdown."""
    lines: List[str] = [
        f"# {header_block['name']}",
    ]
    if header_block.get('contact'):
        lines.append(f"**{header_block['contact']}**  ")
    if header_block.get('links'):
        lines.append(f"*{header_block['links']}*  ")
    if header_block.get('location'):
        lines.append(f"*{header_block['location']}*  ")

    lines.extend([
        "",
        f"**Date:** {header_block['date']}",
        f"**To:** {header_block['recipient']}",
        f"**Subject:** Application for {header_block['target_role']}",
        "",
        "---",
        "",
        salutation,
        "",
    ])

    for p in paragraphs:
        lines.extend([p, ""])

    lines.extend([
        closing_valediction,
        "",
        f"**{full_name}**  ",
    ])
    for s_line in signoff_details.splitlines():
        if s_line.strip():
            lines.append(f"{s_line.strip()}  ")

    return "\n".join(lines).strip() + "\n"


def _render_plain_text(
    header_block: Dict[str, str],
    salutation: str,
    paragraphs: List[str],
    closing_valediction: str,
    full_name: str,
    signoff_details: str,
) -> str:
    """Renders tailored cover letter in clean ATS plain text."""
    lines: List[str] = [
        header_block['name'].upper(),
    ]
    if header_block.get('contact'):
        lines.append(header_block['contact'])
    if header_block.get('location'):
        lines.append(header_block['location'])
    if header_block.get('links'):
        lines.append(header_block['links'])

    lines.extend([
        "-" * 60,
        f"Date: {header_block['date']}",
        f"To: {header_block['recipient']}",
        f"Re: Application for {header_block['target_role']}",
        "",
        salutation,
        "",
    ])

    for p in paragraphs:
        lines.extend([p, ""])

    lines.extend([
        closing_valediction,
        "",
        full_name,
    ])
    if signoff_details:
        lines.append(signoff_details)

    raw_txt = "\n".join(lines).strip() + "\n"
    return clean_ats_text(raw_txt)


def _render_html(
    header_block: Dict[str, str],
    salutation: str,
    paragraphs: List[str],
    closing_valediction: str,
    full_name: str,
    signoff_details: str,
) -> str:
    """Renders tailored cover letter in clean, semantic print HTML."""
    esc = html.escape
    name_esc = esc(header_block['name'])
    contact_esc = esc(header_block['contact'])
    location_esc = esc(header_block['location'])
    links_esc = esc(header_block['links'])
    date_esc = esc(header_block['date'])
    recipient_esc = esc(header_block['recipient'])
    role_esc = esc(header_block['target_role'])
    salutation_esc = esc(salutation)
    valediction_esc = esc(closing_valediction)
    full_name_esc = esc(full_name)

    body_html_parts: List[str] = []
    for p in paragraphs:
        body_html_parts.append(f"    <p>{esc(p)}</p>")

    contact_items = [item for item in [contact_esc, location_esc, links_esc] if item]
    contact_line_html = "<span>•</span>".join(f"<span>{item}</span>" for item in contact_items)

    signoff_lines = [f"      <span>{esc(line.strip())}</span>" for line in signoff_details.splitlines() if line.strip()]
    signoff_html = "\n".join(signoff_lines)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cover Letter - {name_esc} - {role_esc}</title>
  <style>
    @page {{
      size: letter;
      margin: 1in;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 11pt;
      line-height: 1.5;
      color: #1a1a1a;
      background: #ffffff;
      max-width: 800px;
      margin: 0 auto;
      padding: 24px;
      font-variant-ligatures: none;
      -webkit-font-variant-ligatures: none;
    }}
    header {{
      border-bottom: 2px solid #2b4c7e;
      padding-bottom: 12px;
      margin-bottom: 20px;
    }}
    h1 {{
      font-size: 20pt;
      margin: 0 0 6px 0;
      color: #1a365d;
      letter-spacing: -0.5px;
    }}
    .contact-info {{
      font-size: 9.5pt;
      color: #4a5568;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .metadata {{
      margin: 20px 0;
      font-size: 10pt;
      color: #2d3748;
    }}
    .metadata div {{
      margin-bottom: 4px;
    }}
    .subject {{
      font-weight: 600;
      color: #1a365d;
      margin-top: 8px;
    }}
    .salutation {{
      margin-top: 24px;
      margin-bottom: 16px;
      font-weight: 600;
    }}
    p {{
      margin: 0 0 16px 0;
      text-align: justify;
    }}
    .signoff {{
      margin-top: 28px;
      page-break-inside: avoid;
    }}
    .signoff-name {{
      font-weight: 700;
      color: #1a365d;
      font-size: 11.5pt;
      margin-top: 12px;
    }}
    .signoff-details {{
      font-size: 9pt;
      color: #4a5568;
      display: flex;
      flex-direction: column;
      gap: 2px;
      margin-top: 4px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{name_esc}</h1>
    <div class="contact-info">
      {contact_line_html}
    </div>
  </header>

  <section class="metadata">
    <div><strong>Date:</strong> {date_esc}</div>
    <div><strong>To:</strong> {recipient_esc}</div>
    <div class="subject"><strong>Subject:</strong> Application for {role_esc}</div>
  </section>

  <main>
    <div class="salutation">{salutation_esc}</div>
{chr(10).join(body_html_parts)}
  </main>

  <footer class="signoff">
    <div>{valediction_esc}</div>
    <div class="signoff-name">{full_name_esc}</div>
    <div class="signoff-details">
{signoff_html}
    </div>
  </footer>
</body>
</html>
"""
    return html_template


# ============================================================================
# 5. Primary Cover Letter Generator Entrypoint
# ============================================================================

def generate_cover_letter(
    candidate: Union[CandidateProfile, Dict[str, Any], None] = None,
    job_text: str = "",
    target_role: str = "",
    company_name: str = "",
    output_format: str = "md",
    tone: str = "professional",
    date_str: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Generates an ATS-compliant, STAR-methodology tailored cover letter
    conforming strictly to global technical recruitment standards.

    Args:
        candidate: CandidateProfile instance or candidate data dictionary.
        job_text: Raw target job description text or posting requirements.
        target_role: Standardized target title (e.g. 'Cloud Solutions Architect', 'DevOps Engineer').
        company_name: Name of hiring company (e.g. 'Global Cloud Corp', 'AT&T').
        output_format: Target format: 'md' (Markdown), 'html' (print HTML), or 'txt' (plain text).
        tone: Tone mode: 'professional' (default), 'technical', 'executive', or 'results_oriented'.
        date_str: Optional formatted date string (defaults to current date).
        **kwargs: Additional overrides for flexibility.

    Returns:
        Tailored cover letter string in the requested output format.
    """
    # 1. Normalize Candidate Profile
    profile = _resolve_candidate_profile(candidate)

    # 2. Normalize arguments and handle kwargs overrides
    company = str(kwargs.get("company", company_name or "")).strip()
    role = _resolve_target_role(target_role, job_text)
    fmt = str(output_format or kwargs.get("format", "md")).lower().strip().lstrip(".")
    if fmt in ("htm", "html"):
        fmt = "html"
    elif fmt in ("txt", "text", "plain"):
        fmt = "txt"
    else:
        fmt = "md"

    active_tone = str(tone or kwargs.get("tone_mode", "professional")).lower().strip()
    if active_tone in ("results-oriented", "results_oriented"):
        active_tone = "results_oriented"
    elif active_tone not in SUPPORTED_TONES:
        active_tone = "professional"

    current_date = date_str or datetime.date.today().strftime("%B %d, %Y")

    # 3. Match and Extract Skills
    matched_skills = _extract_matched_technologies(profile, job_text, role)

    # 4. Construct Header Block (guarding against literal "None")
    cand_info = profile.candidate or CandidateInfo()
    full_name = profile.full_name or "John Victor Aniekwe"
    if str(full_name).strip().lower() == "none":
        full_name = "John Victor Aniekwe"

    email = profile.email or "aniekwevictor9@gmail.com"
    if str(email).strip().lower() == "none":
        email = ""

    phone = profile.phone or "+2348130004114"
    if str(phone).strip().lower() == "none":
        phone = ""

    location = profile.location or "Lagos, Nigeria (UTC+1 / CET Synchronous)"
    if str(location).strip().lower() == "none":
        location = ""

    portfolio = cand_info.portfolio if (cand_info and cand_info.portfolio) else "https://nice-major.github.io/Nice-Major/"
    if str(portfolio).strip().lower() == "none":
        portfolio = ""

    linkedin = cand_info.linked_in if (cand_info and cand_info.linked_in) else "https://www.linkedin.com/in/victor-aniekwe"
    if str(linkedin).strip().lower() == "none":
        linkedin = ""

    contact_parts = [p for p in [email, phone] if p and str(p).strip() and str(p).strip().lower() != "none"]
    contact_str = " | ".join(contact_parts)

    link_parts = [l for l in [portfolio, linkedin] if l and str(l).strip() and str(l).strip().lower() != "none"]
    links_str = " | ".join(link_parts)

    recipient_name = f"Hiring Team, {company}" if company else "Hiring Team / Engineering Leadership"

    header_block = {
        "name": full_name,
        "contact": contact_str,
        "location": location,
        "links": links_str,
        "date": current_date,
        "recipient": recipient_name,
        "target_role": role,
    }

    # 5. Synthesize STAR Paragraphs
    salutation = _build_salutation(company)
    opening_p = _build_opening_paragraph(profile, role, company, active_tone)
    body_paragraphs = _build_star_body_paragraphs(profile, role, company, matched_skills, active_tone)
    closing_p = _build_closing_paragraph(company, active_tone)

    all_paragraphs = [opening_p] + body_paragraphs + [closing_p]
    valediction, signoff_name, signoff_details = _build_signoff(profile)

    # 6. Render according to requested format
    if fmt == "html":
        raw_output = _render_html(
            header_block=header_block,
            salutation=salutation,
            paragraphs=all_paragraphs,
            closing_valediction=valediction,
            full_name=signoff_name,
            signoff_details=signoff_details,
        )
    elif fmt == "txt":
        raw_output = _render_plain_text(
            header_block=header_block,
            salutation=salutation,
            paragraphs=all_paragraphs,
            closing_valediction=valediction,
            full_name=signoff_name,
            signoff_details=signoff_details,
        )
    else:  # "md" (default)
        raw_output = _render_markdown(
            header_block=header_block,
            salutation=salutation,
            paragraphs=all_paragraphs,
            closing_valediction=valediction,
            full_name=signoff_name,
            signoff_details=signoff_details,
        )

    # 7. Post-Processing & Typographic Sanitization
    sanitized = sanitize_ligatures(raw_output)

    # Zero Buzzword Police
    for buzzword in BANNED_BUZZWORDS:
        if buzzword in sanitized.lower():
            sanitized = re.sub(rf"\b{re.escape(buzzword)}\b", "engineer", sanitized, flags=re.IGNORECASE)

    # Guarantee zero Credly tracking links
    if "credly.com" in sanitized.lower():
        sanitized = re.sub(r"https?://(?:www\.)?credly\.com[^\s\)\"\'>]*", "", sanitized, flags=re.IGNORECASE)

    return sanitized


def generate_cover_letter_pdf(
    candidate: Union[CandidateProfile, Dict[str, Any], None] = None,
    job_text: str = "",
    target_role: str = "",
    company_name: str = "",
    tone: str = "professional",
    date_str: Optional[str] = None,
    output_pdf_path: Optional[Union[str, Path]] = None,
    use_browser: bool = True,
) -> bytes:
    """
    Renders a tailored, STAR-methodology Cover Letter directly into a 1-page binary PDF (.pdf).
    """
    from pathlib import Path
    from tailoring.pdf_renderer import render_html_to_pdf_bytes, render_text_to_pdf_bytes

    html_cl = generate_cover_letter(
        candidate=candidate,
        job_text=job_text,
        target_role=target_role,
        company_name=company_name,
        output_format="html",
        tone=tone,
        date_str=date_str,
    )
    txt_cl = generate_cover_letter(
        candidate=candidate,
        job_text=job_text,
        target_role=target_role,
        company_name=company_name,
        output_format="txt",
        tone=tone,
        date_str=date_str,
    )
    if use_browser:
        return render_html_to_pdf_bytes(html_cl, fallback_text=txt_cl, output_pdf_path=output_pdf_path)
    pdf_bytes = render_text_to_pdf_bytes(txt_cl, title=f"Cover Letter - {company_name or target_role}")
    if output_pdf_path:
        p = Path(output_pdf_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pdf_bytes)
    return pdf_bytes


def get_letter_filename(
    candidate: Union[CandidateProfile, Dict[str, Any], None] = None,
    target_role: str = "DevOps Engineer",
    output_format: str = "pdf",
    company_name: str = "",
) -> str:
    """
    Generates strict ATS-compliant underscore filename for cover letters:
    {First}_{Last}_{Role}_Cover_Letter.{ext} (or {First}_{Last}_{Company}_{Role}_Cover_Letter.{ext}).
    """
    if isinstance(candidate, dict):
        cand = candidate.get("candidate", candidate)
        first = cand.get("first_name", cand.get("firstName", "John"))
        last = cand.get("last_name", cand.get("lastName", "Aniekwe"))
    elif isinstance(candidate, CandidateProfile):
        first = candidate.candidate.first_name
        last = candidate.candidate.last_name
    else:
        first = "John"
        last = "Aniekwe"

    fmt = str(output_format or "pdf").lower().lstrip(".")
    role_part = f"{company_name}_{target_role}" if company_name and company_name.strip() else target_role
    return safe_filename(first, last, role_part, "Cover_Letter", fmt)
