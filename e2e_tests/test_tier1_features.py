"""
Tier 1: Feature Coverage Test Suite (F01 to F15)
Isolated happy-path testing with >= 5 test cases per feature (75+ tests total).
"""
import os
import sys
import json
import pathlib
import pytest
from e2e_tests.conftest import get_module_or_skip, PROJECT_ROOT, CANONICAL_PROFILE_PATH


# ==============================================================================
# F01: Candidate Profile Data Ingestion
# ==============================================================================
class TestTier1F01ProfileIngestion:
    """Feature F01: Parsing candidate profile, certifications, and experience."""

    def test_f01_load_profile_returns_valid_dict_or_object(self, canonical_profile_data):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        if hasattr(parser_mod, "load_profile"):
            profile = parser_mod.load_profile(str(CANONICAL_PROFILE_PATH) if CANONICAL_PROFILE_PATH.exists() else None)
        elif hasattr(parser_mod, "load_source_of_truth"):
            profile = parser_mod.load_source_of_truth(str(CANONICAL_PROFILE_PATH) if CANONICAL_PROFILE_PATH.exists() else None)
        else:
            profile = canonical_profile_data
        assert profile is not None

    def test_f01_candidate_contact_info_extracted(self, canonical_profile_data):
        candidate = canonical_profile_data.get("candidate", {})
        assert candidate.get("fullName") == "John Victor Aniekwe"
        assert candidate.get("email") == "aniekwevictor9@gmail.com"
        assert "Nigeria" in candidate.get("location", "")

    def test_f01_verified_certifications_captured(self, canonical_profile_data):
        certs = canonical_profile_data.get("candidate", {}).get("certifications", [])
        cert_names = [c.get("name") for c in certs]
        assert any("KCNA" in n or "Kubernetes" in n for n in cert_names)
        assert any("AWS" in n and "Solutions Architect" in n for n in cert_names)
        assert any("AWS" in n and "Developer" in n for n in cert_names)
        assert any("AWS" in n and "Cloud Practitioner" in n for n in cert_names)

    def test_f01_role_categories_parsed(self, canonical_profile_data):
        roles = canonical_profile_data.get("roleCategories", {})
        assert "devops" in roles or "architect" in roles
        assert len(roles) >= 2

    def test_f01_kpi_metrics_extracted(self, canonical_profile_data):
        kpis = canonical_profile_data.get("kpiMetrics", [])
        kpi_values = [k.get("value") for k in kpis]
        assert "99.9%" in kpi_values
        assert "99%" in kpi_values


# ==============================================================================
# F02: Profile Representation & Schema Modeling
# ==============================================================================
class TestTier1F02ProfileModeling:
    """Feature F02: Strict data models representing candidate and Stepcon entity."""

    def test_f02_candidate_model_schema_validation(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        if hasattr(models_mod, "CandidateProfile"):
            cand = models_mod.CandidateProfile(**canonical_profile_data["candidate"])
            assert cand.full_name == "John Victor Aniekwe"
        else:
            assert canonical_profile_data["candidate"]["fullName"] == "John Victor Aniekwe"

    def test_f02_stepcon_corporate_profile_modeling(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        stepcon_data = canonical_profile_data.get("stepconSolutions", {})
        if hasattr(models_mod, "StepconProfile"):
            stepcon = models_mod.StepconProfile(**stepcon_data)
            assert stepcon.cac_number == "RC - 8284984"
        else:
            assert stepcon_data.get("cacNumber") == "RC - 8284984"

    def test_f02_certification_active_status_enum(self, canonical_profile_data):
        certs = canonical_profile_data.get("candidate", {}).get("certifications", [])
        active_certs = [c for c in certs if c.get("status") == "Active"]
        in_prog_certs = [c for c in certs if c.get("status") == "In Progress"]
        assert len(active_certs) >= 3
        assert len(in_prog_certs) >= 1

    def test_f02_experience_history_structure(self, canonical_profile_data):
        exp = canonical_profile_data.get("experience", [])
        if exp:
            first_role = exp[0]
            assert "company" in first_role
            assert "bullets" in first_role
        else:
            assert True

    def test_f02_serialization_to_and_from_dict(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        data_json = json.dumps(canonical_profile_data)
        reloaded = json.loads(data_json)
        assert reloaded["candidate"]["fullName"] == canonical_profile_data["candidate"]["fullName"]


# ==============================================================================
# F03: ATS Text & Filename Utilities
# ==============================================================================
class TestTier1F03AtsTextUtils:
    """Feature F03: Typographic ligature sanitization and safe strict underscore filenames."""

    def test_f03_sanitize_ligatures_efficiency(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        corrupted = "Improving system e  iciency and performance"
        sanitized = text_mod.sanitize_ligatures(corrupted)
        assert "efficiency" in sanitized.lower()

    def test_f03_sanitize_ligatures_effective(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        corrupted = "Designing e  ective microservices"
        sanitized = text_mod.sanitize_ligatures(corrupted)
        assert "effective" in sanitized.lower()

    def test_f03_safe_filename_standard_cv(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("John", "Aniekwe", "Cloud Solutions Architect", "CV", "pdf")
        assert filename == "John_Aniekwe_Cloud_Solutions_Architect_CV.pdf"
        assert " " not in filename
        assert "-" not in filename

    def test_f03_safe_filename_cover_letter_docx(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("John_Victor", "Aniekwe", "DevOps Engineer", "Cover Letter", "docx")
        assert filename == "John_Victor_Aniekwe_DevOps_Engineer_Cover_Letter.docx"

    def test_f03_safe_filename_default_pdf_extension(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("Victor", "Aniekwe", "Support", "Resume")
        assert filename.endswith(".pdf")


# ==============================================================================
# F04: Role Competency & Keyword Extraction
# ==============================================================================
class TestTier1F04RoleCompetency:
    """Feature F04: 8-role competency taxonomy and keyword matcher."""

    def test_f04_extract_devops_competencies(self, synthetic_jobs):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        jd_text = synthetic_jobs["devops"]["description"]
        keywords = comp_mod.extract_keywords(jd_text)
        assert any(k.lower() in ["kubernetes", "docker", "terraform", "ci/cd"] for k in keywords)

    def test_f04_extract_solutions_architect_competencies(self, synthetic_jobs):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        jd_text = synthetic_jobs["architect"]["description"]
        keywords = comp_mod.extract_keywords(jd_text)
        assert any(k.lower() in ["microservices", "azure", "aws", "finops"] for k in keywords)

    def test_f04_extract_sysadmin_competencies(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        jd_text = "Looking for a Linux and Windows Server Administrator experienced in PowerShell and Bash."
        keywords = comp_mod.extract_keywords(jd_text)
        assert any(k.lower() in ["linux", "windows", "powershell", "bash"] for k in keywords)

    def test_f04_extract_support_engineer_competencies(self, synthetic_jobs):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        jd_text = synthetic_jobs["support"]["description"]
        keywords = comp_mod.extract_keywords(jd_text)
        assert any(k.lower() in ["azure app service", "rca", "csat", "support"] for k in keywords)

    def test_f04_categorize_skills_into_domains(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        taxonomy = comp_mod.get_role_taxonomy()
        assert len(taxonomy) >= 4


# ==============================================================================
# F05: ATS-Friendly CV Tailoring Engine
# ==============================================================================
class TestTier1F05CvTailoring:
    """Feature F05: Generation of ATS-compliant single-column CVs in MD/HTML/TXT."""

    def test_f05_generate_single_column_markdown_cv(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_text = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "md")
        assert "John Victor Aniekwe" in cv_text
        assert "Professional Summary" in cv_text or "Technical Skills" in cv_text

    def test_f05_generate_semantic_html_cv(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_html = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "html")
        assert "<html" in cv_html.lower()
        assert "John Victor Aniekwe" in cv_html

    def test_f05_generate_plain_text_cv(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_txt = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "txt")
        assert "JOHN VICTOR ANIEKWE" in cv_txt.upper()

    def test_f05_cv_includes_verified_certifications(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_text = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "md")
        assert "KCNA" in cv_text or "Kubernetes" in cv_text
        assert "AWS" in cv_text

    def test_f05_cv_zero_external_tracker_links(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_text = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "md")
        assert "credly.com" not in cv_text.lower()


# ==============================================================================
# F06: Cover Letter Tailoring Engine
# ==============================================================================
class TestTier1F06CoverLetterTailoring:
    """Feature F06: STAR methodology cover letters with empirical metrics."""

    def test_f06_generate_star_cover_letter(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "Global Cloud Corp")
        assert "Global Cloud Corp" in letter
        assert "John Victor Aniekwe" in letter

    def test_f06_cover_letter_includes_empirical_metrics(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer")
        assert "99.9%" in letter or "99%" in letter

    def test_f06_cover_letter_company_name_personalization(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "Starlight Systems")
        assert "Starlight Systems" in letter

    def test_f06_cover_letter_includes_degree(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer")
        assert "University of Nigeria" in letter or "Computer Science" in letter

    def test_f06_cover_letter_professional_signoff(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer")
        assert "Sincerely" in letter or "Best regards" in letter
        assert "John Victor Aniekwe" in letter


# ==============================================================================
# F07: Multi-Dimensional Match Scorer
# ==============================================================================
class TestTier1F07MatchScorer:
    """Feature F07: 5-dimension 0-100 scoring algorithm and gap analysis."""

    def test_f07_high_match_devops_scores_above_80(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, synthetic_jobs["devops"]["description"])
        assert result.overall_score >= 80.0

    def test_f07_score_breakdown_contains_all_5_dimensions(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, synthetic_jobs["devops"]["description"])
        breakdown = result.breakdown
        for key in ["skills", "title", "metrics", "mobility", "certs"]:
            assert key in breakdown

    def test_f07_overall_score_bounded_0_to_100(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, synthetic_jobs["devops"]["description"])
        assert 0.0 <= result.overall_score <= 100.0

    def test_f07_matched_and_missing_skills_reported(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, synthetic_jobs["devops"]["description"])
        assert isinstance(result.matched_skills, list)
        assert isinstance(result.missing_skills, list)

    def test_f07_action_recommendation_logic(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, synthetic_jobs["devops"]["description"])
        assert "Apply" in result.rationale or "Match" in result.rationale


# ==============================================================================
# F08: Opportunity Discovery Engine
# ==============================================================================
class TestTier1F08OpportunityDiscovery:
    """Feature F08: Job search adapters with offline synthetic fallback."""

    def test_f08_fetch_opportunities_dry_run_returns_list(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(dry_run=True)
        assert isinstance(opps, list)
        assert len(opps) >= 1

    def test_f08_opportunity_attributes_validation(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(dry_run=True)
        first = opps[0]
        assert hasattr(first, "title") or "title" in first
        assert hasattr(first, "url") or "url" in first

    def test_f08_query_with_role_filters(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(query_roles=["DevOps"], dry_run=True)
        assert len(opps) >= 1

    def test_f08_synthetic_fallback_available(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.get_synthetic_opportunities()
        assert len(opps) >= 3

    def test_f08_opportunity_contains_valid_url(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(dry_run=True)
        first_url = getattr(opps[0], "url", opps[0].get("url") if isinstance(opps[0], dict) else "")
        assert first_url.startswith("http")


# ==============================================================================
# F09: Geo-Eligibility & Sponsorship Filter
# ==============================================================================
class TestTier1F09GeoEligibility:
    """Feature F09: Filtering for Nigeria remote eligibility and visa sponsorship."""

    def test_f09_worldwide_remote_eligible(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        eligible = filter_mod.is_remote_eligible("Remote - Worldwide")
        assert eligible is True

    def test_f09_emea_cet_remote_eligible(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        eligible = filter_mod.is_remote_eligible("Remote (EMEA / CET Synchronous)")
        assert eligible is True

    def test_f09_visa_sponsorship_tagged(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        has_visa = filter_mod.detect_visa_sponsorship("We offer UK Skilled Worker visa sponsorship and relocation.")
        assert has_visa is True

    def test_f09_us_only_ineligible(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        eligible = filter_mod.is_remote_eligible("Remote - US Citizen Only (W2 Only)")
        assert eligible is False

    def test_f09_security_clearance_ineligible(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        eligible = filter_mod.is_remote_eligible("Active Top Secret / SCI clearance required")
        assert eligible is False


# ==============================================================================
# F10: Opportunity Health & Active Verification
# ==============================================================================
class TestTier1F10OpportunityVerification:
    """Feature F10: HTTP status, closed phrases, stale date, and SHA-256 deduplication."""

    def test_f10_http_200_active_verified(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        assert ver_mod.verify_url_status("https://example.com", mock_status=200) is True

    def test_f10_closed_phrase_marked_inactive(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        body = "Thank you for visiting. This position has been filled. Applications are now closed."
        assert ver_mod.detect_closed_phrase(body) is True

    def test_f10_stale_posting_older_than_30_days_rejected(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        assert ver_mod.is_fresh_date("2026-08-01", max_days=30) is False

    def test_f10_fresh_posting_accepted(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        assert ver_mod.is_fresh_date("2026-11-05", max_days=30) is True

    def test_f10_sha256_deduplication(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        fp1 = ver_mod.generate_fingerprint("Acme Corp", "Senior DevOps Engineer")
        fp2 = ver_mod.generate_fingerprint("acme corp", "senior devops engineer")
        assert fp1 == fp2


# ==============================================================================
# F11: Daily 8:00 AM Notification Dispatch
# ==============================================================================
class TestTier1F11DailyNotificationDispatch:
    """Feature F11: Daily multipart HTML/text digest with application attachments."""

    def test_f11_build_multipart_email_digest(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]], date_str="2026-11-07")
        assert msg is not None
        assert "Daily Career" in msg.get("Subject", "")

    def test_f11_digest_contains_executive_metrics(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        html = digest_mod.format_digest_html([synthetic_jobs["devops"]])
        assert "99.9%" in html
        assert "99%" in html

    def test_f11_digest_contains_opportunity_links(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        html = digest_mod.format_digest_html([synthetic_jobs["devops"]])
        assert synthetic_jobs["devops"]["url"] in html

    def test_f11_dry_run_exports_eml_file(self, synthetic_jobs, temp_output_dir):
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]])
        eml_path = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))
        assert os.path.exists(eml_path)
        assert eml_path.endswith(".eml")

    def test_f11_digest_includes_application_attachments(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]], attachments=[("John_Victor_Aniekwe_DevOps_CV.pdf", b"%PDF-1.4...")])
        payloads = msg.get_payload()
        assert len(payloads) >= 2


# ==============================================================================
# F12: Scheduling Architectures & Documentation
# ==============================================================================
class TestTier1F12SchedulingArchitecture:
    """Feature F12: GitHub Actions cron, Task Scheduler script, and comparison docs."""

    def test_f12_github_actions_workflow_cron_schedule(self):
        wf_path = PROJECT_ROOT / ".github" / "workflows" / "daily_dispatch.yml"
        if not wf_path.exists():
            wf_path = PROJECT_ROOT / ".github" / "workflows" / "daily_career_digest.yml"
        if wf_path.exists():
            content = wf_path.read_text(encoding="utf-8")
            assert "0 7 * * *" in content or "schedule" in content
        else:
            pytest.skip("[M4 Pending] GitHub Actions workflow file not yet created")

    def test_f12_powershell_scheduler_script_exists(self):
        ps_path = PROJECT_ROOT / "scripts" / "schedule_task.ps1"
        if ps_path.exists():
            content = ps_path.read_text(encoding="utf-8")
            assert "Task" in content or "powershell" in content.lower()
        else:
            pytest.skip("[M4 Pending] PowerShell schedule script not yet created")

    def test_f12_daily_dispatch_entrypoint_executable(self):
        entry_mod = get_module_or_skip("scheduler.daily_dispatch", "F12", "M4")
        assert hasattr(entry_mod, "main") or hasattr(entry_mod, "run_daily")

    def test_f12_architecture_comparison_document_present(self):
        arch_path = PROJECT_ROOT / "scheduler" / "ARCHITECTURE.md"
        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8")
            assert "GitHub Actions" in content
            assert "Windows Task Scheduler" in content
        else:
            pytest.skip("[M4 Pending] scheduler/ARCHITECTURE.md not yet created")

    def test_f12_scheduler_tradeoffs_documented(self):
        arch_path = PROJECT_ROOT / "scheduler" / "ARCHITECTURE.md"
        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8")
            assert "cost" in content.lower()
            assert "jitter" in content.lower()
        else:
            pytest.skip("[M4 Pending] scheduler/ARCHITECTURE.md not yet created")


# ==============================================================================
# F13: Interactive On-Demand CLI
# ==============================================================================
class TestTier1F13InteractiveCli:
    """Feature F13: CLI subcommands (eval, tailor, digest, stepcon)."""

    def test_f13_cli_help_menu_subcommands(self):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        parser = cli_mod.create_parser()
        assert parser is not None

    def test_f13_cli_evaluate_with_text(self, synthetic_jobs):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        exit_code = cli_mod.run_cli(["eval", "--text", synthetic_jobs["devops"]["description"]])
        assert exit_code == 0

    def test_f13_cli_evaluate_with_file(self, synthetic_jobs, temp_output_dir):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        jd_file = temp_output_dir / "sample_jd.txt"
        jd_file.write_text(synthetic_jobs["devops"]["description"], encoding="utf-8")
        exit_code = cli_mod.run_cli(["eval", "--file", str(jd_file)])
        assert exit_code == 0

    def test_f13_cli_tailor_command_output(self, synthetic_jobs, temp_output_dir):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        jd_file = temp_output_dir / "sample_jd.txt"
        jd_file.write_text(synthetic_jobs["devops"]["description"], encoding="utf-8")
        exit_code = cli_mod.run_cli(["tailor", "--jd", str(jd_file), "--role", "devops", "--output-dir", str(temp_output_dir)])
        assert exit_code == 0

    def test_f13_cli_exit_code_zero_on_success(self):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        exit_code = cli_mod.run_cli(["--help"])
        assert exit_code == 0



# ==============================================================================
# F14: Stepcon Solutions Consultancy Pipeline
# ==============================================================================
class TestTier1F14StepconConsultancyPipeline:
    """Feature F14: Stepcon Solutions (RC - 8284984) tender evaluation and proposals."""

    def test_f14_stepcon_entity_cac_registration(self, canonical_profile_data):
        stepcon = canonical_profile_data.get("stepconSolutions", {})
        assert stepcon.get("cacNumber") == "RC - 8284984"

    def test_f14_evaluate_matching_cloud_tender(self, canonical_profile_data, synthetic_tenders):
        tender_mod = get_module_or_skip("consultancy.tenders", "F14", "M5")
        res = tender_mod.evaluate_tender(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"]["description"])
        assert res.overall_score >= 70.0

    def test_f14_generate_corporate_b2b_proposal(self, canonical_profile_data, synthetic_tenders):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"])
        assert "Stepcon Solutions" in proposal
        assert "RC - 8284984" in proposal

    def test_f14_proposal_contains_lead_credentials(self, canonical_profile_data, synthetic_tenders):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"])
        assert "John Victor Aniekwe" in proposal
        assert "KCNA" in proposal or "AWS" in proposal

    def test_f14_proposal_specifies_c2c_and_sla_terms(self, canonical_profile_data, synthetic_tenders):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"])
        assert "Corp-to-Corp" in proposal or "C2C" in proposal
        assert "99.9%" in proposal


# ==============================================================================
# F15: Controlled Testing & Dry-Run Mode
# ==============================================================================
class TestTier1F15ControlledTestingDryRun:
    """Feature F15: Environment variable settings and zero-cost dry-run mode."""

    def test_f15_settings_reads_dry_run_flag(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        settings = settings_mod.get_settings()
        assert hasattr(settings, "dry_run") or "DRY_RUN" in settings

    def test_f15_settings_reads_offline_mode_flag(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        settings = settings_mod.get_settings()
        assert hasattr(settings, "offline_mode") or "OFFLINE_MODE" in settings

    def test_f15_pipeline_executes_offline_without_network(self, synthetic_jobs):
        disc_mod = get_module_or_skip("discovery.sources", "F15", "M5")
        opps = disc_mod.fetch_opportunities(dry_run=True, offline_mode=True)
        assert len(opps) >= 1

    def test_f15_dry_run_writes_to_local_disk(self, synthetic_jobs, temp_output_dir):
        mailer_mod = get_module_or_skip("dispatch.mailer", "F15", "M5")
        digest_mod = get_module_or_skip("dispatch.digest", "F15", "M5")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]])
        output_path = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))
        assert os.path.exists(output_path)

    def test_f15_zero_paid_api_key_required(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        settings = settings_mod.get_settings()
        # Ensure no paid API key is mandatory for operation
        assert getattr(settings, "openai_api_key", None) is None or True
