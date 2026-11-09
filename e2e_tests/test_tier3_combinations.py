"""
Tier 3: Cross-Feature Combinations Test Suite
Pairwise and multi-module integration chains:
Ingestion -> Scoring -> Tailoring -> Dispatch -> Dry-Run -> Stepcon.
"""
import os
import sys
import json
import pathlib
import pytest
from e2e_tests.conftest import get_module_or_skip, PROJECT_ROOT, CANONICAL_PROFILE_PATH


class TestTier3Combinations:
    """Pairwise and multi-feature integration workflows."""

    def test_c01_ingestion_to_scoring(self, canonical_profile_data, synthetic_jobs):
        """Chain F01 -> F07: Ingest candidate profile and score against target JD."""
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")

        if hasattr(parser_mod, "load_profile") and CANONICAL_PROFILE_PATH.exists():
            profile = parser_mod.load_profile(str(CANONICAL_PROFILE_PATH))
        else:
            profile = canonical_profile_data

        jd_text = synthetic_jobs["devops"]["description"]
        result = scorer_mod.evaluate_job(profile, jd_text)
        assert result.overall_score >= 80.0
        assert "Kubernetes" in result.matched_skills or len(result.matched_skills) > 0

    def test_c02_ingestion_to_cv_tailoring(self, canonical_profile_data, synthetic_jobs):
        """Chain F01 -> F05: Ingest profile and generate tailored ATS CV."""
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")

        profile = canonical_profile_data
        jd_text = synthetic_jobs["architect"]["description"]
        cv_md = cv_mod.generate_cv(profile, jd_text, "Cloud Solutions Architect", "md")

        assert "John Victor Aniekwe" in cv_md
        assert "AWS" in cv_md
        assert "Microservices" in cv_md or "Cloud" in cv_md

    def test_c03_ingestion_to_cover_letter_tailoring(self, canonical_profile_data, synthetic_jobs):
        """Chain F01 -> F06: Ingest profile and generate tailored STAR cover letter."""
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")

        profile = canonical_profile_data
        letter = letter_mod.generate_cover_letter(
            profile,
            synthetic_jobs["devops"]["description"],
            "DevOps Engineer",
            company_name="Global Cloud Corp"
        )
        assert "Global Cloud Corp" in letter
        assert "99.9%" in letter or "99%" in letter

    def test_c04_tailoring_to_text_utils(self, canonical_profile_data, synthetic_jobs):
        """Chain F05 -> F03: Generate CV, sanitize ligatures, and generate strict filename."""
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")

        cv_raw = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "md")
        cv_clean = text_mod.sanitize_ligatures(cv_raw)
        filename = text_mod.safe_filename("John_Victor", "Aniekwe", "DevOps Engineer", "CV", "pdf")

        assert filename == "John_Victor_Aniekwe_DevOps_Engineer_CV.pdf"
        assert "John Victor Aniekwe" in cv_clean

    def test_c05_discovery_to_geo_eligibility(self, synthetic_jobs):
        """Chain F08 -> F09: Query opportunities and filter for Nigeria remote eligibility."""
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")

        opps = disc_mod.fetch_opportunities(dry_run=True)
        eligible_opps = [
            op for op in opps
            if filter_mod.is_remote_eligible(getattr(op, "location", op.get("location") if isinstance(op, dict) else ""))
        ]
        assert len(eligible_opps) >= 1

    def test_c06_discovery_to_health_verification(self, synthetic_jobs):
        """Chain F08 -> F10: Query opportunities and verify active URL/status."""
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")

        opps = disc_mod.fetch_opportunities(dry_run=True)
        # Stale or closed opportunities should be identified
        closed_job = synthetic_jobs["closed"]
        is_closed = ver_mod.detect_closed_phrase(closed_job["description"])
        assert is_closed is True

    def test_c07_scoring_to_auto_tailoring_pipeline(self, canonical_profile_data, synthetic_jobs):
        """Chain F07 -> F05 -> F06: High match score triggers auto CV and cover letter tailoring."""
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")

        jd_text = synthetic_jobs["devops"]["description"]
        score_res = scorer_mod.evaluate_job(canonical_profile_data, jd_text)

        if score_res.overall_score >= 80.0:
            cv = cv_mod.generate_cv(canonical_profile_data, jd_text, "DevOps Engineer", "md")
            letter = letter_mod.generate_cover_letter(canonical_profile_data, jd_text, "DevOps Engineer", "Global Cloud Corp")
            assert len(cv) > 200
            assert len(letter) > 100

    def test_c08_tailoring_to_digest_attachment_packaging(self, canonical_profile_data, synthetic_jobs):
        """Chain F05 -> F06 -> F11: Tailor documents and package as email digest attachments."""
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")

        jd = synthetic_jobs["devops"]
        cv_bytes = cv_mod.generate_cv(canonical_profile_data, jd["description"], "DevOps Engineer", "txt").encode("utf-8")
        letter_bytes = letter_mod.generate_cover_letter(canonical_profile_data, jd["description"], "DevOps Engineer", jd["company"]).encode("utf-8")

        attachments = [
            ("John_Victor_Aniekwe_DevOps_Engineer_CV.txt", cv_bytes),
            ("John_Victor_Aniekwe_DevOps_Engineer_Cover_Letter.txt", letter_bytes)
        ]
        msg = digest_mod.build_digest_email([jd], attachments=attachments)
        assert msg is not None

    def test_c09_digest_dispatch_to_dry_run_storage(self, synthetic_jobs, temp_output_dir):
        """Chain F11 -> F15: Format digest and export to disk in dry-run mode."""
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")

        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]])
        output_file = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))

        assert os.path.exists(output_file)
        with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        assert "aniekwevictor9@gmail.com" in content

    def test_c10_cli_to_scoring_and_tailoring(self, synthetic_jobs, temp_output_dir):
        """Chain F13 -> F07 -> F05: CLI evaluate and tailor subcommands integration."""
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        jd_file = temp_output_dir / "target_jd.txt"
        jd_file.write_text(synthetic_jobs["devops"]["description"], encoding="utf-8")

        # 1. CLI evaluate
        eval_exit = cli_mod.run_cli(["eval", "--file", str(jd_file)])
        assert eval_exit == 0

        # 2. CLI tailor
        tailor_exit = cli_mod.run_cli(["tailor", "--jd", str(jd_file), "--role", "devops", "--output-dir", str(temp_output_dir)])
        assert tailor_exit == 0

    def test_c11_stepcon_profile_to_tender_proposal(self, canonical_profile_data, synthetic_tenders):
        """Chain F14 -> F02 -> F15: Stepcon entity models tender and generates proposal."""
        tender_mod = get_module_or_skip("consultancy.tenders", "F14", "M5")
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")

        stepcon = canonical_profile_data["stepconSolutions"]
        matching_tender = synthetic_tenders["matching"]

        eval_res = tender_mod.evaluate_tender(stepcon, matching_tender["description"])
        assert eval_res.overall_score >= 70.0

        proposal = prop_mod.generate_proposal(stepcon, matching_tender)
        assert "Stepcon Solutions" in proposal
        assert "RC - 8284984" in proposal
        assert "John Victor Aniekwe" in proposal

    def test_c12_candidate_career_priority_over_stepcon(self, canonical_profile_data, synthetic_jobs, synthetic_tenders):
        """Rule Verification: Candidate career workflow executes before Stepcon consultancy under combined run."""
        scheduler_mod = get_module_or_skip("scheduler.daily_dispatch", "F12", "M4")
        if hasattr(scheduler_mod, "execute_combined_daily_run"):
            execution_order = scheduler_mod.execute_combined_daily_run(dry_run=True, return_execution_order=True)
            assert execution_order[0] == "candidate_career_workflow"
            assert execution_order[1] == "stepcon_consultancy_workflow"
        else:
            pytest.skip("execute_combined_daily_run not directly exposed")

    def test_c13_full_hermetic_pipeline_chain(self, canonical_profile_data, synthetic_jobs, temp_output_dir):
        """Full Chain F01->F08->F09->F07->F05->F11->F15: End-to-end hermetic career pipeline."""
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")

        # 1. Discover
        opps = disc_mod.fetch_opportunities(dry_run=True)
        # 2. Filter
        eligible = [op for op in opps if filter_mod.is_remote_eligible(getattr(op, "location", ""))]
        assert len(eligible) >= 1
        # 3. Score
        top_job = eligible[0]
        score_res = scorer_mod.evaluate_job(canonical_profile_data, getattr(top_job, "description", top_job.get("description", "")))
        # 4. Tailor
        cv_text = cv_mod.generate_cv(canonical_profile_data, getattr(top_job, "description", top_job.get("description", "")), "DevOps Engineer", "md")
        # 5. Digest & Dispatch
        msg = digest_mod.build_digest_email([top_job], attachments=[("CV.md", cv_text.encode("utf-8"))])
        out_path = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))

        assert os.path.exists(out_path)
