"""
ATS-Friendly Single-Column CV Tailoring Engine.
Module: tailoring.cv_tailor
Feature: F05 (ATS-Friendly CV Tailoring Engine)
Milestone: M2 (Competency Matching & ATS Document Tailoring)

Complies with Python 3.10+, zero external dependencies, strict ATS guidelines,
single-column linear layout, dynamic persona lens projection, keyword prioritization,
verified KPI metrics, and strict zero-tracker / zero-Credly link enforcement.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ingestion.models import (
    CandidateProfile,
    Certification,
    Education,
    KpiMetric,
    RoleLens,
    WorkExperience,
)
from ingestion.parser import load_profile, load_profile_from_dict
from ingestion.text_utils import (
    clean_ats_text,
    extract_clean_words,
    safe_filename,
    sanitize_ligatures,
    strip_markdown,
)


# ============================================================================
# 1. Dynamic Skill Prioritization & Matching
# ============================================================================

def _extract_job_keywords(job_text: str) -> Set[str]:
    """Tokenizes and sanitizes job description into lowercase keyword set."""
    if not job_text:
        return set()
    cleaned = sanitize_ligatures(job_text).lower()
    words = extract_clean_words(cleaned)
    keyword_set = set(words)

    # Detect common multi-word technology terms
    common_phrases = [
        "azure app service", "azure kubernetes service", "kubernetes", "terraform",
        "github actions", "azure devops", "azure monitor", "application insights",
        "cloudwatch", "docker", "bicep", "arm", "python", "bash", "powershell",
        "prometheus", "grafana", "microservices", "ci/cd", "devsecops", "devops",
        "active directory", "vpn", "vnet", "vpc", "linux", "ubuntu", "rest api",
        "solutions architect", "system administrator", "root cause analysis",
        "high availability", "disaster recovery", "openai", "copilot", "sla",
        "large language models", "machine learning", "predictive analytics",
        "data pipelines", "decision-support", "ai", "llm", "databricks",
        "retrieval", "version control", "ai foundry"
    ]
    for phrase in common_phrases:
        if phrase in cleaned:
            keyword_set.add(phrase)
    return keyword_set


def _score_skill_item(skill: str, keywords: Set[str]) -> int:
    """Computes match score for a skill item based on keyword hits."""
    if not keywords:
        return 0
    skill_lower = skill.lower()
    score = 0
    for kw in keywords:
        if " " in kw:
            if kw in skill_lower:
                score += 3
        else:
            if re.search(rf"\b{re.escape(kw)}\b", skill_lower):
                score += 1
    return score


def prioritize_skills(
    raw_skills_dict: Dict[str, Any],
    job_text: str = ""
) -> List[Tuple[str, List[str]]]:
    """
    Dynamically prioritizes skill categories and items matching the job description.
    Preserves all baseline skills while placing matched items first.
    """
    keywords = _extract_job_keywords(job_text)

    category_titles = {
        "cloud_architecture": "Cloud Platforms & Architecture",
        "cloudArchitecture": "Cloud Platforms & Architecture",
        "containerization_kubernetes": "Containers & Kubernetes Orchestration",
        "containerizationKubernetes": "Containers & Kubernetes Orchestration",
        "iac_automation": "CI/CD & Infrastructure as Code (IaC)",
        "iacAutomation": "CI/CD & Infrastructure as Code (IaC)",
        "dev_sec_ops": "AI-Augmented Platform Engineering & DevSecOps",
        "devSecOps": "AI-Augmented Platform Engineering & DevSecOps",
        "systems_linux_windows": "Systems Administration, OS & Networking",
        "systemsLinuxWindows": "Systems Administration, OS & Networking",
        "observability_monitoring": "Observability, SRE & Governance",
        "observabilityMonitoring": "Observability, SRE & Governance",
    }

    scored_categories: List[Tuple[int, str, List[str]]] = []

    for cat_key, title in category_titles.items():
        if cat_key not in raw_skills_dict:
            continue
        items = raw_skills_dict.get(cat_key, [])
        if not items or not isinstance(items, list):
            continue

        if not keywords:
            scored_categories.append((0, title, list(items)))
            continue

        matched: List[Tuple[int, str]] = []
        baseline: List[str] = []
        cat_score = 0

        for item in items:
            score = _score_skill_item(str(item), keywords)
            if score > 0:
                matched.append((score, str(item)))
                cat_score += score
            else:
                baseline.append(str(item))

        # Sort matched items descending by score
        matched.sort(key=lambda x: x[0], reverse=True)
        reordered_items = [item for _, item in matched] + baseline
        scored_categories.append((cat_score, title, reordered_items))

    # Sort categories by total match score descending if keywords present
    if keywords:
        scored_categories.sort(key=lambda x: x[0], reverse=True)

    return [(title, items) for _, title, items in scored_categories]


# ============================================================================
# 3. Certification Sanitizer (Zero Credly / Zero Tracker Policy)
# ============================================================================

def clean_certifications_for_ats(certifications: List[Certification]) -> List[str]:
    """
    Renders certifications into clean, verified strings adhering to the
    strict Zero External Tracker / No Credly Links policy.
    """
    cleaned: List[str] = []
    seen: Set[str] = set()

    for cert in certifications:
        name = cert.name.strip()
        issuer = cert.issuer.strip()
        status = cert.status.strip() or "Active"
        details = [status]
        issue_date = cert.issue_date.strip()
        if issue_date:
            details.append(f"issued {issue_date}")
        elif cert.year.strip().lower() not in ("", "active", "in progress"):
            details.append(f"issued {cert.year.strip()}")
        if cert.expiration_date.strip():
            expiry_label = "expired" if status.lower().startswith("expired") else "expires"
            details.append(f"{expiry_label} {cert.expiration_date.strip()}")

        dedup_key = f"{name.lower()}_{issuer.lower()}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        status_suffix = f" ({', '.join(details)})"
        if issuer:
            line = f"{name} — {issuer}{status_suffix}"
        else:
            line = f"{name}{status_suffix}"

        # Guarantee zero Credly or tracker references
        line = re.sub(r"https?://\S*credly\S*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"https?://\S*youracclaim\S*", "", line, flags=re.IGNORECASE)
        line = line.strip().rstrip("—").strip()
        if line:
            cleaned.append(line)

    return cleaned


def _format_work_preferences(categories: List[str]) -> List[str]:
    """Translate profile mobility facts into concise recruiter-facing statements."""
    formatted: List[str] = []
    for category in categories:
        normalized = category.casefold()
        if "remote" in normalized and "nigeria" in normalized:
            statement = "Remote roles: open to opportunities that accept candidates based in Nigeria."
        elif "relocation" in normalized and (
            "sponsor" in normalized or "work authorization" in normalized
        ):
            statement = "Relocation: open where employer-sponsored work authorization is available."
        elif "b2b" in normalized and "stepcon" in normalized:
            statement = "Consulting: B2B engagements through Stepcon Solutions."
        else:
            statement = category.strip().rstrip(".")
        if statement and statement not in formatted:
            formatted.append(statement)
    return formatted


def _unrepresented_kpi_metrics(
    metrics: List[KpiMetric],
    experience_list: List[Dict[str, Any]],
) -> List[KpiMetric]:
    """Keep achievement callouts only when their evidence is not already in experience."""
    experience_parts: List[str] = []
    for experience in experience_list:
        experience_parts.extend([
            str(experience.get("role", "")),
            str(experience.get("company", "")),
        ])
        experience_parts.extend(
            str(bullet if isinstance(bullet, str) else bullet.get("text", ""))
            for bullet in experience.get("bullets", [])
        )
    experience_text = " ".join(experience_parts).casefold()
    experience_text = re.sub(r"[^a-z0-9%]+", " ", experience_text)
    experience_terms = set(re.findall(r"[a-z0-9]+", experience_text))

    unique_metrics: List[KpiMetric] = []
    for metric in metrics:
        value = re.sub(r"[^a-z0-9%]+", " ", metric.value.casefold()).strip()
        label_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", metric.metric.casefold())
            if len(term) >= 3
        }
        matching_label_terms = label_terms.intersection(experience_terms)
        if (
            value
            and value in experience_text
            and matching_label_terms
            and len(matching_label_terms) >= min(2, len(label_terms))
        ):
            continue
        unique_metrics.append(metric)
    return unique_metrics


# ============================================================================
# 4. Markdown Generator (`.md`)
# ============================================================================

def _generate_markdown_cv(
    profile: CandidateProfile,
    lens: RoleLens,
    job_text: str = ""
) -> str:
    """Renders candidate CV into single-column ATS-compliant Markdown."""
    cand = profile.candidate
    full_name = cand.full_name or "Candidate"
    headline = lens.headline or cand.commitment or lens.role_key or "Candidate"

    # 1. Header Block
    contact_parts = []
    if cand.location:
        contact_parts.append(cand.location)
    if cand.phone:
        contact_parts.append(cand.phone)
    if cand.email:
        contact_parts.append(f"[{cand.email}](mailto:{cand.email})")
    if cand.linked_in:
        contact_parts.append(f"[LinkedIn]({cand.linked_in})")
    if cand.github:
        contact_parts.append(f"[GitHub]({cand.github})")
    if cand.portfolio:
        contact_parts.append(f"[Portfolio]({cand.portfolio})")

    experience_list = lens.experience or [e.to_dict() for e in profile.experience]
    unique_metrics = _unrepresented_kpi_metrics(profile.kpi_metrics, experience_list)
    is_domestic_nigeria = False
    if job_text:
        jl = job_text.lower()
        if any(term in jl for term in ["abuja", "lagos", "nigeria", "africa regional offices"]):
            is_domestic_nigeria = True
    work_preferences = _format_work_preferences(cand.mobility_categories)

    lines: List[str] = [
        f"# {full_name}",
        f"**{headline}**",
        "",
        " | ".join(contact_parts),
        "",
    ]
    if not is_domestic_nigeria and work_preferences:
        lines.extend([
            "## Location & Work Preferences",
            *[f"- {preference}" for preference in work_preferences],
            "",
            "---",
            "",
        ])
    lines.extend([
        "---",
        "",
    ])

    # 2. Professional Summary
    summary = lens.summary.strip()
    if summary:
        lines.extend([
            "## Professional Summary",
            summary,
            "",
            "---",
            "",
        ])

    if unique_metrics:
        lines.extend(["## Selected Achievements"])
        for metric in unique_metrics:
            metric_label = metric.metric.strip()
            context = metric.context.strip()
            label = f"{metric_label}: {context}" if metric_label and context else metric_label or context
            lines.append(f"- {metric.value} — {label}" if label else f"- {metric.value}")
        lines.extend(["", "---", ""])

    # 3. Core Competencies
    skills_matrix_dict = profile.skills_matrix.to_dict()
    prioritized_cats = prioritize_skills(skills_matrix_dict, job_text)

    lines.extend([
        "## Core Competencies",
    ])
    for title, items in prioritized_cats:
        if items:
            items_str = ", ".join(items)
            lines.append(f"- **{title}:** {items_str}")
    lines.extend(["", "---", ""])

    # 4. Professional Experience
    lines.append("## Professional Experience")

    for exp in experience_list:
        comp = exp.get("company", "")
        role = exp.get("role", "")
        loc = exp.get("location", "")
        period = exp.get("period", "")
        if not period and (exp.get("startDate") or exp.get("start_date")):
            s_date = exp.get("startDate", exp.get("start_date", ""))
            e_date = exp.get("endDate", exp.get("end_date", "Present"))
            period = f"{s_date} – {e_date}"

        lines.extend([
            f"### {role} — {comp}",
            f"*{loc} | {period}*",
            "",
        ])
        raw_bullets = exp.get("bullets", [])
        for b in raw_bullets:
            b_text = b if isinstance(b, str) else b.get("text", "")
            if b_text:
                lines.append(f"- {b_text}")
        lines.append("")

    lines.extend(["---", ""])

    # 5. Certifications
    certs = lens.certifications or profile.certifications
    cleaned_certs = clean_certifications_for_ats(certs)
    lines.append("## Certifications")
    for c_line in cleaned_certs:
        lines.append(f"- {c_line}")
    lines.extend(["", "---", ""])

    # 6. Key Projects
    projects = profile.projects
    if projects:
        lines.append("## Key Projects")
        for proj in projects:
            p_name = proj.get("name", "")
            p_desc = proj.get("description", "")
            p_tech = proj.get("technologies", [])
            tech_str = f" *(Stack: {', '.join(p_tech)})*" if p_tech else ""
            lines.append(f"- **{p_name}:** {p_desc}{tech_str}")
        lines.extend(["", "---", ""])

    # 7. Education
    edu = profile.education or (profile.candidate.education if profile.candidate else None)
    lines.append("## Education")
    if edu:
        details = " — ".join(value for value in (edu.degree, edu.institution) if value)
        if edu.period:
            details = f"{details} ({edu.period})" if details else edu.period
        if details:
            lines.append(f"- {details}")

    raw_doc = "\n".join(lines)
    return sanitize_ligatures(raw_doc)


# ============================================================================
# 5. Clean Print HTML Generator (`.html`)
# ============================================================================

def _generate_html_cv(
    profile: CandidateProfile,
    lens: RoleLens,
    job_text: str = ""
) -> str:
    """Renders candidate CV into single-column ATS-compliant clean print HTML."""
    cand = profile.candidate
    full_name = cand.full_name or "Candidate"
    headline = lens.headline or cand.commitment or lens.role_key or "Candidate"
    doc_title = f"{safe_filename(cand.first_name, cand.last_name, lens.role_key or 'DevOps', 'CV', 'html')}"

    experience_list = lens.experience or [e.to_dict() for e in profile.experience]
    unique_metrics = _unrepresented_kpi_metrics(profile.kpi_metrics, experience_list)
    is_domestic_nigeria = False
    if job_text:
        jl = job_text.lower()
        if any(term in jl for term in ["abuja", "lagos", "nigeria", "africa regional offices"]):
            is_domestic_nigeria = True

    work_preferences = _format_work_preferences(cand.mobility_categories)
    work_preferences_section_html = ""
    if not is_domestic_nigeria and work_preferences:
        work_preferences_section_html = (
            '<section><h2>Location &amp; Work Preferences</h2><ul>'
            + "".join(f"<li>{html.escape(preference)}</li>" for preference in work_preferences)
            + "</ul></section>"
        )

    # Contact items
    contact_spans = []
    if cand.location:
        contact_spans.append(f"<span>{html.escape(cand.location)}</span>")
    if cand.phone:
        contact_spans.append(f"<span>{html.escape(cand.phone)}</span>")
    if cand.email:
        contact_spans.append(f'<a href="mailto:{html.escape(cand.email)}">{html.escape(cand.email)}</a>')
    if cand.linked_in:
        contact_spans.append(f'<a href="{html.escape(cand.linked_in)}">LinkedIn</a>')
    if cand.github:
        contact_spans.append(f'<a href="{html.escape(cand.github)}">GitHub</a>')
    if cand.portfolio:
        contact_spans.append(f'<a href="{html.escape(cand.portfolio)}">Portfolio</a>')

    # Summary
    summary = lens.summary.strip()
    summary_body = f"<p>{html.escape(summary)}</p>" if summary else ""
    summary_section = f"<section><h2>Professional Summary</h2>{summary_body}</section>"
    kpis_li = []
    for metric in unique_metrics:
        metric_label = metric.metric.strip()
        context = metric.context.strip()
        label = f"{metric_label}: {context}" if metric_label and context else metric_label or context
        display = f"{metric.value} — {label}" if label else metric.value
        kpis_li.append(f"<li>{html.escape(display)}</li>")

    # Core Competencies
    skills_matrix_dict = profile.skills_matrix.to_dict()
    prioritized_cats = prioritize_skills(skills_matrix_dict, job_text)
    competencies_li = []
    for cat_title, items in prioritized_cats:
        if items:
            items_str = html.escape(", ".join(items))
            competencies_li.append(
                f'<li><strong>{html.escape(cat_title)}:</strong> {items_str}</li>'
            )

    # Professional Experience
    exp_articles = []
    for exp in experience_list:
        comp = html.escape(exp.get("company", ""))
        role = html.escape(exp.get("role", ""))
        loc = html.escape(exp.get("location", ""))
        period = exp.get("period", "")
        if not period and (exp.get("startDate") or exp.get("start_date")):
            s_date = exp.get("startDate", exp.get("start_date", ""))
            e_date = exp.get("endDate", exp.get("end_date", "Present"))
            period = f"{s_date} – {e_date}"
        period_esc = html.escape(period)

        bullets_html = []
        for b in exp.get("bullets", []):
            b_text = b if isinstance(b, str) else b.get("text", "")
            if b_text:
                bullets_html.append(f"<li>{html.escape(b_text)}</li>")

        exp_articles.append(f"""
        <article class="exp-item">
          <div class="exp-header">
            <span class="exp-role">{role}</span> — <span class="exp-company">{comp}</span>
            <span class="exp-dates">{loc} | {period_esc}</span>
          </div>
          <ul class="exp-bullets">
            {"".join(bullets_html)}
          </ul>
        </article>
        """)

    # Certifications (Zero Credly)
    certs = lens.certifications or profile.certifications
    cleaned_certs = clean_certifications_for_ats(certs)
    certs_li = [f"<li>{html.escape(c)}</li>" for c in cleaned_certs]

    # Projects (safe escaping for tags like <Platform>)
    projects = profile.projects
    projects_li = []
    for proj in projects:
        p_name = html.escape(proj.get("name", ""))
        p_desc = html.escape(proj.get("description", ""))
        p_tech = proj.get("technologies", [])
        tech_str = f" <em>(Stack: {html.escape(', '.join(p_tech))})</em>" if p_tech else ""
        projects_li.append(f"<li><strong>{p_name}:</strong> {p_desc}{tech_str}</li>")
    projects_section = (
        f'<section><h2>Key Projects</h2><ul>{"".join(projects_li)}</ul></section>'
        if projects_li
        else ""
    )

    # Education
    edu = profile.education or (profile.candidate.education if profile.candidate else None)
    if edu:
        details = " — ".join(value for value in (edu.degree, edu.institution) if value)
        if edu.period:
            details = f"{details} ({edu.period})" if details else edu.period
        edu_html = f"<li>{html.escape(details)}</li>" if details else ""
    else:
        edu_html = ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(doc_title)}</title>
  <style>
    * {{
      box-sizing: border-box;
      font-variant-ligatures: none;
      -webkit-font-variant-ligatures: none;
    }}
    body {{
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1E293B;
      background: #F8FAFC;
      line-height: 1.5;
      font-size: 13.5px;
    }}
    .cv-container {{
      max-width: 820px;
      margin: 24px auto;
      background: #FFFFFF;
      padding: 40px 48px;
      border: 1px solid #E2E8F0;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
    }}
    header {{
      border-bottom: 2px solid #0F52BA;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 4px 0;
      font-size: 26px;
      font-weight: 800;
      color: #0F172A;
      letter-spacing: -0.3px;
    }}
    .role-headline {{
      font-size: 14.5px;
      font-weight: 700;
      color: #0F52BA;
      margin-bottom: 8px;
    }}
    .contact-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12.5px;
      color: #475569;
    }}
    .contact-strip a {{
      color: #0F52BA;
      text-decoration: none;
      font-weight: 500;
    }}
    section {{
      margin-bottom: 18px;
    }}
    h2 {{
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #0F172A;
      border-bottom: 1.5px solid #E2E8F0;
      padding-bottom: 4px;
      margin: 16px 0 10px 0;
    }}
    p {{
      margin: 0 0 8px 0;
      text-align: justify;
    }}
    ul {{
      margin: 4px 0 8px 0;
      padding-left: 18px;
    }}
    li {{
      margin-bottom: 4px;
    }}
    .exp-item {{
      margin-bottom: 14px;
      page-break-inside: avoid;
    }}
    .exp-header {{
      font-size: 13.5px;
      margin-bottom: 4px;
    }}
    .exp-role {{
      font-weight: 700;
      color: #0F172A;
    }}
    .exp-company {{
      font-weight: 700;
      color: #0F52BA;
    }}
    .exp-dates {{
      font-size: 12px;
      color: #64748B;
      float: right;
    }}
    @media print {{
      @page {{
        size: A4;
        margin: 9mm 12mm;
      }}
      body {{
        background: #FFFFFF;
        font-size: 8.8pt;
      }}
      .cv-container {{
        max-width: 100%;
        margin: 0;
        padding: 0;
        border: none;
        box-shadow: none;
      }}
      header {{ padding-bottom: 8px; margin-bottom: 10px; }}
      h1 {{ font-size: 16pt; margin-bottom: 2px; }}
      .role-headline {{ font-size: 10pt; margin-bottom: 4px; }}
      .contact-strip {{ font-size: 8.5pt; gap: 6px; }}
      section {{ margin-bottom: 8px; }}
      h2 {{ font-size: 9.8pt; margin: 8pt 0 4pt 0; padding-bottom: 2px; break-after: avoid; page-break-after: avoid; }}
      p, li {{ font-size: 8.7pt; line-height: 1.28; margin-bottom: 2.5px; }}
      ul {{ margin: 2px 0 5px 0; padding-left: 15px; }}
      .exp-item {{ margin-bottom: 7px; page-break-inside: avoid; }}
      .exp-header {{ font-size: 9.2pt; margin-bottom: 2px; }}
      .exp-dates {{ float: none; display: block; font-size: 8.2pt; color: #475569; margin-top: 1px; }}
    }}
  </style>
</head>
<body>
  <div class="cv-container">
    <header>
      <h1>{html.escape(full_name)}</h1>
      <div class="role-headline">{html.escape(headline)}</div>
      <div class="contact-strip">
        {" | ".join(contact_spans)}
      </div>
    </header>

    <main>
      {summary_section}

      {work_preferences_section_html}

      {f'<section><h2>Selected Achievements</h2><ul>{"".join(kpis_li)}</ul></section>' if kpis_li else ""}

      <section>
        <h2>Core Competencies</h2>
        <ul>
          {"".join(competencies_li)}
        </ul>
      </section>

      <section>
        <h2>Professional Experience</h2>
        {"".join(exp_articles)}
      </section>

      <section>
        <h2>Certifications</h2>
        <ul>
          {"".join(certs_li)}
        </ul>
      </section>

      {projects_section}

      <section>
        <h2>Education</h2>
        <ul>
          {edu_html}
        </ul>
      </section>
    </main>
  </div>
</body>
</html>"""
    return sanitize_ligatures(html_content)


# ============================================================================
# 6. Plain Text Generator (`.txt`)
# ============================================================================

def _generate_plain_text_cv(
    profile: CandidateProfile,
    lens: RoleLens,
    job_text: str = ""
) -> str:
    """Renders candidate CV into single-column ATS-compliant plain text."""
    cand = profile.candidate
    full_name = (cand.full_name or "Candidate").upper()
    headline = lens.headline or cand.commitment or lens.role_key or "Candidate"

    experience_list = lens.experience or [e.to_dict() for e in profile.experience]
    unique_metrics = _unrepresented_kpi_metrics(profile.kpi_metrics, experience_list)
    is_domestic_nigeria = False
    if job_text:
        jl = job_text.lower()
        if any(term in jl for term in ["abuja", "lagos", "nigeria", "africa regional offices"]):
            is_domestic_nigeria = True
    work_preferences = _format_work_preferences(cand.mobility_categories)

    lines: List[str] = [
        full_name,
        headline,
        f"{cand.location} | {cand.phone} | {cand.email}",
        f"LinkedIn: {cand.linked_in} | GitHub: {cand.github} | Portfolio: {cand.portfolio}",
    ]
    if not is_domestic_nigeria and work_preferences:
        lines.extend(["", "LOCATION & WORK PREFERENCES"])
        lines.extend(f"- {preference}" for preference in work_preferences)
    if lens.summary.strip():
        lines.extend(["", "=" * 80, "PROFESSIONAL SUMMARY", "=" * 80, lens.summary.strip()])
    if unique_metrics:
        lines.extend(["", "=" * 80,         "SELECTED ACHIEVEMENTS", "=" * 80])
        for metric in unique_metrics:
            metric_label = metric.metric.strip()
            context = metric.context.strip()
            label = f"{metric_label}: {context}" if metric_label and context else metric_label or context
            lines.append(f"- {metric.value} — {label}" if label else f"- {metric.value}")
    lines.extend([
        "",
        "=" * 80,
        "CORE COMPETENCIES",
        "=" * 80,
    ])

    skills_matrix_dict = profile.skills_matrix.to_dict()
    prioritized_cats = prioritize_skills(skills_matrix_dict, job_text)
    for title, items in prioritized_cats:
        if items:
            lines.append(f"- {title.upper()}: {', '.join(items)}")
    lines.append("")

    lines.extend([
        "=" * 80,
        "PROFESSIONAL EXPERIENCE",
        "=" * 80,
    ])
    for exp in experience_list:
        comp = exp.get("company", "")
        role = exp.get("role", "")
        loc = exp.get("location", "")
        period = exp.get("period", "")
        if not period and (exp.get("startDate") or exp.get("start_date")):
            s_date = exp.get("startDate", exp.get("start_date", ""))
            e_date = exp.get("endDate", exp.get("end_date", "Present"))
            period = f"{s_date} – {e_date}"

        lines.extend([
            f"{role.upper()} — {comp}",
            f"{loc} | {period}",
            "-" * 40,
        ])
        for b in exp.get("bullets", []):
            b_text = b if isinstance(b, str) else b.get("text", "")
            if b_text:
                lines.append(f"- {b_text}")
        lines.append("")

    lines.extend([
        "=" * 80,
        "CERTIFICATIONS",
        "=" * 80,
    ])
    certs = lens.certifications or profile.certifications
    cleaned_certs = clean_certifications_for_ats(certs)
    for c in cleaned_certs:
        lines.append(f"- {c}")
    lines.append("")

    projects = profile.projects
    if projects:
        lines.extend([
            "=" * 80,
            "KEY PROJECTS",
            "=" * 80,
        ])
        for proj in projects:
            p_name = proj.get("name", "")
            p_desc = proj.get("description", "")
            p_tech = proj.get("technologies", [])
            tech_str = f" [Stack: {', '.join(p_tech)}]" if p_tech else ""
            lines.append(f"- {p_name}: {p_desc}{tech_str}")
        lines.append("")

    lines.extend([
        "=" * 80,
        "EDUCATION",
        "=" * 80,
    ])
    edu = profile.education or (profile.candidate.education if profile.candidate else None)
    if edu:
        details = " — ".join(value for value in (edu.degree, edu.institution) if value)
        if edu.period:
            details = f"{details} ({edu.period})" if details else edu.period
        if details:
            lines.append(f"- {details}")

    raw_text = "\n".join(lines)
    return clean_ats_text(raw_text)


# ============================================================================
# 7. Primary Public API
# ============================================================================

def generate_cv(
    candidate: Union[CandidateProfile, Dict[str, Any], str, None],
    job_text: str = "",
    target_role: str = "",
    output_format: str = "md"
) -> str:
    """
    Primary API generating tailored, single-column, ATS-compliant CVs.

    Conforms to:
    - Global ATS single-column hierarchy (Summary, Competencies, Experience, Certs, Projects, Education)
    - Dynamic persona lens projection via candidate.get_role_lens(target_role)
    - Dynamic keyword prioritization matching job description
    - Strict Zero External Tracker / No Credly Links policy
    - Ligature sanitization and Windows safe naming

    Args:
        candidate: CandidateProfile instance, dict, filepath, or None.
        job_text: Optional job description text for keyword prioritization.
        target_role: Target job title (e.g. "DevOps Engineer", "Cloud Solutions Architect").
        output_format: Target format ('md', 'html', 'txt'). Case-insensitive.

    Returns:
        Rendered CV document string.
    """
    # 1. Normalize Candidate Profile
    if candidate is None:
        cand_profile = load_profile()
    elif isinstance(candidate, dict):
        cand_profile = load_profile_from_dict(candidate)
    elif isinstance(candidate, (str, Path)):
        cand_profile = load_profile(candidate)
    elif isinstance(candidate, CandidateProfile):
        cand_profile = candidate
    else:
        raise TypeError(f"Expected CandidateProfile, dict, or path, got {type(candidate).__name__}")

    # 2. Project Role Lens (defaults to devops if unknown/empty)
    clean_role = str(target_role or "DevOps Engineer").strip()
    lens = cand_profile.get_role_lens(clean_role)

    # 3. Format Resolution
    fmt = str(output_format or "md").strip().lower().lstrip(".")

    if fmt in ("html", "htm"):
        cv_out = _generate_html_cv(cand_profile, lens, job_text)
    elif fmt in ("txt", "text", "plain"):
        cv_out = _generate_plain_text_cv(cand_profile, lens, job_text)
    else:
        cv_out = _generate_markdown_cv(cand_profile, lens, job_text)

    # Guarantee zero Credly tracking links
    if "credly.com" in cv_out.lower():
        cv_out = re.sub(r"https?://(?:www\.)?credly\.com[^\s\)\"\'>]*", "", cv_out, flags=re.IGNORECASE)

    return cv_out


def generate_cv_pdf(
    candidate: Union[CandidateProfile, Dict[str, Any], str, None],
    job_text: str = "",
    target_role: str = "",
    output_pdf_path: Optional[Union[str, Path]] = None,
    use_browser: bool = True,
) -> bytes:
    """
    Renders a tailored, single-column, ATS-compliant CV directly into a binary PDF (.pdf).
    Uses Headless Chromium/Edge when use_browser=True and falls back to the pure-Python PDF 1.4 writer.
    """
    from tailoring.pdf_renderer import render_html_to_pdf_bytes, render_text_to_pdf_bytes

    html_cv = generate_cv(candidate, job_text=job_text, target_role=target_role, output_format="html")
    md_cv = generate_cv(candidate, job_text=job_text, target_role=target_role, output_format="md")
    if use_browser:
        return render_html_to_pdf_bytes(html_cv, fallback_text=md_cv, output_pdf_path=output_pdf_path)
    pdf_bytes = render_text_to_pdf_bytes(md_cv, title=f"CV - {target_role or 'DevOps Engineer'}")
    if output_pdf_path:
        p = Path(output_pdf_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pdf_bytes)
    return pdf_bytes


def get_cv_filename(
    candidate: Union[CandidateProfile, Dict[str, Any]],
    target_role: str = "DevOps Engineer",
    output_format: str = "md",
    company_name: str = "",
) -> str:
    """
    Generates strict ATS-compliant underscore filename:
    {First}_{Last}_{Role}_CV.{ext} (or {First}_{Last}_{Company}_{Role}_CV.{ext} when company_name is provided).
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

    fmt = str(output_format or "md").lower().lstrip(".")
    role_part = f"{company_name}_{target_role}" if company_name and company_name.strip() else target_role
    return safe_filename(first, last, role_part, "CV", fmt)
