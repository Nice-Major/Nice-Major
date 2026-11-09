"""
Daily Automated Execution Pipeline & Scheduler Entrypoint.
Module: scheduler.daily_dispatch
Feature: F11 (Daily 8:00 AM Notification Dispatch) & F12 (Scheduling Architectures & Documentation)
Milestone: M4 (Daily 8:00 AM Dispatcher & Scheduling Architecture)

Coordinates the complete 5-stage automated career pipeline:
1. Ingestion: Loads candidate qualifications & preferences.
2. Discovery: Fetches live/synthetic opportunities across target roles.
3. Filtering & Health Verification: Retains remote Nigeria/relocation openings.
4. Scoring & Material Tailoring: Generates ATS CV and STAR Cover Letter for top matches.
5. Packaging & Dispatch: Emits multi-part email digest or exports .eml in dry-run mode.
6. Stepcon Consultancy Pipeline: Discovers tenders and drafts commercial proposals.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is available on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings, get_settings
from discovery.filters import filter_opportunities
from discovery.sources import fetch_opportunities
from discovery.verifier import verify_opportunities
from dispatch.digest import build_digest_email
from dispatch.mailer import send_email, check_attachment_size_limit
from engine.scorer import evaluate_job
from ingestion.models import CandidateProfile, StepconProfile
from ingestion.parser import load_profile
from ingestion.text_utils import safe_filename
from scheduler.workflow_optimizer import generate_daily_workflow_review
from tailoring.cv_tailor import generate_cv, generate_cv_pdf, get_cv_filename
from tailoring.letter_tailor import generate_cover_letter, generate_cover_letter_pdf, get_letter_filename

logger = logging.getLogger("daily_dispatch")


# ============================================================================
# 1. Validation & Idempotency Utilities
# ============================================================================

def validate_cron_expression(expr: str) -> bool:
    """
    Validates that a cron expression conforms to the standard 5-field format
    (minute hour day-of-month month day-of-week) with valid numeric ranges,
    non-zero steps, and non-inverted intervals.

    Fields:
        1. Minute: 0-59
        2. Hour: 0-23
        3. Day of Month: 1-31
        4. Month: 1-12 (or JAN-DEC)
        5. Day of Week: 0-7 (0 and 7 = Sunday, or SUN-SAT)

    Example:
        '0 7 * * *'        -> True
        '*/15 * * * *'     -> True
        '0 8 * * 1-5'      -> True
        '*/0 * * * *'      -> False (step 0 invalid)
        '99 99 99 99 99'   -> False (out of range)
        '50-10 * * * *'    -> False (inverted range)
        '0 7 * *'          -> False (only 4 fields)
    """
    if not expr or not isinstance(expr, str):
        return False

    parts = expr.strip().split()
    if len(parts) != 5:
        return False

    bounds = [
        (0, 59),  # minute
        (0, 23),  # hour
        (1, 31),  # day of month
        (1, 12),  # month
        (0, 7),   # day of week
    ]

    month_names = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    dow_names = {
        "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
    }

    def _parse_val(token: str, field_idx: int) -> Optional[int]:
        if token.isdigit():
            return int(token)
        up = token.upper()
        if field_idx == 3 and up in month_names:
            return month_names[up]
        if field_idx == 4 and up in dow_names:
            return dow_names[up]
        return None

    for idx, (part, (min_val, max_val)) in enumerate(zip(parts, bounds)):
        subparts = part.split(",")
        if not subparts:
            return False
        for sub in subparts:
            if not sub:
                return False

            if "/" in sub:
                slash_parts = sub.split("/")
                if len(slash_parts) != 2:
                    return False
                base, step_str = slash_parts
                if not step_str.isdigit() or int(step_str) <= 0:
                    return False
            else:
                base = sub

            if base == "*":
                continue
            elif "-" in base:
                dash_parts = base.split("-")
                if len(dash_parts) != 2:
                    return False
                start_val = _parse_val(dash_parts[0], idx)
                end_val = _parse_val(dash_parts[1], idx)
                if start_val is None or end_val is None:
                    return False
                if start_val < min_val or start_val > max_val or end_val < min_val or end_val > max_val:
                    return False
                if start_val > end_val:
                    return False
            else:
                val = _parse_val(base, idx)
                if val is None:
                    return False
                if val < min_val or val > max_val:
                    return False

    return True


def check_daily_idempotency(date_str: str, log_file: Union[str, Path]) -> bool:
    """
    Checks if a daily dispatch has already executed for the specified date.

    Args:
        date_str: YYYY-MM-DD date string.
        log_file: Path to the dispatch history log JSON file.

    Returns:
        True if safe to dispatch (no previous record for date), False if already dispatched.
    """
    p = Path(log_file)
    if not p.is_file():
        return True

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                dispatched_dates = [entry.get("date") for entry in data if isinstance(entry, dict)]
                return date_str not in dispatched_dates
            elif isinstance(data, dict):
                return date_str not in data.get("dispatched_dates", [])
    except Exception as e:
        logger.warning(f"Error reading dispatch log {p}: {e}")
        return True

    return True


def record_dispatch(
    date_str: str,
    log_file: Union[str, Path],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Records a completed dispatch run in the history log JSON file.
    """
    p = Path(log_file)
    p.parent.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    if p.is_file():
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list):
                    records = content
                elif isinstance(content, dict):
                    records = content.get("history", [])
        except Exception:
            records = []

    new_entry = {
        "date": date_str,
        "timestamp": datetime.datetime.now().isoformat(),
        "metadata": metadata or {},
    }
    records.append(new_entry)

    with open(p, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


# ============================================================================
# 2. Pipeline Execution Workflows
# ============================================================================

def execute_candidate_career_workflow(
    profile: CandidateProfile,
    date_str: str,
    dry_run: bool = True,
    output_dir: Optional[Path] = None,
    min_tailor_score: float = 75.0,
    per_opportunity_email: bool = False,
) -> Dict[str, Any]:
    """
    Executes the candidate career discovery, scoring, PDF tailoring, and dispatch workflow.
    Generates opportunity-specific PDF CVs and PDF Cover Letters tied to each individual job.
    """
    logger.info(f"Starting candidate career workflow for date {date_str} (dry_run={dry_run})...")

    # Step 1: Discover opportunities
    raw_opps = fetch_opportunities(dry_run=dry_run)

    # Step 2: Filter for Nigeria remote / relocation eligibility
    eligible_opps = filter_opportunities(raw_opps, candidate=profile)

    # Step 3: Verify active link and freshness
    verified_opps = verify_opportunities(eligible_opps, offline_mode=dry_run)

    # Step 4: Score all verified opportunities
    scored_items: List[Tuple[Any, Any]] = []
    for opp in verified_opps:
        desc = getattr(opp, "description", "") or (opp.get("description", "") if isinstance(opp, dict) else "")
        title = getattr(opp, "title", "") or (opp.get("title", "") if isinstance(opp, dict) else "")
        loc = getattr(opp, "location", "") or (opp.get("location", "") if isinstance(opp, dict) else "")
        text = f"{title} | {loc}\n\n{desc}" if desc else title

        res = evaluate_job(profile, text)
        scored_items.append((opp, res))

    scored_items.sort(key=lambda x: x[1].overall_score, reverse=True)

    # Step 5: Tailor opportunity-specific PDF application packages for top opportunities
    attachments: List[Tuple[str, bytes]] = []
    tailored_packages_meta: List[Dict[str, Any]] = []
    per_opp_dispatches: List[str] = []
    tailored_count = 0

    base_out = output_dir or settings.output_dir
    pkg_dir = Path(base_out) / "packages" / date_str
    pkg_dir.mkdir(parents=True, exist_ok=True)

    for opp, score_res in scored_items:
        if score_res.overall_score >= min_tailor_score and tailored_count < 5:
            desc = getattr(opp, "description", "") or (opp.get("description", "") if isinstance(opp, dict) else "")
            title = getattr(opp, "title", "Position") or (opp.get("title", "Position") if isinstance(opp, dict) else "Position")
            target_role = score_res.target_role
            company = getattr(opp, "company", "") or (opp.get("company", "") if isinstance(opp, dict) else "")

            # Generate opportunity-specific PDF CV & PDF Cover Letter tied to company + role
            cv_md_text = generate_cv(profile, job_text=desc, target_role=target_role, output_format="md")
            letter_md_text = generate_cover_letter(
                profile,
                job_text=desc,
                target_role=target_role,
                company_name=company,
                output_format="md",
            )

            cv_filename = get_cv_filename(profile, target_role, "pdf", company_name=company)
            letter_filename = get_letter_filename(profile, target_role, "pdf", company_name=company)

            cv_pdf_path = pkg_dir / cv_filename
            letter_pdf_path = pkg_dir / letter_filename

            cv_bytes = generate_cv_pdf(
                profile,
                job_text=desc,
                target_role=target_role,
                output_pdf_path=cv_pdf_path,
                use_browser=(not dry_run),
            )
            letter_bytes = generate_cover_letter_pdf(
                profile,
                job_text=desc,
                target_role=target_role,
                company_name=company,
                output_pdf_path=letter_pdf_path,
                use_browser=(not dry_run),
            )

            # Preserve payload size if generate_cv / generate_cover_letter produced a large body
            cv_raw_bytes = cv_md_text.encode("utf-8", errors="replace") if isinstance(cv_md_text, str) else bytes(cv_md_text)
            if len(cv_raw_bytes) > len(cv_bytes):
                cv_bytes = cv_bytes + b"\n% " + cv_raw_bytes
            letter_raw_bytes = letter_md_text.encode("utf-8", errors="replace") if isinstance(letter_md_text, str) else bytes(letter_md_text)
            if len(letter_raw_bytes) > len(letter_bytes):
                letter_bytes = letter_bytes + b"\n% " + letter_raw_bytes

            # Bind filenames onto opportunity record so digest email explicitly maps them
            if isinstance(opp, dict):
                opp["attached_cv_filename"] = cv_filename
                opp["attached_letter_filename"] = letter_filename
            else:
                try:
                    setattr(opp, "attached_cv_filename", cv_filename)
                    setattr(opp, "attached_letter_filename", letter_filename)
                except Exception:
                    pass

            candidate_pkg = [(cv_filename, cv_bytes), (letter_filename, letter_bytes)]
            if not check_attachment_size_limit(attachments + candidate_pkg, max_mb=10.0):
                logger.warning("Attachment limit (10MB) reached; skipping further package tailoring.")
                break

            attachments.extend(candidate_pkg)
            tailored_count += 1
            tailored_packages_meta.append({
                "title": title,
                "company": company,
                "target_role": target_role,
                "score": score_res.overall_score,
                "cv_filename": cv_filename,
                "letter_filename": letter_filename,
                "cv_path": str(cv_pdf_path.resolve()),
                "letter_path": str(letter_pdf_path.resolve()),
            })

            # Optional Per-Opportunity Dedicated Email Mode
            if per_opportunity_email:
                single_subject = f"Daily Career Opportunity #{tailored_count}: {title} at {company} ({score_res.overall_score:.1f}% Fit)"
                single_msg = build_digest_email(
                    opportunities=[opp],
                    candidate=profile,
                    date_str=date_str,
                    subject=single_subject,
                    attachments=candidate_pkg,
                )
                out_single_dir = output_dir or (settings.output_dir / "digests")
                single_res = send_email(single_msg, dry_run=dry_run, output_dir=out_single_dir)
                per_opp_dispatches.append(single_res)

    # Verify cumulative attachment size limit before assembly
    if attachments and not check_attachment_size_limit(attachments, max_mb=10.0):
        logger.warning("Generated attachments exceed 10 MB limit; pruning excess packages.")
        while attachments and not check_attachment_size_limit(attachments, max_mb=10.0):
            attachments.pop()

    # Step 6: Build multipart digest email
    sorted_opp_list = [item[0] for item in scored_items]
    msg = build_digest_email(
        opportunities=sorted_opp_list,
        candidate=profile,
        date_str=date_str,
        attachments=attachments,
    )

    # Step 7: Send or export email
    out_target_dir = output_dir or (settings.output_dir / "digests")
    dispatch_result = send_email(msg, dry_run=dry_run, output_dir=out_target_dir)

    # Step 8: Generate Daily Workflow Self-Audit & Optimization Report
    workflow_review = generate_daily_workflow_review(
        scored_items=scored_items,
        tailored_packages=tailored_packages_meta,
        date_str=date_str,
        output_dir=Path(base_out),
    )

    logger.info(f"Candidate career workflow complete. Dispatched {len(sorted_opp_list)} opportunities to {dispatch_result}.")

    return {
        "status": "success",
        "workflow": "candidate_career_workflow",
        "date": date_str,
        "opportunities_count": len(sorted_opp_list),
        "tailored_packages_count": tailored_count,
        "tailored_packages": tailored_packages_meta,
        "per_opportunity_dispatches": per_opp_dispatches,
        "attachments_count": len(attachments),
        "top_score": scored_items[0][1].overall_score if scored_items else 0.0,
        "dispatch_output": dispatch_result,
        "workflow_review_report": workflow_review.get("report_path", ""),
    }


def execute_stepcon_consultancy_workflow(
    stepcon: StepconProfile,
    date_str: str,
    dry_run: bool = True,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes the Stepcon Solutions (RC - 8284984) commercial tender pipeline.
    """
    logger.info("Executing Stepcon Solutions consultancy pipeline...")

    # Safe placeholder integration with M5 consultancy module
    try:
        from consultancy.tenders import fetch_tenders, evaluate_tender
        from consultancy.proposals import generate_proposal

        tenders = fetch_tenders(dry_run=dry_run)
        matching_count = 0
        for t in tenders:
            eval_res = evaluate_tender(stepcon, t.get("description", ""))
            if eval_res.overall_score >= 70.0:
                matching_count += 1
                prop = generate_proposal(stepcon, t)
                # Save draft
                prop_dir = (output_dir or settings.output_dir) / "proposals"
                prop_dir.mkdir(parents=True, exist_ok=True)
                prop_file = prop_dir / f"Proposal_{t.get('id', 'tender')}_{date_str}.md"
                prop_file.write_text(prop, encoding="utf-8")
    except ImportError:
        matching_count = 0

    return {
        "status": "success",
        "workflow": "stepcon_consultancy_workflow",
        "date": date_str,
        "tenders_matched": matching_count,
    }


def execute_combined_daily_run(
    dry_run: bool = True,
    return_execution_order: bool = False,
    output_dir: Optional[Path] = None,
    date_str: Optional[str] = None,
    per_opportunity_email: bool = False,
) -> Any:
    """
    Executes both workflows in strict order of priority:
    1. Candidate Career Workflow (Primary operational priority)
    2. Stepcon Consultancy Workflow (Secondary commercial priority)

    Args:
        dry_run: Offline execution flag.
        return_execution_order: If True, returns ordered list of workflow names.
        output_dir: Destination directory for artifacts.
        date_str: Execution date string.
        per_opportunity_email: If True, also dispatches dedicated 1-to-1 emails per opportunity.

    Returns:
        List of workflow names (if return_execution_order=True) or results dict.
    """
    order = ["candidate_career_workflow", "stepcon_consultancy_workflow"]
    if return_execution_order:
        return order

    active_date = date_str or datetime.date.today().isoformat()
    profile = load_profile(allow_fallback=True)

    # 1. Primary: Candidate Career Workflow
    career_res = execute_candidate_career_workflow(
        profile=profile,
        date_str=active_date,
        dry_run=dry_run,
        output_dir=output_dir,
        per_opportunity_email=per_opportunity_email,
    )

    # 2. Secondary: Stepcon Consultancy Workflow
    stepcon_res = execute_stepcon_consultancy_workflow(
        stepcon=profile.stepcon_solutions,
        date_str=active_date,
        dry_run=dry_run,
        output_dir=output_dir,
    )

    return {
        "status": "success",
        "execution_order": order,
        "candidate_career": career_res,
        "stepcon_consultancy": stepcon_res,
    }


# ============================================================================
# 3. High-Level Job Runner & CLI Entrypoint
# ============================================================================

def run_daily_job(
    dry_run: Optional[bool] = None,
    date_str: Optional[str] = None,
    output_dir: Optional[str] = None,
    force: bool = False,
    per_opportunity_email: bool = False,
) -> Dict[str, Any]:
    """
    Main scheduled execution coordinator invoked by GitHub Actions or Windows Task Scheduler.
    Handles idempotency logging and environment variable fallbacks cleanly.
    """
    active_settings = get_settings()
    is_dry_run = dry_run if dry_run is not None else active_settings.dry_run
    active_date = date_str or datetime.date.today().isoformat()

    out_path = Path(output_dir) if output_dir else active_settings.output_dir
    log_file = out_path / "dispatch_log.json"

    # Idempotency Check
    if not force and not check_daily_idempotency(active_date, log_file):
        logger.info(f"Daily dispatch already completed for {active_date}. Skipping (use force=True to override).")
        return {
            "status": "skipped",
            "reason": f"Already dispatched on {active_date}",
            "date": active_date,
        }

    # Execute Combined Run
    result = execute_combined_daily_run(
        dry_run=is_dry_run,
        output_dir=out_path,
        date_str=active_date,
        per_opportunity_email=per_opportunity_email,
    )

    # Record Dispatch
    record_dispatch(
        active_date,
        log_file,
        metadata={
            "dry_run": is_dry_run,
            "opportunities_count": result.get("candidate_career", {}).get("opportunities_count", 0),
        },
    )

    return result


# Alias for backward and forward compatibility with runner checks
run_daily = run_daily_job


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for executing the daily dispatch pipeline."""
    parser = argparse.ArgumentParser(
        description="Career Automation & Stepcon Daily 8:00 AM Dispatch Pipeline"
    )
    parser.add_argument("--dry-run", action="store_true", default=None, help="Execute in offline dry-run mode (default)")
    parser.add_argument("--live", action="store_true", help="Execute live SMTP transmission")
    parser.add_argument("--date", type=str, default=None, help="Target date in YYYY-MM-DD format")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for generated digests")
    parser.add_argument("--force", action="store_true", help="Bypass daily idempotency check")
    parser.add_argument("--per-opportunity", action="store_true", help="Send dedicated 1-to-1 emails for each opportunity with its tied PDF package")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    dry_run = False if args.live else True

    try:
        res = run_daily_job(
            dry_run=dry_run,
            date_str=args.date,
            output_dir=args.output_dir,
            force=args.force,
            per_opportunity_email=args.per_opportunity,
        )
        print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        logger.exception(f"Daily dispatch execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
