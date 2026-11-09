"""
Empirical Stress Test Harness & Adversarial Challenge Suite for Milestone 3 (F08 & F10).
File: tests/test_empirical_m3_stress.py

Adversarial testing targeting:
1. Malformed raw items with missing, null, or extreme values passed to normalize_opportunities.
2. Massive lists passed to deduplicate_opportunities with identical URLs or titles across subtle whitespace/case differences.
3. fetch_opportunities with simulate_timeout=True and unknown/invalid sources.
4. Closed DOM phrase detection against obfuscated, nested, or encoded HTML.
5. Unparseable date strings in is_fresh_date (relative strings, future dates, epoch dates, extremes).
6. SHA-256 fingerprint generation with complex Unicode characters, emojis, and whitespace.
7. Redirect depth checking with edge-case hops.
8. verify_job_link edge cases, mock status codes, and invalid URL handling.
"""

from __future__ import annotations

import datetime
import hashlib
import time
from typing import Any, Dict, List

import pytest

from discovery.models import JobOpportunity, JobQueryParams, Opportunity
from discovery.sources import (
    CANONICAL_TARGET_ROLES,
    AdapterRegistry,
    BaseSourceAdapter,
    JobicyAdapter,
    RemoteOKAdapter,
    SyntheticSourceAdapter,
    WeWorkRemotelyAdapter,
    deduplicate_opportunities,
    fetch_opportunities,
    get_synthetic_opportunities,
    normalize_opportunities,
    registry,
    search_opportunities,
)
from discovery.verifier import (
    BASELINE_DATE_2026,
    CLOSED_PHRASES,
    MAX_REDIRECT_HOPS,
    MAX_STALE_DAYS,
    VerificationResult,
    check_redirect_depth,
    detect_closed_phrase,
    generate_fingerprint,
    is_fresh_date,
    verify_job_link,
    verify_opportunities,
    verify_url_status,
)


# ============================================================================
# 1. Adversarial Tests: normalize_opportunities
# ============================================================================

class TestNormalizeOpportunitiesAdversarial:
    """Stress tests and boundary challenges for normalize_opportunities."""

    def test_non_list_inputs(self):
        """Pass non-list, None, or empty containers."""
        assert normalize_opportunities(None) == []
        assert normalize_opportunities([]) == []
        assert normalize_opportunities("not a list") == []
        assert normalize_opportunities(12345) == []
        assert normalize_opportunities({"title": "X", "company": "Y", "url": "Z"}) == []

    def test_primitives_in_list(self):
        """Pass primitive types and non-dict/non-JobOpportunity items."""
        raw = [None, 123, 3.14159, True, False, "string", [1, 2, 3], (4, 5), set()]
        assert normalize_opportunities(raw) == []

    def test_missing_required_keys(self):
        """Items missing title, company, or url must be discarded."""
        cases = [
            {},
            {"title": "DevOps"},
            {"company": "Acme"},
            {"url": "https://example.com"},
            {"title": "DevOps", "company": "Acme"},  # missing url
            {"title": "DevOps", "url": "https://example.com"},  # missing company
            {"company": "Acme", "url": "https://example.com"},  # missing title
            {"title": "", "company": "Acme", "url": "https://example.com"},  # empty title
            {"title": "  ", "company": "Acme", "url": "https://example.com"},  # blank title
            {"title": "DevOps", "company": "   ", "url": "https://example.com"},  # blank company
            {"title": "DevOps", "company": "Acme", "url": "   "},  # blank url
        ]
        result = normalize_opportunities(cases)
        assert len(result) == 0

    def test_empirical_finding_null_values_coerced_to_string_none(self):
        """
        EMPIRICAL OBSERVATION / DEFECT PROOF:
        When an external API returns fields with explicit None values
        (e.g. {'title': None, 'company': None, 'url': None}),
        item.get('title', '') returns None because the key exists in dict.
        str(None) converts it to the literal string 'None'.
        Consequently, normalize_opportunities accepts the item as valid!
        """
        raw = [{"title": None, "company": None, "url": None}]
        result = normalize_opportunities(raw)
        # Demonstrating empirical behavior:
        # A corrupted item where all 3 required keys are None is accepted with literal 'None' strings!
        assert len(result) == 0

    def test_extreme_size_strings(self):
        """Handles huge payload strings without memory crash or exception."""
        large_title = "Cloud Architect " * 5000  # ~80KB
        large_company = "Enterprise Corp " * 5000
        large_url = "https://careers.enterprise.com/" + ("subpath/" * 1000)
        item = {
            "title": large_title,
            "company": large_company,
            "url": large_url,
            "description": "Big description " * 10000,
        }
        result = normalize_opportunities([item])
        assert len(result) == 1
        assert result[0].title.startswith("Cloud Architect")
        # JobOpportunity.id is 16 hex chars from truncated sha256
        assert len(result[0].id) == 16

    def test_unicode_and_emojis_in_raw_dict(self):
        """Handles multi-language Unicode and emojis properly."""
        item = {
            "title": "Ingénieur DevOps Cloud 🚀 (H/F)",
            "company": "Société Générale & 阿里巴巴",
            "url": "https://careers.example.com/job/devops-🚀",
            "location": "Paris / Remote (Télétravail)",
            "salary": "€80.000 - €95.000",
        }
        result = normalize_opportunities([item])
        assert len(result) == 1
        assert result[0].title == "Ingénieur DevOps Cloud 🚀 (H/F)"
        assert result[0].company == "Société Générale & 阿里巴巴"
        assert len(result[0].id) == 16

    def test_pass_through_job_opportunity_objects(self):
        """Existing JobOpportunity instances pass through if valid, rejected if blank."""
        valid_opp = JobOpportunity(
            title="DevOps Engineer",
            company="Acme Corp",
            url="https://acme.example/job",
        )
        invalid_opp = JobOpportunity(
            title="",
            company="Acme Corp",
            url="https://acme.example/job",
        )
        result = normalize_opportunities([valid_opp, invalid_opp])
        assert len(result) == 1
        assert result[0].title == "DevOps Engineer"


# ============================================================================
# 2. Adversarial Tests: deduplicate_opportunities
# ============================================================================

class TestDeduplicateOpportunitiesAdversarial:
    """Stress tests and boundary challenges for deduplicate_opportunities."""

    def test_massive_list_deduplication_performance(self):
        """Stress test with 10,000 items containing duplicates."""
        base_items = [
            JobOpportunity(
                title=f"Role {i % 50}",
                company=f"Company {i % 25}",
                url=f"https://example.com/jobs/{i % 100}",
            )
            for i in range(10000)
        ]

        t0 = time.perf_counter()
        deduped = deduplicate_opportunities(base_items)
        elapsed = time.perf_counter() - t0

        # Should be fast (< 2.0 seconds on any machine)
        assert elapsed < 2.0
        # Total distinct combinations should be capped by unique URLs or unique (company, title)
        assert len(deduped) <= 100
        assert len(deduped) > 0

    def test_case_and_outer_whitespace_deduplication(self):
        """Deduplicates when company/title differ only by case and leading/trailing whitespace."""
        opp1 = JobOpportunity(
            title="Senior DevOps Engineer",
            company="Global Cloud Corp",
            url="https://example.com/job/1",
        )
        opp2 = JobOpportunity(
            title=" senior devops engineer ",
            company="GLOBAL CLOUD CORP",
            url="https://example.com/job/2",  # Different URL, same company+title
        )
        deduped = deduplicate_opportunities([opp1, opp2])
        assert len(deduped) == 1
        assert deduped[0].url == "https://example.com/job/1"

    def test_empirical_finding_internal_whitespace_defeats_sources_dedup(self):
        """
        EMPIRICAL OBSERVATION / DEFECT PROOF:
        discovery/verifier.py:generate_fingerprint properly collapses internal whitespace
        via re.sub(r'\\s+', ' ', ...).
        However, discovery/sources.py:deduplicate_opportunities does NOT use generate_fingerprint.
        Instead, it computes inline:
            company = str(getattr(opp, 'company', '')).strip().lower()
            title = str(getattr(opp, 'title', '')).strip().lower()
            fp_raw = f'{company}::{title}'
        This leaves internal multiple spaces or tabs intact.
        Consequently, opportunities with identical titles/companies differing only
        by internal whitespace (e.g. 'Senior   DevOps   Engineer' vs 'Senior DevOps Engineer')
        generate different SHA-256 fingerprints and FAIL to deduplicate!
        """
        opp1 = JobOpportunity(
            title="Senior DevOps Engineer",
            company="Global Cloud Corp",
            url="https://example.com/job/1",
        )
        opp2 = JobOpportunity(
            title="Senior   DevOps   Engineer",  # 3 spaces between words
            company="Global Cloud Corp",
            url="https://example.com/job/2",
        )
        deduped = deduplicate_opportunities([opp1, opp2])
        assert len(deduped) == 1, "Internal whitespace variations must collapse to 1 via generate_fingerprint"

    def test_identical_url_different_title_deduplication(self):
        """Deduplicates when URL is identical, even if title varies."""
        opp1 = JobOpportunity(
            title="Cloud Architect",
            company="Acme Corp",
            url="https://example.com/job/shared-link",
        )
        opp2 = JobOpportunity(
            title="DevOps Lead",
            company="Acme Corp",
            url="https://example.com/job/shared-link",  # Same URL
        )

        deduped = deduplicate_opportunities([opp1, opp2])
        assert len(deduped) == 1
        assert deduped[0].title == "Cloud Architect"

    def test_url_case_insensitivity(self):
        """Deduplicates URLs with different casing."""
        opp1 = JobOpportunity(
            title="Role A",
            company="Company A",
            url="HTTPS://EXAMPLE.COM/JOBS/101",
        )
        opp2 = JobOpportunity(
            title="Role B",
            company="Company B",
            url="https://example.com/jobs/101",
        )
        deduped = deduplicate_opportunities([opp1, opp2])
        assert len(deduped) == 1

    def test_mixed_dict_and_job_opportunity_dedup(self):
        """Deduplicates across mixed dicts and JobOpportunity objects."""
        opp_obj = JobOpportunity(
            title="DevOps Engineer",
            company="Acme Corp",
            url="https://acme.com/job/1",
        )
        opp_dict = {
            "title": "devops engineer",
            "company": "ACME CORP",
            "url": "https://acme.com/job/other",
        }
        deduped = deduplicate_opportunities([opp_obj, opp_dict])
        assert len(deduped) == 1

    def test_empty_or_none_inputs(self):
        """Handles empty lists, None, or lists containing None safely."""
        assert deduplicate_opportunities([]) == []
        assert deduplicate_opportunities(None) == []
        assert deduplicate_opportunities([None, None]) == []


# ============================================================================
# 3. Adversarial Tests: fetch_opportunities
# ============================================================================

class TestFetchOpportunitiesAdversarial:
    """Stress tests and boundary challenges for fetch_opportunities."""

    def test_simulate_timeout_immediate_fallback(self):
        """simulate_timeout=True triggers synthetic fallback immediately."""
        results = fetch_opportunities(simulate_timeout=True, limit=10)
        assert isinstance(results, list)
        assert len(results) > 0
        assert len(results) <= 10
        for opp in results:
            assert isinstance(opp, JobOpportunity)
            assert opp.url.startswith("http")

    def test_unknown_and_invalid_sources_handling(self):
        """Unknown or invalid source names must fall back gracefully."""
        bad_sources = [
            "completely_fake_source_12345",
            "random_api_unknown",
            "",
            "   ",
            "123!@#$",
        ]
        results = fetch_opportunities(sources=bad_sources, dry_run=False)
        assert isinstance(results, list)
        assert len(results) > 0  # Fallback to synthetic

    def test_role_filtering_boundary_empty_vs_nonexistent(self):
        """Empty query_roles list defaults to all roles; nonexistent role handles safely."""
        # Empty list -> all target roles
        all_roles = fetch_opportunities(query_roles=[], dry_run=True)
        assert len(all_roles) >= 5

        # Non-existent role -> returns fallback without throwing
        nonexistent = fetch_opportunities(query_roles=["Astronomer Astronaut FalconPilot"], dry_run=True)
        assert isinstance(nonexistent, list)
        assert len(nonexistent) > 0

    def test_extreme_limits(self):
        """Handles limit=0, limit=1, and limit=10000."""
        zero = fetch_opportunities(limit=0, dry_run=True)
        assert len(zero) == 0

        one = fetch_opportunities(limit=1, dry_run=True)
        assert len(one) == 1

        huge = fetch_opportunities(limit=10000, dry_run=True)
        assert len(huge) >= 5  # Limited to available synthetic jobs


# ============================================================================
# 4. Adversarial Tests: detect_closed_phrase (F10)
# ============================================================================

class TestDetectClosedPhraseAdversarial:
    """Adversarial stress testing of closed/expired phrase detection in HTML/text."""

    def test_heavily_nested_obfuscated_html(self):
        """Detects closed phrases broken across nested tags and spans."""
        html_snippets = [
            "<div><p>This <b>position</b> has been <i>filled</i>.</p></div>",
            "<div class='alert'><p><span>Applications</span> <span>are</span> <span>now</span> <span>closed</span>.</p></div>",
            "<section><h1>Job Status</h1><p>This <strong>posting</strong> <em>has expired</em>.</p></section>",
            "<div><span>Sorry, this</span> <b>job is no longer available</b>.</div>",
            "<table><tr><td>Status:</td><td><b>404 not found</b></td></tr></table>",
            "<p>We are <span>not accepting applications</span> at this time.</p>",
        ]
        for snippet in html_snippets:
            assert detect_closed_phrase(snippet) is True, f"Failed on snippet: {snippet}"

    def test_html_entities_and_encoding(self):
        """Detects closed phrases containing HTML entities (&nbsp;, &period;, etc.)."""
        snippets = [
            "This&nbsp;position&nbsp;has&nbsp;been&nbsp;filled&period;",
            "Applications&nbsp;are&nbsp;closed&period;",
            "&lt;div&gt;This job has expired&lt;/div&gt;",
            "This&#32;position&#32;has&#32;been&#32;filled&#46;",
        ]
        for s in snippets:
            assert detect_closed_phrase(s) is True, f"Failed to detect encoded: {s}"

    def test_multiline_and_extreme_whitespace(self):
        """Detects phrases with line breaks, tabs, and carriage returns."""
        text = (
            "Thank you for your interest.\n\n\t"
            "This    position\n\r\t"
            "has\t\tbeen\n\n\n"
            "filled.\n\n"
            "Check back later."
        )
        assert detect_closed_phrase(text) is True

    def test_case_insensitivity(self):
        """Detects all uppercase, mixed case, and lowercase closed notices."""
        cases = [
            "THIS POSITION HAS BEEN FILLED.",
            "THIS JOB IS NO LONGER AVAILABLE.",
            "APPLICATIONS ARE NOW CLOSED.",
            "ThIs RoLe HaS bEeN fIlLeD.",
        ]
        for c in cases:
            assert detect_closed_phrase(c) is True, f"Failed case test: {c}"

    def test_open_positions_with_similar_words_not_false_positive(self):
        """Does NOT falsely flag active job postings containing 'close' or 'fill' in other contexts."""
        active_descriptions = [
            "You will work closely with our principal cloud architect to design systems.",
            "We are seeking an engineer to fill an immediate opening on our DevOps team.",
            "Our team is located close to London and operates under flexible hybrid hours.",
            "You will be responsible for filling pipelines with automated CI/CD artifacts.",
            "Candidates should be comfortable working behind closed doors on secret clearance tasks.",
            "We review applications on a rolling basis; submit your application today!",
        ]
        for desc in active_descriptions:
            assert detect_closed_phrase(desc) is False, f"False positive on active description: {desc}"

    def test_bytes_input_handling(self):
        """Handles bytes input directly."""
        body_bytes = b"<html><body><p>This position has been filled.</p></body></html>"
        assert detect_closed_phrase(body_bytes) is True

        open_bytes = b"<html><body><p>Join our thriving engineering team!</p></body></html>"
        assert detect_closed_phrase(open_bytes) is False

    def test_none_and_empty_body(self):
        """Handles None, empty string, and whitespace-only body."""
        assert detect_closed_phrase(None) is False
        assert detect_closed_phrase("") is False
        assert detect_closed_phrase("   \n\t  ") is False


# ============================================================================
# 5. Adversarial Tests: is_fresh_date (F10)
# ============================================================================

class TestIsFreshDateAdversarial:
    """Stress tests for date freshness parsing and validation."""

    def test_relative_date_strings(self):
        """Validates relative date terms."""
        ref = datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)
        assert is_fresh_date("today", reference_date=ref) is True
        assert is_fresh_date("yesterday", reference_date=ref) is True
        assert is_fresh_date("just now", reference_date=ref) is True
        assert is_fresh_date("3 hours ago", reference_date=ref) is True
        assert is_fresh_date("5 days ago", reference_date=ref) is True
        assert is_fresh_date("28 days ago", reference_date=ref) is True
        assert is_fresh_date("31 days ago", reference_date=ref) is False
        assert is_fresh_date("two months ago", reference_date=ref) is False
        assert is_fresh_date("three months ago", reference_date=ref) is False
        assert is_fresh_date("90 days ago", reference_date=ref) is False

    def test_future_dates(self):
        """Dates far in the future must be rejected."""
        ref = datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)
        # Far future rejected
        assert is_fresh_date("2099-01-01", reference_date=ref) is False
        assert is_fresh_date("2026-12-01", reference_date=ref) is False
        # 1 day in future allowed for international timezone differences
        assert is_fresh_date("2026-11-08", reference_date=ref) is True
        # 5 days in future rejected
        assert is_fresh_date("2026-11-12", reference_date=ref) is False

    def test_epoch_and_ancient_dates(self):
        """Dates from Unix epoch or ancient past must be rejected as stale."""
        ref = datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)
        assert is_fresh_date("1970-01-01", reference_date=ref) is False
        assert is_fresh_date("1900-01-01", reference_date=ref) is False
        assert is_fresh_date("2000-01-01", reference_date=ref) is False

    def test_unparseable_and_garbage_date_strings(self):
        """Unparseable dates must return False gracefully without throwing exceptions."""
        ref = datetime.datetime(2026, 11, 7, tzinfo=datetime.timezone.utc)
        garbage = [
            "not a date",
            "asap",
            "immediately",
            "Q3 2026",
            "2026-02-31",  # Invalid day
            "2026-13-01",  # Invalid month
            "9999-99-99",
            "NaN",
            "null",
            "undefined",
            "!@#$%^&*()",
            "2026.11.05",
        ]
        for g in garbage:
            assert is_fresh_date(g, reference_date=ref) is False

    def test_none_and_non_string_types(self):
        """Handles None and non-string inputs safely."""
        assert is_fresh_date(None) is False
        assert is_fresh_date(12345) is False
        assert is_fresh_date([]) is False
        assert is_fresh_date({}) is False


# ============================================================================
# 6. Adversarial Tests: generate_fingerprint (F10)
# ============================================================================

class TestGenerateFingerprintAdversarial:
    """Stress tests for SHA-256 fingerprint generation."""

    def test_sha256_length_and_hex_charset(self):
        """Always produces a 64-character lowercase hex string."""
        fp = generate_fingerprint("Acme Corp", "Cloud Architect")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_complex_unicode_and_emojis(self):
        """Generates deterministic hashes for complex Unicode, emojis, and non-Latin scripts."""
        fp1 = generate_fingerprint("腾讯云 🚀", "高级运维工程师 (DevOps)")
        fp2 = generate_fingerprint("  腾讯云 🚀  ", "  高级运维工程师 (DevOps)  ")
        assert len(fp1) == 64
        assert fp1 == fp2  # Whitespace-insensitive

        fp_arabic = generate_fingerprint("شركة السحاب", "مهندس البنية التحتية")
        assert len(fp_arabic) == 64

    def test_zero_width_and_control_chars(self):
        """Handles zero-width spaces, tabs, newlines, and carriage returns."""
        fp_clean = generate_fingerprint("Acme Corp", "DevOps Engineer")
        fp_dirty = generate_fingerprint("Acme\tCorp\n", "\r\nDevOps   Engineer\t")
        assert fp_clean == fp_dirty

    def test_none_and_empty_inputs(self):
        """Handles None, empty strings, and whitespace-only without raising."""
        fp1 = generate_fingerprint("", "")
        fp2 = generate_fingerprint("   ", "   ")
        fp3 = generate_fingerprint(None, None)
        assert len(fp1) == 64
        assert fp1 == fp2 == fp3


# ============================================================================
# 7. Adversarial Tests: check_redirect_depth & verify_job_link (F10)
# ============================================================================

class TestRedirectAndVerificationAdversarial:
    """Stress tests for redirect hops and link verification edge cases."""

    def test_check_redirect_depth_boundaries(self):
        """Tests redirect depth boundary conditions."""
        assert check_redirect_depth(0, max_hops=5) is True
        assert check_redirect_depth(1, max_hops=5) is True
        assert check_redirect_depth(5, max_hops=5) is True
        assert check_redirect_depth(6, max_hops=5) is False
        assert check_redirect_depth(100, max_hops=5) is False

        # String representations of ints
        assert check_redirect_depth("3", max_hops="5") is True
        assert check_redirect_depth("7", max_hops="5") is False

        # Non-numeric inputs
        assert check_redirect_depth("invalid", max_hops=5) is False
        assert check_redirect_depth(None, max_hops=5) is False
        assert check_redirect_depth([], max_hops=5) is False

    def test_verify_job_link_malformed_urls(self):
        """Malformed or incomplete URLs must return inactive VerificationResult."""
        malformed = [
            "",
            "   ",
            None,
            "not-a-url",
            "http://",
            "https://",
            "ftp://",
            "mailto:admin@example.com",
            "://missing-scheme.com",
        ]
        for url in malformed:
            res = verify_job_link(url, offline_mode=True)
            assert isinstance(res, VerificationResult)
            assert res.is_active is False
            assert res.http_status in (400, 404)

    def test_verify_job_link_mock_status_matrix(self):
        """Tests response status handling across standard HTTP status codes."""
        test_url = "https://careers.example.com/jobs/101"

        # Active codes
        for code in [200, 204]:
            res = verify_job_link(test_url, mock_status=code, offline_mode=True)
            assert res.is_active is True
            assert res.http_status == code

        # Inactive codes
        for code in [301, 400, 401, 403, 404, 410, 429, 500, 502, 503]:
            res = verify_job_link(test_url, mock_status=code, offline_mode=True)
            assert res.is_active is False
            assert res.http_status == code

    def test_verify_job_link_simulated_url_patterns(self):
        """Tests offline keyword-based URL pattern simulation."""
        assert verify_job_link("https://example.com/test_url_404").is_active is False
        assert verify_job_link("https://example.com/test_url_410").is_active is False
        assert verify_job_link("https://example.com/test_url_500").is_active is False
        assert verify_job_link("https://example.com/test_url_503").is_active is False
        assert verify_job_link("https://example.com/test_url_timeout").is_active is False
        assert verify_job_link("https://example.com/test_url_redirect_loop").is_active is False
        assert verify_job_link("https://example.com/test_url_expired").is_active is False

    def test_verify_opportunities_batch_helper(self):
        """Tests batch verification helper with mixed active and inactive opportunities."""
        opps = [
            JobOpportunity(title="Active Role", company="Co A", url="https://example.com/active-1"),
            JobOpportunity(title="Dead 404", company="Co B", url="https://example.com/test_url_404"),
            JobOpportunity(title="Expired Role", company="Co C", url="https://example.com/test_url_expired"),
        ]
        results = verify_opportunities(opps, offline_mode=True)
        assert len(results) == 3
        assert results[0].is_active is True
        assert results[1].is_active is False
        assert results[2].is_active is False
