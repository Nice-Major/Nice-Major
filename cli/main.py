"""
Interactive On-Demand Evaluation, Tailoring, Apply & Audit Command-Line Interface.
Module: cli.main
Feature: F13 (Interactive On-Demand Evaluation CLI & Multi-Channel Ingestion)
Milestone: M5 (Interactive CLI & Stepcon Solutions Pipeline)

Subcommands:
- eval: On-demand job evaluation from text, file, URL, clipboard, or stdin against candidate profile.
- tailor: On-demand CV and cover letter tailoring (PDF, Markdown, HTML, TXT) for a specific job description.
- apply: End-to-end 1-step workflow (ingest from URL/paste/dropzone -> evaluate -> generate PDF CV & Cover Letter -> succinct instructions & optional email).
- digest: Generate or dispatch on-demand daily career opportunity digest (consolidated or per-opportunity email mode).
- audit: Run the Daily Workflow Self-Review & Optimization Engine audit.
- stepcon: Stepcon Solutions (RC - 8284984) B2B tender discovery, evaluation, and proposals.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings, settings
from engine.scorer import evaluate_job, MatchResult
from ingestion.job_fetcher import (
    FetchedJobInput,
    fetch_job_from_url,
    read_clipboard_text,
    resolve_job_input,
)
from ingestion.models import CandidateProfile, StepconProfile
from ingestion.parser import load_profile, load_profile_from_dict
from ingestion.text_utils import safe_filename
from tailoring.cv_tailor import generate_cv, generate_cv_pdf, get_cv_filename
from tailoring.letter_tailor import (
    generate_cover_letter,
    generate_cover_letter_pdf,
    get_letter_filename,
)

logger = logging.getLogger("cli.main")


# ============================================================================
# 1. Argument Parser Definition
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """
    Constructs and returns the master ArgumentParser with subparsers:
    eval, tailor, apply, digest, audit, stepcon.
    """
    parser = argparse.ArgumentParser(
        prog="career-automation",
        description="Career Automation & Stepcon Solutions (RC - 8284984) Interactive CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # ------------------------------------------------------------------------
    # Subcommand: eval
    # ------------------------------------------------------------------------
    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate candidate suitability against a target job description.",
        description="Evaluate job posting from text, file, URL, clipboard, or stdin; returns numerical fit score and gap analysis.",
    )
    eval_parser.add_argument("--text", type=str, default=None, help="Raw job description text string or URL")
    eval_parser.add_argument("--file", type=str, default=None, help="Path to job description text file")
    eval_parser.add_argument("--url", type=str, default=None, help="Direct job posting URL (Workday, Greenhouse, Lever, etc.)")
    eval_parser.add_argument("--paste", action="store_true", help="Read job description or URL directly from system clipboard")
    eval_parser.add_argument("--role", type=str, default=None, help="Target role lens override (e.g. devops, architect)")
    eval_parser.add_argument("--profile", type=str, default=None, help="Path to custom candidate profile JSON file")
    eval_parser.add_argument("--json", action="store_true", help="Output match results as machine-readable JSON")

    # ------------------------------------------------------------------------
    # Subcommand: tailor
    # ------------------------------------------------------------------------
    tailor_parser = subparsers.add_parser(
        "tailor",
        help="Generate ATS-compliant CV and STAR cover letter (PDF, MD, HTML, TXT) for a job description.",
        description="Tailor resume and cover letter matching role requirements; auto-creates output directories and PDFs.",
    )
    tailor_parser.add_argument("--jd", type=str, default=None, help="Path to job description file, URL, or raw text")
    tailor_parser.add_argument("--file", type=str, default=None, help="Alternative alias for JD text file path")
    tailor_parser.add_argument("--text", type=str, default=None, help="Alternative alias for JD raw text string")
    tailor_parser.add_argument("--url", type=str, default=None, help="Direct job posting URL to fetch and tailor")
    tailor_parser.add_argument("--paste", action="store_true", help="Read job description or URL from system clipboard")
    tailor_parser.add_argument("--role", type=str, default="DevOps Engineer", help="Target role lens for tailoring")
    tailor_parser.add_argument("--output-dir", type=str, default=None, help="Destination directory for generated files")
    tailor_parser.add_argument(
        "--format",
        type=str,
        default="md",
        choices=["pdf", "md", "html", "txt"],
        help="Primary output document format (PDF companion files are always generated)",
    )
    tailor_parser.add_argument("--company", type=str, default="", help="Hiring company name for cover letter & filename personalization")
    tailor_parser.add_argument("--profile", type=str, default=None, help="Path to custom candidate profile JSON file")

    # ------------------------------------------------------------------------
    # Subcommand: apply
    # ------------------------------------------------------------------------
    apply_parser = subparsers.add_parser(
        "apply",
        help="One-step job ingestion (URL, clipboard, dropzone file, or text) -> evaluation -> PDF CV & Cover Letter generation.",
        description=(
            "Ingest a job description from --url, --paste, --file, --text, or data/paste_job_here.txt, "
            "evaluate fit against the Single Source of Truth, and output opportunity-specific PDF CV and Cover Letter "
            "with succinct application instructions."
        ),
    )
    apply_parser.add_argument("--url", type=str, default=None, help="Job posting URL (e.g., Workday, Greenhouse, Lever, LinkedIn)")
    apply_parser.add_argument("--paste", action="store_true", help="Read job description or URL from system clipboard")
    apply_parser.add_argument("--file", type=str, default=None, help="Path to job description file")
    apply_parser.add_argument("--text", type=str, default=None, help="Raw job description text")
    apply_parser.add_argument("--jd", type=str, default=None, help="Fallback JD file, URL, or raw text")
    apply_parser.add_argument("--role", type=str, default=None, help="Optional role lens override (auto-detected if omitted)")
    apply_parser.add_argument("--company", type=str, default=None, help="Optional company name override (auto-detected if omitted)")
    apply_parser.add_argument("--output-dir", type=str, default=None, help="Destination directory for generated PDF package")
    apply_parser.add_argument("--email", action="store_true", help="Dispatch the generated PDF package to candidate email")
    apply_parser.add_argument("--live", action="store_true", help="Execute live SMTP transmission when --email is enabled")
    apply_parser.add_argument("--profile", type=str, default=None, help="Path to custom candidate profile JSON file")
    apply_parser.add_argument("--json", action="store_true", help="Output result summary as JSON")

    # ------------------------------------------------------------------------
    # Subcommand: digest
    # ------------------------------------------------------------------------
    digest_parser = subparsers.add_parser(
        "digest",
        help="Generate or dispatch the daily opportunity digest with PDF attachments.",
        description="Execute discovery, filtering, match ranking, PDF generation, workflow audit, and email dispatch.",
    )
    digest_parser.add_argument("--dry-run", action="store_true", default=None, help="Execute in offline dry-run mode (default)")
    digest_parser.add_argument("--live", action="store_true", help="Execute live SMTP transmission")
    digest_parser.add_argument("--date", type=str, default=None, help="Target execution date (YYYY-MM-DD)")
    digest_parser.add_argument("--output-dir", type=str, default=None, help="Output directory for generated digest artifacts")
    digest_parser.add_argument("--force", action="store_true", help="Bypass daily idempotency check")
    digest_parser.add_argument("--limit", type=int, default=10, help="Maximum number of opportunities to include")
    digest_parser.add_argument(
        "--per-opportunity",
        action="store_true",
        help="Send a dedicated email per opportunity (each with its specific PDF CV & Cover Letter) instead of one consolidated email",
    )

    # ------------------------------------------------------------------------
    # Subcommand: audit
    # ------------------------------------------------------------------------
    audit_parser = subparsers.add_parser(
        "audit",
        help="Run the Daily Workflow Self-Review & Optimization Engine audit.",
        description="Inspect Single Source of Truth, historical discovery yield, recurring skill gaps, and PDF telemetry.",
    )
    audit_parser.add_argument("--output-dir", type=str, default=None, help="Directory to save daily workflow audit reports")
    audit_parser.add_argument("--json", action="store_true", help="Output workflow audit report as JSON")

    # ------------------------------------------------------------------------
    # Subcommand: stepcon
    # ------------------------------------------------------------------------
    stepcon_parser = subparsers.add_parser(
        "stepcon",
        help="Stepcon Solutions (RC - 8284984) consultancy tender discovery and proposal pipeline.",
        description="Discover tenders, evaluate commercial RFPs, and generate tailored B2B corporate proposals.",
    )
    stepcon_parser.add_argument("--discover", action="store_true", help="Discover corporate and public tenders")
    stepcon_parser.add_argument("--eval", type=str, default=None, help="Tender description text or file path to evaluate")
    stepcon_parser.add_argument("--text", type=str, default=None, help="Raw tender description text")
    stepcon_parser.add_argument("--file", type=str, default=None, help="Path to tender description file")
    stepcon_parser.add_argument("--proposal", type=str, default=None, help="Generate proposal for tender (accepts file or text)")
    stepcon_parser.add_argument("--client", type=str, default="", help="Client organization name for proposal")
    stepcon_parser.add_argument("--output-dir", type=str, default=None, help="Output directory to save generated proposal")
    stepcon_parser.add_argument("--dry-run", action="store_true", default=True, help="Operate in offline synthetic mode")
    stepcon_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    # ------------------------------------------------------------------------
    # Subcommand: rebuild (alias: render)
    # ------------------------------------------------------------------------
    rebuild_parser = subparsers.add_parser(
        "rebuild",
        aliases=["render"],
        help="Rebuild opportunity PDFs directly from edited Markdown (.md) or HTML (.html) files.",
        description="Recompiles edited application documents into verified ATS-compliant PDFs with page-budget enforcement.",
    )
    rebuild_parser.add_argument("--opportunity", "-o", type=str, default="Gates_Foundation", help="Opportunity directory name or keyword (e.g. Gates_Foundation)")
    rebuild_parser.add_argument("--file", "-f", type=str, default=None, help="Direct path to an edited .md or .html file")
    rebuild_parser.add_argument("--from", dest="from_format", choices=["md", "html", "all"], default="md", help="Source format to compile from (default: md)")
    rebuild_parser.add_argument("--json", action="store_true", help="Output result summary in JSON format")

    # ------------------------------------------------------------------------
    # Subcommand: correct (alias: patch)
    # ------------------------------------------------------------------------
    correct_parser = subparsers.add_parser(
        "correct",
        aliases=["patch"],
        help="Find and replace text across an opportunity package and immediately recompile PDFs.",
        description="Fix typos or update phrases in .md, .html, and .txt files, and instantly regenerate verified PDFs.",
    )
    correct_parser.add_argument("--find", required=True, type=str, help="Target string or typo to search for")
    correct_parser.add_argument("--replace", required=True, type=str, help="Replacement string")
    correct_parser.add_argument("--opportunity", "-o", type=str, default="Gates_Foundation", help="Target opportunity directory name or pattern (default: Gates_Foundation)")
    correct_parser.add_argument("--profile", action="store_true", help="Also apply correction to the Single Source of Truth profile-data.json")
    correct_parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    return parser


# ============================================================================
# 2. Subcommand Handlers
# ============================================================================

def _resolve_input_text(
    direct_text: Optional[str],
    file_path: Optional[str],
    fallback_arg: Optional[str] = None,
    url: Optional[str] = None,
    from_clipboard: bool = False,
    check_dropzone: bool = False,
) -> Optional[str]:
    """
    Resolves input text from URL, clipboard, direct string, file path, fallback argument, or dropzone.
    Returns None if an explicitly specified file path does not exist.
    """
    fetched, err = _resolve_fetched_job(
        direct_text=direct_text,
        file_path=file_path,
        fallback_arg=fallback_arg,
        url=url,
        from_clipboard=from_clipboard,
        check_dropzone=check_dropzone,
    )
    if err == "FILE_NOT_FOUND":
        return None
    if fetched and fetched.text.strip():
        return fetched.text.strip()
    return ""


def _resolve_fetched_job(
    direct_text: Optional[str] = None,
    file_path: Optional[str] = None,
    fallback_arg: Optional[str] = None,
    url: Optional[str] = None,
    from_clipboard: bool = False,
    check_dropzone: bool = False,
) -> Tuple[Optional[FetchedJobInput], Optional[str]]:
    """
    Resolves a FetchedJobInput (preserving extracted title, company, url, and text)
    across all supported ingestion channels.
    """
    # 1. Explicit file check for strict error reporting
    if file_path:
        p = Path(file_path)
        if not p.is_file():
            logger.error(f"Input file not found: {file_path}")
            return None, "FILE_NOT_FOUND"

    # 2. If fallback_arg looks like an existing file or URL or raw text
    effective_text = direct_text
    effective_file = file_path
    effective_url = url

    if not effective_text and not effective_file and not effective_url and fallback_arg:
        cand_str = fallback_arg.strip()
        cand_path = Path(cand_str)
        if cand_path.is_file():
            effective_file = cand_str
        elif cand_str.startswith(("http://", "https://")):
            effective_url = cand_str
        else:
            effective_text = cand_str

    active_settings = get_settings()
    dropzone = (active_settings.data_dir / "paste_job_here.txt") if check_dropzone else Path("non_existent_dropzone_xyz")

    fetched = resolve_job_input(
        text=effective_text,
        file_path=effective_file,
        url=effective_url,
        from_clipboard=from_clipboard,
        dropzone_path=dropzone if check_dropzone else None,
    )
    if fetched and fetched.text.strip():
        return fetched, None
    return None, "EMPTY"


def handle_eval(args: argparse.Namespace) -> int:
    """Executes the 'eval' subcommand."""
    if args.file and not Path(args.file).is_file():
        sys.stderr.write(f"Error: Job description file does not exist: {args.file}\n")
        return 1

    fetched, err = _resolve_fetched_job(
        direct_text=args.text,
        file_path=args.file,
        url=getattr(args, "url", None),
        from_clipboard=getattr(args, "paste", False),
    )
    if err == "FILE_NOT_FOUND":
        sys.stderr.write("Error: Specified job description file could not be read.\n")
        return 1

    if not fetched or not fetched.text.strip():
        sys.stderr.write("Error: No job description provided. Specify --text, --file, --url, or --paste.\n")
        return 1

    jd_text = fetched.text

    # Load profile
    try:
        profile = load_profile(args.profile, allow_fallback=True)
    except Exception as e:
        sys.stderr.write(f"Error loading candidate profile: {e}\n")
        return 1

    # Evaluate match
    result = evaluate_job(profile, jd_text)

    # Optional role override handling
    if args.role and args.role.strip():
        logger.debug(f"Role override requested: {args.role}")

    if args.json:
        out_dict = result.to_dict()
        if fetched.title:
            out_dict["extracted_title"] = fetched.title
        if fetched.company:
            out_dict["extracted_company"] = fetched.company
        if fetched.url:
            out_dict["source_url"] = fetched.url
        print(json.dumps(out_dict, indent=2))
        return 0

    # Human-readable formatted output
    bd = result.breakdown
    print("\n" + "=" * 72)
    print("CAREER AUTOMATION: JOB SUITABILITY EVALUATION")
    print("=" * 72)
    if fetched.title:
        print(f"Posting Title:     {fetched.title}")
    if fetched.company:
        print(f"Organization:      {fetched.company}")
    if fetched.url:
        print(f"Source URL:        {fetched.url}")
    print(f"Target Role Lens:  {result.target_role}")
    print(f"Overall Fit Score: {result.overall_score:.1f}%")
    print(f"Recommendation:    {result.rationale}")
    print("-" * 72)
    print("Dimension Breakdown:")
    print(f"  - Skills Match (35%):     {bd.get('skills', 0.0):.1f}%")
    print(f"  - Title Alignment (25%):  {bd.get('title', 0.0):.1f}%")
    print(f"  - KPI Metrics (15%):      {bd.get('metrics', 0.0):.1f}%")
    print(f"  - Mobility Match (15%):   {bd.get('mobility', 0.0):.1f}%")
    print(f"  - Certifications (10%):   {bd.get('certs', 0.0):.1f}%")
    print("-" * 72)
    if result.matched_skills:
        print(f"Matched Skills ({len(result.matched_skills)}): {', '.join(result.matched_skills[:12])}")
    if result.missing_skills:
        print(f"Skill Gaps ({len(result.missing_skills)}):     {', '.join(result.missing_skills[:8])}")
    print("=" * 72 + "\n")
    return 0


def handle_tailor(args: argparse.Namespace) -> int:
    """Executes the 'tailor' subcommand."""
    if args.file and not Path(args.file).is_file():
        sys.stderr.write(f"Error: Job description file does not exist: {args.file}\n")
        return 1

    fetched, err = _resolve_fetched_job(
        direct_text=args.text,
        file_path=args.file,
        fallback_arg=args.jd,
        url=getattr(args, "url", None),
        from_clipboard=getattr(args, "paste", False),
    )
    if err == "FILE_NOT_FOUND":
        sys.stderr.write("Error: Could not read specified job description file.\n")
        return 1

    if not fetched or not fetched.text.strip():
        sys.stderr.write("Error: No job description provided. Specify --jd, --file, --text, --url, or --paste.\n")
        return 1

    jd_text = fetched.text

    # Load candidate profile
    try:
        profile = load_profile(args.profile, allow_fallback=True)
    except Exception as e:
        sys.stderr.write(f"Error loading candidate profile: {e}\n")
        return 1

    # Resolve output directory with automatic recursive creation
    active_settings = get_settings()
    out_dir_path = Path(args.output_dir) if args.output_dir else (active_settings.output_dir / "tailored")
    out_dir_path.mkdir(parents=True, exist_ok=True)

    role_lens = args.role or fetched.title or "DevOps Engineer"
    company_name = args.company or fetched.company or ""
    fmt = (args.format or "md").lower().lstrip(".")

    try:
        if fmt == "pdf":
            cv_pdf_bytes = generate_cv_pdf(profile, job_text=jd_text, target_role=role_lens)
            letter_pdf_bytes = generate_cover_letter_pdf(
                profile,
                job_text=jd_text,
                target_role=role_lens,
                company_name=company_name,
            )
            cv_filename = get_cv_filename(profile, target_role=role_lens, output_format="pdf", company_name=company_name)
            letter_filename = get_letter_filename(profile, target_role=role_lens, output_format="pdf", company_name=company_name)
            cv_path = out_dir_path / cv_filename
            letter_path = out_dir_path / letter_filename
            cv_path.write_bytes(cv_pdf_bytes)
            letter_path.write_bytes(letter_pdf_bytes)
            cv_pdf_path = cv_path
            letter_pdf_path = letter_path
        else:
            cv_content = generate_cv(profile, job_text=jd_text, target_role=role_lens, output_format=fmt)
            letter_content = generate_cover_letter(
                profile,
                job_text=jd_text,
                target_role=role_lens,
                company_name=company_name,
                output_format=fmt,
            )
            cv_filename = get_cv_filename(profile, target_role=role_lens, output_format=fmt)
            letter_filename = safe_filename(
                profile.candidate.first_name,
                profile.candidate.last_name,
                role_lens,
                "Cover_Letter",
                fmt,
            )
            cv_path = out_dir_path / cv_filename
            letter_path = out_dir_path / letter_filename
            cv_path.write_text(cv_content, encoding="utf-8")
            letter_path.write_text(letter_content, encoding="utf-8")

            # Always generate companion PDF files so every tailored job has ready-to-send PDFs
            cv_pdf_bytes = generate_cv_pdf(profile, job_text=jd_text, target_role=role_lens)
            letter_pdf_bytes = generate_cover_letter_pdf(
                profile,
                job_text=jd_text,
                target_role=role_lens,
                company_name=company_name,
            )
            cv_pdf_path = out_dir_path / get_cv_filename(profile, target_role=role_lens, output_format="pdf", company_name=company_name)
            letter_pdf_path = out_dir_path / get_letter_filename(profile, target_role=role_lens, output_format="pdf", company_name=company_name)
            cv_pdf_path.write_bytes(cv_pdf_bytes)
            letter_pdf_path.write_bytes(letter_pdf_bytes)
    except Exception as e:
        sys.stderr.write(f"Error generating tailored materials: {e}\n")
        return 1

    print("\n" + "=" * 72)
    print("CAREER AUTOMATION: TAILORED APPLICATION PACKAGE GENERATED")
    print("=" * 72)
    print(f"Target Role:        {role_lens}")
    print(f"Target Company:     {company_name or 'General Application'}")
    print(f"Primary Format:     {fmt.upper()}")
    print(f"Tailored CV:        {cv_path.resolve()}")
    print(f"Tailored Letter:    {letter_path.resolve()}")
    print(f"PDF CV:             {cv_pdf_path.resolve()}")
    print(f"PDF Cover Letter:   {letter_pdf_path.resolve()}")
    print("=" * 72 + "\n")
    return 0


def handle_apply(args: argparse.Namespace) -> int:
    """
    Executes the 'apply' subcommand:
    1. Ingests job from --url, --paste, --file, --text, --jd, or data/paste_job_here.txt.
    2. Evaluates fit against Single Source of Truth.
    3. Generates opportunity-specific PDF CV and PDF Cover Letter (plus MD/HTML).
    4. Outputs succinct application instructions and optionally emails the PDF package.
    """
    if args.file and not Path(args.file).is_file():
        sys.stderr.write(f"Error: Job description file does not exist: {args.file}\n")
        return 1

    fetched, err = _resolve_fetched_job(
        direct_text=args.text,
        file_path=args.file,
        fallback_arg=args.jd,
        url=args.url,
        from_clipboard=args.paste,
        check_dropzone=True,
    )
    if err == "FILE_NOT_FOUND":
        sys.stderr.write("Error: Specified job description file could not be read.\n")
        return 1

    if not fetched or not fetched.text.strip():
        sys.stderr.write(
            "Error: No job description found. Pass --url, --paste, --file, --text, "
            "or paste the job description into data/paste_job_here.txt.\n"
        )
        return 1

    try:
        profile = load_profile(args.profile, allow_fallback=True)
    except Exception as e:
        sys.stderr.write(f"Error loading candidate profile: {e}\n")
        return 1

    jd_text = fetched.text
    eval_res = evaluate_job(profile, jd_text)

    role_title = args.role or fetched.title or eval_res.target_role or "Cloud & DevOps Engineer"
    company_name = args.company or fetched.company or "Hiring Organization"

    active_settings = get_settings()
    out_dir_path = Path(args.output_dir) if args.output_dir else (active_settings.output_dir / "applications")
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # Generate PDF CV & PDF Cover Letter (and companion MD/HTML)
    try:
        from tailoring.opportunity_storage import store_opportunity_package

        cv_pdf_bytes = generate_cv_pdf(profile, job_text=jd_text, target_role=role_title)
        letter_pdf_bytes = generate_cover_letter_pdf(
            profile,
            job_text=jd_text,
            target_role=role_title,
            company_name=company_name,
        )
        cv_md = generate_cv(profile, job_text=jd_text, target_role=role_title, output_format="md")
        letter_md = generate_cover_letter(
            profile,
            job_text=jd_text,
            target_role=role_title,
            company_name=company_name,
            output_format="md",
        )
        try:
            cv_html = generate_cv(profile, job_text=jd_text, target_role=role_title, output_format="html")
            letter_html = generate_cover_letter(
                profile,
                job_text=jd_text,
                target_role=role_title,
                company_name=company_name,
                output_format="html",
            )
        except Exception:
            cv_html = ""
            letter_html = ""

        cv_pdf_name = get_cv_filename(profile, target_role=role_title, output_format="pdf", company_name=company_name)
        letter_pdf_name = get_letter_filename(profile, target_role=role_title, output_format="pdf", company_name=company_name)
        cv_md_name = get_cv_filename(profile, target_role=role_title, output_format="md", company_name=company_name)
        letter_md_name = get_letter_filename(profile, target_role=role_title, output_format="md", company_name=company_name)

        # Store in dedicated opportunity folder with deduplication check
        eval_dict = {
            "overall_score": eval_res.overall_score,
            "rationale": eval_res.rationale,
            "breakdown": eval_res.breakdown,
            "matched_skills": eval_res.matched_skills,
            "missing_skills": eval_res.missing_skills,
        }
        pkg_res = store_opportunity_package(
            base_dir=out_dir_path,
            company=company_name,
            role_title=role_title,
            jd_text=jd_text,
            cv_pdf_bytes=cv_pdf_bytes,
            letter_pdf_bytes=letter_pdf_bytes,
            cv_md_text=cv_md,
            letter_md_text=letter_md,
            cv_html_text=cv_html,
            letter_html_text=letter_html,
            cv_pdf_filename=cv_pdf_name,
            letter_pdf_filename=letter_pdf_name,
            eval_summary=eval_dict,
            source_url=fetched.url or "",
            location=fetched.location or "",
            check_deduplication=True,
        )

        is_reused = bool(pkg_res.get("reused"))
        reused_reason = pkg_res.get("match_reason", "")
        opp_folder = pkg_res["folder_path"]
        cv_pdf_path = pkg_res.get("cv_pdf_path") or (opp_folder / cv_pdf_name)
        letter_pdf_path = pkg_res.get("letter_pdf_path") or (opp_folder / letter_pdf_name)
        cv_md_path = opp_folder / cv_md_name
        letter_md_path = opp_folder / letter_md_name

        # If caller specified a custom output_dir, ensure root copy also exists for test compatibility
        if args.output_dir:
            direct_cv = Path(args.output_dir) / cv_pdf_name
            direct_letter = Path(args.output_dir) / letter_pdf_name
            if not direct_cv.is_file():
                direct_cv.write_bytes(cv_pdf_bytes)
            if not direct_letter.is_file():
                direct_letter.write_bytes(letter_pdf_bytes)
    except Exception as e:
        sys.stderr.write(f"Error generating PDF application package: {e}\n")
        return 1

    email_dispatched = False
    email_result_path = ""
    if args.email:
        try:
            from dispatch.digest import build_digest_email
            from dispatch.mailer import send_email

            opp_payload = {
                "title": role_title,
                "company": company_name,
                "location": fetched.location or "Remote / Nigeria Eligible",
                "url": fetched.url or "",
                "overall_score": eval_res.overall_score,
                "rationale": eval_res.rationale,
                "matched_skills": eval_res.matched_skills,
                "missing_skills": eval_res.missing_skills,
                "attached_cv_filename": cv_pdf_name,
                "attached_letter_filename": letter_pdf_name,
            }
            subject = f"Daily Career Application Package: {role_title} at {company_name} ({eval_res.overall_score:.1f}% Fit)"
            msg = build_digest_email(
                opportunities=[opp_payload],
                candidate=profile,
                recipient=active_settings.notification_email,
                subject=subject,
                attachments=[
                    (cv_pdf_name, cv_pdf_bytes),
                    (letter_pdf_name, letter_pdf_bytes),
                ],
            )
            email_result_path = send_email(
                msg,
                dry_run=(not args.live),
                output_dir=out_dir_path,
            )
            email_dispatched = bool(email_result_path)
        except Exception as e:
            logger.warning(f"Email dispatch warning: {e}")

    summary = {
        "source_type": fetched.source_type,
        "source_url": fetched.url,
        "role_title": role_title,
        "company_name": company_name,
        "location": fetched.location,
        "overall_score": eval_res.overall_score,
        "rationale": eval_res.rationale,
        "breakdown": eval_res.breakdown,
        "matched_skills": eval_res.matched_skills,
        "missing_skills": eval_res.missing_skills,
        "opportunity_directory": str(opp_folder.resolve()),
        "reused_existing": is_reused,
        "cv_pdf_path": str(cv_pdf_path.resolve()),
        "letter_pdf_path": str(letter_pdf_path.resolve()),
        "cv_md_path": str(cv_md_path.resolve()),
        "letter_md_path": str(letter_md_path.resolve()),
        "email_dispatched": email_dispatched,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("\n" + "=" * 76)
    print("CAREER AUTOMATION: ONE-STEP JOB EVALUATION & PDF APPLICATION PACKAGE")
    print("=" * 76)
    print(f"Ingestion Channel:  {fetched.source_type}")
    if fetched.url:
        print(f"Job Posting URL:    {fetched.url}")
    print(f"Target Role:        {role_title}")
    print(f"Organization:       {company_name}")
    print(f"Overall Fit Score:  {eval_res.overall_score:.1f}% ({eval_res.rationale})")
    if is_reused:
        print("-" * 76)
        print(f"[REUSED EXISTING PACKAGE] Closely matches existing opportunity: {opp_folder.name}")
        print(f"  Similarity Match Reason: {reused_reason}")
        print("  Reusing already tailored, verified documents (preventing duplicate files).")
    else:
        print(f"Dedicated Folder:   {opp_folder.resolve()}")
    print("-" * 76)
    print("Opportunity Application Files:")
    print(f"  [1] Dedicated Dir:    {opp_folder.resolve()}")
    print(f"  [2] PDF CV:           {cv_pdf_path.resolve()}")
    print(f"  [3] PDF Cover Letter: {letter_pdf_path.resolve()}")
    print(f"  [4] Markdown CV:      {cv_md_path.resolve()}")
    print(f"  [5] Markdown Letter:  {letter_md_path.resolve()}")
    print("-" * 76)
    print("Succinct Application Instructions:")
    print(f"  1. Open Portal:  {fetched.url or 'Open the employer application portal'}")
    print(f"  2. Upload CV:    Attach '{cv_pdf_name}'")
    print(f"  3. Upload Letter:Attach '{letter_pdf_name}'")
    print(
        f"  4. Key Pitch:    Emphasize 99.9% uptime SLA, 65% deploy acceleration, "
        f"KCNA + Cisco CyberOps Associate, and {', '.join(eval_res.matched_skills[:5]) or 'AWS/Azure/Kubernetes'}."
    )
    if args.email:
        mode_str = "LIVE SMTP" if args.live else "DRY-RUN"
        print(f"  5. Email Status: Dispatched ({mode_str}) to {active_settings.recipient_email}: {email_dispatched}")
    print("=" * 76 + "\n")
    return 0


def handle_digest(args: argparse.Namespace) -> int:
    """Executes the 'digest' subcommand."""
    try:
        from scheduler.daily_dispatch import run_daily_job
    except ImportError as e:
        sys.stderr.write(f"Error importing scheduler module: {e}\n")
        return 1

    dry_run = False if args.live else True
    try:
        res = run_daily_job(
            dry_run=dry_run,
            date_str=args.date,
            output_dir=args.output_dir,
            force=args.force,
            per_opportunity=getattr(args, "per_opportunity", False),
        )
        print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        sys.stderr.write(f"Digest execution failed: {e}\n")
        return 1


def handle_audit(args: argparse.Namespace) -> int:
    """Executes the 'audit' subcommand for Daily Workflow Self-Review & Optimization."""
    try:
        from scheduler.workflow_optimizer import format_audit_markdown, run_workflow_audit
    except ImportError as e:
        sys.stderr.write(f"Error importing workflow optimizer: {e}\n")
        return 1

    try:
        profile = load_profile(allow_fallback=True)
        out_dir = Path(args.output_dir) if args.output_dir else None
        report = run_workflow_audit(profile=profile, output_dir=out_dir)
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(format_audit_markdown(report))
        return 0
    except Exception as e:
        sys.stderr.write(f"Workflow audit failed: {e}\n")
        return 1


def handle_stepcon(args: argparse.Namespace) -> int:
    """Executes the 'stepcon' subcommand."""
    if args.file and not Path(args.file).is_file():
        sys.stderr.write(f"Error: Tender description file does not exist: {args.file}\n")
        return 1

    try:
        from consultancy.tenders import evaluate_tender, fetch_tenders
        from consultancy.proposals import generate_proposal, get_proposal_filename
    except ImportError as e:
        sys.stderr.write(f"Error importing consultancy module: {e}\n")
        return 1

    try:
        profile = load_profile(allow_fallback=True)
        stepcon = profile.stepcon_solutions
    except Exception as e:
        sys.stderr.write(f"Error loading Stepcon profile: {e}\n")
        return 1

    # Mode 1: Discover tenders
    if args.discover:
        tenders = fetch_tenders(dry_run=args.dry_run)
        if args.json:
            print(json.dumps([t.to_dict() for t in tenders], indent=2))
            return 0
        print("\n" + "=" * 72)
        print("STEPCON SOLUTIONS (RC - 8284984): DISCOVERED TENDERS")
        print("=" * 72)
        for idx, t in enumerate(tenders, 1):
            eval_res = evaluate_tender(stepcon, t.description)
            print(f"#{idx}. [{t.id}] {t.title}")
            print(f"    Client: {t.client or 'Open Tender'} | Budget: {t.budget}")
            print(f"    Fit Score: {eval_res.overall_score:.1f}% ({eval_res.rationale})")
            print("-" * 72)
        print("=" * 72 + "\n")
        return 0

    # Mode 2: Proposal generation
    if args.proposal:
        tender_text = _resolve_input_text(None, None, fallback_arg=args.proposal)
        if not tender_text:
            sys.stderr.write("Error: No tender description provided for proposal generation.\n")
            return 1

        tender_data = {
            "title": "Enterprise Cloud & DevSecOps Modernization",
            "client": args.client or "Enterprise Client",
            "description": tender_text,
        }
        proposal_text = generate_proposal(stepcon, tender_data, candidate=profile)

        if args.output_dir:
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            prop_filename = get_proposal_filename(tender_data)
            prop_path = out_dir / prop_filename
            prop_path.write_text(proposal_text, encoding="utf-8")
            print(f"Proposal written to: {prop_path.resolve()}")
        else:
            print(proposal_text)
        return 0

    # Mode 3: Evaluate tender
    tender_input = _resolve_input_text(args.text, args.file, fallback_arg=args.eval)
    if args.file and tender_input is None:
        sys.stderr.write(f"Error: Could not read specified tender file: {args.file}\n")
        return 1

    if args.eval is not None or args.text is not None or args.file is not None:
        if not tender_input or not str(tender_input).strip():
            sys.stderr.write("Error: No tender description provided. Specify --text, --file, or --eval.\n")
            return 1

    if tender_input and str(tender_input).strip():
        res = evaluate_tender(stepcon, tender_input)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
            return 0

        print("\n" + "=" * 72)
        print("STEPCON SOLUTIONS (RC - 8284984): TENDER EVALUATION")
        print("=" * 72)
        print(f"Overall Fit Score: {res.overall_score:.1f}%")
        print(f"Recommendation:    {res.rationale}")
        print("-" * 72)
        bd = res.breakdown
        print(f"  - Offerings Match (40%):  {bd.get('offerings', 0.0):.1f}%")
        print(f"  - SLA Alignment (25%):    {bd.get('sla', 0.0):.1f}%")
        print(f"  - Commercial Model (20%): {bd.get('commercial', 0.0):.1f}%")
        print(f"  - Credentials Match (15%):{bd.get('credentials', 0.0):.1f}%")
        print("=" * 72 + "\n")
        return 0

    # Default fallback: show tenders
    tenders = fetch_tenders(dry_run=True)
    print(f"Stepcon Solutions (RC - 8284984) pipeline active. {len(tenders)} tenders available. Use --help for options.")
    return 0


# ============================================================================
# 3. Dedicated Stdin Evaluation Interface
# ============================================================================

def evaluate_from_stdin(text: str) -> int:
    """
    Evaluates candidate suitability directly from a standard input text string.
    Explicitly contracted by e2e_tests/test_tier2_boundaries.py (test_f13_b2_empty_stdin_input).
    """
    if text is None or not str(text).strip():
        sys.stderr.write("Error: evaluate_from_stdin received empty or whitespace input.\n")
        return 1

    try:
        profile = load_profile(allow_fallback=True)
        res = evaluate_job(profile, str(text).strip())
        print(f"Evaluated Match Score: {res.overall_score:.1f}% | {res.rationale}")
        return 0
    except Exception as e:
        sys.stderr.write(f"Error during stdin evaluation: {e}\n")
        return 1


def handle_rebuild(args: argparse.Namespace) -> int:
    """Executes the 'rebuild' (alias: 'render') subcommand."""
    from tailoring.rebuilder import rebuild_opportunity_package
    target = args.opportunity or args.file or "Gates_Foundation"
    from_fmt = getattr(args, "from_format", "md")

    try:
        res = rebuild_opportunity_package(target, from_format=from_fmt)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
            return 0

        print("\n" + "=" * 76)
        print("CAREER AUTOMATION: APPLICATION DOCUMENT REBUILD ENGINE")
        print("=" * 76)
        print(f"Opportunity Directory: {res['opportunity_directory']}")
        print(f"Source Format:         {from_fmt.upper()} -> PDF")
        print("-" * 76)
        print("Rebuilt Documents:")
        for doc in res["rebuilt_documents"]:
            print(f"  [{doc['type']}] Source: {doc['source']} -> PDF: {doc['pdf']} ({doc['pages']} pages) [{doc['status'].upper()}]")
        print("=" * 76 + "\n")
        return 0
    except Exception as e:
        sys.stderr.write(f"Error rebuilding application documents: {e}\n")
        return 1


def handle_correct(args: argparse.Namespace) -> int:
    """Executes the 'correct' (alias: 'patch') subcommand."""
    from tailoring.rebuilder import patch_opportunity_text
    target = args.opportunity or "Gates_Foundation"
    find_str = args.find
    replace_str = args.replace

    if not find_str or replace_str is None:
        sys.stderr.write("Error: Both --find and --replace must be specified.\n")
        return 1

    try:
        res = patch_opportunity_text(target, find_str, replace_str)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
            return 0

        print("\n" + "=" * 76)
        print("CAREER AUTOMATION: FIND & REPLACE CORRECTION ENGINE")
        print("=" * 76)
        print(f"Opportunity Target: {res['folder']}")
        print(f"Find String:        '{find_str}'")
        print(f"Replacement:        '{replace_str}'")
        print(f"Patched Files ({len(res['modified_files'])}): {', '.join(res['modified_files']) if res['modified_files'] else 'None (string not present)'}")
        print("-" * 76)
        print("Recompiled Application Documents:")
        for doc in res["rebuilt"]:
            print(f"  [{doc['type']}] Source: {doc['source']} -> PDF: {doc['pdf']} ({doc['pages']} pages)")

        if getattr(args, "profile", False):
            for p_path in (Path("data/profile-data.json"), Path("profile-data.json")):
                if p_path.is_file():
                    p_txt = p_path.read_text(encoding="utf-8")
                    if find_str in p_txt:
                        p_path.write_text(p_txt.replace(find_str, replace_str), encoding="utf-8")
                        print(f"  [Single Source of Truth Updated]: {p_path.name}")

        print("=" * 76 + "\n")
        return 0
    except Exception as e:
        sys.stderr.write(f"Error executing correction: {e}\n")
        return 1


# ============================================================================
# 4. Master CLI Runner
# ============================================================================

def run_cli(args: Optional[List[str]] = None) -> int:
    """
    Primary program entry point for executing CLI commands programmatically or via sys.argv.
    """
    parser = create_parser()

    if args is None:
        args = sys.argv[1:]

    if not args:
        parser.print_help()
        return 0

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1

    if getattr(parsed_args, "verbose", False):
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    subcmd = getattr(parsed_args, "subcommand", None)
    if subcmd == "eval":
        return handle_eval(parsed_args)
    elif subcmd == "tailor":
        return handle_tailor(parsed_args)
    elif subcmd == "apply":
        return handle_apply(parsed_args)
    elif subcmd == "digest":
        return handle_digest(parsed_args)
    elif subcmd == "audit":
        return handle_audit(parsed_args)
    elif subcmd == "stepcon":
        return handle_stepcon(parsed_args)
    elif subcmd in ("rebuild", "render"):
        return handle_rebuild(parsed_args)
    elif subcmd in ("correct", "patch"):
        return handle_correct(parsed_args)
    else:
        sys.stderr.write(f"Error: Unrecognized subcommand '{subcmd}'. Run --help for usage.\n")
        return 2


def main() -> int:
    """CLI script entry point."""
    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
