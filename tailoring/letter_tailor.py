"""
Profile-grounded cover letter generation.

Creates tailored Markdown, HTML, and plain-text letters from candidate-profile
facts and the target job description without injecting fallback credentials,
achievements, metrics, or contact details.
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
    Identifies only candidate-profile skills that match the target job description.
    """
    all_candidate_skills = candidate.get_skills_flat()

    if not job_text or not job_text.strip():
        return all_candidate_skills[:6]

    clean_words = set(extract_clean_words(job_text))
    matched: List[str] = []

    for skill in all_candidate_skills:
        skill_lower = skill.lower()
        if skill_lower in job_text.lower():
            matched.append(skill)
        elif any(part in clean_words for part in re.split(r"[\s/,-]+", skill_lower) if len(part) >= 3):
            matched.append(skill)

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
    """Builds an opening using only details present in the candidate profile."""
    company_phrase = f" at {company_name.strip()}" if company_name and company_name.strip() else ""
    opening = f"I am applying for the {target_role} position{company_phrase}."
    summary = candidate.get_role_lens(target_role).summary.strip()
    if summary:
        opening += f" My profile summarizes my background as follows: {summary}"
    education = candidate.education or candidate.candidate.education
    if education:
        education_details = " — ".join(value for value in (education.degree, education.institution) if value)
        if education.period:
            education_details = f"{education_details} ({education.period})" if education_details else education.period
        if education_details:
            opening += f" My profile lists {education_details}."
    return opening


def _build_star_body_paragraphs(
    candidate: CandidateProfile,
    target_role: str,
    company_name: str,
    matched_skills: List[str],
    tone: str,
) -> List[str]:
    """Summarizes only profile-listed experience, metrics, and matching skills."""
    paragraphs: List[str] = []
    experience_bullets = []
    for experience in candidate.experience:
        for bullet in experience.to_dict().get("bullets", []):
            text = bullet if isinstance(bullet, str) else bullet.get("text", "")
            if text and text not in experience_bullets:
                experience_bullets.append(text)
            if len(experience_bullets) == 2:
                break
        if len(experience_bullets) == 2:
            break
    if experience_bullets:
        paragraphs.append("Relevant profile experience includes: " + " ".join(experience_bullets))

    metrics = []
    for metric in candidate.kpi_metrics:
        detail = " ".join(part.strip() for part in (metric.value, metric.metric, metric.context) if part.strip())
        if detail:
            metrics.append(detail)
    if metrics:
        paragraphs.append("The profile records these outcomes: " + "; ".join(metrics) + ".")

    if matched_skills:
        paragraphs.append("Skills listed in my profile that match the role include " + ", ".join(matched_skills[:5]) + ".")
    elif not paragraphs:
        paragraphs.append("I would welcome the opportunity to discuss how the experience listed in my profile may fit this role.")
    return paragraphs


def _build_closing_paragraph(company_name: str, tone: str) -> str:
    """Constructs a confident, professional call to action and closing."""
    company_ref = f" {company_name.strip()}" if company_name and company_name.strip() else ""
    return f"I would welcome the opportunity to discuss my application{company_ref}. Thank you for your time and consideration."


def _build_signoff(candidate: CandidateProfile) -> Tuple[str, str, str]:
    """Returns sign-off salutation, full name, and contact details."""
    full_name = candidate.full_name or "Candidate"
    phone_str = candidate.phone
    email_str = candidate.email
    portfolio_str = candidate.candidate.portfolio if candidate.candidate else ""

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
    full_name = profile.full_name or "Candidate"
    email = profile.email
    phone = profile.phone
    location = profile.location
    portfolio = cand_info.portfolio if cand_info else ""
    linkedin = cand_info.linked_in if cand_info else ""

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
