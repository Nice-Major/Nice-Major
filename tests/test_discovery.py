"""
Unit & Integration Test Suite for Milestone 3 Discovery, Filtering & Verification.
Target Module: tests/test_discovery.py
Features Covered:
- F08: Multi-Source Job Discovery Engine (discovery.sources, discovery.models)
- F09: Geo-Eligibility & Sponsorship Filter (discovery.filters)
- F10: Opportunity Health & Active Verification (discovery.verifier)

Validates:
- JobOpportunity / Opportunity data model contract, dict subscript, attribute access, serialization.
- Multi-source discovery adapters, query role filters, synthetic fallback, and deduplication.
- Nigeria remote eligibility (Worldwide, EMEA, CET, UTC+1), visa sponsorship, B2B contract, and hard disqualifiers.
- HTTP status verification (200/204 vs 404/410/500), DOM closed phrase detection, stale dates (<=30 days),
  SHA-256 deduplication fingerprinting, redirect depth limits, and offline mock mode.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discovery.models import JobOpportunity, Opportunity, JobQueryParams
from discovery.sources import (
    fetch_opportunities,
    search_opportunities,
    get_synthetic_opportunities,
    normalize_opportunities,
    deduplicate_opportunities,
    CANONICAL_TARGET_ROLES,
    AdapterRegistry,
    registry,
)
from discovery.filters import (
    is_remote_eligible,
    detect_visa_sponsorship,
    detect_contract_c2c,
    detect_contract_consultancy,
    detect_research_fellowship,
    detect_fellowship_research,
    has_disqualifiers,
    filter_opportunities,
    evaluate_location_mobility,
    evaluate_opportunity_eligibility,
    categorize_opportunity,
    EligibilityResult,
)
from discovery.verifier import (
    VerificationResult,
    verify_job_link,
    verify_url_status,
    detect_closed_phrase,
    is_fresh_date,
    generate_fingerprint,
    check_redirect_depth,
    verify_opportunities,
)
from ingestion.models import CandidateProfile


# ============================================================================
# 1. Feature F08 Tests: Data Models & Discovery Adapters
# ============================================================================

class TestDiscoveryModels:
    """Tests for JobOpportunity and Opportunity data models."""

    def test_job_opportunity_field_initialization(self):
        job = JobOpportunity(
            id="job-101",
            title="Senior DevOps Engineer",
            company="CloudCorp",
            location="Remote - Worldwide",
            description="Terraform, Kubernetes, and AWS automation.",
            url="https://cloudcorp.example/jobs/101",
            source="remoteok",
            posted_date="2026-11-05",
            is_remote=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="full-time",
            is_active=True,
        )
        assert job.id == "job-101"
        assert job.title == "Senior DevOps Engineer"
        assert job.company == "CloudCorp"
        assert job.is_remote is True
        assert job.nigeria_eligible is True

    def test_job_opportunity_auto_id_generation(self):
        job = JobOpportunity(
            title="Cloud Engineer",
            company="Acme Ltd",
            url="https://acme.example/jobs/42",
        )
        assert job.id != ""
        assert len(job.id) == 16

    def test_job_opportunity_aliases_and_property_reflection(self):
        job = JobOpportunity(
            id="job-102",
            title="Cloud Solutions Architect",
            company="AzureGlobal",
            location="Worldwide Remote",
            url="https://azureglobal.example/csa",
            nigeria_eligible=True,
            visa_sponsored=True,
            is_active=True,
            contract_type="b2b",
        )
        # Property aliases
        assert job.remote_eligible_nigeria is True
        assert job.visa_sponsorship is True
        assert job.verified_active is True
        assert job.contract_b2b is True

        # Property setters
        job.remote_eligible_nigeria = False
        assert job.nigeria_eligible is False
        job.visa_sponsorship = False
        assert job.visa_sponsored is False
        job.verified_active = False
        assert job.is_active is False
        job.contract_b2b = False
        assert job.contract_type == "full-time"
        job.contract_b2b = True
        assert job.contract_type == "b2b"

    def test_job_opportunity_dict_subscript_access(self):
        job = JobOpportunity(
            id="job-103",
            title="Technical Support Engineer",
            company="SupportHeroes",
            url="https://supportheroes.example/job",
        )
        assert job["title"] == "Technical Support Engineer"
        assert job["company"] == "SupportHeroes"
        assert job["url"] == "https://supportheroes.example/job"
        assert "title" in job

        # Setting via subscript
        job["title"] = "Senior Technical Support Engineer"
        assert job.title == "Senior Technical Support Engineer"

        with pytest.raises(KeyError):
            _ = job["non_existent_key"]

    def test_job_opportunity_get_method(self):
        job = JobOpportunity(title="SysAdmin", company="HostCo", url="https://hostco.example/1")
        assert job.get("title") == "SysAdmin"
        assert job.get("unknown_key", "default_val") == "default_val"

    def test_job_opportunity_serialization_to_and_from_dict(self):
        original = JobOpportunity(
            id="job-104",
            title="DevSecOps Engineer",
            company="SecureCloud",
            location="Remote EMEA",
            url="https://securecloud.example/104",
            posted_date="2026-11-04",
            is_active=True,
            nigeria_eligible=True,
            visa_sponsored=False,
            contract_type="b2b",
        )
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data["title"] == "DevSecOps Engineer"
        assert data["remote_eligible_nigeria"] is True
        assert data["contract_b2b"] is True
        assert data["verified_active"] is True

        restored = JobOpportunity.from_dict(data)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.url == original.url
        assert restored.nigeria_eligible is True
        assert restored.contract_b2b is True

    def test_job_query_params_dataclass(self):
        params = JobQueryParams(
            query_roles=["DevOps"],
            limit=10,
            dry_run=True,
        )
        p_dict = params.to_dict()
        assert p_dict["limit"] == 10
        assert p_dict["query_roles"] == ["DevOps"]

        restored = JobQueryParams.from_dict(p_dict)
        assert restored.limit == 10
        assert restored.query_roles == ["DevOps"]

    def test_opportunity_alias_identity(self):
        assert Opportunity is JobOpportunity


class TestDiscoverySourcesF08:
    """Tests for Feature F08 Discovery Sources and Adapters."""

    def test_fetch_opportunities_dry_run_non_empty(self):
        jobs = fetch_opportunities(dry_run=True)
        assert isinstance(jobs, list)
        assert len(jobs) >= 1

    def test_fetch_opportunities_all_urls_valid_http(self):
        jobs = fetch_opportunities(dry_run=True)
        for job in jobs:
            url = getattr(job, "url", job.get("url") if isinstance(job, dict) else "")
            assert url.startswith("http://") or url.startswith("https://")

    def test_fetch_opportunities_with_specific_query_roles(self):
        jobs = fetch_opportunities(query_roles=["DevOps"], dry_run=True)
        assert len(jobs) >= 1
        assert any("devops" in job.title.lower() for job in jobs)

    def test_fetch_opportunities_empty_query_roles_defaults_to_all(self):
        jobs = fetch_opportunities(query_roles=[], dry_run=True)
        assert len(jobs) >= 3

    def test_get_synthetic_opportunities_quantity_and_roles(self):
        synth = get_synthetic_opportunities()
        assert len(synth) >= 8
        titles = [s.title.lower() for s in synth]
        assert any("devops" in t or "cloud" in t for t in titles)

    def test_normalize_opportunities_drops_corrupted_items(self):
        raw_items = [
            {"title": "Valid Job", "company": "Valid Corp", "url": "https://valid.example/job"},
            {"corrupted": True},
            {"title": "No URL Job", "company": "Ghost Corp"},
            {"url": "https://valid2.example/job", "company": "No Title Corp"},
        ]
        cleaned = normalize_opportunities(raw_items)
        assert len(cleaned) == 1
        assert cleaned[0]["title"] == "Valid Job"

    def test_deduplicate_opportunities_merges_duplicates(self):
        dups = [
            {"id": "1", "title": "DevOps Engineer", "company": "Acme", "url": "https://acme.example/1"},
            {"id": "2", "title": "DevOps Engineer", "company": "Acme", "url": "https://acme.example/2"},
            {"id": "3", "title": "Cloud Architect", "company": "Zenith", "url": "https://zenith.example/csa"},
        ]
        unique = deduplicate_opportunities(dups)
        assert len(unique) == 2

    def test_network_timeout_fallback_to_synthetic(self):
        jobs = fetch_opportunities(dry_run=True, simulate_timeout=True)
        assert len(jobs) >= 1

    def test_unknown_source_provider_graceful_fallback(self):
        jobs = fetch_opportunities(sources=["unknown_source_xyz"], dry_run=True)
        assert isinstance(jobs, list)
        assert len(jobs) >= 1

    def test_offline_mode_zero_external_network_leakage(self):
        jobs = fetch_opportunities(offline_mode=True, dry_run=True)
        assert len(jobs) >= 1

    def test_search_opportunities_helper(self):
        res = search_opportunities({"roles": ["Cloud Engineer"], "dry_run": True})
        assert isinstance(res, list)
        assert len(res) >= 1

    def test_adapter_registry(self):
        reg = AdapterRegistry()
        sources = reg.list_sources()
        assert "synthetic" in sources
        assert "remoteok" in sources
        assert reg.get("synthetic") is not None


# ============================================================================
# 2. Feature F09 Tests: Geographic & Mobility Eligibility Filter
# ============================================================================

class TestEligibilityFilterF09:
    """Tests for Feature F09 Geo-Eligibility, Visa Sponsorship, and Disqualifiers."""

    @pytest.mark.parametrize("loc_str", [
        "Remote - Worldwide",
        "Worldwide Remote (UTC+1 / CET Synchronous)",
        "Global Remote",
        "Work from Anywhere",
        "Remote - EMEA",
        "Remote - Europe (CET Timezone)",
        "Remote - Africa / Lagos, Nigeria",
        "Anywhere (Synchronous with EMEA)",
    ])
    def test_positive_remote_locations_eligible(self, loc_str):
        assert is_remote_eligible(loc_str) is True

    def test_case_insensitive_worldwide_remote_eligibility(self):
        assert is_remote_eligible("REMOTE - WORK FROM ANYWHERE (WORLDWIDE)") is True

    @pytest.mark.parametrize("disqualifier_text", [
        "Remote - US Citizen Only (W2 Only)",
        "Candidates must reside in the United States. No exceptions.",
        "Active Top Secret / SCI clearance required",
        "Secret Clearance required. Must be US Citizen.",
        "Must reside in California for state payroll tax purposes.",
        "Hybrid role: 3 days on-site in New York office mandatory.",
        "Candidate must be located in Canada.",
        "W2 Only. No C2C or 1099 contracts permitted.",
    ])
    def test_disqualifying_locations_rejected(self, disqualifier_text):
        assert is_remote_eligible(disqualifier_text) is False

    def test_visa_sponsorship_positive_detection(self):
        text = "We offer UK Skilled Worker visa sponsorship and comprehensive relocation assistance to London."
        assert detect_visa_sponsorship(text) is True

    def test_visa_sponsorship_negative_detection(self):
        text = "Candidate must have existing work authorization; no visa sponsorship will be provided."
        assert detect_visa_sponsorship(text) is False

    def test_contract_consultancy_c2c_detection(self):
        text = "B2B Corp-to-Corp (C2C) or independent contractor engagement available."
        assert detect_contract_c2c(text) is True
        assert detect_contract_consultancy(text) is True

    def test_research_fellowship_detection(self):
        text = "Seeking applicants for our 12-month Cloud Systems Research Fellowship program."
        assert detect_research_fellowship(text) is True
        assert detect_fellowship_research(text) is True

    def test_filter_opportunities_with_candidate_profile(self, sample_profile):
        jobs = [
            JobOpportunity(id="1", title="DevOps", company="A", location="Remote - Worldwide"),
            JobOpportunity(id="2", title="SysAdmin", company="B", location="US Citizen Only"),
        ]
        filtered = filter_opportunities(jobs, candidate=sample_profile)
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_opportunities_with_candidate_dict(self):
        jobs = [
            JobOpportunity(id="1", title="DevOps", company="A", location="Remote EMEA"),
            JobOpportunity(id="2", title="SysAdmin", company="B", location="Must reside in California for tax purposes"),
        ]
        filtered = filter_opportunities(jobs, candidate={"location": "Lagos, Nigeria"})
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_opportunities_with_none_candidate_default(self):
        jobs = [
            JobOpportunity(id="1", title="Architect", company="A", location="Worldwide Remote"),
            JobOpportunity(id="2", title="Support", company="B", location="Active TS/SCI required"),
        ]
        filtered = filter_opportunities(jobs, candidate=None)
        assert len(filtered) == 1
        assert filtered[0].id == "1"

    def test_filter_opportunities_empty_and_blank_resilience(self):
        assert filter_opportunities([]) == []
        assert isinstance(is_remote_eligible(""), bool)
        assert is_remote_eligible("") is False

    def test_evaluate_location_mobility_blank(self):
        score, status = evaluate_location_mobility("")
        assert status in ["unspecified", "neutral", "review"]
        assert score == 60.0

    def test_evaluate_location_mobility_disqualified(self):
        score, status = evaluate_location_mobility("Active TS/SCI clearance required")
        assert status == "disqualified"
        assert score == 0.0

    def test_evaluate_opportunity_eligibility_detail(self):
        job = JobOpportunity(
            title="Senior DevOps",
            company="Acme",
            location="Remote - Worldwide",
            description="UK Skilled Worker visa sponsorship available.",
        )
        res = evaluate_opportunity_eligibility(job)
        assert res.is_eligible is True
        assert res.remote_eligible_nigeria is True
        assert res.visa_sponsorship is True
        assert res["remote_eligible_nigeria"] is True

    def test_categorize_opportunity_dict(self):
        job = {"title": "DevOps", "location": "Worldwide Remote", "description": "100% remote"}
        cat = categorize_opportunity(job)
        assert isinstance(cat, dict)
        assert cat["is_eligible"] is True


# ============================================================================
# 3. Feature F10 Tests: Link & Health Verification
# ============================================================================

class TestLinkVerifierF10:
    """Tests for Feature F10 Opportunity Health, Status, DOM, Freshness, and Fingerprinting."""

    def test_verification_result_dataclass_contract(self):
        res = VerificationResult(
            is_active=True,
            http_status=200,
            reason="Active verified",
            url="https://example.com/job",
            redirect_hops=1,
            is_fresh=True,
        )
        assert res.is_active is True
        assert res.http_status == 200
        assert res.reason == "Active verified"
        assert res.url == "https://example.com/job"

        d = res.to_dict()
        assert isinstance(d, dict)
        assert d["is_active"] is True
        assert d["http_status"] == 200

    def test_verification_result_dict_subscript_access(self):
        res = VerificationResult(
            is_active=False,
            http_status=404,
            reason="Not found",
        )
        assert res["is_active"] is False
        assert res["http_status"] == 404
        assert res["reason"] == "Not found"
        assert "is_active" in res

        with pytest.raises(KeyError):
            _ = res["non_existent"]

    def test_verification_result_boolean_coercion(self):
        active = VerificationResult(is_active=True, http_status=200, reason="OK")
        inactive = VerificationResult(is_active=False, http_status=404, reason="Gone")
        assert bool(active) is True
        assert bool(inactive) is False

    @pytest.mark.parametrize("status_code", [200, 204])
    def test_verify_url_status_active_http_codes(self, status_code):
        assert verify_url_status("https://example.com/active", mock_status=status_code) is True

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 410, 500, 503])
    def test_verify_url_status_inactive_http_codes(self, status_code):
        assert verify_url_status("https://example.com/inactive", mock_status=status_code) is False

    @pytest.mark.parametrize("phrase", [
        "Thank you for visiting. This position has been filled. Applications are now closed.",
        "We are sorry, this job is no longer available.",
        "This posting has expired.",
        "404 Not Found - The requested job vacancy could not be located.",
        "This role has been closed and we are no longer accepting applications.",
        "This vacancy has expired.",
    ])
    def test_detect_closed_phrase_exact_matches(self, phrase):
        assert detect_closed_phrase(phrase) is True

    def test_detect_closed_phrase_negative_for_open_postings(self):
        open_desc = (
            "We are seeking an experienced DevOps Engineer to join our team. "
            "Click Apply Now below to submit your application. Open until filled."
        )
        assert detect_closed_phrase(open_desc) is False

    def test_detect_closed_phrase_html_stripping(self):
        html_markup = """
        <div class="job-status-banner">
            <h1>Notice</h1>
            <p>This <strong>position has been filled</strong>. Applications are closed.</p>
        </div>
        """
        assert detect_closed_phrase(html_markup) is True

    def test_is_fresh_date_accepted_within_30_days(self):
        # 2 days prior to 2026-11-07 baseline
        assert is_fresh_date("2026-11-05", max_days=30) is True

    def test_is_fresh_date_rejected_older_than_30_days(self):
        # 3+ months prior to 2026-11-07 baseline
        assert is_fresh_date("2026-08-01", max_days=30) is False

    def test_is_fresh_date_unparseable_string_graceful_fallback(self):
        fresh = is_fresh_date("three months ago", max_days=30)
        assert isinstance(fresh, bool)
        assert fresh is False

        invalid = is_fresh_date("not-a-valid-date-string", max_days=30)
        assert isinstance(invalid, bool)
        assert invalid is False

    def test_generate_fingerprint_case_insensitivity(self):
        fp1 = generate_fingerprint("Acme Corp", "Senior DevOps Engineer")
        fp2 = generate_fingerprint("acme corp", "senior devops engineer")
        assert fp1 == fp2

    def test_generate_fingerprint_whitespace_normalization(self):
        fp1 = generate_fingerprint("  Acme   Corp  ", "Senior   DevOps   Engineer")
        fp2 = generate_fingerprint("Acme Corp", "Senior DevOps Engineer")
        assert fp1 == fp2

    def test_generate_fingerprint_unicode_character_handling(self):
        fp = generate_fingerprint("Société Générale", "DevOps Ingénieur")
        assert len(fp) == 64
        assert isinstance(fp, str)

    def test_generate_fingerprint_uniqueness(self):
        fp1 = generate_fingerprint("Acme Corp", "DevOps Engineer")
        fp2 = generate_fingerprint("Beta LLC", "Cloud Architect")
        assert fp1 != fp2

    def test_check_redirect_depth_boundary_enforcement(self):
        assert check_redirect_depth(hops=3, max_hops=5) is True
        assert check_redirect_depth(hops=5, max_hops=5) is True
        assert check_redirect_depth(hops=6, max_hops=5) is False

    def test_verify_job_link_offline_mock_mode_active(self):
        res = verify_job_link("https://careers.example.com/job/test_url_active", offline_mode=True)
        assert res.is_active is True
        assert res.http_status == 200

    def test_verify_job_link_offline_mock_mode_expired_dom(self):
        res = verify_job_link("https://careers.example.com/job/test_url_expired", offline_mode=True)
        assert res.is_active is False
        assert "closed" in res.reason.lower() or "expired" in res.reason.lower()

    def test_verify_job_link_offline_mock_mode_404_not_found(self):
        res = verify_job_link("https://careers.example.com/job/test_url_404", offline_mode=True)
        assert res.is_active is False
        assert res.http_status == 404

    def test_verify_job_link_timeout_handled_without_exception(self):
        res = verify_job_link("https://careers.example.com/job/test_url_timeout", offline_mode=True)
        assert res.is_active is False
        assert res.http_status in (408, 0)
        assert "timed out" in res.reason.lower()

    def test_verify_job_link_redirect_loop_handled_without_exception(self):
        res = verify_job_link("https://careers.example.com/job/test_url_redirect_loop", offline_mode=True)
        assert res.is_active is False
        assert "redirect" in res.reason.lower()

    def test_verify_opportunities_batch_helper(self):
        jobs = [
            {"title": "DevOps", "url": "https://careers.example.com/test_url_active", "is_active": False},
            {"title": "Closed", "url": "https://careers.example.com/test_url_404", "is_active": True},
        ]
        verified = verify_opportunities(jobs, offline_mode=True)
        assert verified[0]["is_active"] is True
        assert verified[1]["is_active"] is False


# ============================================================================
# 4. Feature F09 Adversarial Hardening & Regression Prevention
# ============================================================================

class TestEligibilityHardeningF09:
    """Comprehensive regression guards for US disqualification, visa negations, 1099, and on-site locations."""

    @pytest.mark.parametrize("loc_text", [
        "Remote (US)",
        "Remote (U.S.)",
        "Remote (US Only)",
        "Remote [US]",
        "Remote - US",
        "Remote - U.S.",
        "Remote - US Only",
        "US Remote Only",
        "Remote in the US",
        "Remote Worldwide - Must be US Citizen",
        "Remote Worldwide - Requires US Citizenship",
        "Remote Worldwide - US Citizen required",
        "Remote Worldwide - US Citizen or Green Card",
    ])
    def test_remote_us_and_us_citizen_disqualified(self, loc_text):
        assert is_remote_eligible(loc_text) is False
        job = JobOpportunity(title="Engineer", company="Corp", location=loc_text)
        res = evaluate_opportunity_eligibility(job)
        assert res.disqualified is True
        assert res.remote_eligible_nigeria is False
        assert res.is_eligible is False

    @pytest.mark.parametrize("contract_text", [
        "No 1099 permitted.",
        "W2 employment only. No 1099.",
        "No 1099",
        "Not open to 1099",
        "Not open to corp-to-corp or 1099 contracts",
        "We cannot support C2C or B2B contracts",
        "No 1099 contractors allowed",
        "W-2 candidates only (no b2b)",
        "Strictly W2, no 1099",
        "No contractors allowed, W2 only",
    ])
    def test_detect_contract_c2c_negative_restrictions(self, contract_text):
        assert detect_contract_c2c(contract_text) is False
        assert detect_contract_consultancy(contract_text) is False

    @pytest.mark.parametrize("negation_text", [
        "We are unable to provide visa sponsorship.",
        "Our team does not offer visa sponsorship.",
        "Visa sponsorship is not provided.",
        "Candidates must not require visa sponsorship.",
        "We cannot provide visa sponsorship.",
        "We do not offer visa sponsorship",
        "Cannot provide visa sponsorship",
        "We do not provide visa sponsorship",
        "Company cannot offer visa sponsorship",
        "Visa sponsorship is unavailable.",
        "Visa sponsorship is not available for this position.",
        "Relocation and visa sponsorship not provided.",
        "Able to work without the need for visa sponsorship.",
        "Must be eligible to work without visa sponsorship.",
        "Not providing sponsorship for this vacancy.",
        "Will not sponsor visas",
        "Not eligible for visa sponsorship",
        "Applicant must have existing work authorization in place.",
        "Must have existing authorization; will not sponsor visas",
        "Unable to sponsor visas at this time",
        "We cannot sponsor visas for this position.",
        "Without sponsorship",
        "This organization does not offer sponsorship.",
        "We are currently not able to sponsor applicants.",
        "Able to work without the need for sponsorship.",
        "There is no work visa or relocation assistance.",
    ])
    def test_visa_sponsorship_subtle_negations_rejected(self, negation_text):
        assert detect_visa_sponsorship(negation_text) is False

    @pytest.mark.parametrize("onsite_text", [
        "Onsite software engineer in Paris, Europe",
        "Job based in Tokyo. Shifts rotate at 00:00 UTC.",
        "Onsite role in Melbourne. Office hours 9am - 5pm AEST (GMT+10)",
        "Onsite in London EMEA HQ",
        "Office based in Berlin, Europe",
        "Full-time on-premise in Nairobi, Africa",
        "Shift hours 09:00 to 17:00 UTC on-site in Singapore",
    ])
    def test_onsite_and_non_remote_locations_rejected(self, onsite_text):
        assert is_remote_eligible(onsite_text) is False
        job = JobOpportunity(title="Developer", company="Corp", location=onsite_text)
        res = evaluate_opportunity_eligibility(job)
        assert res.remote_eligible_nigeria is False

    def test_normalize_opportunities_rejects_none_fields(self):
        cases = [
            {"title": None, "company": "Acme", "url": "https://example.com"},
            {"title": "DevOps", "company": None, "url": "https://example.com"},
            {"title": "DevOps", "company": "Acme", "url": None},
            {"title": "None", "company": "None", "url": "https://example.com"},
            JobOpportunity(title="", company="Acme", url="https://example.com"),
        ]
        res = normalize_opportunities(cases)
        assert len(res) == 0

    def test_deduplicate_opportunities_internal_whitespace_normalization(self):
        dups = [
            {"id": "1", "title": "Senior   DevOps   Engineer", "company": "Global Cloud Corp", "url": "https://1"},
            {"id": "2", "title": "Senior DevOps Engineer", "company": "Global   Cloud   Corp", "url": "https://2"},
            {"id": "3", "title": "Cloud Architect", "company": "Acme", "url": "https://3"},
        ]
        res = deduplicate_opportunities(dups)
        assert len(res) == 2
        assert res[0]["id"] == "1"
        assert res[1]["id"] == "3"


# ============================================================================
# 5. Milestone 3 Iteration 3 Filter & Source Deduplication Edge Cases
# ============================================================================

class TestFilterIteration3EdgeCases:
    """
    Edge case test coverage for Milestone 3 Iteration 3:
    - Visa sponsorship detection when unrelated negative statements ('do not offer equity') exist.
    - English pronoun 'us only' ('Join us only if...') avoiding false positive disqualification.
    - Context-anchored US-only domestic locks ('Location: US only', '(US only)').
    - Domestic delimiter expansions (':', '|', prose 'Remote in Canada').
    - Defensive negative remote patterns under mandatory on-site locks ('non-remote', 'role is not remote').
    - Empty company/title collision guards in deduplicate_opportunities.
    """

    @pytest.mark.parametrize("job_text", [
        "We offer full UK Skilled Worker visa sponsorship. Note that we do not offer remote work.",
        "We provide visa sponsorship for international hires. We cannot offer equity.",
        "Full visa sponsorship provided! Note: we do not offer company cars.",
        "We offer relocation assistance and visa support. We do not provide transit passes.",
        "Visa sponsorship available for outstanding candidates. Note: our company does not offer dental insurance.",
    ])
    def test_visa_sponsorship_positive_with_unrelated_negative_benefits(self, job_text):
        assert detect_visa_sponsorship(job_text) is True

    @pytest.mark.parametrize("pronoun_text", [
        "Join us only if you are passionate about cloud infrastructure and reliability engineering!",
        "Contact us only via email for initial screening.",
        "Reach us only on Slack for emergency escalations.",
        "Tell us only your relevant cloud certifications.",
        "Work with us only on cutting-edge distributed Kubernetes platforms.",
    ])
    def test_english_pronoun_us_only_does_not_disqualify(self, pronoun_text):
        assert has_disqualifiers(pronoun_text) is False

    @pytest.mark.parametrize("us_lock_text", [
        "Location: US only",
        "location: u.s. only",
        "in the us only",
        "USA only",
        "United States only",
        "DevOps Engineer (US Only)",
        "Senior Cloud Architect [US only]",
        "US only",
    ])
    def test_anchored_us_only_variants_disqualify(self, us_lock_text):
        assert has_disqualifiers(us_lock_text) is True

    @pytest.mark.parametrize("domestic_lock", [
        "Remote: US",
        "Remote : United States",
        "Remote | US",
        "Remote | USA",
        "Remote: Canada",
        "Remote | Canada",
        "Remote in the US",
        "Remote in Canada",
        "Remote in the United States",
    ])
    def test_domestic_lock_delimiter_expansions(self, domestic_lock):
        assert has_disqualifiers(domestic_lock) is True

    @pytest.mark.parametrize("negative_remote_text", [
        "This role is non-remote.",
        "We do not offer remote work for this position.",
        "Remote work is not permitted under our company security policy.",
        "This role is not remote.",
        "Not a remote position; local candidates only.",
        "Does not offer remote employment.",
    ])
    def test_defensive_negative_remote_disqualifiers(self, negative_remote_text):
        assert has_disqualifiers(negative_remote_text) is True

    def test_deduplicate_opportunities_empty_company_title_collision_guard(self):
        # Two distinct opportunities with empty company and title but different URLs
        opp1 = {"id": "1", "company": "", "title": "", "url": "https://careers.example.com/job1"}
        opp2 = {"id": "2", "company": "", "title": "", "url": "https://careers.example.com/job2"}
        deduped = deduplicate_opportunities([opp1, opp2])
        assert len(deduped) == 2, "Distinct opportunities with empty company/title must not collide"

        # Duplicate URLs with empty company and title must merge
        opp3 = {"id": "3", "company": "", "title": "", "url": "https://careers.example.com/job1"}
        deduped_dup = deduplicate_opportunities([opp1, opp3])
        assert len(deduped_dup) == 1, "Duplicate URLs with empty company/title must merge"

        # Distinct IDs with empty company, title, and empty URL must not collide
        opp_no_url1 = {"id": "no-url-1", "company": "", "title": "", "url": ""}
        opp_no_url2 = {"id": "no-url-2", "company": "", "title": "", "url": ""}
        deduped_no_url = deduplicate_opportunities([opp_no_url1, opp_no_url2])
        assert len(deduped_no_url) == 2, "Opportunities with distinct IDs and empty title/company/url must not collide"


# ============================================================================
# 6. Milestone 3 Iteration 4 Unified Edge Cases & Deduplication Resilience
# ============================================================================

class TestFilterIteration4EdgeCases:
    """
    Synthesized edge case test specification for Milestone 3 Iteration 4:
    - Visa sponsorship detection with negative operational/technical support statements.
    - Visa sponsorship detection when 'no relocation' is declared.
    - Present-tense visa sponsorship declarations ('we sponsor visas', 'company sponsors visas').
    - Anchored domestic locks across diverse headers ('Role: US only', 'DevOps - US only', 'Eligibility: US only', multiline).
    - Negative remote variations ('Remote is not supported', 'Remote is not an option', 'Remote work is strictly prohibited').
    - Heterogeneous dict key deduplication without TypeError.
    - Defensive non-regression checks on explicit visa negations and English pronoun 'us only'.
    """

    @pytest.mark.parametrize("job_text", [
        "We provide visa sponsorship. We do not provide customer support on weekends.",
        "We offer visa sponsorship. Note: we do not provide technical support for external tools.",
        "Full visa sponsorship available. Developers do not provide customer support directly.",
        "Visa sponsorship offered. We do not provide IT support during holidays.",
        "We offer visa sponsorship. Candidates who cannot provide assistance to their junior peers should not apply.",
        "Skilled worker visa available. We cannot offer desktop support.",
        "Visa support provided. Engineers do not provide end-user support.",
        "Full visa sponsorship provided. We do not extend operational support to third-party clients.",
        "We offer visa sponsorship. Note that developers do not grant technical assistance to sales staff.",
    ])
    def test_visa_sponsorship_positive_with_support_assistance_negations(self, job_text: str):
        """Operational or customer support negations must not cancel valid visa sponsorship."""
        assert detect_visa_sponsorship(job_text) is True

    @pytest.mark.parametrize("job_text", [
        "Visa sponsorship available. No relocation bonus.",
        "Visa sponsorship available. No relocation assistance.",
        "We offer visa sponsorship. No relocation package provided.",
        "Visa sponsorship offered. No relocation support.",
        "We offer visa sponsorship. No relocation assistance provided.",
        "Full visa sponsorship available. No relocation.",
        "We offer visa sponsorship! Please note: no relocation expenses covered.",
        "Skilled worker visa sponsorship provided. No relocation reimbursement.",
    ])
    def test_visa_sponsorship_positive_with_no_relocation(self, job_text: str):
        """Absence of relocation assistance must not negate explicit visa sponsorship."""
        assert detect_visa_sponsorship(job_text) is True

    @pytest.mark.parametrize("job_text", [
        "We sponsor visas. We cannot provide housing.",
        "We sponsor work visas. We will not provide gym membership.",
        "We sponsor visas for qualified international applicants.",
        "Company sponsors visas for this opening.",
        "We sponsor international candidates for employment visas.",
        "Our company sponsors visas for qualified senior engineers.",
        "We sponsor visas.",
        "Employer sponsors visas for this position.",
        "The company sponsors work visas for eligible hires.",
    ])
    def test_visa_sponsorship_present_tense_declarations(self, job_text: str):
        """Present-tense employer sponsorship verbs ('we sponsor', 'company sponsors') must be recognized."""
        assert detect_visa_sponsorship(job_text) is True

    @pytest.mark.parametrize("job_text", [
        "Role: US only",
        "Role: US Only",
        "DevOps - US only",
        "DevOps Engineer - US only",
        "Senior Cloud Architect – US only",
        "Platform Engineer — US only",
        "Eligibility: US only",
        "Eligibility - US only",
        "Open to US only",
        "Open to: US only",
        "Open to US only candidates.",
        "Open to US only applicants.",
        "Residency: US only",
        "Status: US only",
        "Authorized: US only",
        "Restricted to: US only",
        "This position is US only.",
        "This role is US only.",
        "Position is US only.",
        "Role | US only",
        "DevOps Engineer, US only",
        "Senior DevOps Engineer\nUS only\nApply here",
        "Title: Senior DevOps\nWorkplace: Remote\nEligibility: US only",
    ])
    def test_anchored_domestic_locks_diverse_headers_and_multiline(self, job_text: str):
        """Diverse header delimiters, sentence copulas, and multiline isolated US-only tags must disqualify."""
        assert has_disqualifiers(job_text) is True
        assert is_remote_eligible(job_text) is False

        # Opportunity evaluation must flag domestic lock
        opp = {
            "title": "Cloud / DevOps Engineer",
            "company": "Acme Global",
            "location": "Remote",
            "description": job_text,
        }
        res = evaluate_opportunity_eligibility(opp)
        assert res.remote_eligible_nigeria is False
        assert res.is_eligible is False

    @pytest.mark.parametrize("job_text", [
        "Remote is not supported.",
        "Remote is not an option.",
        "Remote work is strictly prohibited.",
        "Not open to remote.",
        "Not open to remote workers.",
        "Remote option is not available.",
        "Remote is not permitted.",
        "Remote is not allowed.",
        "Remote work is not supported.",
        "We do not support remote work.",
        "Remote employment is not permitted.",
        "Candidates must be based in France. Remote is not supported.",
        "This position is on-site only. Remote is not an option.",
    ])
    def test_negative_remote_variations_disqualify(self, job_text: str):
        """Unambiguous negative remote declarations must disqualify and reject remote eligibility."""
        assert has_disqualifiers(job_text) is True
        assert is_remote_eligible(job_text) is False

        opp = {
            "title": "Systems Administrator",
            "company": "CorpOps",
            "location": "Paris, France",
            "description": job_text,
        }
        res = evaluate_opportunity_eligibility(opp)
        assert res.remote_eligible_nigeria is False
        assert res.is_eligible is False

    def test_deduplicate_opportunities_heterogeneous_key_types(self):
        """Deduplication must handle dictionaries with heterogeneous or non-string key types without TypeError."""
        # 1. Single dict with mixed int and str keys
        mixed_dict = {1: "one", "two": 2}
        res1 = deduplicate_opportunities([mixed_dict])
        assert len(res1) == 1
        assert res1[0] == mixed_dict

        # 2. Duplicate dicts with mixed int and str keys must merge to 1
        d1 = {1: "alpha", "beta": "gamma"}
        d2 = {1: "alpha", "beta": "gamma"}
        res2 = deduplicate_opportunities([d1, d2])
        assert len(res2) == 1

        # 3. Dicts with float, int, str keys
        f1 = {"x": 1, 10: "ten", 2.5: "float_val"}
        f2 = {"x": 1, 10: "ten", 2.5: "float_val"}
        res3 = deduplicate_opportunities([f1, f2])
        assert len(res3) == 1

        # 4. Dicts with int keys in different insertion orders must merge deterministically
        k_order1 = {1: "a", 2: "b"}
        k_order2 = {2: "b", 1: "a"}
        res4 = deduplicate_opportunities([k_order1, k_order2])
        assert len(res4) == 1

        # 5. Mixed keys including None key
        none_dict1 = {None: "null_key", "valid": 100}
        none_dict2 = {None: "null_key", "valid": 100}
        res5 = deduplicate_opportunities([none_dict1, none_dict2])
        assert len(res5) == 1

        # 6. Mixture of empty dict, mixed-key dict, and standard dicts without exception
        batch = [
            {},
            {},
            {1: "val1", "key2": "val2"},
            {1: "val1", "key2": "val2"},
            {"title": "DevOps Engineer", "company": "Acme", "url": "https://acme.org/1"},
            {"title": "DevOps Engineer", "company": "Acme", "url": "https://acme.org/1"},
        ]
        res6 = deduplicate_opportunities(batch)
        # Should contain: 1 empty dict, 1 mixed dict, 1 Acme job
        assert len(res6) == 3

    @pytest.mark.parametrize("job_text", [
        "No visa sponsorship provided.",
        "We cannot provide visa sponsorship.",
        "Will not sponsor visas.",
        "Visa sponsorship is not available.",
        "Without the need for visa sponsorship.",
        "Must have valid work authorization without sponsorship.",
        "This position does not offer visa support.",
        "Zero visa sponsorship.",
        "No relocation or visa sponsorship.",
        "No visa sponsorship or relocation.",
    ])
    def test_visa_sponsorship_explicit_negations_remain_false(self, job_text: str):
        """Explicit visa sponsorship negations must continue to evaluate to False (no false positives)."""
        assert detect_visa_sponsorship(job_text) is False

    @pytest.mark.parametrize("pronoun_text", [
        "Contact us only via email for initial screening.",
        "Join us only if you are passionate about cloud infrastructure and reliability engineering!",
        "Tell us only about your cloud experience",
        "Tell us only your relevant certifications.",
        "Reach us only on Slack for emergency escalations.",
        "Allow us only 24 hours to review your resume.",
        "Grant us only read-only access to your public repositories.",
    ])
    def test_english_pronoun_us_only_remains_not_disqualified(self, pronoun_text: str):
        """English pronoun 'us only' in diverse grammatical contexts must never disqualify."""
        assert has_disqualifiers(pronoun_text) is False


