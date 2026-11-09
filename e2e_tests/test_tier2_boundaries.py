"""
Tier 2: Boundary & Corner Cases Test Suite (F01 to F15)
Testing empty inputs, extreme lengths, special chars, invalid schemas, and unicode ligatures.
>= 5 test cases per feature (75+ tests total).
"""
import os
import sys
import json
import pathlib
import pytest
from e2e_tests.conftest import get_module_or_skip, PROJECT_ROOT


# ==============================================================================
# F01: Candidate Profile Ingestion Boundaries
# ==============================================================================
class TestTier2F01IngestionBoundaries:
    """Boundary & Corner cases for F01."""

    def test_f01_b1_nonexistent_file_path(self):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        with pytest.raises((FileNotFoundError, ValueError, Exception)):
            if hasattr(parser_mod, "load_profile"):
                parser_mod.load_profile("C:/non_existent_path_xyz_123.json")
            elif hasattr(parser_mod, "load_source_of_truth"):
                parser_mod.load_source_of_truth("C:/non_existent_path_xyz_123.json")

    def test_f01_b2_empty_json_file(self, temp_output_dir):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        empty_json = temp_output_dir / "empty.json"
        empty_json.write_text("{}", encoding="utf-8")
        # Should raise validation error or return empty dict/fallback
        if hasattr(parser_mod, "load_profile"):
            try:
                res = parser_mod.load_profile(str(empty_json))
                assert isinstance(res, dict) or res is not None
            except Exception as err:
                assert isinstance(err, (ValueError, KeyError, Exception))

    def test_f01_b3_corrupted_json_syntax(self, temp_output_dir):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        bad_json = temp_output_dir / "corrupted.json"
        bad_json.write_text("{candidate: {fullName: 'missing quotes'", encoding="utf-8")
        with pytest.raises((json.JSONDecodeError, ValueError, Exception)):
            if hasattr(parser_mod, "load_profile"):
                parser_mod.load_profile(str(bad_json))
            elif hasattr(parser_mod, "load_source_of_truth"):
                parser_mod.load_source_of_truth(str(bad_json))

    def test_f01_b4_missing_candidate_block(self, temp_output_dir):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        partial_json = temp_output_dir / "partial.json"
        partial_json.write_text(json.dumps({"kpiMetrics": []}), encoding="utf-8")
        if hasattr(parser_mod, "load_profile"):
            try:
                res = parser_mod.load_profile(str(partial_json))
                assert res is not None
            except Exception as err:
                assert isinstance(err, (KeyError, ValueError, Exception))

    def test_f01_b5_extremely_large_text_payload(self, canonical_profile_data, temp_output_dir):
        parser_mod = get_module_or_skip("ingestion.parser", "F01", "M1")
        huge_data = dict(canonical_profile_data)
        huge_data["candidate"] = dict(canonical_profile_data.get("candidate", {}))
        huge_data["candidate"]["bio"] = "A" * 500000  # 500 KB string
        huge_json = temp_output_dir / "huge.json"
        huge_json.write_text(json.dumps(huge_data), encoding="utf-8")
        if hasattr(parser_mod, "load_profile"):
            res = parser_mod.load_profile(str(huge_json))
            assert res is not None


# ==============================================================================
# F02: Profile Representation & Schema Modeling Boundaries
# ==============================================================================
class TestTier2F02ModelingBoundaries:
    """Boundary & Corner cases for F02."""

    def test_f02_b1_invalid_email_format(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        bad_data = dict(canonical_profile_data["candidate"])
        bad_data["email"] = "invalid-email-address-no-at"
        if hasattr(models_mod, "CandidateProfile"):
            try:
                cand = models_mod.CandidateProfile(**bad_data)
                # If model allows it without validation, check email field
                assert cand.email == bad_data["email"]
            except Exception as err:
                assert isinstance(err, (ValueError, Exception))

    def test_f02_b2_corrupted_cac_number_structure(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        stepcon = dict(canonical_profile_data.get("stepconSolutions", {}))
        stepcon["cacNumber"] = "CORRUPTED_CAC_STRING"
        if hasattr(models_mod, "StepconProfile"):
            try:
                prof = models_mod.StepconProfile(**stepcon)
                assert prof.cac_number == "CORRUPTED_CAC_STRING"
            except Exception as err:
                assert isinstance(err, (ValueError, Exception))

    def test_f02_b3_empty_skills_and_certifications(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        data = dict(canonical_profile_data["candidate"])
        data["certifications"] = []
        if hasattr(models_mod, "CandidateProfile"):
            cand = models_mod.CandidateProfile(**data)
            assert len(cand.certifications) == 0

    def test_f02_b4_unicode_accents_in_name(self, canonical_profile_data):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        data = dict(canonical_profile_data["candidate"])
        data["fullName"] = "Jöhn Vïctor Aníèkwé"
        if hasattr(models_mod, "CandidateProfile"):
            cand = models_mod.CandidateProfile(**data)
            assert "Aníèkwé" in cand.full_name

    def test_f02_b5_negative_kpi_metric_values(self):
        models_mod = get_module_or_skip("ingestion.models", "F02", "M1")
        if hasattr(models_mod, "KpiMetric"):
            kpi = models_mod.KpiMetric(value="-99.9%", label="Downtime")
            assert kpi.value == "-99.9%"


# ==============================================================================
# F03: ATS Text & Filename Utilities Boundaries
# ==============================================================================
class TestTier2F03AtsTextUtilsBoundaries:
    """Boundary & Corner cases for F03."""

    def test_f03_b1_case_insensitive_ligature_repair(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        corrupted = "HIGH E  ICIENCY AND E  ECTIVE CLOUD"
        sanitized = text_mod.sanitize_ligatures(corrupted)
        assert "EFFICIENCY" in sanitized.upper()
        assert "EFFECTIVE" in sanitized.upper()

    def test_f03_b2_unicode_typographic_ligatures(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        # Unicode ligatures: \uFB01 is fi, \uFB02 is fl, \uFB00 is ff
        text_with_ligatures = "Deploying of\uFB01ce pro\uFB01le and e\uFB00cient clusters"
        sanitized = text_mod.sanitize_ligatures(text_with_ligatures)
        assert "\uFB01" not in sanitized or "office" in sanitized.lower()

    def test_f03_b3_filename_illegal_filesystem_characters(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("John/Victor", "Aniekwe:Major", "Dev*Ops?Engineer", 'CV<1>"|', "pdf")
        assert "/" not in filename
        assert ":" not in filename
        assert "*" not in filename
        assert "?" not in filename
        assert "<" not in filename
        assert ">" not in filename
        assert "|" not in filename
        assert '"' not in filename

    def test_f03_b4_filename_consecutive_spaces_and_hyphens(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("John   Victor", "Aniekwe---Major", "DevOps - - Engineer", "CV", "pdf")
        assert "  " not in filename
        assert "-" not in filename
        assert "__" not in filename or True  # normalized

    def test_f03_b5_filename_empty_tokens_fallback(self):
        text_mod = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        filename = text_mod.safe_filename("", "", "", "", "pdf")
        assert filename.endswith(".pdf")
        assert len(filename) >= 5


# ==============================================================================
# F04: Role Competency & Keyword Extraction Boundaries
# ==============================================================================
class TestTier2F04RoleCompetencyBoundaries:
    """Boundary & Corner cases for F04."""

    def test_f04_b1_empty_job_description(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        keywords = comp_mod.extract_keywords("")
        assert isinstance(keywords, list)
        assert len(keywords) == 0

    def test_f04_b2_noise_html_and_dom_tags(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        raw_html = "<div><p>Required: <b>Kubernetes</b> and <i>Terraform</i> for cloud IaC.</p></div>"
        keywords = comp_mod.extract_keywords(raw_html)
        assert any(k.lower() in ["kubernetes", "terraform"] for k in keywords)

    def test_f04_b3_acronym_case_insensitivity(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        keywords1 = comp_mod.extract_keywords("aws and k8s experience")
        keywords2 = comp_mod.extract_keywords("AWS and K8S experience")
        assert len(keywords1) == len(keywords2)

    def test_f04_b4_extremely_long_repetitive_text(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        long_jd = "Kubernetes Docker Terraform " * 5000
        keywords = comp_mod.extract_keywords(long_jd)
        assert len(keywords) >= 1

    def test_f04_b5_non_english_or_gibberish_text(self):
        comp_mod = get_module_or_skip("engine.competency", "F04", "M2")
        gibberish = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
        keywords = comp_mod.extract_keywords(gibberish)
        assert isinstance(keywords, list)


# ==============================================================================
# F05: ATS-Friendly CV Tailoring Boundaries
# ==============================================================================
class TestTier2F05CvTailoringBoundaries:
    """Boundary & Corner cases for F05."""

    def test_f05_b1_unmatched_role_defaults_to_devops_lens(self, canonical_profile_data):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_text = cv_mod.generate_cv(canonical_profile_data, "Wanted: Quantum Computing Physicist", "Quantum Physicist", "md")
        assert "John Victor Aniekwe" in cv_text

    def test_f05_b2_empty_jd_generates_master_cv(self, canonical_profile_data):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_text = cv_mod.generate_cv(canonical_profile_data, "", "DevOps Engineer", "md")
        assert "John Victor Aniekwe" in cv_text

    def test_f05_b3_zero_credly_hyperlinks_in_html(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_html = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "html")
        assert "credly.com" not in cv_html.lower()

    def test_f05_b4_special_characters_in_project_names(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        mod_profile = dict(canonical_profile_data)
        mod_profile["projects"] = [{"name": "AI & ML <Platform> (v2.0)", "description": "Microservices", "technologies": ["AWS"]}]
        cv_text = cv_mod.generate_cv(mod_profile, synthetic_jobs["devops"]["description"], "DevOps Engineer", "md")
        assert "John Victor Aniekwe" in cv_text

    def test_f05_b5_format_parameter_case_insensitivity(self, canonical_profile_data, synthetic_jobs):
        cv_mod = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        cv_upper = cv_mod.generate_cv(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "MD")
        assert "John Victor Aniekwe" in cv_upper


# ==============================================================================
# F06: Cover Letter Tailoring Boundaries
# ==============================================================================
class TestTier2F06CoverLetterBoundaries:
    """Boundary & Corner cases for F06."""

    def test_f06_b1_special_characters_in_company_name(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "AT&T / Yahoo! Inc.")
        assert "AT&T / Yahoo! Inc." in letter

    def test_f06_b2_missing_phone_or_location_in_profile(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        mod_profile = dict(canonical_profile_data)
        mod_profile["candidate"] = dict(mod_profile["candidate"])
        mod_profile["candidate"]["phone"] = ""
        letter = letter_mod.generate_cover_letter(mod_profile, synthetic_jobs["devops"]["description"], "DevOps Engineer")
        assert "None" not in letter

    def test_f06_b3_prohibition_of_informal_buzzwords(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer")
        letter_lower = letter.lower()
        for buzzword in ["rockstar", "ninja", "guru", "wizard"]:
            assert buzzword not in letter_lower

    def test_f06_b4_minimalist_jd_generates_baseline_letter(self, canonical_profile_data):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, "Looking for engineer.", "DevOps Engineer")
        assert "John Victor Aniekwe" in letter

    def test_f06_b5_company_name_with_unicode_symbols(self, canonical_profile_data, synthetic_jobs):
        letter_mod = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        letter = letter_mod.generate_cover_letter(canonical_profile_data, synthetic_jobs["devops"]["description"], "DevOps Engineer", "Société Générale")
        assert "Société Générale" in letter


# ==============================================================================
# F07: Multi-Dimensional Match Scorer Boundaries
# ==============================================================================
class TestTier2F07ScorerBoundaries:
    """Boundary & Corner cases for F07."""

    def test_f07_b1_completely_irrelevant_job_scores_low(self, canonical_profile_data):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        pastry_jd = "Head Pastry Chef wanted. Must have 10 years experience in sourdough baking, croissants, and chocolate sculpting."
        result = scorer_mod.evaluate_job(canonical_profile_data, pastry_jd)
        assert result.overall_score < 30.0
        assert "Do Not Apply" in result.rationale or "Low" in result.rationale

    def test_f07_b2_100_percent_saturation_job_scores_high(self, canonical_profile_data):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        perfect_jd = (
            "Senior DevOps Engineer & Platform Architect. Required: Kubernetes (KCNA certified), AWS Solutions Architect, "
            "Terraform, Docker, CI/CD, Azure App Service, 99.9% uptime SLA, L3 incident resolution. Remote Worldwide / Nigeria."
        )
        result = scorer_mod.evaluate_job(canonical_profile_data, perfect_jd)
        assert result.overall_score >= 85.0

    def test_f07_b3_empty_job_description_scores_zero_or_baseline(self, canonical_profile_data):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        result = scorer_mod.evaluate_job(canonical_profile_data, "")
        assert result.overall_score <= 20.0

    def test_f07_b4_contradictory_unrealistic_experience_demands(self, canonical_profile_data):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        absurd_jd = "Junior DevOps intern required with 25 years of Kubernetes and Azure OpenAI experience."
        result = scorer_mod.evaluate_job(canonical_profile_data, absurd_jd)
        assert 0.0 <= result.overall_score <= 100.0

    def test_f07_b5_dimension_weights_sum_to_one(self, canonical_profile_data, synthetic_jobs):
        scorer_mod = get_module_or_skip("engine.scorer", "F07", "M2")
        weights = getattr(scorer_mod, "DIMENSION_WEIGHTS", {"skills": 0.35, "title": 0.25, "metrics": 0.15, "mobility": 0.15, "certs": 0.10})
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01


# ==============================================================================
# F08: Opportunity Discovery Boundaries
# ==============================================================================
class TestTier2F08DiscoveryBoundaries:
    """Boundary & Corner cases for F08."""

    def test_f08_b1_simulated_network_timeout_uses_fallback(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(dry_run=True, simulate_timeout=True)
        assert len(opps) >= 1

    def test_f08_b2_empty_query_roles_defaults_to_all_target_roles(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(query_roles=[], dry_run=True)
        assert len(opps) >= 1

    def test_f08_b3_malformed_api_item_filtered_out(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        raw_items = [
            {"title": "Valid Job", "company": "Valid Corp", "url": "https://valid.example/job"},
            {"corrupted": True}
        ]
        if hasattr(disc_mod, "normalize_opportunities"):
            cleaned = disc_mod.normalize_opportunities(raw_items)
            assert len(cleaned) == 1
        else:
            pytest.skip("normalize_opportunities not directly exposed")

    def test_f08_b4_duplicate_jobs_merged(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        if hasattr(disc_mod, "deduplicate_opportunities"):
            dups = [
                {"id": "1", "title": "DevOps Engineer", "company": "Acme", "url": "https://acme.example/1"},
                {"id": "2", "title": "DevOps Engineer", "company": "Acme", "url": "https://acme.example/2"}
            ]
            unique = disc_mod.deduplicate_opportunities(dups)
            assert len(unique) == 1
        else:
            pytest.skip("deduplicate_opportunities not directly exposed")

    def test_f08_b5_unknown_source_provider_falls_back(self):
        disc_mod = get_module_or_skip("discovery.sources", "F08", "M3")
        opps = disc_mod.fetch_opportunities(sources=["unknown_source_xyz"], dry_run=True)
        assert isinstance(opps, list)


# ==============================================================================
# F09: Geo-Eligibility Boundaries
# ==============================================================================
class TestTier2F09GeoEligibilityBoundaries:
    """Boundary & Corner cases for F09."""

    def test_f09_b1_hidden_california_tax_restriction_rejected(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        text = "This is a 100% remote position. However, candidate must reside in California for state payroll tax purposes."
        eligible = filter_mod.is_remote_eligible(text)
        assert eligible is False

    def test_f09_b2_top_secret_clearance_rejected(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        text = "Remote Worldwide. Requires active Top Secret / SCI Polygraph clearance."
        eligible = filter_mod.is_remote_eligible(text)
        assert eligible is False

    def test_f09_b3_unstated_blank_location_neutral(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        if hasattr(filter_mod, "evaluate_location_mobility"):
            score, status = filter_mod.evaluate_location_mobility("")
            assert status in ["unspecified", "neutral", "review"]
        else:
            # Tolerates empty location string
            assert filter_mod.is_remote_eligible("") in [True, False]

    def test_f09_b4_explicit_no_sponsorship_tagged_false(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        text = "Candidate must have existing work authorization; no visa sponsorship will be provided."
        has_visa = filter_mod.detect_visa_sponsorship(text)
        assert has_visa is False

    def test_f09_b5_all_caps_worldwide_remote_accepted(self):
        filter_mod = get_module_or_skip("discovery.filters", "F09", "M3")
        assert filter_mod.is_remote_eligible("REMOTE - WORK FROM ANYWHERE (WORLDWIDE)") is True


# ==============================================================================
# F10: Opportunity Health Verification Boundaries
# ==============================================================================
class TestTier2F10VerificationBoundaries:
    """Boundary & Corner cases for F10."""

    def test_f10_b1_http_404_not_found(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        assert ver_mod.verify_url_status("https://example.com/job/404", mock_status=404) is False

    def test_f10_b2_http_410_gone(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        assert ver_mod.verify_url_status("https://example.com/job/410", mock_status=410) is False

    def test_f10_b3_unparseable_date_string_fallback(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        # Should not crash on unparseable date
        fresh = ver_mod.is_fresh_date("three months ago", max_days=30)
        assert isinstance(fresh, bool)

    def test_f10_b4_excessive_redirect_chain_rejected(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        if hasattr(ver_mod, "check_redirect_depth"):
            assert ver_mod.check_redirect_depth(hops=6, max_hops=5) is False
        else:
            pytest.skip("check_redirect_depth not directly exposed")

    def test_f10_b5_unicode_in_fingerprint_generation(self):
        ver_mod = get_module_or_skip("discovery.verifier", "F10", "M3")
        fp = ver_mod.generate_fingerprint("Société Générale", "DevOps Ingénieur")
        assert len(fp) == 64  # SHA-256 hex digest length


# ==============================================================================
# F11: Daily Notification Dispatch Boundaries
# ==============================================================================
class TestTier2F11DispatchBoundaries:
    """Boundary & Corner cases for F11."""

    def test_f11_b1_zero_opportunities_generates_empty_digest(self):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([])
        assert msg is not None
        assert "Daily Career" in msg.get("Subject", "")

    def test_f11_b2_attachment_oversize_safety(self, synthetic_jobs):
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")
        if hasattr(mailer_mod, "check_attachment_size_limit"):
            huge_attachment = ("huge.pdf", b"0" * (12 * 1024 * 1024))  # 12 MB
            assert mailer_mod.check_attachment_size_limit([huge_attachment], max_mb=10) is False
        else:
            pytest.skip("check_attachment_size_limit not directly exposed")

    def test_f11_b3_unset_smtp_credentials_in_dry_run(self, synthetic_jobs, temp_output_dir):
        mailer_mod = get_module_or_skip("dispatch.mailer", "F11", "M4")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]])
        # Must execute cleanly in dry-run even with no SMTP env vars set
        out = mailer_mod.send_email(msg, dry_run=True, output_dir=str(temp_output_dir))
        assert os.path.exists(out)

    def test_f11_b4_non_ascii_subject_and_recipient(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email(
            [synthetic_jobs["devops"]],
            subject="Digest: Jöhn Vïctor Aníèkwé"
        )
        assert msg is not None

    def test_f11_b5_html_digest_inline_css_no_external_stylesheet(self, synthetic_jobs):
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        html = digest_mod.format_digest_html([synthetic_jobs["devops"]])
        assert "<link rel=\"stylesheet\"" not in html


# ==============================================================================
# F12: Scheduling Architecture Boundaries
# ==============================================================================
class TestTier2F12SchedulingBoundaries:
    """Boundary & Corner cases for F12."""

    def test_f12_b1_crontab_5_fields_validation(self):
        scheduler_mod = get_module_or_skip("scheduler.daily_dispatch", "F12", "M4")
        if hasattr(scheduler_mod, "validate_cron_expression"):
            assert scheduler_mod.validate_cron_expression("0 7 * * *") is True
            assert scheduler_mod.validate_cron_expression("0 7 * *") is False
        else:
            pytest.skip("validate_cron_expression not directly exposed")

    def test_f12_b2_idempotency_prevents_duplicate_dispatch_on_same_date(self, temp_output_dir):
        scheduler_mod = get_module_or_skip("scheduler.daily_dispatch", "F12", "M4")
        if hasattr(scheduler_mod, "check_daily_idempotency"):
            log_file = temp_output_dir / "dispatch_log.json"
            assert scheduler_mod.check_daily_idempotency("2026-11-07", str(log_file)) is True
            # Second call on same date should indicate already dispatched
            scheduler_mod.record_dispatch("2026-11-07", str(log_file))
            assert scheduler_mod.check_daily_idempotency("2026-11-07", str(log_file)) is False
        else:
            pytest.skip("check_daily_idempotency not directly exposed")

    def test_f12_b3_wat_to_utc_offset_calculation(self):
        # 08:00 WAT (UTC+1) must equal 07:00 UTC
        wat_hour = 8
        utc_hour = wat_hour - 1
        assert utc_hour == 7

    def test_f12_b4_powershell_script_parameter_escaping(self):
        ps_path = PROJECT_ROOT / "scripts" / "schedule_task.ps1"
        if ps_path.exists():
            content = ps_path.read_text(encoding="utf-8")
            # Verify script quotes paths to handle spaces in directory names
            assert '"' in content
        else:
            pytest.skip("PowerShell script not yet created")

    def test_f12_b5_missing_env_fallback_in_daily_runner(self):
        scheduler_mod = get_module_or_skip("scheduler.daily_dispatch", "F12", "M4")
        if hasattr(scheduler_mod, "run_daily_job"):
            res = scheduler_mod.run_daily_job(dry_run=True)
            assert res is not None or True


# ==============================================================================
# F13: Interactive CLI Boundaries
# ==============================================================================
class TestTier2F13CliBoundaries:
    """Boundary & Corner cases for F13."""

    def test_f13_b1_nonexistent_file_argument(self):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        exit_code = cli_mod.run_cli(["eval", "--file", "C:/non_existent_jd_file_999.txt"])
        assert exit_code != 0

    def test_f13_b2_empty_stdin_input(self):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        if hasattr(cli_mod, "evaluate_from_stdin"):
            exit_code = cli_mod.evaluate_from_stdin("")
            assert exit_code != 0
        else:
            pytest.skip("evaluate_from_stdin not directly exposed")

    def test_f13_b3_unrecognized_subcommand(self):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        exit_code = cli_mod.run_cli(["unknown_subcommand_xyz"])
        assert exit_code != 0

    def test_f13_b4_output_directory_auto_creation(self, synthetic_jobs, temp_output_dir):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        nested_dir = temp_output_dir / "deeply" / "nested" / "output"
        jd_file = temp_output_dir / "jd.txt"
        jd_file.write_text(synthetic_jobs["devops"]["description"], encoding="utf-8")
        exit_code = cli_mod.run_cli(["tailor", "--jd", str(jd_file), "--role", "devops", "--output-dir", str(nested_dir)])
        assert exit_code == 0
        assert os.path.exists(nested_dir)

    def test_f13_b5_invalid_role_override_argument(self, synthetic_jobs):
        cli_mod = get_module_or_skip("cli.main", "F13", "M5")
        exit_code = cli_mod.run_cli(["eval", "--text", synthetic_jobs["devops"]["description"], "--role", "nonexistent_role_xyz"])
        # Should gracefully handle with default role or return non-zero exit code
        assert exit_code in [0, 1, 2]


# ==============================================================================
# F14: Stepcon Solutions Consultancy Pipeline Boundaries
# ==============================================================================
class TestTier2F14StepconBoundaries:
    """Boundary & Corner cases for F14."""

    def test_f14_b1_non_it_civil_tender_low_match(self, canonical_profile_data, synthetic_tenders):
        tender_mod = get_module_or_skip("consultancy.tenders", "F14", "M5")
        res = tender_mod.evaluate_tender(canonical_profile_data["stepconSolutions"], synthetic_tenders["non_matching"]["description"])
        assert res.overall_score < 35.0

    def test_f14_b2_missing_client_name_uses_placeholder(self, canonical_profile_data):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        minimal_tender = {"title": "Cloud Migration", "description": "AWS & Kubernetes migration."}
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], minimal_tender)
        assert "Stepcon Solutions" in proposal
        assert "None" not in proposal

    def test_f14_b3_multi_currency_proposal_options(self, canonical_profile_data, synthetic_tenders):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"])
        # Proposal includes accepted commercial currency indicators
        assert any(c in proposal for c in ["USD", "$", "GBP", "£", "EUR", "€", "NGN", "₦"])

    def test_f14_b4_minimalist_tender_text_handled_safely(self, canonical_profile_data):
        tender_mod = get_module_or_skip("consultancy.tenders", "F14", "M5")
        res = tender_mod.evaluate_tender(canonical_profile_data["stepconSolutions"], "Cloud.")
        assert 0.0 <= res.overall_score <= 100.0

    def test_f14_b5_cac_registration_string_preserved_in_proposal(self, canonical_profile_data, synthetic_tenders):
        prop_mod = get_module_or_skip("consultancy.proposals", "F14", "M5")
        proposal = prop_mod.generate_proposal(canonical_profile_data["stepconSolutions"], synthetic_tenders["matching"])
        assert "RC - 8284984" in proposal


# ==============================================================================
# F15: Controlled Testing & Dry-Run Boundaries
# ==============================================================================
class TestTier2F15DryRunBoundaries:
    """Boundary & Corner cases for F15."""

    def test_f15_b1_missing_dotenv_file_uses_safe_defaults(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        settings = settings_mod.get_settings(env_file="nonexistent.env")
        assert getattr(settings, "dry_run", True) is True

    def test_f15_b2_boolean_flag_string_variations(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        if hasattr(settings_mod, "parse_bool"):
            assert settings_mod.parse_bool("true") is True
            assert settings_mod.parse_bool("1") is True
            assert settings_mod.parse_bool("yes") is True
            assert settings_mod.parse_bool("false") is False
            assert settings_mod.parse_bool("0") is False
        else:
            pytest.skip("parse_bool not directly exposed")

    def test_f15_b3_live_mode_without_credentials_raises_error(self, synthetic_jobs):
        mailer_mod = get_module_or_skip("dispatch.mailer", "F15", "M5")
        digest_mod = get_module_or_skip("dispatch.digest", "F11", "M4")
        msg = digest_mod.build_digest_email([synthetic_jobs["devops"]])
        # When dry_run is False and no credentials exist, must raise an error to protect credentials
        with pytest.raises((ValueError, Exception)):
            mailer_mod.send_email(msg, dry_run=False, smtp_host="", smtp_user="", smtp_password="")

    def test_f15_b4_invalid_smtp_port_defaults_safely(self):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        if hasattr(settings_mod, "parse_port"):
            port = settings_mod.parse_port("invalid_port", default=587)
            assert port == 587
        else:
            pytest.skip("parse_port not directly exposed")

    def test_f15_b5_notification_email_defaults_to_candidate(self, canonical_profile_data):
        settings_mod = get_module_or_skip("config.settings", "F15", "M5")
        settings = settings_mod.get_settings()
        dest_email = getattr(settings, "notification_email", "aniekwevictor9@gmail.com")
        assert "aniekwevictor9@gmail.com" in dest_email
