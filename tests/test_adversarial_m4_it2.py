"""
Empirical Stress Test Harness & Adversarial Challenge Suite for Milestone 4 (Iteration 2).
Author: challenger_m4_2 (Teamwork Challenger Subagent)
Module: tests.test_adversarial_m4_it2

Focus Areas Mandated:
1. Concurrency and Duplicate Run Attacks:
   - Simultaneous daily runs on the same date (TOCTOU race conditions, double dispatch, file lock contention).
   - Forcing runs with --force flag (idempotency override, unique artifact generation, log integrity).
   - Recovery and resilience against corrupted dispatch logs.
2. MIME Email Compliance:
   - RFC 5322 zero-defects compliance via BytesParser (Date, From, To, Subject, Message-ID, MIME-Version).
   - Boundary strings uniqueness, correct multipart/mixed wrapping multipart/alternative, and terminator syntax.
   - Byte-exact payload fidelity across binary streams, null bytes, PDFs, and high-Unicode text upon decoding.
   - Cumulative attachment size limit enforcement.
3. Priority Enforcement Attacks:
   - Empirical proof that candidate career workflow finishes completely before Stepcon consultancy starts.
   - Error injection: proof that candidate workflow crash prevents Stepcon execution.
   - Artificial latency & 0-opportunity edge cases.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import email
import email.parser
import email.policy
from email.utils import parsedate_to_datetime
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


# ============================================================================
# Synthetic Test Fixtures
# ============================================================================

@pytest.fixture
def synthetic_candidate() -> Dict[str, Any]:
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
def synthetic_opportunity() -> Dict[str, Any]:
    return {
        "title": "Lead Cloud Infrastructure Engineer (EMEA / UTC+1)",
        "company": "Apex Global Cloud Solutions",
        "location": "Remote - Nigeria / EMEA Eligible",
        "url": "https://careers.apexcloud.example/jobs/infra-404",
        "description": (
            "Seeking a Cloud Infrastructure Engineer with deep Terraform, Kubernetes, "
            "AWS, and Azure experience. Role requires sustaining 99.9% uptime SLA and 99% RCA."
        ),
        "posted_date": "2026-11-06",
        "overall_score": 92.5,
        "breakdown": {
            "skills": 95.0,
            "title": 90.0,
            "metrics": 90.0,
            "mobility": 95.0,
            "certs": 90.0,
        },
        "matched_skills": ["Terraform", "Kubernetes", "AWS", "Azure"],
        "missing_skills": [],
        "target_role": "Cloud Infrastructure Engineer",
        "rationale": "Exceptional fit across cloud architecture and IaC.",
    }


# ============================================================================
# 1. Concurrency and Duplicate Run Attacks
# ============================================================================

class TestConcurrencyAndDuplicateRunAttacks:
    """Stress tests covering concurrent dispatches, duplicate dates, --force flag, and log corruption."""

    def test_sequential_duplicate_runs_idempotency_prevents_reexecution(self, tmp_path):
        """Verify that running sequentially on the same date dispatches once and skips on the second run."""
        test_date = "2026-11-15"
        out_dir = tmp_path / "seq_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        # First run: should succeed
        res1 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res1.get("status") == "success"

        # Count .eml files produced
        eml_files_after_1 = list(out_dir.rglob("*.eml"))
        assert len(eml_files_after_1) >= 1

        # Second run: should be skipped
        res2 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res2.get("status") == "skipped"
        assert f"Already dispatched on {test_date}" in res2.get("reason", "")

        # Verify no additional .eml files were created
        eml_files_after_2 = list(out_dir.rglob("*.eml"))
        assert len(eml_files_after_2) == len(eml_files_after_1)

    def test_force_flag_bypasses_idempotency_and_creates_distinct_eml(self, tmp_path):
        """Verify that --force allows repeated execution on the same date without overwriting existing files."""
        test_date = "2026-11-16"
        out_dir = tmp_path / "force_test"
        out_dir.mkdir(parents=True, exist_ok=True)

        res1 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res1.get("status") == "success"

        # Force run 2
        time.sleep(0.01)  # small pause to guarantee different millisecond timestamp
        res2 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=True)
        assert res2.get("status") == "success"

        # Force run 3
        time.sleep(0.01)
        res3 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=True)
        assert res3.get("status") == "success"

        # Verify distinct .eml files exist
        eml_files = list(out_dir.rglob("*.eml"))
        assert len(eml_files) >= 3

        # Subsequent run without force must still be skipped
        res4 = run_daily_job(dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
        assert res4.get("status") == "skipped"

        # Inspect dispatch_log.json
        log_file = out_dir / "dispatch_log.json"
        assert log_file.exists()
        with open(log_file, "r", encoding="utf-8") as f:
            log_entries = json.load(f)
        assert len(log_entries) >= 3

    def test_simultaneous_concurrent_runs_race_condition_behavior(self, tmp_path):
        """
        Adversarially probe time-of-check to time-of-use (TOCTOU) race condition.
        When multiple threads execute simultaneously on an un-dispatched date,
        document how many pass the idempotency check and verify dispatch_log.json resilience.
        """
        test_date = "2026-11-17"
        out_dir = tmp_path / "concurrent_test"
        out_dir.mkdir(parents=True, exist_ok=True)
        workers = 6

        # Use ThreadPoolExecutor to trigger concurrent dispatches
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(run_daily_job, dry_run=True, date_str=test_date, output_dir=str(out_dir), force=False)
                for _ in range(workers)
            ]
        statuses = []
        errors = []
        for f in futures:
            try:
                r = f.result()
                statuses.append(r.get("status"))
            except Exception as e:
                errors.append(e)

        # Empirical proof of concurrency vulnerability:
        # 1. Multiple workers passed idempotency check before the first completed (TOCTOU).
        # 2. On Windows, concurrent writes to dispatch_log.json produce PermissionError or JSONDecodeError.
        success_count = statuses.count("success")
        assert success_count >= 1, "At least one worker must succeed."
        has_concurrency_anomaly = (success_count > 1) or (len(errors) > 0)
        assert has_concurrency_anomaly is True, "Expected concurrency race condition (TOCTOU duplicate run or file lock contention)."

        # Check log file integrity after concurrent writes
        log_file = out_dir / "dispatch_log.json"
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                assert isinstance(entries, list)
            except json.decoder.JSONDecodeError:
                # Documented empirical vulnerability: unsynchronized concurrent writes produce JSONDecodeError
                pass

    def test_corrupted_dispatch_log_recovery(self, tmp_path):
        """Verify that check_daily_idempotency and record_dispatch gracefully recover if log is corrupted."""
        log_file = tmp_path / "dispatch_log.json"
        # Write corrupted garbage
        log_file.write_text("CORRUPTED_JSON_DATA{invalid", encoding="utf-8")

        # Idempotency check should not crash; it logs warning and returns True (fail-safe to dispatch)
        safe = check_daily_idempotency("2026-11-18", log_file)
        assert safe is True

        # Recording a dispatch should overwrite or recover without crashing
        record_dispatch("2026-11-18", log_file, metadata={"test": True})
        assert log_file.exists()
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[-1]["date"] == "2026-11-18"


# ============================================================================
# 2. MIME Email Compliance & Byte-Exact Fidelity
# ============================================================================

class TestMIMEComplianceAndByteExactness:
    """Rigorous RFC 5322 compliance and binary attachment fidelity verification."""

    def test_rfc5322_zero_defects_and_mandatory_headers(self, synthetic_opportunity, synthetic_candidate, tmp_path):
        """Validate RFC 5322 compliance using Python's standard BytesParser with default policy."""
        msg = build_digest_email(
            [synthetic_opportunity],
            candidate=synthetic_candidate,
            date_str="2026-11-19",
        )
        eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path))

        with open(eml_path, "rb") as f:
            parsed = email.parser.BytesParser(policy=email.policy.default).parse(f)

        # RFC 5322 zero-defect check
        assert len(parsed.defects) == 0, f"MIME syntax defects found: {parsed.defects}"

        # Mandatory RFC 5322 headers
        assert parsed["From"] is not None
        assert parsed["To"] is not None
        assert parsed["Subject"] is not None
        assert parsed["Date"] is not None
        assert parsed["Message-ID"] is not None
        assert parsed["MIME-Version"] is not None

        # Validate Message-ID syntax: <...+@...+>
        msg_id = str(parsed["Message-ID"]).strip()
        assert msg_id.startswith("<") and msg_id.endswith(">")
        assert "@" in msg_id

        # Validate Date parsing conforms to RFC 2822 / RFC 5322
        dt = parsedate_to_datetime(str(parsed["Date"]))
        assert dt is not None
        assert dt.tzinfo is not None

    def test_multipart_nesting_and_boundary_uniqueness(self, synthetic_opportunity, synthetic_candidate):
        """Verify multipart/mixed root wrapping multipart/alternative and unique boundary strings."""
        attachments = [("sample.txt", b"Test content")]
        msg = build_digest_email(
            [synthetic_opportunity],
            candidate=synthetic_candidate,
            attachments=attachments,
        )
        raw_bytes = msg.as_bytes()
        raw_text = raw_bytes.decode("utf-8", errors="replace")

        # Top-level Content-Type must be multipart/mixed
        assert msg.get_content_type() == "multipart/mixed"
        mixed_boundary = msg.get_boundary()
        assert mixed_boundary is not None

        # Subpart 0 must be multipart/alternative
        alt_part = msg.get_payload(0)
        assert alt_part.get_content_type() == "multipart/alternative"
        alt_boundary = alt_part.get_boundary()
        assert alt_boundary is not None

        # Boundaries must be distinct
        assert mixed_boundary != alt_boundary

        # Verify boundaries appear with '--' prefix and terminator '--...--'
        assert f"--{mixed_boundary}" in raw_text
        assert f"--{mixed_boundary}--\n" in raw_text or f"--{mixed_boundary}--\r\n" in raw_text
        assert f"--{alt_boundary}" in raw_text
        assert f"--{alt_boundary}--\n" in raw_text or f"--{alt_boundary}--\r\n" in raw_text

        # Verify alternative subparts
        alt_subparts = alt_part.get_payload()
        assert len(alt_subparts) == 2
        assert alt_subparts[0].get_content_type() == "text/plain"
        assert alt_subparts[1].get_content_type() == "text/html"

    def test_attachment_payload_byte_exactness_binary_and_pdf(self, synthetic_opportunity):
        """
        Adversarially verify that attachment payloads are byte-for-byte exact upon decoding.
        Tests:
        1. Arbitrary binary stream with null bytes (\x00) and byte 0xFF.
        2. Synthetic PDF header & binary structure.
        3. High-Unicode UTF-8 text with emojis and ligatures.
        """
        # 1. Raw binary stream (50 KB)
        raw_binary = bytes(i % 256 for i in range(50000))

        # 2. Synthetic PDF with null and high bytes
        pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Length 12 >>\nstream\n\x00\x01\x02\xff\xfe\xfd\nendstream\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 >>\nstartxref\n99\n%%EOF"

        # 3. Unicode text with ligatures
        unicode_text = "John Victor Aniekwe — Cloud Architect & Platform Engineer 🚀\nSLA: 99.9% | RCA: 99%\nLigatures: ﬀ, ﬁ, ﬂ, ﬃ, ﬄ\n"
        unicode_bytes = unicode_text.encode("utf-8")

        attachments = [
            ("binary_payload.bin", raw_binary),
            ("John_Aniekwe_DevOps_CV.pdf", pdf_bytes),
            ("John_Aniekwe_Cover_Letter.txt", unicode_bytes),
        ]

        msg = build_digest_email([synthetic_opportunity], attachments=attachments)
        raw_eml = msg.as_bytes()

        # Parse message back from serialized bytes
        parsed = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw_eml)
        assert len(parsed.defects) == 0

        # Extract and verify all attachments
        found_attachments: Dict[str, bytes] = {}
        for part in parsed.iter_attachments():
            fname = part.get_filename()
            decoded_payload = part.get_payload(decode=True)
            found_attachments[fname] = decoded_payload

        # Byte-exact assertion
        assert "binary_payload.bin" in found_attachments
        assert found_attachments["binary_payload.bin"] == raw_binary

        assert "John_Aniekwe_DevOps_CV.pdf" in found_attachments
        assert found_attachments["John_Aniekwe_DevOps_CV.pdf"] == pdf_bytes

        assert "John_Aniekwe_Cover_Letter.txt" in found_attachments
        assert found_attachments["John_Aniekwe_Cover_Letter.txt"] == unicode_bytes

    def test_attachment_size_limit_guardrail(self):
        """Verify strict cumulative attachment size limit checking (default 10 MB threshold)."""
        # 1 MB + 2 MB = 3 MB (within 10 MB)
        att_valid = [
            ("file1.pdf", b"0" * (1 * 1024 * 1024)),
            ("file2.pdf", b"0" * (2 * 1024 * 1024)),
        ]
        assert check_attachment_size_limit(att_valid, max_mb=10.0) is True

        # Exactly 10 MB
        att_exact = [("exact.pdf", b"0" * (10 * 1024 * 1024))]
        assert check_attachment_size_limit(att_exact, max_mb=10.0) is True

        # 10 MB + 1 byte (oversized)
        att_over = [("over.pdf", b"0" * (10 * 1024 * 1024 + 1))]
        assert check_attachment_size_limit(att_over, max_mb=10.0) is False

        # Cumulative overage (3 x 4 MB = 12 MB)
        att_cum_over = [
            ("f1.pdf", b"0" * (4 * 1024 * 1024)),
            ("f2.pdf", b"0" * (4 * 1024 * 1024)),
            ("f3.pdf", b"0" * (4 * 1024 * 1024)),
        ]
        assert check_attachment_size_limit(att_cum_over, max_mb=10.0) is False

        # Empty attachments list
        assert check_attachment_size_limit([]) is True


# ============================================================================
# 3. Priority Enforcement Attacks
# ============================================================================

class TestPriorityEnforcementAttacks:
    """
    Adversarially proves that candidate career workflow finishes completely
    before Stepcon consultancy workflow is ever invoked under all execution conditions.
    """

    def test_strict_temporal_sequencing_candidate_finishes_before_stepcon_starts(self, tmp_path):
        """Empirically trace start and completion timestamps of both workflows."""
        events: List[Tuple[str, str, float]] = []

        import scheduler.daily_dispatch as dd
        orig_career = dd.execute_candidate_career_workflow
        orig_stepcon = dd.execute_stepcon_consultancy_workflow

        def spy_career(*args, **kwargs):
            events.append(("candidate_career_workflow", "start", time.perf_counter()))
            res = orig_career(*args, **kwargs)
            events.append(("candidate_career_workflow", "finish", time.perf_counter()))
            return res

        def spy_stepcon(*args, **kwargs):
            events.append(("stepcon_consultancy_workflow", "start", time.perf_counter()))
            res = orig_stepcon(*args, **kwargs)
            events.append(("stepcon_consultancy_workflow", "finish", time.perf_counter()))
            return res

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=spy_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=spy_stepcon):

            result = execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert result.get("status") == "success"
        assert len(events) == 4

        # Verify exact sequence: candidate_start -> candidate_finish -> stepcon_start -> stepcon_finish
        assert events[0][0] == "candidate_career_workflow" and events[0][1] == "start"
        assert events[1][0] == "candidate_career_workflow" and events[1][1] == "finish"
        assert events[2][0] == "stepcon_consultancy_workflow" and events[2][1] == "start"
        assert events[3][0] == "stepcon_consultancy_workflow" and events[3][1] == "finish"

        # Temporal constraint: candidate finish time <= stepcon start time
        candidate_finish_time = events[1][2]
        stepcon_start_time = events[2][2]
        assert candidate_finish_time <= stepcon_start_time

    def test_candidate_workflow_exception_prevents_stepcon_execution(self, tmp_path):
        """
        Adversarially inject an exception into candidate workflow.
        Prove that Stepcon consultancy is NEVER invoked when candidate workflow fails.
        """
        stepcon_called = []

        def failing_career(*args, **kwargs):
            raise RuntimeError("CRITICAL_INJECTED_FAILURE: Candidate database corrupted.")

        def spy_stepcon(*args, **kwargs):
            stepcon_called.append(True)
            return {"status": "success"}

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=failing_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=spy_stepcon):

            with pytest.raises(RuntimeError, match="CRITICAL_INJECTED_FAILURE"):
                execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        # Stepcon must NOT have been called
        assert len(stepcon_called) == 0, "Security violation: Stepcon ran despite candidate workflow failure!"

    def test_artificial_latency_candidate_workflow_never_preempted(self, tmp_path):
        """Prove that even when candidate workflow suffers significant latency, Stepcon does not start early."""
        stepcon_started = []

        import scheduler.daily_dispatch as dd
        orig_career = dd.execute_candidate_career_workflow

        def slow_career(*args, **kwargs):
            time.sleep(0.2)  # Inject 200ms latency
            assert len(stepcon_started) == 0, "Preemption violation: Stepcon started while candidate was running!"
            return orig_career(*args, **kwargs)

        def spy_stepcon(*args, **kwargs):
            stepcon_started.append(time.perf_counter())
            return {"status": "success", "workflow": "stepcon_consultancy_workflow"}

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=slow_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=spy_stepcon):

            res = execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert res.get("status") == "success"
        assert len(stepcon_started) == 1

    def test_empty_candidate_opportunities_still_preserves_priority(self, tmp_path):
        """When candidate discovery yields 0 opportunities, candidate digest completes before Stepcon."""
        order_list = []

        def empty_career(*args, **kwargs):
            order_list.append("candidate_empty")
            return {"status": "success", "opportunities_count": 0}

        def stepcon_run(*args, **kwargs):
            order_list.append("stepcon")
            return {"status": "success", "tenders_matched": 0}

        with patch("scheduler.daily_dispatch.execute_candidate_career_workflow", side_effect=empty_career), \
             patch("scheduler.daily_dispatch.execute_stepcon_consultancy_workflow", side_effect=stepcon_run):

            res = execute_combined_daily_run(dry_run=True, output_dir=tmp_path)

        assert order_list == ["candidate_empty", "stepcon"]
        assert res.get("status") == "success"


# ============================================================================
# 4. Digest Content and Executive Metric Integrity
# ============================================================================

class TestDigestContentAndExecutiveIntegrity:
    """Verifies that executive credentials and zero-stylesheet constraints are strictly met."""

    def test_digest_contains_both_99_9_and_99_metrics_in_html_and_text(self, synthetic_opportunity):
        """Assert both verified enterprise metrics appear in HTML and Plain Text formats."""
        html_out = format_digest_html([synthetic_opportunity])
        text_out = format_digest_text([synthetic_opportunity])

        assert "99.9%" in html_out
        assert "99%" in html_out
        assert "99.9%" in text_out
        assert "99%" in text_out

    def test_digest_strict_inline_styles_zero_link_tags(self, synthetic_opportunity):
        """Verify absolute absence of external stylesheets (<link rel='stylesheet'>) in HTML output."""
        html_out = format_digest_html([synthetic_opportunity])
        assert "<link" not in html_out.lower()
        assert "@import" not in html_out.lower()

    def test_cron_syntax_adversarial_validation(self):
        """Verify 5-field cron parser against adversarial valid and invalid expressions."""
        # Valid standard 5-field expressions
        assert validate_cron_expression("0 7 * * *") is True
        assert validate_cron_expression("0 8 * * 1-5") is True
        assert validate_cron_expression("*/15 * * * *") is True
        assert validate_cron_expression("0,30 6-9 * * *") is True

        # Invalid expressions
        assert validate_cron_expression("0 7 * *") is False          # 4 fields
        assert validate_cron_expression("0 7 * * * *") is False        # 6 fields
        assert validate_cron_expression("0 7 * * * * *") is False      # 7 fields
        assert validate_cron_expression("") is False                   # Empty
        assert validate_cron_expression("invalid_cron_string") is False
        assert validate_cron_expression(None) is False
