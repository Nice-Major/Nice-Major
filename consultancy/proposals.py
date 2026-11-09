"""
Stepcon Solutions (RC - 8284984) Tailored B2B Commercial Proposal Generator.
Module: consultancy.proposals
Feature: F14 (Stepcon Solutions Consultancy Pipeline)
Milestone: M5 (Interactive CLI & Stepcon Solutions Pipeline)

Produces complete, enterprise-grade commercial proposals featuring:
- Statutory CAC entity validation (Stepcon Solutions, RC - 8284984).
- Lead Engagement Architect John Victor Aniekwe (KCNA, AWS SAA & Developer, B.Sc. Comp Sci).
- Quantifiable operational commitments (99.9% Uptime SLA, 99% same-day L3 RCA resolution).
- Corp-to-Corp (C2C) B2B contracting model in synchronous CET/EMEA hours.
- Multi-currency commercial terms (USD $, GBP £, EUR €, NGN ₦).
- Rigorous placeholder protection against accidental literal "None" pollution.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ingestion.models import CandidateProfile, StepconProfile
from ingestion.parser import load_profile
from ingestion.text_utils import safe_filename, sanitize_ligatures


# ============================================================================
# 1. Proposal Construction Engine
# ============================================================================

def _clean_field(val: Any, default: str) -> str:
    """Guarantees a field is non-empty and never evaluates to literal string 'None'."""
    if val is None:
        return default
    s = str(val).strip()
    if not s or s.lower() == "none":
        return default
    return s


def generate_proposal(
    stepcon: Union[StepconProfile, Dict[str, Any]],
    tender: Union[Any, Dict[str, Any]],
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
    date_str: Optional[str] = None,
) -> str:
    """
    Generates a formal, tailored B2B corporate proposal for Stepcon Solutions (RC - 8284984).

    Args:
        stepcon: StepconProfile instance or raw dictionary.
        tender: TenderOpportunity instance or dictionary containing title, description, client, etc.
        candidate: Optional CandidateProfile instance for Lead Architect credentials.
        date_str: Optional formatted date string.

    Returns:
        Structured Markdown proposal document string.
    """
    # 1. Normalize Stepcon Profile
    if isinstance(stepcon, dict):
        stepcon_obj = StepconProfile.from_dict(stepcon)
    elif isinstance(stepcon, StepconProfile):
        stepcon_obj = stepcon
    else:
        stepcon_obj = StepconProfile()

    # 2. Normalize Lead Candidate Profile
    if candidate is None:
        cand_profile = load_profile(allow_fallback=True)
    elif isinstance(candidate, dict):
        from ingestion.parser import load_profile_from_dict
        cand_profile = load_profile_from_dict(candidate)
    elif isinstance(candidate, CandidateProfile):
        cand_profile = candidate
    else:
        cand_profile = CandidateProfile()

    # 3. Extract and Sanitize Tender Attributes
    if isinstance(tender, dict):
        t_id = _clean_field(tender.get("tender_id", tender.get("id")), "TND-2026-CONSULTANCY")
        t_title = _clean_field(tender.get("title"), "Enterprise Cloud Infrastructure & DevSecOps Modernization")
        t_client = _clean_field(tender.get("client"), "Enterprise Procurement Committee")
        t_desc = _clean_field(tender.get("description"), "Turnkey multi-cloud platform architecture and automation.")
        t_budget = _clean_field(tender.get("budget"), "B2B Milestone Retainer (Multi-Currency Options)")
        t_deadline = _clean_field(tender.get("deadline"), "Standard Evaluation Window")
    else:
        t_id = _clean_field(getattr(tender, "tender_id", getattr(tender, "id", None)), "TND-2026-CONSULTANCY")
        t_title = _clean_field(getattr(tender, "title", None), "Enterprise Cloud Infrastructure & DevSecOps Modernization")
        t_client = _clean_field(getattr(tender, "client", None), "Enterprise Procurement Committee")
        t_desc = _clean_field(getattr(tender, "description", None), "Turnkey multi-cloud platform architecture and automation.")
        t_budget = _clean_field(getattr(tender, "budget", None), "B2B Milestone Retainer (Multi-Currency Options)")
        t_deadline = _clean_field(getattr(tender, "deadline", None), "Standard Evaluation Window")

    active_date = date_str or datetime.date.today().strftime("%B %d, %Y")

    # Lead Architect Credentials
    lead_name = _clean_field(cand_profile.full_name, "John Victor Aniekwe")
    lead_email = _clean_field(cand_profile.email, "aniekwevictor9@gmail.com")
    lead_phone = _clean_field(cand_profile.phone, "+2348130004114")
    cac_reg = _clean_field(stepcon_obj.cac_number, "RC - 8284984")
    company_name = _clean_field(stepcon_obj.company_name, "Stepcon Solutions")

    # Build Proposal Markdown Content
    lines = [
        f"# COMMERCIAL B2B CONSULTANCY PROPOSAL",
        f"**Tender Reference:** {t_id} — {t_title}",
        f"**Client Organization:** {t_client}",
        f"**Prepared By:** {company_name} (CAC Statutory Registration: {cac_reg})",
        f"**Lead Engagement Architect:** {lead_name}",
        f"**Date:** {active_date}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        f"{company_name} ({cac_reg}) is pleased to submit this comprehensive commercial proposal in response to the request for ",
        f"proposal from **{t_client}** regarding *{t_title}*. As an incorporated technology consultancy registered with the Corporate ",
        "Affairs Commission (CAC) of the Federal Republic of Nigeria, Stepcon Solutions delivers high-availability Cloud Architecture, ",
        "DevSecOps automation pipelines, Kubernetes container orchestration pods, and L3 infrastructure escalation engineering.",
        "",
        "We offer an immediate, turnkey **Corp-to-Corp (C2C)** operational engagement model operating in synchronous CET/UK/EMEA business ",
        "hours. This model eliminates international employer-of-record (EOR) markups, payroll complexities, and cross-border tax friction ",
        "while providing institutional-grade engineering rigor backed by strict Service Level Agreements (SLAs).",
        "",
        "---",
        "",
        "## 2. Statutory Legal Identity & Corporate Credentials",
        f"- **Corporate Entity Name:** {company_name}",
        f"- **Statutory Registration Number:** {cac_reg}",
        "- **Registration Authority:** Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
        "- **Operating Time Zone:** UTC+1 / CET / UK / EMEA Synchronous Business Hours",
        "- **Engagement Model:** Direct B2B Corp-to-Corp (C2C) Retainer or Fixed-Milestone SOW",
        "- **Official Contact:** aniekwevictor9@gmail.com | +2348130004114",
        "",
        "---",
        "",
        "## 3. Scope of Work & Solution Architecture",
        f"Based on our evaluation of the requirements for **{t_title}**, Stepcon Solutions proposes a phased implementation architecture:",
        "",
        "### Phase 1: Declarative Infrastructure as Code (IaC) & Cloud Estate Governance",
        "- Architect scalable, modular multi-cloud infrastructure across Amazon Web Services (AWS) and Microsoft Azure using Terraform and ARM/Bicep.",
        "- Apply the Well-Architected Framework: implement zero-trust networking, virtual networks (VNets/VPCs), private endpoints, and FinOps cost governance.",
        "- Accelerate environment provisioning from days to **<15 minutes** through deterministic GitOps pipelines.",
        "",
        "### Phase 2: Kubernetes Container Orchestration & Microservices",
        "- Deploy production-grade Kubernetes clusters (AKS / EKS) utilizing declarative manifests and Helm charts.",
        "- Configure horizontal and vertical pod auto-scalers, ingress controllers, network security policies, and container registry scanning.",
        "- Operationalize AI/ML microservices and containerized backends maintaining optimal resource utilization and latency thresholds.",
        "",
        "### Phase 3: Automated DevSecOps CI/CD Delivery Pipelines",
        "- Implement automated GitHub Actions and Azure DevOps CI/CD workflows with mandatory linting, static code analysis, and vulnerability gating.",
        "- Establish automated staging, canary, and blue-green deployments for zero-downtime production rollouts.",
        "",
        "### Phase 4: L3 Escalation Support & Observability Governance",
        "- Author comprehensive Troubleshooting Guides (TsG) and engineering wikis for operational handover.",
        "- Configure centralized monitoring dashboards using Azure Monitor, Application Insights, and CloudWatch.",
        "- Establish an automated escalation hub achieving a verified **99% first-day Root Cause Analysis (RCA)** resolution rate.",
        "",
        "---",
        "",
        "## 4. Key Personnel & Lead Architect Credentials",
        "Stepcon Solutions engagements are led by verified, industry-certified cloud and platform engineering leaders:",
        "",
        f"### {lead_name} — Lead Cloud Solutions Architect & Managing Principal",
        "- **Formal Education:** Bachelor of Science (B.Sc.) in Computer Science, University of Nigeria (2014 – 2018).",
        "- **CNCF / Linux Foundation Certification:** Kubernetes and Cloud Native Associate (KCNA) — Active.",
        "- **Amazon Web Services Certifications:**",
        "  - AWS Certified Solutions Architect – Associate (Active)",
        "  - AWS Certified Developer – Associate (Active)",
        "  - AWS Certified Cloud Practitioner (Active)",
        "- **Industry Track Record:** Over 5 years of verified production systems experience maintaining a sustained **99.9% uptime SLA** across hybrid cloud environments.",
        "",
        "---",
        "",
        "## 5. Service Level Agreement (SLA) & Operational Commitments",
        "Stepcon Solutions binds its commercial deliverables to strict, measurable operational guarantees:",
        "",
        "| Metric | Target Commitment | Measurement & Verification |",
        "|---|---|---|",
        "| **Infrastructure Availability SLA** | **99.9% Production Uptime** | Automated synthetic probes & CloudWatch/Azure Monitor metrics |",
        "| **L3 Incident RCA Resolution** | **99% Same-Day Resolution** | Post-incident root-cause documentation within 24 hours |",
        "| **Multi-Environment Provisioning** | **<15 Minutes** | Automated Terraform execution via CI/CD pipelines |",
        "| **Working Hours Alignment** | **CET / UTC+1 Synchronous** | Real-time Slack/Teams collaboration with European & African teams |",
        "",
        "---",
        "",
        "## 6. Commercial Terms & Multi-Currency Invoicing",
        f"{company_name} operates on a straightforward corporate Corp-to-Corp (C2C) billing structure. We accommodate international ",
        "and domestic banking rails with multi-currency invoice settlement:",
        "",
        "### Accepted Settlement Currencies:",
        "1. **United States Dollars (USD - $)**: Corporate wire via SWIFT / ACH / Federal Reserve wire.",
        "2. **British Pounds Sterling (GBP - £)**: UK Faster Payments / BACS corporate wire.",
        "3. **European Union Euros (EUR - €)**: SEPA Credit Transfer / European interbank settlement.",
        "4. **Nigerian Naira (NGN - ₦)**: Central Bank of Nigeria NIBSS Instant Payment (NIP) / Corporate RTGS.",
        "",
        "### Commercial Structure:",
        f"- **Project Reference Budget:** {t_budget}",
        "- **Payment Terms:** Net 15 or Net 30 corporate invoicing upon milestone completion or monthly engineering pod retainer.",
        f"- **Tax Compliance:** Stepcon Solutions is a duly registered corporate entity ({cac_reg}); engagement operates as independent B2B vendor contract.",
        "",
        "---",
        "",
        "## 7. Execution Sign-Off & Corporate Authorization",
        f"This proposal is submitted on behalf of **{company_name}** ({cac_reg}) and remains valid for acceptance within 60 days.",
        "",
        "**Authorized Corporate Representative:**",
        f"**{lead_name}**  ",
        f"Lead Cloud Solutions Architect & Managing Principal  ",
        f"**{company_name}** ({cac_reg})  ",
        f"Email: {lead_email} | Phone: {lead_phone}  ",
        f"Lagos, Nigeria (UTC+1 / CET Synchronous)  ",
    ]

    proposal_raw = "\n".join(lines)
    proposal_clean = sanitize_ligatures(proposal_raw)

    # Post-processing guarantee: absolute zero literal "None" occurrences
    if "None" in proposal_clean:
        proposal_clean = re.sub(r"\bNone\b", "Standard Corporate Term", proposal_clean)

    return proposal_clean


def get_proposal_filename(
    tender: Union[Any, Dict[str, Any]],
    date_str: Optional[str] = None,
) -> str:
    """
    Generates a clean, ATS/Windows-safe filename for a generated corporate proposal:
    Proposal_Stepcon_{TenderId}_{Date}.md
    """
    if isinstance(tender, dict):
        raw_id = tender.get("tender_id") or tender.get("id") or "Tender"
    elif hasattr(tender, "tender_id") or hasattr(tender, "id"):
        raw_id = getattr(tender, "tender_id", None) or getattr(tender, "id", None) or "Tender"
    else:
        raw_id = str(tender) if tender is not None else "Tender"

    clean_tid = _clean_field(raw_id, "Tender")
    clean_id = re.sub(r"[^\w\-]", "_", str(clean_tid)).strip("_")
    if not clean_id or clean_id.lower() == "none":
        clean_id = "Tender"
    active_date = (date_str or datetime.date.today().isoformat()).replace("-", "")
    return f"Proposal_Stepcon_{clean_id}_{active_date}.md"
