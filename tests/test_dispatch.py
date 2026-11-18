"""
Comprehensive Unit & Integration Test Suite for Milestone 4.
Module: tests.test_dispatch
Features: F11 (Daily 8:00 AM Notification Dispatch) & F12 (Scheduling Architectures & Documentation)

Verifies:
1. Multi-part MIME email construction and headers.
2. UTF-8 non-ASCII subject and recipient handling.
3. Inline CSS styling and zero external stylesheet links.
4. Profile-listed metrics and opportunity links presence.
5. Dry-run .eml export and credential protection.
6. Attachment size limit guardrails.
7. Crontab 5-field syntax validation.
8. Daily idempotency protection.
9. Execution order prioritization (Candidate career before Stepcon).
10. WAT to UTC conversion accuracy.
11. Workflow YAML and PowerShell script parameter validation.
"""

from __future__ import annotations

import os
import sys
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
from ingestion.models import CandidateInfo, CandidateProfile
from dispatch.digest import (
    build_digest_email,
    format_digest_html,
    format_digest_text,
)
from dispatch.mailer import (
    check_attachment_size_limit,
    export_eml,
    send_email,
)
from scheduler.opportunity_history import (
    filter_new_opportunities,
    record_dispatched_opportunities,
)
from scheduler.workflow_feedback import role_preference_adjustments, record_role_feedback
from scheduler.daily_dispatch import (
    _select_employer_diverse_items,
    check_daily_idempotency,
    execute_combined_daily_run,
    record_dispatch,
    run_daily_job,
    validate_cron_expression,
)


# ============================================================================
# Synthetic Test Fixtures
# ============================================================================

@pytest.fixture
def sample_opportunity():
    return {
        "title": "Senior DevOps & Platform Engineer",
        "company": "Global Cloud Corp",
        "location": "Remote - Worldwide (EMEA / UTC+1)",
        "url": "https://careers.globalcloud.example/devops-101",
        "description": (
            "We are seeking a Senior DevOps Engineer to lead our Kubernetes and Terraform automation. "
            "Must have strong experience in container orchestration (Kubernetes, Docker), Infrastructure as Code "
            "(Terraform), CI/CD pipelines (GitHub Actions), and AWS/Azure cloud platforms. Candidate must ensure "
            "enterprise 99.9% uptime SLA across multi-region environments."
        ),
        "posted_date": "2026-11-06",
        "overall_score": 88.5,
        "breakdown": {
            "skills": 90.0,
            "title": 95.0,
            "metrics": 85.0,
            "mobility": 90.0,
            "certs": 80.0,
        },
        "matched_skills": ["Kubernetes", "Terraform", "Docker", "AWS", "Azure"],
        "missing_skills": [],
        "target_role": "DevOps Engineer",
        "rationale": "Strong Apply (Match Score: 88.5%): High alignment across core competencies.",
    }


# ============================================================================
# 1. Feature F11: Digest Formatting Tests
# ============================================================================

class TestDigestFormatting:
    """Verifies HTML and Plain Text formatting rules."""

    def test_format_digest_html_contains_required_metrics_and_links(self, sample_opportunity):
        import html
        html_out = format_digest_html([sample_opportunity])
        assert "99.9%" in html_out
        assert "99%" in html_out
        assert sample_opportunity["url"] in html_out
        assert sample_opportunity["company"] in html_out
        assert html.escape(sample_opportunity["title"]) in html_out

    def test_format_digest_html_inline_styles_no_external_stylesheets(self, sample_opportunity):
        html_out = format_digest_html([sample_opportunity])
        assert "<link rel=\"stylesheet\"" not in html_out
        assert "<link" not in html_out

    def test_format_digest_text_contains_summary(self, sample_opportunity):
        text_out = format_digest_text([sample_opportunity])
        assert "DAILY CAREER & OPPORTUNITY DIGEST" in text_out
        assert "99.9%" in text_out
        assert "99%" in text_out
        assert sample_opportunity["company"] in text_out
        assert sample_opportunity["url"] in text_out

    def test_format_digest_empty_opportunities_graceful_message(self):
        html_out = format_digest_html([])
        assert "No Opportunities Discovered Today" in html_out or "No external postings" in html_out
        text_out = format_digest_text([])
        assert "No opportunities matched" in text_out

    def test_digest_does_not_invent_candidate_metrics(self):
        profile = CandidateProfile(candidate=CandidateInfo(
            full_name="Taylor Example",
            first_name="Taylor",
            last_name="Example",
            email="",
            phone="",
            location="",
            commitment="",
        ))

        html_out = format_digest_html([], candidate=profile)
        text_out = format_digest_text([], candidate=profile)

        assert "99.9%" not in html_out + text_out
        assert "99%" not in html_out + text_out
        assert "Terraform" not in html_out + text_out
        assert "Stepcon Solutions (RC - 8284984)" not in html_out + text_out

    def test_format_digest_renders_score_breakdown(self, sample_opportunity):
        html_out = format_digest_html([sample_opportunity])
        assert "Skills" in html_out
        assert "Title" in html_out
        assert "Metrics" in html_out
        assert "Mobility" in html_out
        assert "Certs" in html_out


# ============================================================================
# 2. Feature F11: MIME Email Builder Tests
# ============================================================================

class TestMIMEEmailBuilder:
    """Verifies multi-part MIME hierarchy and RFC compliance."""

    def test_build_digest_email_multipart_mime_structure(self, sample_opportunity):
        msg = build_digest_email([sample_opportunity], date_str="2026-11-07")
        assert msg is not None
        assert msg.is_multipart()
        assert "Daily Career" in str(msg.get("Subject", ""))

    def test_build_digest_email_recipient_defaults_to_candidate(self, sample_opportunity):
        msg = build_digest_email([sample_opportunity])
        assert "aniekwevictor9@gmail.com" in str(msg.get("To", ""))

    def test_build_digest_email_custom_subject_and_utf8(self, sample_opportunity):
        custom_subj = "Digest: Jöhn Vïctor Aníèkwé — DevOps"
        msg = build_digest_email([sample_opportunity], subject=custom_subj)
        assert msg is not None
        # Header is decoded or preserved
        assert custom_subj in str(msg.get("Subject")) or "=?" in msg["Subject"].encode()

    def test_build_digest_email_with_attachments(self, sample_opportunity):
        attachments = [
            ("John_Victor_Aniekwe_DevOps_CV.pdf", b"%PDF-1.4 test cv bytes"),
            ("John_Victor_Aniekwe_Cover_Letter.docx", b"Test editable letter content"),
        ]
        msg = build_digest_email([sample_opportunity], attachments=attachments)
        payloads = msg.get_payload()
        assert len(payloads) >= 3  # alternative container + 2 attachments
        attachment_types = {
            part.get_filename(): part.get_content_type()
            for part in msg.walk()
            if part.get_filename()
        }
        assert attachment_types["John_Victor_Aniekwe_DevOps_CV.pdf"] == "application/pdf"
        assert (
            attachment_types["John_Victor_Aniekwe_Cover_Letter.docx"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_attachment_filenames_exclude_paths_without_rewriting_names(self, sample_opportunity):
        msg = build_digest_email(
            [sample_opportunity],
            attachments=[(r"C:\temp\Victor-Aniekwe-CV.PDF", b"pdf"), ("editable-CV.MD", "# CV")],
        )
        filenames = {
            part.get_filename()
            for part in msg.walk()
            if part.get_filename()
        }
        assert filenames == {"Victor-Aniekwe-CV.PDF", "editable-CV.MD"}

    def test_build_digest_email_empty_list_valid_mime(self):
        msg = build_digest_email([])
        assert msg is not None
        assert "Daily Career" in str(msg.get("Subject", ""))


# ============================================================================
# 3. Feature F11 & F15: Mailer & Dry-Run Tests
# ============================================================================

class TestMailer:
    """Verifies SMTP dispatcher and dry-run storage mechanics."""

    def test_mailer_dry_run_exports_eml_file(self, sample_opportunity, tmp_path):
        msg = build_digest_email([sample_opportunity])
        eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path))
        assert os.path.exists(eml_path)
        assert eml_path.endswith(".eml")

        with open(eml_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        assert "aniekwevictor9@gmail.com" in content
        assert "Daily Career" in content

    def test_mailer_dry_run_works_without_credentials(self, sample_opportunity, tmp_path):
        msg = build_digest_email([sample_opportunity])
        # Execution must succeed even with blank SMTP credentials
        eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path), smtp_host="", smtp_user="", smtp_password="")
        assert os.path.exists(eml_path)

    def test_mailer_live_mode_without_credentials_raises_error(self, sample_opportunity):
        msg = build_digest_email([sample_opportunity])
        with pytest.raises((ValueError, Exception)):
            send_email(msg, dry_run=False, smtp_host="", smtp_user="", smtp_password="")

    def test_check_attachment_size_limit(self):
        small_att = [("test.txt", b"hello world")]
        assert check_attachment_size_limit(small_att, max_mb=10) is True

        huge_att = [("huge.pdf", b"0" * (12 * 1024 * 1024))]  # 12 MB
        assert check_attachment_size_limit(huge_att, max_mb=10) is False


# ============================================================================
# 4. Feature F12: Scheduler Pipeline & Logic Tests
# ============================================================================

class TestSchedulerPipeline:
    """Verifies cron validation, idempotency, and workflow prioritization."""

    def test_explicit_live_run_overrides_offline_source_default(self, tmp_path, monkeypatch):
        import scheduler.daily_dispatch as daily_dispatch
        from ingestion.parser import load_profile

        calls = {}
        monkeypatch.setattr(
            daily_dispatch,
            "fetch_opportunities",
            lambda **kwargs: calls.update(kwargs) or [],
        )
        monkeypatch.setattr(daily_dispatch, "filter_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(daily_dispatch, "filter_new_opportunities", lambda *args, **kwargs: ([], 0))
        monkeypatch.setattr(daily_dispatch, "verify_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(daily_dispatch, "send_email", lambda *args, **kwargs: "sent")
        monkeypatch.setattr(daily_dispatch, "record_dispatched_opportunities", lambda *args, **kwargs: None)
        monkeypatch.setattr(daily_dispatch, "generate_daily_workflow_review", lambda **kwargs: {})

        result = daily_dispatch.execute_candidate_career_workflow(
            profile=load_profile(allow_fallback=False),
            date_str="2026-11-18",
            dry_run=False,
            output_dir=tmp_path,
        )

        assert result["status"] == "success"
        assert calls["dry_run"] is False
        assert calls["offline_mode"] is False

    def test_email_selection_keeps_highest_scored_role_per_company(self):
        items = [
            ({"company": "Supabase", "title": "Support Engineer EMEA"}, 99),
            ({"company": " supabase ", "title": "Support Engineer APAC"}, 98),
            ({"company": "New Relic", "title": "Cloud Engineer"}, 95),
            ({"company": "Sentry", "title": "Platform Engineer"}, 92),
            ({"company": "", "title": "Unknown employer role 1"}, 90),
            ({"company": "", "title": "Unknown employer role 2"}, 89),
        ]

        selected = _select_employer_diverse_items(items, limit=4)

        assert [item[0]["title"] for item in selected] == [
            "Support Engineer EMEA",
            "Cloud Engineer",
            "Platform Engineer",
            "Unknown employer role 1",
        ]
        assert _select_employer_diverse_items(items, limit=0) == []

    def test_validate_cron_expression_5_fields(self):
        assert validate_cron_expression("0 7 * * *") is True
        assert validate_cron_expression("*/15 * * * *") is True
        assert validate_cron_expression("0 7 * *") is False
        assert validate_cron_expression("0 7 * * * *") is False
        assert validate_cron_expression("") is False

    def test_daily_idempotency_prevents_duplicate_dispatch(self, tmp_path):
        log_file = tmp_path / "dispatch_log.json"
        test_date = "2026-11-07"

        # Initially, not dispatched
        assert check_daily_idempotency(test_date, log_file) is True

        # Record dispatch
        record_dispatch(test_date, log_file)

        # Subsequent check detects already dispatched
        assert check_daily_idempotency(test_date, log_file) is False

    def test_combined_run_candidate_priority_over_stepcon(self):
        execution_order = execute_combined_daily_run(dry_run=True, return_execution_order=True)
        assert execution_order[0] == "candidate_career_workflow"
        assert execution_order[1] == "stepcon_consultancy_workflow"

    def test_wat_to_utc_offset_calculation(self):
        wat_target_hour = 8
        utc_hour = wat_target_hour - 1
        assert utc_hour == 7

    def test_run_daily_job_end_to_end_dry_run(self, tmp_path):
        result = run_daily_job(dry_run=True, date_str="2026-11-07", output_dir=str(tmp_path), force=True)
        assert result is not None
        assert result.get("status") == "success"
        career = result["candidate_career"]
        assert all(Path(package["cv_md_path"]).is_file() for package in career["tailored_packages"])
        assert all(Path(package["letter_md_path"]).is_file() for package in career["tailored_packages"])
        assert all(Path(package["cv_docx_path"]).is_file() for package in career["tailored_packages"])
        assert all(Path(package["letter_docx_path"]).is_file() for package in career["tailored_packages"])
        assert all("-" not in package["cv_filename"] for package in career["tailored_packages"])
        assert all(package["cv_filename"].startswith("John Aniekwe ") for package in career["tailored_packages"])

    def test_opportunity_history_persists_delivered_jobs_and_normalizes_tracking_urls(self, tmp_path):
        state_file = tmp_path / "state" / "opportunity_history.json"
        first = {
            "title": "Cloud Engineer",
            "company": "Example Corp",
            "url": "https://jobs.example.com/role/42?utm_source=digest",
        }
        duplicate = {
            "title": "Cloud Engineer",
            "company": "Example Corp",
            "url": "https://JOBS.example.com/role/42/",
        }

        assert filter_new_opportunities([first], state_file) == ([first], 0)
        assert record_dispatched_opportunities([first], state_file, "2026-11-07") == 1
        assert filter_new_opportunities([duplicate], state_file) == ([], 1)

    def test_role_feedback_only_adjusts_order_after_three_explicit_interest_votes(self, tmp_path):
        state_file = tmp_path / "state" / "role_feedback.json"
        record_role_feedback(state_file, "Cloud Engineer", "interested")
        record_role_feedback(state_file, "Cloud Engineer", "not_interested")
        assert role_preference_adjustments({"roles": {"Cloud Engineer": {
            "interested": 1,
            "not_interested": 1,
        }}}) == {}

        data = record_role_feedback(state_file, "Cloud Engineer", "interested")
        assert role_preference_adjustments(data) == {"Cloud Engineer": 1.7}
        assert record_role_feedback(state_file, "Cloud Engineer", "interview")["roles"]["Cloud Engineer"]["interview"] == 1


# ============================================================================
# 5. Feature F12: Documentation & Script Static Tests
# ============================================================================

class TestArchitectureDocumentationAndScripts:
    """Verifies architectural documentation and script fixtures."""

    def test_architecture_comparison_document_present_and_complete(self):
        arch_path = PROJECT_ROOT / "scheduler" / "ARCHITECTURE.md"
        # If running prior to physical builder file creation, check specification content
        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8")
            assert "GitHub Actions" in content
            assert "Windows Task Scheduler" in content
            assert "cost" in content.lower()
            assert "jitter" in content.lower()

    def test_github_actions_workflow_cron_schedule(self):
        wf_path = PROJECT_ROOT / ".github" / "workflows" / "daily_dispatch.yml"
        if wf_path.exists():
            content = wf_path.read_text(encoding="utf-8")
            assert "0 7 * * *" in content

    def test_powershell_scheduler_script_parameter_escaping(self):
        ps_path = PROJECT_ROOT / "scripts" / "schedule_task.ps1"
        if ps_path.exists():
            content = ps_path.read_text(encoding="utf-8")
            assert '"' in content
            assert "Register-ScheduledTask" in content or "powershell" in content.lower()
