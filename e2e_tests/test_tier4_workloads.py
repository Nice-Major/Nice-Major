"""
Tier 4: Real-World Application Scenarios Test Suite
Comprehensive, end-to-end operational career & consultancy workflows:
- Worldwide remote role discovery (Nigeria eligible) scoring 85+, tailoring CV & cover letter, dispatching digest.
- High-match UK/EU visa sponsorship opportunity evaluation.
- Stepcon Solutions (RC - 8284984) B2B corporate tender proposal generation.
- Adversarial gatekeeper: US-only & security clearance immediate rejection.
- Stale & zombie job posting verification and elimination.
"""
import os
import sys
import json
import pathlib
import pytest
from e2e_tests.conftest import get_module_or_skip, PROJECT_ROOT, CANONICAL_PROFILE_PATH


class TestTier4RealWorldWorkloads:
    """End-to-end realistic production workload scenarios."""

    def test_scenario1_nigeria_remote_devops_flow(self, canonical_profile_data, temp_output_dir):
        """
        Scenario 1: Full career pipeline for discovering a Worldwide remote role open to Nigeria.
        1. Ingest candidate profile.
        2. Match opportunity (Senior DevOps & Kubernetes Engineer - Worldwide Remote).
        3. Score opportunity against candidate profile (expect >= 85%).
        4. Tailor ATS-compliant Markdown CV & STAR Cover Letter.
        5. Package into daily 8:00 AM WAT email digest.
        6. Verify .eml export in dry-run mode without live SMTP or paid APIs.
        """
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")

        # Opportunity definition
        remote_role = {
            "title": "Staff Platform & DevOps Engineer",
            "company": "KubeScale Technologies Inc.",
            "location": "Remote - Worldwide (EMEA / UTC+1 Synchronous)",
            "url": "https://careers.kubescale.example/jobs/platform-77",
            "description": (
                "KubeScale is seeking a Staff Platform & DevOps Engineer to scale our multi-cloud infrastructure. "
                "Requirements: 5+ years experience in Kubernetes (KCNA preferred), Terraform Infrastructure as Code, "
                "AWS & Azure cloud estates, CI/CD with GitHub Actions, and container security. Must maintain 99.9% uptime SLA."
            ),
            "posted_date": "2026-11-05"
        }

        # Step 1 & 2: Score role against candidate
        score_result = scorer_mod.evaluate_job(canonical_profile_data, remote_role["description"])
        assert score_result.overall_score >= 85.0
        assert "Strong Apply" in score_result.rationale or score_result.overall_score >= 80.0

        # Step 3: Tailor documents
        cv_content = cv_mod.generate_cv(canonical_profile_data, remote_role["description"], "DevOps Engineer", "md")
        letter_content = letter_mod.generate_cover_letter(
            canonical_profile_data,
            remote_role["description"],
            "DevOps Engineer",
            company_name=remote_role["company"]
        )

        assert "John Victor Aniekwe" in cv_content
        assert "KCNA" in cv_content or "Kubernetes" in cv_content
        assert "KubeScale Technologies Inc." in letter_content
        assert "99.9%" in letter_content

        # Step 4 & 5: Build email digest with attachments
        attachments = [
            ("John_Victor_Aniekwe_DevOps_Engineer_CV.md", cv_content.encode("utf-8")),
            ("John_Victor_Aniekwe_DevOps_Engineer_Cover_Letter.txt", letter_content.encode("utf-8"))
        ]
        msg = digest_mod.build_digest_email([remote_role], attachments=attachments)

        # Step 6: Dispatch in dry-run mode
        eml_file = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))
        assert os.path.exists(eml_file)
        assert eml_file.endswith(".eml")

        with open(eml_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_eml = f.read()
        assert "aniekwevictor9@gmail.com" in raw_eml
        assert "Daily Career" in raw_eml

    def test_scenario2_visa_sponsorship_architect_flow(self, canonical_profile_data, temp_output_dir):
        """
        Scenario 2: High-Match UK/EU Visa Sponsorship Opportunity.
        1. Opportunity offers UK Skilled Worker Visa / Relocation in London.
        2. Verify geo/visa filter tags role as [VISA_SPONSORSHIP].
        3. Match score evaluates to >= 80%.
        4. Cover letter emphasizes relocation readiness and verified AWS/KCNA credentials.
        5. Verify top table placement in email digest.
        """
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")

        visa_role = {
            "title": "Cloud Solutions Architect (Multi-Cloud)",
            "company": "Metropolitan Cloud Partners UK",
            "location": "London, UK (Visa Sponsorship Available / Full Relocation)",
            "url": "https://careers.metropolitancloud.example/csa-uk",
            "description": (
                "Metropolitan Cloud Partners is hiring a Cloud Solutions Architect to lead enterprise migrations across AWS and Azure. "
                "Must apply the Well-Architected Framework, design microservices on Kubernetes, and ensure 99.9% uptime SLA. "
                "We provide full UK Skilled Worker Visa Sponsorship and relocation assistance."
            ),
            "posted_date": "2026-11-04"
        }

        # Step 1: Detect visa sponsorship
        has_visa = filter_mod.detect_visa_sponsorship(visa_role["description"])
        assert has_visa is True

        # Step 2: Score match
        score = scorer_mod.evaluate_job(canonical_profile_data, visa_role["description"])
        assert score.overall_score >= 80.0

        # Step 3: Tailor cover letter
        letter = letter_mod.generate_cover_letter(
            canonical_profile_data,
            visa_role["description"],
            "Cloud Solutions Architect",
            company_name=visa_role["company"]
        )
        assert "Metropolitan Cloud Partners UK" in letter
        assert "Solutions Architect" in letter

        # Step 4: Verify digest includes visa opportunity
        digest_html = digest_mod.format_digest_html([visa_role])
        assert "Metropolitan Cloud Partners UK" in digest_html

    def test_scenario3_stepcon_b2b_tender_proposal_flow(self, canonical_profile_data, synthetic_tenders):
        """
        Scenario 3: Stepcon Solutions (RC - 8284984) Enterprise B2B Tender Proposal Flow.
        1. Evaluate Pan-African Financial Group Cloud Modernization RFP.
        2. Match score against Stepcon capabilities evaluates >= 70%.
        3. Generate full corporate commercial proposal referencing:
           - Stepcon Solutions (RC - 8284984)
           - Lead Architect John Victor Aniekwe (KCNA, AWS SAA, B.Sc. Comp Sci)
           - 99.9% SLA commitment
           - C2C contracting terms in synchronous CET/EMEA hours.
        """
        tender_mod = get_module_or_skip("consultancy.tenders", "F14", "M5")
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")

        stepcon = canonical_profile_data["stepconSolutions"]
        tender = synthetic_tenders["matching"]

        # Step 1 & 2: Score tender
        eval_result = tender_mod.evaluate_tender(stepcon, tender["description"])
        assert eval_result.overall_score >= 70.0

        # Step 3: Generate corporate proposal
        proposal = prop_mod.generate_proposal(stepcon, tender)

        assert "Stepcon Solutions" in proposal
        assert "RC - 8284984" in proposal
        assert "John Victor Aniekwe" in proposal
        assert "99.9%" in proposal
        assert "Corp-to-Corp" in proposal or "C2C" in proposal

    def test_scenario4_adversarial_clearance_and_us_gatekeeper(self, synthetic_jobs):
        """
        Scenario 4: Adversarial Gatekeeper - Immediate Rejection of US-only / Clearance roles.
        1. Given job posting with "US Citizen Only" and "Active TS/SCI Clearance".
        2. Ensure filter rejects candidate eligibility with 0% false positives.
        3. Verify job is cleanly excluded from candidate's daily email digest.
        """
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")

        disqualifying_job = synthetic_jobs["us_only"]
        is_eligible = filter_mod.is_remote_eligible(disqualifying_job["location"] + " " + disqualifying_job["description"])
        assert is_eligible is False

        # Verify excluded from digest when filtered list is passed
        eligible_jobs = [disqualifying_job] if is_eligible else []
        digest_html = digest_mod.format_digest_html(eligible_jobs)
        assert "American Defense Systems" not in digest_html

    def test_scenario5_stale_and_closed_job_elimination(self, synthetic_jobs):
        """
        Scenario 5: Stale & Zombie Job Elimination.
        1. Stale job posted 90 days ago -> rejected (> 30 days).
        2. Closed job with DOM marker "This position has been filled" -> rejected.
        3. Verify neither is accepted into active opportunity stream.
        """
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")

        # Stale test
        stale_job = synthetic_jobs["stale"]
        is_fresh = ver_mod.is_fresh_date(stale_job["posted_date"], max_days=30)
        assert is_fresh is False

        # Closed test
        closed_job = synthetic_jobs["closed"]
        is_closed = ver_mod.detect_closed_phrase(closed_job["description"])
        assert is_closed is True
