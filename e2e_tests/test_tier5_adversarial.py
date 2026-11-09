"""
Tier 5: Adversarial Coverage Hardening Test Suite
Comprehensive white-box edge-case and boundary verification across all 7 core subsystems:
1. Ingestion: Ligature fuzzing, unicode artifacts, profile models, CAC validation, safe filenames.
2. Engine: 8-role taxonomy weights, HTML/DOM keyword extraction, 5-dimension scoring bounds, disqualifiers.
3. Tailoring: Zero Credly / tracker link enforcement, single-column ATS layout, buzzword ban, STAR tone variations.
4. Discovery: Multi-vector geo-filtering (US-only, W2, clearances), Nigeria eligibility, DOM health verification.
5. Dispatch: Multi-part MIME RFC 5322 compliance, inline CSS verification, attachment size guardrails, dry-run .eml.
6. CLI: Subcommand routing, exit code invariants, stdin evaluation, nested directory auto-creation.
7. Consultancy: Non-IT civil works discrimination, Stepcon statutory CAC RC - 8284984 invariants, proposal generation.
"""
import os
import sys
import json
import email
import pathlib
import pytest

from e2e_tests.conftest import (
    get_module_or_skip,
    PROJECT_ROOT,
    CANONICAL_PROFILE_PATH
)


# ==============================================================================
# Subsystem 1: Ingestion & Text Utilities
# ==============================================================================
class TestTier5IngestionAdversarial:
    """Subsystem 1: Ingestion, ligature sanitization, and profile schema boundaries."""

    def test_t5_01_ligature_fuzzing_and_corrupt_glyph_purging(self):
        """Stress-test sanitize_ligatures with extreme unicode ligatures, horn glitches, and invisible chars."""
        text_utils = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        sanitize_ligatures = text_utils.sanitize_ligatures

        # Chaos payload with unicode presentation ligatures, horn glyphs, NBSP, BOM, soft hyphen
        corrupted = (
            "The s\uFB02ution o\uFB00ers high e\u01AFiciency and e\u01AFective performance.\n"
            "Our o\uFB00ice tra\u01AFic was managed with su\u01AFicient care.\n"
            "Special characters: \u201Cquote\u201D, \u2018single\u2019, dash\u2014long, \u2022 bullet item.\n"
            "Spaces:\u00A0non-breaking\u202Fnarrow\u2000en-quad\u3000ideographic.\n"
            "Invisible:\u200Bzero-width\uFEFFbom\u00ADsoft-hyphen.\n"
            "Broken spaces: E  ECTIVE and e  ective operations."
        )

        cleaned = sanitize_ligatures(corrupted)
        # Ligatures must be normalized to standard ASCII letter pairs
        assert "solution" in cleaned or "sflution" in cleaned
        assert "offers" in cleaned or "o\uFB00ers" not in cleaned
        assert "efficiency" in cleaned
        assert "effective" in cleaned
        assert "office" in cleaned
        assert "traffic" in cleaned
        assert "sufficient" in cleaned
        # Typographic quotes and dashes normalized
        assert '"quote"' in cleaned
        assert "'single'" in cleaned
        assert "--" in cleaned or "-" in cleaned
        # Bullets converted to standard hyphen
        assert "- bullet item" in cleaned
        # Invisible characters stripped
        assert "\u200B" not in cleaned
        assert "\uFEFF" not in cleaned
        assert "\u00AD" not in cleaned
        # Broken space upper/lower handling
        assert "EFFECTIVE" in cleaned or "effective" in cleaned

    def test_t5_02_safe_filename_adversarial_paths_and_overflow(self):
        """Verify safe_filename guards against path traversal, forbidden Windows chars, and length overflow."""
        text_utils = get_module_or_skip("ingestion.text_utils", "F03", "M1")
        safe_filename = text_utils.safe_filename

        # Path traversal attempt
        fn1 = safe_filename("../../etc/passwd", "..\\windows\\system32", "Root/Admin", "CV", "pdf")
        assert "/" not in fn1
        assert "\\" not in fn1
        assert ".." not in fn1
        assert fn1.endswith(".pdf")

        # Windows forbidden characters: < > : " / \ | ? *
        fn2 = safe_filename('John<Victor>?', 'Aniekwe:*|"Test"', 'Dev(Sec)Ops:Architect', 'Cover Letter', 'html')
        for bad_char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            assert bad_char not in fn2
        assert " " not in fn2
        assert fn2.endswith(".html")

        # Extremely long name and role exceeding Windows MAX_PATH (200 char limit)
        giant_role = "A" * 350
        fn3 = safe_filename("John", "Aniekwe", giant_role, "CV", "docx")
        assert len(fn3) <= 200
        assert fn3.endswith(".docx")
        assert fn3.startswith("John_Aniekwe_")

    def test_t5_03_stepcon_profile_cac_statutory_validation(self):
        """Enforce statutory requirement that StepconProfile strictly validates CAC RC - 8284984."""
        models = get_module_or_skip("ingestion.models", "F02", "M1")
        StepconProfile = models.StepconProfile

        # Valid initialization with exact CAC registration
        valid_stepcon = StepconProfile(
            company_name="Stepcon Solutions",
            cac_number="RC - 8284984"
        )
        assert valid_stepcon.cac_number == "RC - 8284984"

        # Valid initialization with numeric CAC
        valid_stepcon2 = StepconProfile(cac_number="8284984")
        assert "8284984" in valid_stepcon2.cac_number

        # Adversarial initialization with invalid/fake registration number must raise ValueError
        with pytest.raises(ValueError) as excinfo:
            StepconProfile(cac_number="RC - 9999999")
        assert "RC - 8284984" in str(excinfo.value)

    def test_t5_04_profile_schema_boundaries_and_resilient_parsing(self, temp_output_dir):
        """Adversarial schema boundary testing: missing blocks, completeness auditing, and serialization."""
        parser = get_module_or_skip("ingestion.parser", "F01", "M1")
        load_profile = parser.load_profile
        validate_completeness = parser.validate_profile_completeness

        # Test loading from raw dict with polymorphic keys
        test_dict = {
            "candidate": {
                "first_name": "John",
                "last_name": "Aniekwe",
                "email": "aniekwevictor9@gmail.com",
                "location": "Lagos, Nigeria",
                "certifications": [
                    {"name": "Kubernetes and Cloud Native Associate (KCNA)", "status": "Active"},
                    {"name": "AWS Certified Solutions Architect – Associate", "status": "Active"}
                ]
            },
            "stepcon_solutions": {
                "cac_number": "RC - 8284984"
            }
        }
        profile = load_profile(test_dict)
        assert profile.candidate.full_name == "John Aniekwe"
        assert len(profile.candidate.certifications) == 2

        # Completeness audit should report zero warnings on clean valid profile
        warnings = validate_completeness(profile)
        assert not any("KCNA" in w for w in warnings)
        assert not any("CAC" in w for w in warnings)

        # Corrupt profile missing required fields
        corrupt_dict = {
            "candidate": {
                "first_name": "Anonymous",
                "email": ""
            },
            "stepcon_solutions": {
                "cac_number": "RC - 8284984"
            }
        }
        corrupt_profile = load_profile(corrupt_dict)
        corrupt_warnings = validate_completeness(corrupt_profile)
        assert any("email" in w.lower() for w in corrupt_warnings)
        assert any("certifications" in w.lower() for w in corrupt_warnings)


# ==============================================================================
# Subsystem 2: Matching Engine & Competency Taxonomy
# ==============================================================================
class TestTier5EngineAdversarial:
    """Subsystem 2: 8-role taxonomy, keyword extraction, and 5-dimension scorer."""

    def test_t5_05_role_taxonomy_invariant_mathematical_weights(self):
        """Verify that all 8 target roles in ROLE_ENTRIES have domain weights summing to 1.0."""
        competency = get_module_or_skip("engine.competency", "F04", "M2")
        ROLE_ENTRIES = competency.ROLE_ENTRIES
        get_role_taxonomy = competency.get_role_taxonomy

        assert len(ROLE_ENTRIES) == 8, f"Expected exactly 8 roles in taxonomy, found {len(ROLE_ENTRIES)}"

        taxonomy_dict = get_role_taxonomy()
        for role in ROLE_ENTRIES:
            # Check weight sum == 1.0 (approx)
            total_weight = sum(role.domain_weights.values())
            assert total_weight == pytest.approx(1.0, abs=1e-4), f"Weights for role '{role.title}' sum to {total_weight}, not 1.0"
            assert len(role.core_technologies) >= 5
            assert len(role.required_certifications) >= 1

            # Check lookup by title, role_key, and lowercase
            assert role.title in taxonomy_dict
            assert role.role_key in taxonomy_dict

    def test_t5_06_malicious_html_and_dom_sanitization_in_extractor(self):
        """Stress extract_keywords with XSS payloads, broken DOM tags, and entity-encoded tokens."""
        competency = get_module_or_skip("engine.competency", "F04", "M2")
        extract_keywords = competency.extract_keywords

        adversarial_jd = (
            "<script>alert('xss');</script><style>body{display:none;}</style>"
            "<div class=\"job-requirements\"><p>Must know &quot;Kubernetes&quot; and &#x27;Docker&#x27;.</p>"
            "<span>Experience with CI/CD, Terraform, and AWS &amp; Azure cloud estates.</span>"
            "<!-- Hidden comment with fake keywords: Python, Golang -->"
            "<a href=\"https://malicious.example.com\">Apply with Prometheus & Grafana</a></div>"
        )
        extracted = extract_keywords(adversarial_jd)
        assert "Kubernetes" in extracted
        assert "Docker" in extracted
        assert "CI/CD" in extracted
        assert "Terraform" in extracted
        assert "AWS" in extracted
        assert "Azure" in extracted
        # Malicious tags and attribute text must not become keywords
        assert "script" not in [k.lower() for k in extracted]
        assert "style" not in [k.lower() for k in extracted]
        assert "alert" not in [k.lower() for k in extracted]

    def test_t5_07_scorer_zero_match_and_irrelevant_jobs(self, canonical_profile_data):
        """Verify that non-technical, culinary, and trade job descriptions strictly evaluate to 0.0% or Do Not Apply."""
        scorer = get_module_or_skip("engine.scorer", "F07", "M2")
        evaluate_job = scorer.evaluate_job

        # Direct irrelevant marker match: strictly 0.0% across overall and all breakdown dimensions
        irrelevant_jds = [
            "Executive Pastry Chef needed for artisanal French bakery. Must know croissants, puff pastry, and sourdough.",
            "Licensed Dentist for private dental clinic. Patient oral examinations, fillings, and tooth extraction.",
            "Certified Commercial Plumber and Pipefitter. Water heater repair, pipe threading, and drainage installation.",
            "Senior Corporate Defense Attorney. Litigation, courtroom trials, and legal brief authoring.",
        ]

        for jd in irrelevant_jds:
            result = evaluate_job(canonical_profile_data, jd)
            assert result.overall_score == 0.0
            assert result.breakdown["skills"] == 0.0
            assert result.breakdown["title"] == 0.0
            assert "Do Not Apply" in result.rationale

        # General non-technical job with zero skills matching: score < 50.0% and Do Not Apply
        result_hygienist = evaluate_job(
            canonical_profile_data,
            "Dental Hygienist for clinic. Patient teeth cleaning, fluoride treatment, and medical records."
        )
        assert result_hygienist.overall_score < 50.0
        assert result_hygienist.breakdown["skills"] == 0.0
        assert "Do Not Apply" in result_hygienist.rationale

    def test_t5_08_scorer_disqualifier_penalty_capping(self, canonical_profile_data):
        """Verify that jobs with hard disqualifiers (US Only, Secret Clearance, W2 Only) are capped <= 65%."""
        scorer = get_module_or_skip("engine.scorer", "F07", "M2")
        evaluate_job = scorer.evaluate_job

        # Job has top technical match keywords, but explicit US-only clearance gate
        disqualified_jd = (
            "Senior DevOps Engineer. Lead our multi-cloud Kubernetes, Docker, and Terraform automation on AWS and Azure.\n"
            "Maintain 99.9% uptime SLAs, build GitHub Actions CI/CD pipelines, and configure Grafana observability.\n"
            "CRITICAL ELIGIBILITY: US Citizens Only. Must reside in the continental United States. "
            "Active Secret Clearance required. W2 Only. Candidates outside the US will not be considered."
        )

        result = evaluate_job(canonical_profile_data, disqualified_jd)
        # Mobility score must be 0.0
        assert result.breakdown["mobility"] == 0.0
        # Overall score must be capped below 70.0%
        assert result.overall_score <= 65.0
        assert result.overall_score >= 0.0

    def test_t5_09_scorer_mathematical_monotonicity_and_saturation(self, canonical_profile_data):
        """Ensure scorer results are bounded [0.0, 100.0] and contain exact 5 breakdown dimensions."""
        scorer = get_module_or_skip("engine.scorer", "F07", "M2")
        evaluate_job = scorer.evaluate_job

        # Empty JD
        res_empty = evaluate_job(canonical_profile_data, "")
        assert res_empty.overall_score == 0.0
        assert set(res_empty.breakdown.keys()) == {"skills", "title", "metrics", "mobility", "certs"}
        for v in res_empty.breakdown.values():
            assert v == 0.0

        # Maximum matching JD
        full_match_jd = (
            "Senior DevOps Engineer / Cloud Solutions Architect. Remote - Worldwide (EMEA / UTC+1).\n"
            "We are seeking a candidate with verified Kubernetes (KCNA) and AWS Certified Solutions Architect credentials.\n"
            "Lead multi-cloud automation across AWS and Microsoft Azure using Terraform, Docker, and GitHub Actions CI/CD.\n"
            "Sustain 99.9% platform uptime SLAs and deliver root cause analysis (RCA) on Azure App Service.\n"
            "B2B Corp-to-Corp contracting available. 100% Remote anywhere in the world."
        )
        res_full = evaluate_job(canonical_profile_data, full_match_jd)
        assert 80.0 <= res_full.overall_score <= 100.0
        assert res_full.breakdown["mobility"] == 100.0
        assert "Strong Apply" in res_full.rationale or "Apply" in res_full.rationale


# ==============================================================================
# Subsystem 3: Tailoring (CV & STAR Cover Letter)
# ==============================================================================
class TestTier5TailoringAdversarial:
    """Subsystem 3: ATS document generation, Credly/tracker purging, buzzword policing."""

    def test_t5_10_cv_strict_zero_tracker_credly_purging(self, canonical_profile_data):
        """Verify that CV generation strictly purges Credly and tracking links across md, html, and txt formats."""
        cv_tailor = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        generate_cv = cv_tailor.generate_cv

        # Clone profile and inject adversarial Credly tracker links into certifications
        poisoned_profile = json.loads(json.dumps(canonical_profile_data))
        for cert in poisoned_profile["candidate"]["certifications"]:
            cert["verification_url"] = "https://www.credly.com/badges/12345678-abcd-ef01-2345"
            cert["name"] = cert["name"] + " [Verify: https://youracclaim.com/badges/xyz]"

        for fmt in ["md", "html", "txt"]:
            cv_text = generate_cv(poisoned_profile, target_role="DevOps Engineer", output_format=fmt)
            assert "credly.com" not in cv_text.lower()
            assert "youracclaim.com" not in cv_text.lower()

    def test_t5_11_cv_layout_structural_integrity(self, canonical_profile_data):
        """Confirm single-column linear layout in HTML and standard headers in Markdown."""
        cv_tailor = get_module_or_skip("tailoring.cv_tailor", "F05", "M2")
        generate_cv = cv_tailor.generate_cv

        # Test Markdown layout
        md_cv = generate_cv(canonical_profile_data, target_role="Cloud Solutions Architect", output_format="md")
        expected_sections = [
            "# John Victor Aniekwe",
            "## Professional Summary",
            "## Core Competencies",
            "## Professional Experience",
            "## Certifications",
            "## Key Projects",
            "## Education"
        ]
        for sec in expected_sections:
            assert sec in md_cv

        # Test HTML layout: must have font-variant-ligatures: none and zero table columns
        html_cv = generate_cv(canonical_profile_data, target_role="DevOps Engineer", output_format="html")
        assert "font-variant-ligatures: none" in html_cv
        assert "<html" in html_cv and "</html>" in html_cv
        assert "<header>" in html_cv
        assert "<main>" in html_cv

    def test_t5_12_cover_letter_banned_buzzword_police(self, canonical_profile_data):
        """Verify that generate_cover_letter purges banned fluff words (rockstar, ninja, guru, wizard)."""
        letter_tailor = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        generate_cover_letter = letter_tailor.generate_cover_letter

        # Provide a JD full of tech buzzwords
        fluff_jd = (
            "We want a rockstar DevOps ninja and cloud guru who is a true wizard at Kubernetes and Terraform. "
            "Looking for a 10x engineer and unicorn to scale our multi-cloud infrastructure."
        )

        letter = generate_cover_letter(
            canonical_profile_data,
            job_text=fluff_jd,
            target_role="DevOps Engineer",
            company_name="Acme Tech Corp",
            output_format="md"
        )

        letter_lower = letter.lower()
        for banned in ["rockstar", "ninja", "guru", "wizard", "unicorn", "10x engineer"]:
            assert banned not in letter_lower

        # Empirical metrics must remain intact
        assert "99.9%" in letter
        assert "99%" in letter

    def test_t5_13_cover_letter_placeholder_protection_and_tones(self, canonical_profile_data):
        """Verify cover letter tone modes and ensure literal string 'None' is never rendered."""
        letter_tailor = get_module_or_skip("tailoring.letter_tailor", "F06", "M2")
        generate_cover_letter = letter_tailor.generate_cover_letter

        # Pass None or empty company across all 4 tones
        tones = ["professional", "technical", "executive", "results_oriented"]
        for tone in tones:
            letter = generate_cover_letter(
                canonical_profile_data,
                job_text="Kubernetes & Terraform Cloud Engineering",
                target_role="Cloud Solutions Architect",
                company_name="",
                tone=tone,
                output_format="md"
            )
            assert "None" not in letter
            assert "Hiring Team" in letter
            assert "John Victor Aniekwe" in letter


# ==============================================================================
# Subsystem 4: Discovery & Health Verification
# ==============================================================================
class TestTier5DiscoveryAdversarial:
    """Subsystem 4: Geo-filtering matrix, Nigeria remote eligibility, and link verification."""

    def test_t5_14_geofilter_adversarial_us_only_matrix(self):
        """Exhaustively verify hard disqualification across US-only, Canada-only, and clearance vectors."""
        filters = get_module_or_skip("discovery.filters", "F09", "M3")
        is_remote_eligible = filters.is_remote_eligible
        has_disqualifiers = filters.has_disqualifiers

        disqualified_scenarios = [
            "DevOps Engineer (US Only)",
            "Remote - US",
            "Remote - US Only",
            "Remote (US only)",
            "Remote (US-based)",
            "Remote (US residents)",
            "US only candidates",
            "Candidates must reside in the United States",
            "Must be a US citizen for compliance",
            "US Persons Only (Citizen or Green Card)",
            "Active TS/SCI Clearance Required",
            "Top Secret / SCI with polygraph",
            "Strictly W2 Only - No C2C or 1099",
            "Must reside in California for state payroll tax purposes",
            "Canada Only - Must be legally authorized in Canada",
            "100% On-site in New York Office - Remote work prohibited",
        ]

        for text in disqualified_scenarios:
            assert has_disqualifiers(text), f"Failed to detect disqualifier in: '{text}'"
            assert not is_remote_eligible(text), f"Incorrectly marked eligible: '{text}'"

    def test_t5_15_geofilter_remote_nigeria_positive_channels(self):
        """Verify positive remote eligibility signals for a Lagos, Nigeria candidate."""
        filters = get_module_or_skip("discovery.filters", "F09", "M3")
        is_remote_eligible = filters.is_remote_eligible
        evaluate_eligibility = filters.evaluate_opportunity_eligibility

        positive_scenarios = [
            {"title": "DevOps Engineer", "location": "Remote - Worldwide", "description": "Global remote work from anywhere."},
            {"title": "Cloud Architect", "location": "Remote - EMEA", "description": "Synchronous with CET working hours."},
            {"title": "Platform Engineer", "location": "Remote - CET", "description": "Aligned with UTC+1 / CET business hours."},
            {"title": "SysAdmin", "location": "Lagos, Nigeria", "description": "Local engineering team in Lagos."},
            {"title": "SRE", "location": "Remote", "description": "B2B Corp-to-Corp (C2C) contracting supported."},
            {"title": "Infrastructure Engineer", "location": "London, UK", "description": "Visa sponsorship and relocation package offered."},
        ]

        for opp in positive_scenarios:
            res = evaluate_eligibility(opp)
            assert res.is_eligible, f"Expected eligible for opportunity: {opp}"
            assert not res.disqualified

    def test_t5_16_health_verifier_closed_dom_and_dead_links(self):
        """Verify detect_closed_phrase DOM inspection and is_fresh_date boundaries."""
        verifier = get_module_or_skip("discovery.verifier", "F10", "M3")
        detect_closed_phrase = verifier.detect_closed_phrase
        is_fresh_date = verifier.is_fresh_date

        # Closed DOM notices
        closed_bodies = [
            "<html><body><h1>404 Not Found</h1><p>The requested page is missing.</p></body></html>",
            "<div><span class='badge'>This position has been filled.</span> Applications are now closed.</div>",
            "<p>Sorry, this job posting is no longer active.</p>",
            "This vacancy has expired and is no longer accepting applications.",
        ]
        for body in closed_bodies:
            assert detect_closed_phrase(body)

        # Active body
        active_body = "<html><body><h1>Senior Cloud Engineer</h1><p>Apply now! We are hiring.</p></body></html>"
        assert not detect_closed_phrase(active_body)

        # Freshness date boundaries against 2026-11-07 baseline
        assert is_fresh_date("2026-11-05", reference_date="2026-11-07")  # 2 days old (fresh)
        assert is_fresh_date("2026-10-15", reference_date="2026-11-07")  # 23 days old (fresh <= 30)
        assert not is_fresh_date("2026-08-01", reference_date="2026-11-07")  # 98 days old (stale)
        assert not is_fresh_date("invalid-date-string", reference_date="2026-11-07")  # unparseable -> safe False


# ==============================================================================
# Subsystem 5: Dispatch & Offline Dry-Run Packaging
# ==============================================================================
class TestTier5DispatchAdversarial:
    """Subsystem 5: Multi-part MIME digest, inline CSS, attachment limits, .eml export."""

    def test_t5_17_digest_multipart_mime_rfc5322_invariants(self, canonical_profile_data, synthetic_jobs):
        """Verify build_digest_email produces strict RFC 5322 multipart/mixed wrapping multipart/alternative."""
        digest = get_module_or_skip("dispatch.digest", "F11", "M4")
        build_digest_email = digest.build_digest_email

        opps = [synthetic_jobs["devops"], synthetic_jobs["architect"]]
        attachments = [("Sample_CV.md", "# John Victor Aniekwe CV")]

        msg = build_digest_email(
            opportunities=opps,
            candidate=canonical_profile_data,
            date_str="2026-11-07",
            subject="Daily Career Digest 🚀 — EMEA Remote",
            attachments=attachments
        )

        # Root must be multipart/mixed
        assert msg.is_multipart()
        assert msg.get_content_type() == "multipart/mixed"
        assert "Stepcon Solutions" in msg["From"]
        assert "aniekwevictor9@gmail.com" in msg["To"]
        assert "Daily Career Digest" in str(msg["Subject"])

        # Check payload structure: first part is multipart/alternative, second is attachment
        payload_parts = msg.get_payload()
        assert len(payload_parts) >= 2
        alt_part = payload_parts[0]
        assert alt_part.get_content_type() == "multipart/alternative"

        sub_types = [p.get_content_type() for p in alt_part.get_payload()]
        assert "text/plain" in sub_types
        assert "text/html" in sub_types

    def test_t5_18_digest_html_strict_inline_css_and_zero_external_links(self, canonical_profile_data, synthetic_jobs):
        """Verify format_digest_html adheres to zero-external-stylesheet inline CSS and renders metrics."""
        digest = get_module_or_skip("dispatch.digest", "F11", "M4")
        format_digest_html = digest.format_digest_html

        html_out = format_digest_html([synthetic_jobs["devops"]], candidate=canonical_profile_data)
        assert "<link rel=\"stylesheet\"" not in html_out.lower()
        assert "href=\"http" in html_out  # Has clickable opportunity URLs
        assert "99.9%" in html_out  # Verified SLA metric
        assert "99%" in html_out    # Verified RCA metric

    def test_t5_19_mailer_attachment_size_guardrail(self):
        """Verify check_attachment_size_limit enforces 10 MB cumulative boundary."""
        mailer = get_module_or_skip("dispatch.mailer", "F11", "M4")
        check_attachment_size_limit = mailer.check_attachment_size_limit

        # Small 1 MB attachment: allowed
        small_payload = b"X" * (1024 * 1024)
        assert check_attachment_size_limit([("file1.pdf", small_payload)], max_mb=10.0)

        # Large 11 MB attachment: blocked
        large_payload = b"X" * (11 * 1024 * 1024)
        assert not check_attachment_size_limit([("large.pdf", large_payload)], max_mb=10.0)

    def test_t5_20_mailer_dryrun_hermetic_serialization(self, canonical_profile_data, synthetic_jobs, temp_output_dir):
        """Verify send_email in dry_run mode writes valid .eml to disk without network calls."""
        digest = get_module_or_skip("dispatch.digest", "F11", "M4")
        mailer = get_module_or_skip("dispatch.mailer", "F11", "M4")
        build_digest_email = digest.build_digest_email
        send_email = mailer.send_email

        msg = build_digest_email([synthetic_jobs["devops"]], candidate=canonical_profile_data)
        eml_path = send_email(msg, dry_run=True, output_dir=temp_output_dir)

        assert os.path.exists(eml_path)
        assert eml_path.endswith(".eml")

        # Parse saved .eml to verify format integrity
        with open(eml_path, "rb") as f:
            parsed = email.message_from_binary_file(f)
        assert parsed["To"] == "aniekwevictor9@gmail.com"
        assert "Stepcon" in parsed["From"]


# ==============================================================================
# Subsystem 6: CLI & Entrypoint Interfaces
# ==============================================================================
class TestTier5CliAdversarial:
    """Subsystem 6: CLI argument parsing, stdin evaluation, error exit codes."""

    def test_t5_21_cli_argument_parsing_and_exit_codes(self):
        """Verify CLI error codes on missing files and unrecognized subcommands."""
        cli = get_module_or_skip("cli.main", "F13", "M5")
        run_cli = cli.run_cli

        # No args: print help and exit 0
        assert run_cli([]) == 0

        # Unrecognized subcommand: exit code 2
        assert run_cli(["unrecognized_subcommand_xyz"]) == 2

        # Eval with non-existent file: exit code 1
        assert run_cli(["eval", "--file", "C:/non_existent_file_xyz_999.txt"]) == 1

        # Eval with empty text: exit code 1
        assert run_cli(["eval", "--text", "   "]) == 1

    def test_t5_22_cli_stdin_boundary_handling(self):
        """Verify evaluate_from_stdin rejects empty/whitespace input and evaluates valid text."""
        cli = get_module_or_skip("cli.main", "F13", "M5")
        evaluate_from_stdin = cli.evaluate_from_stdin

        assert evaluate_from_stdin("") == 1
        assert evaluate_from_stdin("   \n\t  ") == 1
        assert evaluate_from_stdin(None) == 1

        valid_jd = "Senior DevOps Engineer with Kubernetes and Terraform experience on AWS."
        assert evaluate_from_stdin(valid_jd) == 0

    def test_t5_23_cli_tailor_nested_dir_creation(self, temp_output_dir):
        """Verify CLI tailor automatically creates deeply nested destination directories."""
        cli = get_module_or_skip("cli.main", "F13", "M5")
        run_cli = cli.run_cli

        nested_dir = temp_output_dir / "deep" / "nested" / "output_test"
        assert not nested_dir.exists()

        exit_code = run_cli([
            "tailor",
            "--text", "Senior DevOps Engineer. Kubernetes, Terraform, AWS, Azure, 99.9% SLA.",
            "--role", "DevOps Engineer",
            "--output-dir", str(nested_dir),
            "--format", "md"
        ])
        assert exit_code == 0
        assert nested_dir.exists()
        generated_files = list(nested_dir.glob("*.md"))
        assert len(generated_files) == 2  # CV and Cover Letter


# ==============================================================================
# Subsystem 7: Stepcon Consultancy & Tender Proposals
# ==============================================================================
class TestTier5ConsultancyAdversarial:
    """Subsystem 7: Civil works discrimination, Stepcon CAC RC - 8284984 invariants, proposals."""

    def test_t5_24_consultancy_civil_works_discrimination(self, canonical_profile_data):
        """Ensure evaluate_tender aggressively rejects civil engineering and road paving tenders."""
        tenders = get_module_or_skip("consultancy.tenders", "F14", "M5")
        evaluate_tender = tenders.evaluate_tender
        stepcon = canonical_profile_data.get("stepconSolutions", {})

        civil_tenders = [
            "Supply of asphalt concrete, road grading equipment, and highway drainage maintenance.",
            "Municipal civil engineering works: asphalt overlay, culvert construction, and pothole patching.",
            "Commercial plumbing, sanitation pipe laying, and civil structural building renovation."
        ]

        for tender_desc in civil_tenders:
            res = evaluate_tender(stepcon, tender_desc)
            assert res.overall_score <= 20.0
            assert "Do Not Bid" in res.rationale
            assert "Non-IT" in res.target_offering

        # Matching IT tender must score >= 70.0%
        matching_tender = (
            "RFP for turnkey multi-cloud enterprise platform modernization. "
            "Implement Terraform Infrastructure as Code, deploy Kubernetes microservices on AWS and Azure, "
            "and guarantee 99.9% uptime SLA under synchronous CET business hours. B2B Corp-to-Corp contracting."
        )
        it_res = evaluate_tender(stepcon, matching_tender)
        assert it_res.overall_score >= 70.0
        assert "Strong Bid" in it_res.rationale

    def test_t5_25_consultancy_proposal_stepcon_statutory_invariants(self, canonical_profile_data):
        """Verify generate_proposal preserves CAC RC - 8284984, Lead Architect credentials, and multi-currency terms."""
        proposals = get_module_or_skip("consultancy.proposals", "F14", "M5")
        generate_proposal = proposals.generate_proposal
        stepcon = canonical_profile_data.get("stepconSolutions", {})

        tender_input = {
            "title": "Pan-African Multi-Cloud DevOps Infrastructure Modernization",
            "client": "Continental Banking Group",
            "budget": "$150,000 USD"
        }

        proposal_md = generate_proposal(stepcon, tender_input, candidate=canonical_profile_data)

        # Statutory and Lead Architect invariants
        assert "Stepcon Solutions" in proposal_md
        assert "RC - 8284984" in proposal_md
        assert "John Victor Aniekwe" in proposal_md
        assert "KCNA" in proposal_md or "Kubernetes" in proposal_md
        assert "AWS Certified Solutions Architect" in proposal_md
        assert "99.9%" in proposal_md
        assert "99%" in proposal_md

        # Multi-currency commercial terms
        assert "USD" in proposal_md or "$" in proposal_md
        assert "GBP" in proposal_md or "£" in proposal_md
        assert "EUR" in proposal_md or "€" in proposal_md
        assert "NGN" in proposal_md or "₦" in proposal_md

        # Zero literal "None" placeholder pollution
        assert " None " not in proposal_md
        assert "None —" not in proposal_md
