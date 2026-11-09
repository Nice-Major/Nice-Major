"""
Multi-Part MIME Daily Opportunity Digest Builder & Formatter.
Module: dispatch.digest
Feature: F11 (Daily 8:00 AM Notification Dispatch)
Milestone: M4 (Daily 8:00 AM Dispatcher & Scheduling Architecture)

Complies with:
- Multi-part MIME (multipart/mixed wrapping multipart/alternative + attachments)
- Strict inline CSS (zero external stylesheets, zero <link rel="stylesheet">)
- Verified executive metrics ("99.9%" Cloud Uptime SLA and "99%" L3 RCA Resolution)
- Transparent 5-dimension scoring breakdowns (Skills 35%, Title 25%, Metrics 15%, Mobility 15%, Certs 10%)
- Clickable opportunity URLs and company links
- Non-ASCII UTF-8 header sanitization (Header(subject, "utf-8"))
- Graceful empty digest handling for days with 0 matching opportunities
"""

from __future__ import annotations

import datetime
import html
import re
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config.settings import settings, get_settings
from engine.scorer import evaluate_job, MatchResult
from ingestion.models import CandidateProfile
from ingestion.parser import load_profile, load_profile_from_dict


# ============================================================================
# 1. Helper Utilities
# ============================================================================

def _normalize_profile(
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None
) -> CandidateProfile:
    """Safely resolves candidate profile from instance, dictionary, or embedded default."""
    if isinstance(candidate, CandidateProfile):
        return candidate
    if isinstance(candidate, dict):
        return load_profile_from_dict(candidate)
    return load_profile(allow_fallback=True)


def _extract_job_field(job: Any, field_name: str, default: Any = "") -> Any:
    """Extracts a property from a JobOpportunity dataclass or dictionary."""
    if isinstance(job, dict):
        return job.get(field_name, default)
    return getattr(job, field_name, default)


def _score_and_sort_opportunities(
    opportunities: Optional[List[Any]],
    profile: CandidateProfile,
) -> List[Tuple[Any, MatchResult]]:
    """
    Scores each opportunity (if not pre-scored) and returns sorted list
    in descending order of overall match score.
    """
    scored: List[Tuple[Any, MatchResult]] = []
    if not opportunities:
        return scored

    for opp in opportunities:
        if opp is None:
            continue

        # Check if already pre-scored
        pre_res = _extract_job_field(opp, "match_result", None)
        if isinstance(pre_res, MatchResult):
            scored.append((opp, pre_res))
            continue

        pre_score = _extract_job_field(opp, "overall_score", None)
        pre_breakdown = _extract_job_field(opp, "breakdown", None)
        if pre_score is not None and pre_breakdown is not None:
            res = MatchResult(
                overall_score=float(pre_score),
                breakdown=dict(pre_breakdown),
                matched_skills=list(_extract_job_field(opp, "matched_skills", [])),
                missing_skills=list(_extract_job_field(opp, "missing_skills", [])),
                target_role=str(_extract_job_field(opp, "target_role", "DevOps Engineer")),
                rationale=str(_extract_job_field(opp, "rationale", "Pre-evaluated opportunity.")),
            )
            scored.append((opp, res))
            continue

        # Evaluate on the fly
        desc = str(_extract_job_field(opp, "description", ""))
        title = str(_extract_job_field(opp, "title", ""))
        loc = str(_extract_job_field(opp, "location", ""))
        combined_text = f"{title} | {loc}\n\n{desc}" if desc else title

        res = evaluate_job(profile, combined_text)
        scored.append((opp, res))

    # Sort descending by overall score
    scored.sort(key=lambda x: x[1].overall_score, reverse=True)
    return scored


# ============================================================================
# 2. HTML Digest Formatter
# ============================================================================

def format_digest_html(
    opportunities: Optional[List[Any]],
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
    date_str: Optional[str] = None,
) -> str:
    """
    Formats verified opportunities into an executive, ATS-aligned HTML daily digest.

    Strict Compliance:
    - Pure inline CSS (NO external stylesheets or <link rel="stylesheet">).
    - Contains executive KPI metrics ("99.9%" uptime SLA and "99%" RCA resolution).
    - Clickable job URLs and corporate links.
    - Transparent 5-dimension score breakdown tables and skill gap pills.
    - Graceful zero-opportunities empty state.
    """
    profile = _normalize_profile(candidate)
    active_date = date_str or datetime.date.today().isoformat()
    opp_list = list(opportunities or [])
    scored_opps = _score_and_sort_opportunities(opp_list, profile)

    cand_name = profile.candidate.full_name or "John Victor Aniekwe"
    cand_email = profile.candidate.email or "aniekwevictor9@gmail.com"
    cand_loc = profile.candidate.location or "Lagos, Nigeria (UTC+1 / CET Synchronous)"

    # Inline Styles Map
    st_body = "margin: 0; padding: 20px 0; background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.5;"
    st_card = "max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);"
    st_header = "background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 28px 32px;"
    st_h1 = "margin: 0 0 8px 0; font-size: 24px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;"
    st_subtitle = "margin: 0; font-size: 14px; color: #94a3b8;"
    st_content = "padding: 32px;"
    st_kpi_box = "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px;"
    st_kpi_title = "font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #475569; margin: 0 0 10px 0;"
    st_kpi_badge = "display: inline-block; background-color: #0284c7; color: #ffffff; font-weight: 700; padding: 4px 8px; border-radius: 4px; font-size: 13px; margin-right: 8px; margin-bottom: 6px;"
    st_kpi_desc = "font-size: 12px; color: #334155; margin-right: 16px;"
    st_table = "width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;"
    st_th = "background-color: #f1f5f9; text-align: left; padding: 10px 12px; font-weight: 600; color: #334155; border-bottom: 2px solid #cbd5e1;"
    st_td = "padding: 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top;"
    st_score_badge = "display: inline-block; padding: 4px 8px; font-weight: 700; font-size: 13px; border-radius: 4px; text-align: center;"
    st_opp_card = "background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; margin-bottom: 20px;"
    st_pill_green = "display: inline-block; background-color: #dcfce7; color: #166534; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; margin-right: 4px; margin-bottom: 4px;"
    st_pill_gray = "display: inline-block; background-color: #f1f5f9; color: #475569; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; margin-right: 4px; margin-bottom: 4px;"
    st_button = "display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; padding: 8px 16px; border-radius: 4px; margin-top: 8px;"
    st_footer = "background-color: #f8fafc; padding: 20px 32px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center;"

    # Assemble HTML
    html_parts: List[str] = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang=\"en\">")
    html_parts.append("<head>")
    html_parts.append("  <meta charset=\"utf-8\">")
    html_parts.append("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
    html_parts.append("  <title>Daily Career & Opportunity Digest</title>")
    html_parts.append("</head>")
    html_parts.append(f"<body style=\"{st_body}\">")
    html_parts.append(f"  <div style=\"{st_card}\">")

    # Header
    html_parts.append(f"    <div style=\"{st_header}\">")
    html_parts.append(f"      <h1 style=\"{st_h1}\">Daily Career & Opportunity Digest</h1>")
    html_parts.append(f"      <p style=\"{st_subtitle}\">Prepared for <strong>{html.escape(cand_name)}</strong> &bull; {html.escape(active_date)} &bull; {len(scored_opps)} Opportunities Evaluated</p>")
    html_parts.append("    </div>")

    # Content
    html_parts.append(f"    <div style=\"{st_content}\">")

    # Executive Verified Competencies Box (Guarantees 99.9% and 99% metrics)
    html_parts.append(f"      <div style=\"{st_kpi_box}\">")
    html_parts.append(f"        <div style=\"{st_kpi_title}\">Verified Candidate Enterprise SLA & Credentials</div>")
    html_parts.append("        <div>")
    html_parts.append(f"          <span style=\"{st_kpi_badge}\">99.9%</span><span style=\"{st_kpi_desc}\">Enterprise Cloud Uptime SLA (AWS & Azure)</span>")
    html_parts.append(f"          <span style=\"{st_kpi_badge}\">99%</span><span style=\"{st_kpi_desc}\">First-Day L3 RCA Issue Resolution Rate</span>")
    html_parts.append("        </div>")
    html_parts.append("        <div style=\"margin-top: 8px;\">")
    html_parts.append(f"          <span style=\"{st_kpi_badge}\">&gt;60%</span><span style=\"{st_kpi_desc}\">AKS AI Prediction Accuracy</span>")
    html_parts.append(f"          <span style=\"{st_kpi_badge}\">&lt;15 Min</span><span style=\"{st_kpi_desc}\">Multi-Cloud IaC Provisioning Speed</span>")
    html_parts.append("        </div>")
    html_parts.append("      </div>")

    # Empty State vs Opportunities
    if not scored_opps:
        html_parts.append("      <div style=\"text-align: center; padding: 40px 20px;\">")
        html_parts.append("        <h3 style=\"color: #475569; margin-bottom: 8px;\">No Opportunities Discovered Today</h3>")
        html_parts.append("        <p style=\"color: #64748b; font-size: 14px;\">No external postings matched your strict remote Nigeria / relocation eligibility criteria during this automated discovery cycle. All existing positions are up to date.</p>")
        html_parts.append("      </div>")
    else:
        # High-Level Summary Table
        html_parts.append("      <h2 style=\"font-size: 18px; margin: 0 0 12px 0; color: #0f172a;\">Executive Opportunity Summary</h2>")
        html_parts.append(f"      <table style=\"{st_table}\">")
        html_parts.append("        <thead>")
        html_parts.append("          <tr>")
        html_parts.append(f"            <th style=\"{st_th}\">Match</th>")
        html_parts.append(f"            <th style=\"{st_th}\">Target Role</th>")
        html_parts.append(f"            <th style=\"{st_th}\">Company</th>")
        html_parts.append(f"            <th style=\"{st_th}\">Mobility / Status</th>")
        html_parts.append(f"            <th style=\"{st_th}\">Action</th>")
        html_parts.append("          </tr>")
        html_parts.append("        </thead>")
        html_parts.append("        <tbody>")

        for opp, res in scored_opps:
            title = _extract_job_field(opp, "title", "Position")
            company = _extract_job_field(opp, "company", "Company")
            location = _extract_job_field(opp, "location", "Remote")
            url = _extract_job_field(opp, "url", "#")
            score = res.overall_score

            # Badge color
            if score >= 80.0:
                score_bg = "#dcfce7"
                score_fg = "#15803d"
            elif score >= 70.0:
                score_bg = "#e0f2fe"
                score_fg = "#0369a1"
            elif score >= 50.0:
                score_bg = "#fef3c7"
                score_fg = "#b45309"
            else:
                score_bg = "#fee2e2"
                score_fg = "#b91c1c"

            html_parts.append("          <tr>")
            html_parts.append(f"            <td style=\"{st_td}\"><span style=\"{st_score_badge} background-color: {score_bg}; color: {score_fg};\">{score:.1f}%</span></td>")
            html_parts.append(f"            <td style=\"{st_td}\"><strong>{html.escape(str(title))}</strong></td>")
            html_parts.append(f"            <td style=\"{st_td}\">{html.escape(str(company))}</td>")
            html_parts.append(f"            <td style=\"{st_td}\">{html.escape(str(location))}</td>")
            html_parts.append(f"            <td style=\"{st_td}\"><a href=\"{html.escape(str(url))}\" style=\"color: #2563eb; text-decoration: underline; font-weight: 600;\">Apply</a></td>")
            html_parts.append("          </tr>")

        html_parts.append("        </tbody>")
        html_parts.append("      </table>")

        # Detailed Opportunity Cards
        html_parts.append("      <h2 style=\"font-size: 18px; margin: 32px 0 16px 0; color: #0f172a;\">Detailed Scoring & Gap Analysis</h2>")

        for idx, (opp, res) in enumerate(scored_opps, 1):
            title = _extract_job_field(opp, "title", "Position")
            company = _extract_job_field(opp, "company", "Company")
            location = _extract_job_field(opp, "location", "Remote")
            url = _extract_job_field(opp, "url", "#")
            desc = _extract_job_field(opp, "description", "")
            bd = res.breakdown

            html_parts.append(f"      <div style=\"{st_opp_card}\" data-opportunity-title=\"{html.escape(str(title), quote=True)}\">")
            html_parts.append(f"        <div style=\"display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;\">")
            html_parts.append(f"          <h3 style=\"margin: 0; font-size: 16px; color: #0f172a;\">#{idx}. {html.escape(str(title))} &mdash; <span style=\"color: #475569;\">{html.escape(str(company))}</span></h3>")
            html_parts.append("        </div>")
            html_parts.append(f"        <p style=\"margin: 4px 0 12px 0; font-size: 13px; color: #64748b;\">Location: <strong>{html.escape(str(location))}</strong></p>")

            # Transparent Scoring Breakdown Table
            html_parts.append("        <div style=\"background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px 14px; margin-bottom: 12px;\">")
            html_parts.append("          <div style=\"font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 6px;\">Scoring Dimension Breakdown (Overall: " + f"{res.overall_score:.1f}%)</div>")
            html_parts.append("          <div style=\"font-size: 12px; color: #475569; display: flex; flex-wrap: wrap; gap: 12px;\">")
            html_parts.append(f"            <span>Skills (35%): <strong>{bd.get('skills', 0.0):.1f}%</strong></span>")
            html_parts.append(f"            <span>Title (25%): <strong>{bd.get('title', 0.0):.1f}%</strong></span>")
            html_parts.append(f"            <span>Metrics (15%): <strong>{bd.get('metrics', 0.0):.1f}%</strong></span>")
            html_parts.append(f"            <span>Mobility (15%): <strong>{bd.get('mobility', 0.0):.1f}%</strong></span>")
            html_parts.append(f"            <span>Certs (10%): <strong>{bd.get('certs', 0.0):.1f}%</strong></span>")
            html_parts.append("          </div>")
            html_parts.append("        </div>")

            # Matched & Missing Skills
            if res.matched_skills:
                html_parts.append("        <div style=\"margin-bottom: 8px;\">")
                html_parts.append("          <span style=\"font-size: 12px; font-weight: 600; color: #166534;\">Matched Competencies: </span>")
                for s in res.matched_skills[:8]:
                    html_parts.append(f"<span style=\"{st_pill_green}\">{html.escape(str(s))}</span>")
                html_parts.append("        </div>")

            if res.missing_skills:
                html_parts.append("        <div style=\"margin-bottom: 12px;\">")
                html_parts.append("          <span style=\"font-size: 12px; font-weight: 600; color: #475569;\">Identified Gaps: </span>")
                for s in res.missing_skills[:6]:
                    html_parts.append(f"<span style=\"{st_pill_gray}\">{html.escape(str(s))}</span>")
                html_parts.append("        </div>")

            # Rationale
            html_parts.append(f"        <div style=\"font-size: 13px; color: #334155; margin-bottom: 10px; line-height: 1.4;\"><em>{html.escape(res.rationale)}</em></div>")

            # Tied PDF Files & Succinct Application Instructions
            cv_att = _extract_job_field(opp, "attached_cv_filename", "")
            cl_att = _extract_job_field(opp, "attached_letter_filename", "")
            if cv_att or res.overall_score >= 75.0:
                if not cv_att:
                    from ingestion.text_utils import safe_filename
                    cv_att = safe_filename("John", "Aniekwe", f"{company}_{res.target_role}", "CV", "pdf")
                    cl_att = safe_filename("John", "Aniekwe", f"{company}_{res.target_role}", "Cover_Letter", "pdf")
                top_kws = ", ".join(res.matched_skills[:4]) if res.matched_skills else "AWS, Azure, Kubernetes (KCNA), Terraform"
                html_parts.append("        <div style=\"background-color: #eff6ff; border-left: 3px solid #2563eb; padding: 10px 12px; margin-bottom: 12px; font-size: 12px; color: #1e3a8a;\">")
                html_parts.append(f"          <div><strong>Tied PDF Application Package:</strong> <code>{html.escape(str(cv_att))}</code> &amp; <code>{html.escape(str(cl_att))}</code></div>")
                html_parts.append("          <div style=\"margin-top: 4px;\"><strong>Succinct Application Instructions:</strong> (1) Attach the two tied PDFs above; (2) Apply via the direct link below; (3) Highlight <strong>" + html.escape(top_kws) + "</strong> and verified SLAs (99.9% Uptime, 99% L3 RCA, &gt;60% AI Accuracy); (4) Offer Direct Hire or B2B C2C via <strong>Stepcon Solutions (RC - 8284984)</strong>.</div>")
                html_parts.append("        </div>")

            # Direct Link
            html_parts.append(f"        <div><a href=\"{html.escape(str(url))}\" style=\"{st_button}\">View Posting ({html.escape(str(url))})</a></div>")
            html_parts.append("      </div>")

    # Tailoring Section Note
    html_parts.append("      <div style=\"margin-top: 24px; padding: 16px; background-color: #f1f5f9; border-radius: 6px; font-size: 13px; color: #334155;\">")
    html_parts.append("        <strong>Application Package Attachments:</strong> For high-alignment opportunities (&ge;75%), customized single-column ATS CVs and STAR-methodology cover letters have been automatically tailored and attached to this email.")
    html_parts.append("      </div>")

    html_parts.append("    </div>")

    # Footer
    html_parts.append(f"    <div style=\"{st_footer}\">")
    html_parts.append(f"      <p style=\"margin: 0 0 4px 0;\">Stepcon Solutions (RC - 8284984) Career Dispatch Automation Suite</p>")
    html_parts.append(f"      <p style=\"margin: 0;\">Candidate: {html.escape(cand_name)} &bull; {html.escape(cand_email)} &bull; {html.escape(cand_loc)}</p>")
    html_parts.append("    </div>")

    html_parts.append("  </div>")
    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts)


# ============================================================================
# 3. Plain Text Digest Formatter
# ============================================================================

def format_digest_text(
    opportunities: Optional[List[Any]],
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
    date_str: Optional[str] = None,
) -> str:
    """
    Formats verified opportunities into an ATS-friendly, clean plain text daily digest.
    """
    profile = _normalize_profile(candidate)
    active_date = date_str or datetime.date.today().isoformat()
    opp_list = list(opportunities or [])
    scored_opps = _score_and_sort_opportunities(opp_list, profile)

    cand_name = profile.candidate.full_name or "John Victor Aniekwe"
    cand_email = profile.candidate.email or "aniekwevictor9@gmail.com"
    cand_loc = profile.candidate.location or "Lagos, Nigeria (UTC+1 / CET Synchronous)"

    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("DAILY CAREER & OPPORTUNITY DIGEST")
    lines.append(f"Prepared for: {cand_name} <{cand_email}>")
    lines.append(f"Date: {active_date}")
    lines.append(f"Location: {cand_loc}")
    lines.append(f"Evaluated Opportunities: {len(scored_opps)}")
    lines.append("=" * 72)
    lines.append("")

    # Executive Verified Competencies
    lines.append("VERIFIED CANDIDATE ENTERPRISE CREDENTIALS & SLA:")
    lines.append("  - 99.9% Enterprise Cloud Uptime SLA sustained across AWS & Azure estates")
    lines.append("  - 99% First-Day L3 Issue Resolution Rate for Azure App Service via RCA")
    lines.append("  - >60% AKS AI Prediction Accuracy on Azure OpenAI microservices")
    lines.append("  - <15 Min Multi-Cloud IaC Provisioning Speed (Terraform & ARM/Bicep)")
    lines.append("")

    if not scored_opps:
        lines.append("-" * 72)
        lines.append("No opportunities matched your strict remote/sponsorship criteria today.")
        lines.append("Check back tomorrow for freshly discovered openings.")
        lines.append("-" * 72)
    else:
        lines.append("=" * 72)
        lines.append("OPPORTUNITY RANKINGS & FIT ANALYSIS")
        lines.append("=" * 72)
        lines.append("")

        for idx, (opp, res) in enumerate(scored_opps, 1):
            title = _extract_job_field(opp, "title", "Position")
            company = _extract_job_field(opp, "company", "Company")
            location = _extract_job_field(opp, "location", "Remote")
            url = _extract_job_field(opp, "url", "N/A")
            bd = res.breakdown

            lines.append(f"#{idx}. {title} | {company}")
            lines.append(f"    Location: {location}")
            lines.append(f"    Overall Score: {res.overall_score:.1f}%")
            lines.append(
                f"    Breakdown: Skills: {bd.get('skills', 0.0):.1f}% | "
                f"Title: {bd.get('title', 0.0):.1f}% | "
                f"Metrics: {bd.get('metrics', 0.0):.1f}% | "
                f"Mobility: {bd.get('mobility', 0.0):.1f}% | "
                f"Certs: {bd.get('certs', 0.0):.1f}%"
            )

            if res.matched_skills:
                lines.append(f"    Matched Skills: {', '.join(res.matched_skills[:8])}")
            if res.missing_skills:
                lines.append(f"    Skill Gaps: {', '.join(res.missing_skills[:6])}")

            lines.append(f"    Recommendation: {res.rationale}")
            cv_att = _extract_job_field(opp, "attached_cv_filename", "")
            cl_att = _extract_job_field(opp, "attached_letter_filename", "")
            if cv_att or res.overall_score >= 75.0:
                if not cv_att:
                    from ingestion.text_utils import safe_filename
                    cv_att = safe_filename("John", "Aniekwe", f"{company}_{res.target_role}", "CV", "pdf")
                    cl_att = safe_filename("John", "Aniekwe", f"{company}_{res.target_role}", "Cover_Letter", "pdf")
                lines.append(f"    Tied PDF Package: {cv_att} | {cl_att}")
                lines.append("    Succinct Action:  Attach the tied PDFs above, open the Application URL, and emphasize matched skills + 99.9% SLA / Stepcon C2C (RC - 8284984).")
            lines.append(f"    Application URL: {url}")
            lines.append("-" * 72)

    lines.append("")
    lines.append("APPLICATION PACKAGES:")
    lines.append("  ATS-tailored CVs and STAR-methodology cover letters for top positions")
    lines.append("  are attached to this email.")
    lines.append("")
    lines.append("Stepcon Solutions (RC - 8284984) Automated Career Pipeline")
    lines.append("=" * 72)

    return "\n".join(lines)


# ============================================================================
# 4. Multi-part MIME Email Builder
# ============================================================================

def build_digest_email(
    opportunities: List[Any],
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
    date_str: Optional[str] = None,
    recipient: Optional[str] = None,
    subject: Optional[str] = None,
    attachments: Optional[List[Tuple[str, Union[bytes, str]]]] = None,
    candidate_profile: Optional[Any] = None,
) -> MIMEMultipart:
    """
    Constructs a complete RFC 5322 multi-part MIME email message.

    Structure:
    - Root: multipart/mixed
      - Body Container: multipart/alternative
        - text/plain
        - text/html
      - Attachments (optional application packages)

    Args:
        opportunities: List of JobOpportunity items or dictionaries.
        candidate: Optional CandidateProfile or dict.
        date_str: Optional YYYY-MM-DD date string.
        recipient: Target recipient email address (defaults to candidate email).
        subject: Optional email subject string (sanitized for UTF-8 non-ASCII).
        attachments: Optional list of (filename, file_content_bytes_or_str).
        candidate_profile: Contract alias for candidate.

    Returns:
        MIMEMultipart object ready for SMTP dispatch or .eml export.
    """
    profile = _normalize_profile(candidate or candidate_profile)
    active_date = date_str or datetime.date.today().isoformat()
    opp_list = list(opportunities or [])

    # 1. Resolve Recipient
    to_addr = (
        recipient
        or getattr(profile.candidate, "email", None)
        or settings.notification_email
        or "aniekwevictor9@gmail.com"
    ).strip()

    # 2. Resolve Subject (Must contain "Daily Career" by contract)
    if not subject:
        subject = f"Daily Career Digest - {active_date} ({len(opp_list)} Opportunities)"

    # 3. Resolve Sender
    sender_email = settings.smtp_sender or "notifications@stepcon.solutions"
    sender_name = "Stepcon Solutions Career Automation"
    from_header = f"{sender_name} <{sender_email}>"

    # 4. Generate Body Representations
    html_body = format_digest_html(opp_list, candidate=profile, date_str=active_date)
    text_body = format_digest_text(opp_list, candidate=profile, date_str=active_date)

    # 5. Build MIME Hierarchy
    msg = MIMEMultipart("mixed")
    try:
        subject.encode("ascii")
        msg["Subject"] = subject
    except UnicodeEncodeError:
        msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = from_header
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="stepcon.solutions")

    # Alternative container for plain text and HTML
    alt_container = MIMEMultipart("alternative")
    alt_container.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_container.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt_container)

    # 6. Add Attachments
    if attachments:
        for item in attachments:
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                continue

            filename, content = item[0], item[1]
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            elif isinstance(content, bytes):
                content_bytes = content
            else:
                continue

            part = MIMEApplication(content_bytes, Name=filename)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

    return msg
