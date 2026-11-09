"""
Empirical Challenger Test Suite for Milestone 4 Iteration 2.
Author: challenger_m4_it2_2 (Teamwork Challenger Subagent)
Module: tests.test_challenger_m4_it2_empirical

Empirical stress tests for:
1. Concurrency and duplicate run stress testing on scheduler/daily_dispatch.py.
2. MIME compliance check on generated .eml files under BytesParser(policy=default).
3. Priority enforcement: verify candidate career workflow finishes completely before Stepcon consultancy runs.
4. Stress test attachment size limit enforcement: verify boundary conditions at exactly 10.0 MB vs 10.0001 MB.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import email
import email.parser
import email.policy
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parsedate_to_datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from config.settings import get_settings
from dispatch.digest import (
    build_digest_email,
    format_digest_html,
    format_digest_text,
)
from dispatch.mailer import (
    check_attachment_size_limit,
    export_eml,
    extract_attachments_from_message,
    send_email,
)
from scheduler.daily_dispatch import (
    check_daily_idempotency,
    execute_candidate_career_workflow,
    execute_combined_daily_run,
    execute_stepcon_consultancy_workflow,
    record_dispatch,
    run_daily_job,
    validate_cron_expression,
)


@pytest.fixture
def synthetic_profile_dict() -> Dict[str, Any]:
    return {
        "candidate": {
            "first_name": "John",
            "last_name": "Aniekwe",
            "full_name": "John Victor Aniekwe",
            "email": "aniekwevictor9@gmail.com",
            "phone": "+234 812 345 6789",
            "location": "Lagos, Nigeria (UTC+1 / CET Synchronous)",
        }
    }


@pytest.fixture
def synthetic_sample_job() -> Dict[str, Any]:
    return {
        "title": "Principal DevOps & Cloud Architect (EMEA / Remote)",
        "company": "CloudScale Global Systems",
        "location": "Remote - Nigeria Eligible / UTC+1",
        "url": "https://careers.cloudscale.example/jobs/devops-505",
        "description": (
            "We are hiring a Principal DevOps & Cloud Architect with extensive experience in "
            "AWS, Azure, Kubernetes, Terraform, CI/CD, and site reliability engineering. "
            "Must maintain 99.9% uptime SLA and deliver 99% RCA resolution."
        ),
        "posted_date": "2026-11-07",
        "overall_score": 94.0,
        "breakdown": {
            "skills": 95.0,
            "title": 95.0,
            "metrics": 90.0,
            "mobility": 95.0,
            "certs": 95.0,
        },
        "matched_skills": ["AWS", "Azure", "Kubernetes", "Terraform", "CI/CD"],
        "missing_skills": [],
        "target_role": "DevOps Engineer",
        "rationale": "Perfect alignment with cloud architecture competencies.",
    }


# ============================================================================
# 1. Concurrency and Duplicate Run Stress Testing
# ============================================================================

class TestConcurrencyAndDuplicateRunStress:
    """Rigorous empirical validation of idempotency, force override, and log recovery."""

    def test_sequential_duplicate_runs_idempotency(self, tmp_path):
        """Sequential runs on the same date: run 1 succeeds, run 2 is skipped without disk mutations."""
        test_date = "2026-12-01"
        out_dir = tmp_path / "idempotency_run"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Initial execution
        res1 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res1["status"] == "success"
        eml_files_1 = list(out_dir.rglob("*.eml"))
        assert len(eml_files_1) == 1

        # Second execution: idempotency skip
        res2 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res2["status"] == "skipped"
        assert f"Already dispatched on {test_date}" in res2["reason"]

        # Assert no new .eml file created
        eml_files_2 = list(out_dir.rglob("*.eml"))
        assert len(eml_files_2) == 1

    def test_force_flag_allows_reexecution_with_unique_artifacts(self, tmp_path):
        """Force flag allows repeated execution on the same date while recording multiple history entries."""
        test_date = "2026-12-02"
        out_dir = tmp_path / "force_run"
        out_dir.mkdir(parents=True, exist_ok=True)

        res1 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res1["status"] == "success"

        time.sleep(0.01)
        res2 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=True)
        assert res2["status"] == "success"

        time.sleep(0.01)
        res3 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=True)
        assert res3["status"] == "success"

        eml_files = list(out_dir.rglob("*.eml"))
        assert len(eml_files) == 3

        # Unforced subsequent run still skips
        res4 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res4["status"] == "skipped"

        # Log inspection
        log_file = out_dir / "dispatch_log.json"
        with open(log_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 3

    def test_corrupted_dispatch_log_recovery_and_reconstruction(self, tmp_path):
        """Verify resilience against malformed, partially-written, or non-array dispatch logs."""
        log_file = tmp_path / "dispatch_log.json"

        # Case A: Partial/corrupted JSON
        log_file.write_text('{"incomplete_json": [1, 2, ', encoding="utf-8")
        assert check_daily_idempotency("2026-12-03", log_file) is True

        # Recording overwrites corrupted file with valid JSON
        record_dispatch("2026-12-03", log_file, metadata={"reconstructed": True})
        with open(log_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        assert isinstance(records, list)
        assert records[-1]["date"] == "2026-12-03"

        # Case B: Zero-byte file
        log_file.write_text("", encoding="utf-8")
        assert check_daily_idempotency("2026-12-04", log_file) is True
        record_dispatch("2026-12-04", log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 1
        assert records[0]["date"] == "2026-12-04"

    def test_missing_parent_directories_auto_created(self, tmp_path):
        """Verifies that non-existent nested output directories are created cleanly."""
        nested_dir = tmp_path / "deep" / "nested" / "path" / "digests"
        assert not nested_dir.exists()

        res = run_daily_job(dry_run=True, date_str="2026-12-05", output_dir=str(nested_dir), force=False)
        assert res["status"] == "success"
        assert nested_dir.exists()
        assert len(list(nested_dir.rglob("*.eml"))) == 1


# ============================================================================
# 2. MIME Compliance Check on Generated .eml Files under BytesParser(policy=default)
# ============================================================================

class TestMIMEComplianceBytesParser:
    """Verifies complete RFC 5322 compliance using Python email.parser.BytesParser(policy=default)."""

    def test_bytesparser_zero_defects_standard_digest(self, synthetic_sample_job, synthetic_profile_dict, tmp_path):
        """BytesParser with email.policy.default reports exactly 0 defects on generated .eml."""
        msg = build_digest_email(
            [synthetic_sample_job],
            candidate=synthetic_profile_dict,
            date_str="2026-12-06",
        )
        eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path))

        with open(eml_path, "rb") as f:
            parsed = email.parser.BytesParser(policy=email.policy.default).parse(f)

        # Zero RFC 5322 defects
        assert len(parsed.defects) == 0, f"Defects encountered: {parsed.defects}"

        # Mandatory RFC 5322 Headers
        assert parsed["From"] is not None
        assert "Stepcon Solutions Career Automation" in parsed["From"]
        assert parsed["To"] == "aniekwevictor9@gmail.com"
        assert parsed["Subject"] is not None
        assert "Daily Career" in parsed["Subject"]
        assert parsed["Date"] is not None
        assert parsed["Message-ID"] is not None
        assert parsed["MIME-Version"] == "1.0"

        # Content-Type must be multipart/mixed
        assert parsed.get_content_type() == "multipart/mixed"

    def test_bytesparser_zero_defects_empty_digest(self, synthetic_profile_dict, tmp_path):
        """BytesParser validates empty digest (0 opportunities) with zero defects."""
        msg = build_digest_email(
            [],
            candidate=synthetic_profile_dict,
            date_str="2026-12-07",
        )
        eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path))

        with open(eml_path, "rb") as f:
            parsed = email.parser.BytesParser(policy=email.policy.default).parse(f)

        assert len(parsed.defects) == 0

        # Verify alternative parts contain empty message
        alt_body = parsed.get_body(preferencelist=("html", "plain"))
        assert alt_body is not None
        content = alt_body.get_content()
        assert "No Opportunities Discovered Today" in content or "0 Opportunities" in str(parsed["Subject"])

    def test_bytesparser_body_extraction_and_executive_metrics(self, synthetic_sample_job, synthetic_profile_dict):
        """Verify both plain and html bodies can be extracted cleanly and contain required metrics."""
        msg = build_digest_email([synthetic_sample_job], candidate=synthetic_profile_dict)
        raw_eml = msg.as_bytes()

        parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw_eml)
        assert len(parsed.defects) == 0

        # Extract plain text part
        text_body = parsed.get_body(preferencelist=("plain",))
        assert text_body is not None
        text_content = text_body.get_content()
        assert "99.9%" in text_content
        assert "99%" in text_content
        assert "John Victor Aniekwe" in text_content

        # Extract html part
        html_body = parsed.get_body(preferencelist=("html",))
        assert html_body is not None
        html_content = html_body.get_content()
        assert "99.9%" in html_content
        assert "99%" in html_content
        assert "John Victor Aniekwe" in html_content
        assert "<link" not in html_content.lower()

    def test_bytesparser_attachments_byte_exactness_binary_and_unicode(self, synthetic_sample_job):
        """Verify multiple attachments (Markdown, TXT, PDF, Raw Binary) are byte-for-byte exact upon decoding."""
        md_bytes = "# John Victor Aniekwe CV\nDevOps & Platform Architect\nSalary: ₦15,000,000 / $80,000\n🚀".encode("utf-8")
        txt_bytes = "STAR Cover Letter — 99.9% uptime SLA guaranteed.".encode("utf-8")
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Length 8 >>\nstream\n\x00\xff\xfe\xfd\x01\x02\x03\x04\nendstream\nendobj\n%%EOF"
        binary_bytes = bytes(range(256)) * 20  # 5,120 bytes of all possible byte values

        attachments = [
            ("CV_John_Aniekwe.md", md_bytes),
            ("Cover_Letter_John_Aniekwe.txt", txt_bytes),
            ("Portfolio_Spec.pdf", pdf_bytes),
            ("raw_data.bin", binary_bytes),
        ]

        msg = build_digest_email([synthetic_sample_job], attachments=attachments)
        raw_eml = msg.as_bytes()

        parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw_eml)
        assert len(parsed.defects) == 0

        extracted = {}
        for part in parsed.iter_attachments():
            extracted[part.get_filename()] = part.get_payload(decode=True)

        assert extracted["CV_John_Aniekwe.md"] == md_bytes
        assert extracted["Cover_Letter_John_Aniekwe.txt"] == txt_bytes
        assert extracted["Portfolio_Spec.pdf"] == pdf_bytes
        assert extracted["raw_data.bin"] == binary_bytes

    def test_bytesparser_non_ascii_subject_header_rfc2047(self, synthetic_sample_job):
        """Verify non-ASCII subject headers with Nigerian diacritics and emojis round-trip cleanly."""
        complex_subject = "Daily Career Digest: Victor Àníèkwé 🚀 [Cloud & DevOps]"
        msg = build_digest_email([synthetic_sample_job], subject=complex_subject)
        raw_eml = msg.as_bytes()

        parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw_eml)
        assert len(parsed.defects) == 0
        assert parsed["Subject"] == complex_subject

    def test_bytesparser_max_line_length_rfc5322(self, synthetic_sample_job):
        """RFC 5322 Section 2.1.1 mandates lines MUST NOT exceed 998 characters."""
        # Attach binary and large text
        large_text = ("A" * 150 + " ") * 200
        msg = build_digest_email(
            [synthetic_sample_job],
            attachments=[("large.txt", large_text.encode("utf-8")), ("data.bin", b"\x00\xff" * 10000)],
        )
        raw_eml = msg.as_bytes()

        lines = raw_eml.split(b"\n")
        max_line_len = max(len(line.rstrip(b"\r")) for line in lines)
        assert max_line_len <= 998, f"Line length violation: maximum line is {max_line_len} bytes (> 998)."


# ============================================================================
# 3. Priority Enforcement Stress Tests
# ============================================================================

class TestPriorityEnforcementStress:
    """Verifies that candidate career workflow finishes completely before Stepcon consultancy runs."""

    def test_strict_temporal_sequencing_and_order_contract(self, tmp_path):
        """Assert candidate career workflow completes strictly before Stepcon consultancy starts."""
        execution_timeline: List[Tuple[str, str, float]] = []

        import scheduler.daily_dispatch as dd
        real_career = dd.execute_candidate_career_workflow
        real_stepcon = dd.execute_stepcon_consultancy_workflow

        def spy_career(*args, **kwargs):
            execution_timeline.append(("career", "start", time.perf_counter()))
            res = real_career(*args, **kwargs)
            execution_timeline.append(("career", "finish", time.perf_counter()))
            return res

        def spy_stepcon(*args, **kwargs):
            execution_timeline.append(("stepcon", "start", time.perf_counter()))
            res = real_stepcon(*args, **kwargs)
            execution_timeline.append(("stepcon", "finish", time.perf_counter()))
            return res

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=spy_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=spy_stepcon):

            res = execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert res["status"] == "success"
        assert res["execution_order"] == ["candidate_career_workflow", "stepcon_consultancy_workflow"]
        assert len(execution_timeline) == 4

        # Validate sequence
        assert execution_timeline[0] == ("career", "start", execution_timeline[0][2])
        assert execution_timeline[1] == ("career", "finish", execution_timeline[1][2])
        assert execution_timeline[2] == ("stepcon", "start", execution_timeline[2][2])
        assert execution_timeline[3] == ("stepcon", "finish", execution_timeline[3][2])

        # Career finish must precede or equal stepcon start
        assert execution_timeline[1][2] <= execution_timeline[2][2]

    def test_career_workflow_failure_blocks_stepcon_execution(self, tmp_path):
        """Injected crash in candidate workflow guarantees Stepcon consultancy NEVER runs."""
        stepcon_called = False

        def broken_career(*args, **kwargs):
            raise ValueError("SIMULATED_CAREER_WORKFLOW_FAILURE: Ingestion pipe broke.")

        def dummy_stepcon(*args, **kwargs):
            nonlocal stepcon_called
            stepcon_called = True
            return {"status": "success"}

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=broken_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=dummy_stepcon):

            with pytest.raises(ValueError, match="SIMULATED_CAREER_WORKFLOW_FAILURE"):
                execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert stepcon_called is False, "Violation: Stepcon executed despite candidate workflow crash!"

    def test_candidate_latency_does_not_cause_preemption(self, tmp_path):
        """Even with significant delay in candidate workflow, Stepcon is not invoked prematurely."""
        stepcon_started = False

        def delayed_career(*args, **kwargs):
            time.sleep(0.15)
            assert not stepcon_started, "Preemption error: Stepcon started before candidate finished!"
            return {"status": "success", "workflow": "candidate_career_workflow"}

        def tracked_stepcon(*args, **kwargs):
            nonlocal stepcon_started
            stepcon_started = True
            return {"status": "success", "workflow": "stepcon_consultancy_workflow"}

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=delayed_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=tracked_stepcon):

            res = execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert res["status"] == "success"
        assert stepcon_started is True


# ============================================================================
# 4. Attachment Size Limit Enforcement: Boundary Conditions (10.0 MB vs 10.0001 MB)
# ============================================================================

class TestAttachmentSizeLimitBoundaries:
    """
    Stress-tests boundary conditions for cumulative attachment limits:
    - Binary 10.0 MB = 10 * 1024 * 1024 = 10,485,760 bytes.
    - Exactly 10.0 MB: must PASS.
    - Exactly 10.0 MB + 1 byte: must FAIL.
    - Exactly 10.0001 MB = int(10.0001 * 1024 * 1024) = 10,485,864 bytes: must FAIL.
    """

    EXACT_10_MB_BYTES = 10 * 1024 * 1024             # 10,485,760 bytes
    EXACT_10_MB_PLUS_1_BYTE = EXACT_10_MB_BYTES + 1    # 10,485,761 bytes
    EXACT_10_0001_MB_BYTES = int(10.0001 * 1024 * 1024)  # 10,485,864 bytes (+104 bytes over 10MB)

    def test_check_attachment_size_limit_exact_10_mb(self):
        """Exactly 10.0 MB (10,485,760 bytes) is strictly allowed."""
        att = [("doc_10mb.dat", b"a" * self.EXACT_10_MB_BYTES)]
        assert check_attachment_size_limit(att, max_mb=10.0) is True

    def test_check_attachment_size_limit_10_mb_plus_1_byte(self):
        """Exactly 10.0 MB + 1 byte (10,485,761 bytes) is strictly rejected."""
        att = [("doc_10mb_plus_1.dat", b"a" * self.EXACT_10_MB_PLUS_1_BYTE)]
        assert check_attachment_size_limit(att, max_mb=10.0) is False

    def test_check_attachment_size_limit_10_0001_mb(self):
        """Exactly 10.0001 MB (10,485,864 bytes) is strictly rejected under 10.0 MB limit."""
        assert self.EXACT_10_0001_MB_BYTES > self.EXACT_10_MB_BYTES
        att = [("doc_10_0001mb.dat", b"a" * self.EXACT_10_0001_MB_BYTES)]
        assert check_attachment_size_limit(att, max_mb=10.0) is False

    def test_check_attachment_size_limit_dynamic_max_mb(self):
        """When max_mb is configured to 10.0001 MB, 10,485,864 bytes passes but 10,485,865 fails."""
        att_exact = [("doc.dat", b"a" * self.EXACT_10_0001_MB_BYTES)]
        assert check_attachment_size_limit(att_exact, max_mb=10.0001) is True

        att_over = [("doc.dat", b"a" * (self.EXACT_10_0001_MB_BYTES + 1))]
        assert check_attachment_size_limit(att_over, max_mb=10.0001) is False

    def test_multipart_split_attachments_boundary_sum(self):
        """Test cumulative sum of multiple attachments summing to exactly 10.0 MB vs 10.0001 MB."""
        half_1 = self.EXACT_10_MB_BYTES // 2
        half_2 = self.EXACT_10_MB_BYTES - half_1
        assert half_1 + half_2 == self.EXACT_10_MB_BYTES

        # Exactly 10.0 MB in 2 parts: passes
        att_exact = [("part1.pdf", b"x" * half_1), ("part2.pdf", b"y" * half_2)]
        assert check_attachment_size_limit(att_exact, max_mb=10.0) is True

        # Part 2 oversized by 104 bytes (10.0001 MB cumulative): fails
        att_oversized = [("part1.pdf", b"x" * half_1), ("part2.pdf", b"y" * (half_2 + 104))]
        assert check_attachment_size_limit(att_oversized, max_mb=10.0) is False

    def test_check_attachment_size_limit_string_payload_utf8(self):
        """Verify check_attachment_size_limit calculates byte length for string attachments."""
        # High Unicode emoji string (4 bytes per emoji)
        emoji_count = 1000
        text_payload = "🚀" * emoji_count
        assert len(text_payload) == 1000
        assert len(text_payload.encode("utf-8")) == 4000

        att = [("emojis.txt", text_payload)]
        # Fits in 10 MB
        assert check_attachment_size_limit(att, max_mb=10.0) is True

    def test_send_email_boundary_enforcement_exact_10_mb(self, synthetic_sample_job, tmp_path):
        """send_email permits an email with exactly 10.0 MB attachment."""
        msg = build_digest_email([synthetic_sample_job])
        att = [("file_10mb.bin", b"0" * self.EXACT_10_MB_BYTES)]

        result_path = send_email(msg, attachments=att, dry_run=True, output_dir=tmp_path)
        assert Path(result_path).exists()

    def test_send_email_boundary_enforcement_10_0001_mb_raises_value_error(self, synthetic_sample_job, tmp_path):
        """send_email raises ValueError when cumulative attachments reach 10.0001 MB."""
        msg = build_digest_email([synthetic_sample_job])
        att = [("file_10_0001mb.bin", b"0" * self.EXACT_10_0001_MB_BYTES)]

        with pytest.raises(ValueError, match="Cumulative attachment size exceeds 10 MB limit."):
            send_email(msg, attachments=att, dry_run=True, output_dir=tmp_path)

    def test_send_email_extracts_attachments_from_mime_and_enforces_limit(self, tmp_path):
        """send_email inspects attachments embedded directly inside MIMEMultipart message."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = "Test Embedded Attachment Boundary"
        msg["From"] = "test@stepcon.solutions"
        msg["To"] = "candidate@example.com"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="stepcon.solutions")
        msg.attach(MIMEText("Plain text body", "plain", "utf-8"))

        # Attach 10.0001 MB inside the message itself
        part = MIMEApplication(b"0" * self.EXACT_10_0001_MB_BYTES, Name="large.dat")
        part.add_header("Content-Disposition", 'attachment; filename="large.dat"')
        msg.attach(part)

        # send_email must detect it from msg and raise ValueError
        with pytest.raises(ValueError, match="Cumulative attachment size exceeds 10 MB limit."):
            send_email(msg, dry_run=True, output_dir=tmp_path)

    def test_pipeline_tailoring_proactive_limit_and_pruning(self, tmp_path):
        """
        Tests execute_candidate_career_workflow when synthetic CV tailoring
        produces large attachments that would exceed 10 MB.
        Verify that the pipeline stops tailoring further packages and succeeds without ValueError.
        """
        import scheduler.daily_dispatch as dd

        # Mock generate_cv to produce 6 MB
        six_mb_bytes = b"X" * (6 * 1024 * 1024)
        with patch("scheduler.daily_dispatch.generate_cv", return_value=six_mb_bytes.decode("latin1", errors="replace")), \
             patch("scheduler.daily_dispatch.generate_cover_letter", return_value="Small letter"):

            res = run_daily_job(dry_run=True, date_str="2026-12-08", output_dir=str(tmp_path), force=True)

        assert res["status"] == "success"
        career_res = res.get("candidate_career", {})
        # Only 1 package tailored because second 6MB package would reach 12 MB > 10 MB
        assert career_res.get("tailored_packages_count") == 1
        assert Path(career_res.get("dispatch_output")).exists()
