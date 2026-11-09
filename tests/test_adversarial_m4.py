"""
Adversarial Stress Test Suite for Milestone 4 (Features F11 & F12).
Author: challenger_m4_1 (Empirical Challenger Subagent)
Scope:
- Boundary & Extreme Inputs (0 opportunities, None input, 150+ opportunities, malformed objects)
- Malicious HTML/Script Injections & XSS in job fields (attribute breakout & unescaped tags)
- Non-ASCII, Unicode, Emojis, and International Encodings in MIME
- Attachment Size Limit Guardrails & Extreme Payloads (>10MB)
- Idempotency File Corruption, Type Mismatches, and Lock Stress
- Crontab Syntax, Step by Zero, and Out-of-Range Field Edge Cases
- Hermetic Dry-Run Verification (Strict Zero Network/Socket Guarantee)
- Corrupted & Malformed Environment Variable Settings
"""

from __future__ import annotations

import email
import html as html_lib
import json
import os
import re
import socket
import sys
import urllib.request
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings, get_settings, parse_bool, parse_port
from dispatch.digest import (
    build_digest_email,
    format_digest_html,
    format_digest_text,
    _extract_job_field,
    _score_and_sort_opportunities,
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
    record_dispatch,
    run_daily_job,
    validate_cron_expression,
)
from ingestion.parser import load_profile


# ============================================================================
# 1. Boundary & Extreme Inputs: Volume & Malformed Objects
# ============================================================================

class TestAdversarialVolumeAndMalformed:
    """Stress tests boundary opportunity counts and malformed records."""

    def test_zero_opportunities_graceful_handling(self):
        """0 opportunities must produce clean, non-crashing output."""
        html_out = format_digest_html([])
        text_out = format_digest_text([])
        msg = build_digest_email([])

        assert "No Opportunities Discovered Today" in html_out or "No external postings" in html_out
        assert "No opportunities matched" in text_out
        assert msg is not None
        assert msg.is_multipart()
        assert "Daily Career" in str(msg.get("Subject", ""))

    def test_none_opportunities_in_build_digest_email(self):
        """None passed to build_digest_email is guarded by opp_list = list(opportunities or [])."""
        msg = build_digest_email(None)
        assert msg is not None
        assert "Daily Career" in str(msg.get("Subject", ""))

    def test_none_opportunities_in_format_digest_functions(self):
        """
        format_digest_html(None) and format_digest_text(None) must normalize None to []
        and return graceful empty state digests without raising TypeError.
        """
        html_out = format_digest_html(None)
        text_out = format_digest_text(None)
        assert "No Opportunities Discovered Today" in html_out or "No external postings" in html_out
        assert "No opportunities matched" in text_out

    def test_150_opportunities_large_scale_stress(self):
        """150+ opportunities must format cleanly without OOM or sorting corruption."""
        large_opps = []
        for i in range(150):
            large_opps.append({
                "id": f"opp-stress-{i:03d}",
                "title": f"DevOps Platform Engineer #{i}",
                "company": f"Enterprise Cloud Cluster {i}",
                "location": "Remote - EMEA (UTC+1)",
                "url": f"https://careers.cloudcorp.example/jobs/{i}",
                "description": (
                    f"Job #{i}: Enterprise Kubernetes, Terraform, AWS, Azure, CI/CD automation. "
                    "Maintain 99.9% uptime SLA across distributed clusters."
                ),
                "overall_score": float(50 + (i % 50)),
                "breakdown": {
                    "skills": 80.0,
                    "title": 75.0,
                    "metrics": 70.0,
                    "mobility": 85.0,
                    "certs": 70.0,
                },
                "matched_skills": ["Kubernetes", "Terraform", "AWS", "Azure"],
                "missing_skills": ["Go", "GCP"],
                "target_role": "DevOps Engineer",
                "rationale": f"Candidate aligns well with requirement {i}.",
            })

        html_out = format_digest_html(large_opps)
        text_out = format_digest_text(large_opps)
        msg = build_digest_email(large_opps)

        # Confirm all 150 rendered in table rows
        assert html_out.count("<tr>") >= 151  # 1 header + 150 rows
        assert "150 Opportunities Evaluated" in html_out
        assert "Evaluated Opportunities: 150" in text_out
        assert msg.is_multipart()

        # Check descending sort invariant: top score in the table must be 99.0%
        table_scores = [float(m.group(1)) for m in re.finditer(r'<td[^>]*><span[^>]*>(\d+\.\d+)%</span></td>', html_out)]
        assert len(table_scores) == 150
        assert table_scores[0] == 99.0
        assert table_scores == sorted(table_scores, reverse=True)

    def test_malformed_opportunity_objects(self):
        """Opportunities with missing fields, None values, or unexpected types."""
        malformed = [
            None,  # None element
            {},    # completely empty dict
            {"title": None, "company": None, "url": None},
            {"title": 12345, "company": False, "overall_score": 75.0, "breakdown": {"skills": 70.0}},
            {"description": "Just description without title or company"},
        ]
        html_out = format_digest_html(malformed)
        text_out = format_digest_text(malformed)
        msg = build_digest_email(malformed)

        assert html_out is not None
        assert text_out is not None
        assert msg is not None


# ============================================================================
# 2. Malicious HTML Injections & XSS Vulnerability Verification
# ============================================================================

class TestAdversarialHTMLInjection:
    """Verifies HTML sanitization against XSS and attribute breakout attacks."""

    def test_vulnerability_unescaped_title_in_card_data_attribute(self):
        """
        Verifies that line 252 escapes title in data-opportunity-title attribute,
        preventing attribute breakout and XSS injections.
        """
        malicious_title = 'DevOps" onmouseover="alert(\'XSS\')" data-injected="'
        opp = {
            "title": malicious_title,
            "company": "BreakoutCorp",
            "location": "Remote",
            "url": "https://example.com/job",
            "overall_score": 90.0,
            "breakdown": {"skills": 90.0, "title": 90.0, "metrics": 90.0, "mobility": 90.0, "certs": 90.0},
        }

        html_out = format_digest_html([opp])

        # Verify that attribute breakout is strictly prevented
        attribute_breakout_present = 'data-opportunity-title="DevOps" onmouseover="alert(\'XSS\')"' in html_out
        assert not attribute_breakout_present, "Attribute breakout must be prevented"
        assert 'data-opportunity-title="DevOps&quot;' in html_out

    def test_script_tag_leakage_in_card_attribute(self):
        """
        Verifies that <script> tags within titles are safely escaped in card attributes.
        """
        malicious_title = 'DevOps <script>alert(1)</script>'
        opp = {
            "title": malicious_title,
            "company": "TestCorp",
            "location": "Remote",
            "url": "https://example.com/job",
            "overall_score": 85.0,
            "breakdown": {"skills": 85.0, "title": 85.0, "metrics": 85.0, "mobility": 85.0, "certs": 85.0},
        }

        html_out = format_digest_html([opp])
        raw_script_in_card = 'data-opportunity-title="DevOps <script>alert(1)</script>"' in html_out
        assert not raw_script_in_card, "Raw script tags must not leak into HTML attributes"
        assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html_out

    def test_table_summary_properly_escapes_title(self):
        """Verifies that line 232 (the summary table) DOES properly escape the title."""
        malicious_title = 'DevOps <script>alert(1)</script>'
        opp = {
            "title": malicious_title,
            "company": "TestCorp",
            "location": "Remote",
            "url": "https://example.com/job",
            "overall_score": 85.0,
            "breakdown": {"skills": 85.0, "title": 85.0, "metrics": 85.0, "mobility": 85.0, "certs": 85.0},
        }

        html_out = format_digest_html([opp])
        # In the summary table: <strong>{html.escape(str(title))}</strong>
        assert "DevOps &lt;script&gt;alert(1)&lt;/script&gt;" in html_out


# ============================================================================
# 3. Unicode, Emojis, and International Character Encoding Stress
# ============================================================================

class TestAdversarialUnicodeAndEmojis:
    """Verifies multi-part MIME RFC compliance under non-ASCII and emoji stress."""

    def test_emoji_in_title_and_subject(self):
        """Tests emojis in job title, company name, and subject header."""
        emoji_title = "🚀 Senior DevOps & SRE 🔥 [100% Remote 💻]"
        emoji_company = "Cloud Corp 🌍 ✨"
        emoji_subj = "Daily Career Digest: 🎯 12 New High-Match Roles 🚀"

        opp = {
            "title": emoji_title,
            "company": emoji_company,
            "location": "Lagos, Nigeria 🇳🇬",
            "url": "https://example.com/emoji-job",
            "description": "Manage Kubernetes clusters ☸️ with Terraform 🏗️.",
            "overall_score": 92.0,
            "breakdown": {"skills": 90.0, "title": 95.0, "metrics": 90.0, "mobility": 95.0, "certs": 90.0},
        }

        msg = build_digest_email([opp], subject=emoji_subj)
        msg_bytes = msg.as_bytes()
        assert len(msg_bytes) > 0

        # Verify parsing back from bytes via RFC parser
        parsed = email.message_from_bytes(msg_bytes)
        assert parsed is not None

        # Verify subject header decoding
        header_val, header_enc = email.header.decode_header(parsed["Subject"])[0]
        if isinstance(header_val, bytes):
            decoded_subj = header_val.decode(header_enc or "utf-8")
        else:
            decoded_subj = header_val
        assert "🎯" in decoded_subj

    def test_multilingual_non_ascii_roundtrip(self):
        """Tests Yoruba, Arabic, Chinese, Cyrillic, and German diacritics roundtrip."""
        international_title = "Olùdarí Ẹ̀rọ Ìṣirò / 云计算工程师 / مهندس سحابي / Инженер"
        opp = {
            "title": international_title,
            "company": "Börse & Société Générale Über",
            "location": "München, Deutschland & Lagos, Nàìjíríà",
            "url": "https://example.com/intl-job",
            "overall_score": 88.0,
            "breakdown": {"skills": 88.0, "title": 88.0, "metrics": 88.0, "mobility": 88.0, "certs": 88.0},
        }

        msg = build_digest_email([opp])
        msg_bytes = msg.as_bytes()

        # Parse back and decode base64 MIME payload
        parsed = email.message_from_bytes(msg_bytes)
        # Walk subparts to find plain text and HTML
        text_payload = ""
        html_payload = ""
        for part in parsed.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                text_payload = part.get_payload(decode=True).decode("utf-8")
            elif ctype == "text/html":
                html_payload = part.get_payload(decode=True).decode("utf-8")

        assert "Börse" in text_payload
        assert "Börse" in html_payload
        assert "Olùdarí Ẹ̀rọ Ìṣirò" in text_payload


# ============================================================================
# 4. Attachment Size Limit Guardrails & Extreme Payloads
# ============================================================================

class TestAdversarialAttachments:
    """Verifies attachment threshold detection and integration gaps."""

    def test_attachment_exact_boundary(self):
        """Tests exact 10 MB limit and 10 MB + 1 byte."""
        ten_mb = 10 * 1024 * 1024
        # Exactly 10 MB
        att_exact = [("exact_10mb.dat", b"x" * ten_mb)]
        assert check_attachment_size_limit(att_exact, max_mb=10.0) is True

        # 10 MB + 1 byte
        att_over = [("over_10mb.dat", b"x" * (ten_mb + 1))]
        assert check_attachment_size_limit(att_over, max_mb=10.0) is False

    def test_cumulative_attachment_sizes(self):
        """Tests cumulative sum across multiple attachments."""
        three_mb = 3 * 1024 * 1024
        att_multi = [
            ("doc1.pdf", b"a" * three_mb),
            ("doc2.pdf", b"b" * three_mb),
            ("doc3.pdf", b"c" * three_mb),
            ("doc4.pdf", b"d" * (2 * 1024 * 1024)),  # total = 11 MB
        ]
        assert check_attachment_size_limit(att_multi, max_mb=10.0) is False

    def test_send_email_enforces_attachment_limit(self, tmp_path):
        """
        Verifies that send_email() enforces the cumulative attachment size limit (10 MB)
        and raises ValueError when presented with oversized attachments.
        """
        msg = build_digest_email([], attachments=[("huge.bin", b"0" * (12 * 1024 * 1024))])
        with pytest.raises(ValueError) as exc:
            send_email(msg, dry_run=True, output_dir=str(tmp_path))
        assert "attachment" in str(exc.value).lower() and "limit" in str(exc.value).lower()


# ============================================================================
# 5. Idempotency File Corruption & Error Recovery
# ============================================================================

class TestAdversarialIdempotencyCorruption:
    """Tests resiliency against malformed, corrupted, or locked dispatch_log.json."""

    def test_corrupted_json_content(self, tmp_path):
        """Corrupted JSON in dispatch_log.json must not crash idempotency check."""
        log_file = tmp_path / "dispatch_log.json"
        log_file.write_text("{'invalid_json': true, not valid json...", encoding="utf-8")

        safe = check_daily_idempotency("2026-11-07", log_file)
        assert safe is True

    def test_record_dispatch_recovers_from_corrupted_json(self, tmp_path):
        """Recording dispatch on top of a corrupted file recovers and writes valid JSON."""
        log_file = tmp_path / "dispatch_log.json"
        log_file.write_text("CORRUPTED GIBBERISH DATA", encoding="utf-8")

        record_dispatch("2026-11-07", log_file, metadata={"test": True})

        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["date"] == "2026-11-07"

    def test_empty_zero_byte_file(self, tmp_path):
        """Tests 0-byte dispatch_log.json."""
        log_file = tmp_path / "dispatch_log.json"
        log_file.touch()

        assert check_daily_idempotency("2026-11-07", log_file) is True


# ============================================================================
# 6. Crontab Syntax & Edge Cases
# ============================================================================

class TestAdversarialCronValidation:
    """Tests crontab validator against extreme, invalid, and out-of-range notations."""

    def test_valid_standard_and_step_expressions(self):
        """Tests standard 5-field cron notations."""
        assert validate_cron_expression("0 7 * * *") is True
        assert validate_cron_expression("*/15 * * * *") is True
        assert validate_cron_expression("0,30 8-17 * * 1-5") is True

    def test_invalid_field_counts(self):
        """Tests strings with 0, 1, 2, 3, 4, 6, and 7 fields."""
        assert validate_cron_expression("") is False
        assert validate_cron_expression("0 7") is False
        assert validate_cron_expression("0 7 * *") is False       # 4 fields
        assert validate_cron_expression("0 0 7 * * *") is False   # 6 fields
        assert validate_cron_expression("0 0 7 * * * *") is False # 7 fields
        assert validate_cron_expression(None) is False
        assert validate_cron_expression(12345) is False

    def test_crontab_range_and_step_zero_rejection(self):
        """
        Verifies that validate_cron_expression rejects step zero, out-of-range fields,
        and inverted ranges.
        """
        assert validate_cron_expression("*/0 * * * *") is False
        assert validate_cron_expression("99 99 99 99 99") is False
        assert validate_cron_expression("50-10 * * * *") is False


# ============================================================================
# 7. Hermetic Dry-Run Verification (Strict Zero Network/Socket Guarantee)
# ============================================================================

class TestAdversarialDryRunNetworkIsolation:
    """Enforces that dry-run mode strictly NEVER touches sockets or network."""

    def test_send_email_dry_run_zero_socket_activity(self, tmp_path):
        """send_email with dry_run=True must never open sockets."""
        opp = {
            "title": "Cloud Engineer",
            "company": "Network Isolation Corp",
            "location": "Remote",
            "url": "https://example.com/job",
            "overall_score": 85.0,
        }
        msg = build_digest_email([opp])

        with patch("socket.socket") as mock_sock, \
             patch("smtplib.SMTP") as mock_smtp, \
             patch("urllib.request.urlopen") as mock_urlopen:

            eml_path = send_email(msg, dry_run=True, output_dir=str(tmp_path))

            assert os.path.exists(eml_path)
            mock_sock.assert_not_called()
            mock_smtp.assert_not_called()
            mock_urlopen.assert_not_called()

    def test_run_daily_job_dry_run_zero_socket_activity(self, tmp_path):
        """Entire daily dispatch job under dry_run=True must not make outbound connections."""
        with patch("socket.socket") as mock_sock, \
             patch("smtplib.SMTP") as mock_smtp, \
             patch("urllib.request.urlopen") as mock_urlopen:

            result = run_daily_job(
                dry_run=True,
                date_str="2026-11-07",
                output_dir=str(tmp_path),
                force=True,
            )

            assert result.get("status") == "success"
            mock_sock.assert_not_called()
            mock_smtp.assert_not_called()
            mock_urlopen.assert_not_called()


# ============================================================================
# 8. Corrupted & Extreme Environment Variables
# ============================================================================

class TestAdversarialEnvironmentVariables:
    """Tests system stability when environment variables are corrupted."""

    def test_corrupted_smtp_port(self):
        """Non-numeric SMTP_PORT should fall back to safe default (587)."""
        assert parse_port("invalid_port_string", default=587) == 587
        assert parse_port("-10", default=587) == 587
        assert parse_port("999999", default=587) == 587

    def test_boolean_env_string_variations(self):
        """Tests parsing of irregular boolean environment variables."""
        assert parse_bool("true") is True
        assert parse_bool("True") is True
        assert parse_bool("1") is True
        assert parse_bool("yes") is True
        assert parse_bool("on") is True

        assert parse_bool("false") is False
        assert parse_bool("0") is False
        assert parse_bool("no") is False
        assert parse_bool("off") is False
        assert parse_bool("") is False
