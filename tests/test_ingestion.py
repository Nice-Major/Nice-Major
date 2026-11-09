"""
Unit Test Suite for Milestone 1: Ingestion, Modeling, and ATS Text Utilities.
Target Module: tests/test_ingestion.py

Coverage:
- Feature F01: Candidate Profile Ingestion (ingestion.parser)
- Feature F02: Profile Representation & Schema Modeling (ingestion.models)
- Feature F03: ATS Text Utilities & Safe Filenames (ingestion.text_utils)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import pytest

from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
    KpiMetric,
    RoleCategory,
    SkillsMatrix,
    StepconProfile,
    WorkExperience,
)
from ingestion.parser import (
    ProfileError,
    ProfileNotFoundError,
    ProfileParseError,
    ProfileValidationError,
    find_profile_data_path,
    get_embedded_default_profile,
    load_profile,
    load_profile_from_dict,
    load_profile_from_file,
    normalize_profile_dict,
    validate_profile_completeness,
)
from ingestion.text_utils import (
    clean_ats_text,
    extract_clean_words,
    normalize_whitespace,
    safe_filename,
    sanitize_ligatures,
    strip_markdown,
)


# ============================================================================
# 1. Feature F03: Ligature Sanitization Tests
# ============================================================================

class TestLigatureSanitization:
    """Verifies font ligature repair, glyph restoration, and space normalization."""

    def test_glitch_efficiency_variations(self):
        """Validates that Ư and ư in efficiency variations are accurately repaired."""
        assert sanitize_ligatures("cost eƯiciency through proactive management") == "cost efficiency through proactive management"
        assert sanitize_ligatures("procedures for operational eƯiciency") == "procedures for operational efficiency"
        assert sanitize_ligatures("Cost Optimization & EƯiciency:") == "Cost Optimization & Efficiency:"
        assert sanitize_ligatures("Achieved high eƯiciency") == "Achieved high efficiency"
        assert sanitize_ligatures("Operated eƯiciently across pods") == "Operated efficiently across pods"
        assert sanitize_ligatures("eƯicient resource provisioning") == "efficient resource provisioning"

    def test_glitch_effective_variations(self):
        """Validates that Ư and ư in effective variations are accurately repaired."""
        assert sanitize_ligatures("and eƯective stakeholder communication") == "and effective stakeholder communication"
        assert sanitize_ligatures("Collaboration: EƯective team player") == "Collaboration: Effective team player"
        assert sanitize_ligatures("eƯective leadership in incident management") == "effective leadership in incident management"
        assert sanitize_ligatures("High eƯort, direct eƯect") == "High effort, direct effect"
        assert sanitize_ligatures("Positive eƯects observed") == "Positive effects observed"

    def test_glitch_other_vocabulary(self):
        """Validates that Ư in difference, sufficient, and office words is restored to ff."""
        assert sanitize_ligatures("Observed major diƯerence in latency") == "Observed major difference in latency"
        assert sanitize_ligatures("Provided suƯicient compute capacity") == "Provided sufficient compute capacity"
        assert sanitize_ligatures("Headquarters oƯice administration") == "Headquarters office administration"
        assert sanitize_ligatures("Network traƯic shaping") == "Network traffic shaping"

    def test_broken_whitespace_ligatures(self):
        """Validates that whitespace-separated broken ligatures are repaired."""
        assert sanitize_ligatures("Cost e  ective solutions") == "Cost effective solutions"
        assert sanitize_ligatures("operational e ective communication") == "operational effective communication"
        assert sanitize_ligatures("highly e  icient pipelines") == "highly efficient pipelines"
        assert sanitize_ligatures("improved e iciency significantly") == "improved efficiency significantly"
        assert sanitize_ligatures("E  ective incident response") == "Effective incident response"
        assert sanitize_ligatures("Clearly de  ined boundaries") == "Clearly defined boundaries"
        assert sanitize_ligatures("Advanced con  iguration options") == "Advanced configuration options"
        assert sanitize_ligatures("Automated work  low execution") == "Automated workflow execution"

    def test_unicode_presentation_ligatures(self):
        """Validates that standard presentation ligatures (U+FB00..U+FB06) convert to ASCII."""
        assert sanitize_ligatures("o\uFB00er valid positions") == "offer valid positions"       # ﬀ -> ff
        assert sanitize_ligatures("con\uFB01gure infrastructure") == "configure infrastructure" # ﬁ -> fi
        assert sanitize_ligatures("work\uFB02ow automation") == "workflow automation"           # ﬂ -> fl
        assert sanitize_ligatures("e\uFB03cient compute nodes") == "efficient compute nodes"    # ﬃ -> ffi
        assert sanitize_ligatures("a\uFB04uent customers") == "affluent customers"              # ﬄ -> ffl
        assert sanitize_ligatures("o\uFB05en deployed") == "often deployed"                     # ﬅ -> ft
        assert sanitize_ligatures("fa\uFB06est response") == "fastest response"                 # ﬆ -> st

    def test_non_breaking_spaces_and_invisibles(self):
        """Validates that non-breaking spaces become ASCII spaces and invisibles are purged."""
        # Non-breaking space \u00A0
        assert sanitize_ligatures("AWS\u00A0Certified\u00A0Architect") == "AWS Certified Architect"
        # Narrow NBSP \u202F
        assert sanitize_ligatures("10\u202FGB") == "10 GB"
        # Zero-width space \u200B and soft hyphen \u00AD stripped
        assert sanitize_ligatures("Kuber\u200Bnetes") == "Kubernetes"
        assert sanitize_ligatures("infra\u00ADstructure") == "infrastructure"
        # UTF-8 BOM \uFEFF stripped
        assert sanitize_ligatures("\uFEFFProfile Headline") == "Profile Headline"

    def test_typographic_quotes_and_dashes(self):
        """Validates standardizing smart quotes and dashes."""
        assert sanitize_ligatures("\u201CHigh Availability\u201D") == '"High Availability"'
        assert sanitize_ligatures("Candidate\u2019s Resume") == "Candidate's Resume"
        assert sanitize_ligatures("2021\u20132025") == "2021-2025"
        assert sanitize_ligatures("Lagos \u2014 Nigeria") == "Lagos -- Nigeria"
        assert sanitize_ligatures("\u2022 Provisioned AKS") == "- Provisioned AKS"

    def test_replacement_character_recovery(self):
        """Validates that \\uFFFD in known glitch patterns is correctly resolved."""
        assert sanitize_ligatures("cost e\uFFFDiciency analysis") == "cost efficiency analysis"
        assert sanitize_ligatures("highly e\uFFFDective team") == "highly effective team"

    def test_clean_text_remains_unmodified(self):
        """Confirms that clean text without ligatures is unchanged."""
        clean_sample = "Senior Cloud Architect with 5+ years experience designing AWS and Azure microservices."
        assert sanitize_ligatures(clean_sample) == clean_sample

    def test_edge_cases_empty_and_none(self):
        """Validates boundary conditions: None, empty string, non-string."""
        assert sanitize_ligatures(None) == ""
        assert sanitize_ligatures("") == ""
        assert sanitize_ligatures("   ") == "   "
        assert sanitize_ligatures(12345) == "12345"


# ============================================================================
# 2. Feature F03: Safe Filename Generation Tests
# ============================================================================

class TestSafeFilename:
    """Verifies strict underscore filename formatting and Windows MAX_PATH limits."""

    def test_standard_safe_filename(self):
        """Validates canonical candidate naming format."""
        filename = safe_filename("John", "Aniekwe", "DevOps Engineer", "CV", "pdf")
        assert filename == "John_Aniekwe_DevOps_Engineer_CV.pdf"

    def test_compound_first_name(self):
        """Validates handling of compound first/middle name combination."""
        filename = safe_filename("John Victor", "Aniekwe", "Cloud Solutions Architect", "Cover Letter", "pdf")
        assert filename == "John_Victor_Aniekwe_Cloud_Solutions_Architect_Cover_Letter.pdf"

    def test_special_characters_and_brackets(self):
        """Validates elimination of hyphens, brackets, slashes, and symbols."""
        filename = safe_filename(
            first="John-Victor!",
            last="O'Aniekwe",
            role="Dev(Sec)Ops / SRE [Senior]",
            doc_type="CV & Resume!",
            ext="pdf",
        )
        assert filename == "John_Victor_O_Aniekwe_Dev_Sec_Ops_SRE_Senior_CV_Resume.pdf"
        assert " " not in filename
        assert "-" not in filename
        assert "(" not in filename
        assert ")" not in filename
        assert "/" not in filename
        assert "[" not in filename
        assert "]" not in filename
        assert "!" not in filename

    def test_extension_normalization(self):
        """Validates extension handling: leading dot, uppercase, and alternative formats."""
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext=".PDF") == "John_Aniekwe_DevOps_CV.pdf"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext="DOCX") == "John_Aniekwe_DevOps_CV.docx"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext=".md") == "John_Aniekwe_DevOps_CV.md"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext="") == "John_Aniekwe_DevOps_CV.pdf"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext=None) == "John_Aniekwe_DevOps_CV.pdf"

    def test_path_traversal_prevention(self):
        """Validates that directory traversal patterns (../ or ..\\) are stripped."""
        filename = safe_filename("../../evil_path", "Aniekwe", "DevOps", "CV", "pdf")
        assert ".." not in filename
        assert "/" not in filename
        assert "\\" not in filename
        assert filename == "evil_path_Aniekwe_DevOps_CV.pdf"

    def test_consecutive_underscores_collapsed(self):
        """Validates that redundant underscores are cleanly collapsed."""
        filename = safe_filename("John___Victor", "Aniekwe", "DevOps____Platform___Lead", "CV", "pdf")
        assert "__" not in filename
        assert filename == "John_Victor_Aniekwe_DevOps_Platform_Lead_CV.pdf"

    def test_empty_or_whitespace_fallbacks(self):
        """Validates safe default fallbacks when components are empty."""
        filename = safe_filename("", "", "", "", "")
        assert filename == "Candidate_Profile_General_Document.pdf"
        filename_spaces = safe_filename("   ", "   ", "   ", "   ")
        assert filename_spaces == "Candidate_Profile_General_Document.pdf"

    def test_max_length_truncation_for_windows(self):
        """Validates that an excessively long role name is safely truncated <= 200 chars."""
        very_long_role = "Senior Multi-Cloud Platform Infrastructure Solutions Architect and DevSecOps Site Reliability Lead Engineer Specialized in High Availability Microservices" * 2
        filename = safe_filename("John_Victor", "Aniekwe", very_long_role, "CV", "pdf")
        assert len(filename) <= 200
        assert filename.startswith("John_Victor_Aniekwe_")
        assert filename.endswith("_CV.pdf")


# ============================================================================
# 3. Auxiliary ATS Normalization Utilities Tests
# ============================================================================

class TestAuxiliaryTextUtils:
    """Verifies clean_ats_text, normalize_whitespace, strip_markdown, and word extraction."""

    def test_clean_ats_text(self):
        raw = "Line 1 with eƯiciency\r\nLine 2 with \x00control\x08 and \uFB01le.\r\n\r\n\r\n\r\nLine 3."
        cleaned = clean_ats_text(raw)
        assert "\r" not in cleaned
        assert "\x00" not in cleaned
        assert "\x08" not in cleaned
        assert "efficiency" in cleaned
        assert "file" in cleaned
        # Maximum consecutive newlines is 2
        assert "\n\n\n" not in cleaned

    def test_normalize_whitespace(self):
        raw = "DevOps    Engineer   with\u00A0\u00A0Azure\tand   AWS."
        normalized = normalize_whitespace(raw)
        assert normalized == "DevOps Engineer with Azure and AWS."

    def test_strip_markdown(self):
        md = "# John Victor Aniekwe\n**Senior DevOps Engineer**\n- [GitHub](https://github.com/Nice-Major)\n- `kubectl` cluster admin."
        plain = strip_markdown(md)
        assert "#" not in plain
        assert "**" not in plain
        assert "[" not in plain
        assert "`" not in plain
        assert "John Victor Aniekwe" in plain
        assert "GitHub" in plain
        assert "kubectl cluster admin." in plain

    def test_extract_clean_words(self):
        text = "Kubernetes, Docker, & Terraform! 99.9% uptime SLA."
        words = extract_clean_words(text)
        assert "kubernetes" in words
        assert "docker" in words
        assert "terraform" in words
        assert "uptime" in words
        assert "sla" in words


# ============================================================================
# 4. Feature F01: Profile Ingestion & Parser Tests
# ============================================================================

class TestProfileParser:
    """Verifies Candidate Profile Ingestion from file, dict, and fallbacks."""

    def test_load_profile_from_dict(self, minimal_candidate_dict):
        """Validates instantiating CandidateProfile from dictionary."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        assert isinstance(profile, CandidateProfile)
        assert profile.candidate.first_name == "John"
        assert profile.candidate.last_name == "Aniekwe"
        assert profile.candidate.email == "aniekwevictor9@gmail.com"
        assert profile.stepcon_solutions.cac_number == "RC - 8284984"

    def test_load_profile_from_json_file(self, minimal_candidate_dict):
        """Validates loading from an explicit JSON file."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(minimal_candidate_dict, f)
            temp_path = f.name
        try:
            profile = load_profile_from_file(temp_path)
            assert isinstance(profile, CandidateProfile)
            assert profile.candidate.full_name == "John Victor Aniekwe"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_profile_file_not_found_raises(self):
        """Validates that a non-existent path raises ProfileNotFoundError when fallback disabled."""
        non_existent = "non_existent_profile_path_12345.json"
        with pytest.raises(ProfileNotFoundError):
            load_profile_from_file(non_existent, allow_fallback=False)

    def test_load_profile_file_not_found_with_fallback(self):
        """Validates that a non-existent path falls back to embedded profile when fallback enabled."""
        non_existent = "non_existent_profile_path_12345.json"
        profile = load_profile_from_file(non_existent, allow_fallback=True)
        assert isinstance(profile, CandidateProfile)
        assert profile.candidate.full_name == "John Victor Aniekwe"

    def test_load_profile_invalid_json_raises(self):
        """Validates that malformed JSON raises ProfileParseError."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("{\"candidate\": { malformed json")
            temp_path = f.name
        try:
            with pytest.raises(ProfileParseError):
                load_profile_from_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_profile_missing_candidate_key_raises(self):
        """Validates that dictionary missing required 'candidate' key raises ProfileValidationError."""
        bad_dict = {"stepcon_solutions": {"company_name": "Stepcon Solutions"}}
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(bad_dict)

    def test_verified_certifications_integrity(self, minimal_candidate_dict):
        """Validates that verified certifications are parsed without omitting any."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        cert_names = [c.name for c in profile.candidate.certifications]
        assert any("KCNA" in c for c in cert_names)
        assert any("Solutions Architect" in c for c in cert_names)

    def test_kpi_metrics_preservation(self, minimal_candidate_dict):
        """Validates that empirical KPI metrics are preserved."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        assert len(profile.kpi_metrics) >= 2
        values = [k.value for k in profile.kpi_metrics]
        assert "99.9%" in values
        assert "99%" in values

    def test_stepcon_solutions_cac_preservation(self, minimal_candidate_dict):
        """Validates that Stepcon Solutions CAC registration is strictly preserved."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        assert profile.stepcon_solutions.cac_number == "RC - 8284984"
        assert profile.stepcon_solutions.company_name == "Stepcon Solutions"

    def test_normalize_profile_dict_camel_to_snake(self):
        """Validates recursive conversion of camelCase JSON keys to snake_case."""
        camel_dict = {
            "firstName": "John",
            "kpiMetrics": [{"value": "99.9%", "label": "Uptime"}],
            "roleCategories": {"devOps": {"categoryTitle": "Engineer"}},
        }
        normalized = normalize_profile_dict(camel_dict)
        assert "first_name" in normalized
        assert "kpi_metrics" in normalized
        assert "role_categories" in normalized

    def test_find_profile_data_path_and_fallbacks(self, tmp_path):
        """Validates 5-tier path discovery logic."""
        test_file = tmp_path / "profile-data.json"
        test_file.write_text('{"candidate": {"fullName": "Test User"}}', encoding="utf-8")
        
        # Test Tier 1: explicit file path
        found = find_profile_data_path(test_file)
        assert found == test_file.resolve()

        # Test Tier 1: directory containing profile-data.json
        found_dir = find_profile_data_path(tmp_path)
        assert found_dir == test_file.resolve()

        # Test embedded profile fallback
        default_dict = get_embedded_default_profile()
        assert "candidate" in default_dict
        assert "stepconSolutions" in default_dict
        profile = load_profile(source=None, allow_fallback=True)
        assert profile.stepcon_solutions.cac_number == "RC - 8284984"

    def test_validate_profile_completeness(self, minimal_candidate_dict):
        """Validates audit checks for candidate profile completeness."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        warnings = validate_profile_completeness(profile)
        # minimal profile has full_name, email, KCNA, AWS SAA, Stepcon CAC
        assert not any("KCNA" in w for w in warnings)
        assert not any("Solutions Architect" in w for w in warnings)
        assert not any("CAC" in w for w in warnings)


# ============================================================================
# 5. Feature F02: Profile Schema Models Tests
# ============================================================================

class TestProfileModels:
    """Verifies schema validation and convenience methods on CandidateProfile."""

    def test_candidate_info_initialization(self):
        info = CandidateInfo(
            first_name="John",
            last_name="Aniekwe",
            full_name="John Victor Aniekwe",
            email="aniekwevictor9@gmail.com",
            phone="+234 816 484 1085",
            location="Lagos, Nigeria",
        )
        assert info.full_name == "John Victor Aniekwe"
        assert info.email == "aniekwevictor9@gmail.com"
        assert info.phone == "+234 816 484 1085"

    def test_certification_model(self):
        cert = Certification(
            name="Kubernetes and Cloud Native Associate (KCNA)",
            issuer="The Linux Foundation / CNCF",
            status="Active",
            tags=["all", "devops"],
        )
        assert cert.status == "Active"
        assert cert.is_active is True
        assert cert.credly_tracker_link_policy == "no_external_tracker_links"

    def test_role_categories_lenses(self, minimal_candidate_dict):
        profile = load_profile_from_dict(minimal_candidate_dict)
        devops_lens = profile.get_role_lens("devops")
        assert devops_lens is not None
        assert "Dev(Sec)Ops" in devops_lens.category_title
        # Test dict and attribute dual access
        assert devops_lens.category_title == devops_lens["category_title"]

    def test_skills_matrix_flattening(self, minimal_candidate_dict):
        profile = load_profile_from_dict(minimal_candidate_dict)
        flat_skills = profile.get_skills_flat()
        assert "AWS" in flat_skills
        assert "Microsoft Azure" in flat_skills
        assert "Kubernetes" in flat_skills

    def test_to_dict_and_from_dict_roundtrip(self, minimal_candidate_dict):
        profile = load_profile_from_dict(minimal_candidate_dict)
        profile_dict = profile.to_dict()
        reconstructed = CandidateProfile.from_dict(profile_dict)
        assert reconstructed.candidate.full_name == profile.candidate.full_name
        assert reconstructed.stepcon_solutions.cac_number == profile.stepcon_solutions.cac_number
        assert len(reconstructed.certifications) == len(profile.certifications)

    def test_stepcon_profile_validation(self):
        stepcon = StepconProfile(
            company_name="Stepcon Solutions",
            cac_number="RC - 8284984",
        )
        assert stepcon.cac_number == "RC - 8284984"
        assert stepcon.company_name == "Stepcon Solutions"
        assert "RC - 8284984" in stepcon.b2b_consultancy_pitch

    def test_stepcon_invalid_cac_raises_error(self):
        with pytest.raises(ValueError) as excinfo:
            StepconProfile(
                company_name="Stepcon Solutions",
                cac_number="INVALID_CAC_NUMBER_9999",
            )
        assert "Invalid CAC registration number" in str(excinfo.value)


# ============================================================================
# 6. Milestone 1 Iteration 2 Gate Defects Remediation Tests
# ============================================================================

class TestGateDefectsRemediationM1:
    """
    Validates genuine remediation of all Milestone 1 Gate and Adversarial defects:
    1. StepconProfile .services and .legal_status property mapping & to_dict export
    2. RoleCategory.from_dict() serialization roundtrip without duplicate key TypeError
    3. SkillsMatrix category precedence ensuring Domain 6 receives its 5 skills
    4. SkillsMatrix dictionary mapping protocol (.items(), .keys(), .values(), .get(), __iter__, __len__, __contains__)
    5. CandidateProfile.from_dict() certification priority fallback
    6. CandidateProfile.get_role_lens() slash/whitespace normalization and 8 target roles
    7. sanitize_ligatures() bullet point spacing (no double spaces)
    8. sanitize_ligatures() presentation ligatures adjacent to NBSP
    9. safe_filename() extension length clamping (<= 10 chars, Windows MAX_PATH <= 200)
    """

    def test_stepcon_profile_services_and_legal_status_contract(self):
        """StepconProfile exposes .services and .legal_status getters, setters, and exports to_dict."""
        stepcon = StepconProfile(
            cac_number="RC - 8284984",
            services=["Cloud Solutions Architecture", "DevSecOps Automation"],
            legal_status="Corporate Affairs Commission (CAC), Nigeria",
        )
        # Contract property getters
        assert stepcon.services == ["Cloud Solutions Architecture", "DevSecOps Automation"]
        assert stepcon.offerings == ["Cloud Solutions Architecture", "DevSecOps Automation"]
        assert stepcon.legal_status == "Corporate Affairs Commission (CAC), Nigeria"
        assert stepcon.jurisdiction == "Corporate Affairs Commission (CAC), Nigeria"
        assert stepcon.legalStatus == "Corporate Affairs Commission (CAC), Nigeria"

        # Contract property setters
        stepcon.services = ["Enterprise Kubernetes Pods"]
        assert stepcon.offerings == ["Enterprise Kubernetes Pods"]
        assert stepcon.services == ["Enterprise Kubernetes Pods"]

        stepcon.legal_status = "Updated Registration Authority"
        assert stepcon.jurisdiction == "Updated Registration Authority"
        assert stepcon.legal_status == "Updated Registration Authority"

        # to_dict export
        data = stepcon.to_dict()
        assert "services" in data
        assert data["services"] == ["Enterprise Kubernetes Pods"]
        assert "legal_status" in data
        assert data["legal_status"] == "Updated Registration Authority"
        assert "legalStatus" in data

        # from_dict reconstruction
        reconstructed = StepconProfile.from_dict(data)
        assert reconstructed.services == ["Enterprise Kubernetes Pods"]
        assert reconstructed.legal_status == "Updated Registration Authority"

    def test_role_category_serialization_roundtrip_no_duplicate_key_error(self):
        """RoleCategory.from_dict() does not crash with duplicate keyword argument 'key'."""
        rc = RoleCategory(
            title="Senior DevSecOps Engineer",
            key="devops",
            headline="DevOps Lead",
        )
        exported = rc.to_dict()
        assert "key" in exported
        assert exported["key"] == "devops"

        # Roundtrip invocation passing key explicitly while exported dict already contains "key"
        reconstructed = RoleCategory.from_dict(exported, key="devops")
        assert reconstructed.key == "devops"
        assert reconstructed.title == "Senior DevSecOps Engineer"

        # Roundtrip invocation without passing key explicitly
        reconstructed_no_key = RoleCategory.from_dict(exported)
        assert reconstructed_no_key.key == "devops"

    def test_skills_matrix_domain_6_observability_sre_classification(self):
        """Observability, SRE & DevSecOps Governance routes to Domain 6 (observability_monitoring)."""
        raw_categories = [
            {
                "category": "Cloud Platform Architecture (AWS & Azure)",
                "items": ["AWS", "Azure"],
            },
            {
                "category": "AI-Augmented Engineering & MLOps",
                "items": ["Prompt Engineering", "MLOps"],
            },
            {
                "category": "CI/CD, IaC & Automation Scripting",
                "items": ["Terraform", "GitHub Actions"],
            },
            {
                "category": "Linux & Windows Systems Administration",
                "items": ["Ubuntu", "Active Directory"],
            },
            {
                "category": "Containerization & Kubernetes Orchestration",
                "items": ["Docker", "Kubernetes"],
            },
            {
                "category": "Observability, SRE & DevSecOps Governance",
                "items": [
                    "Observability Frameworks (Logs, Metrics, Traces)",
                    "AWS CloudWatch, Azure Monitor, Prometheus/Grafana",
                    "SLI / SLO / SLA Compliance (99.9% Uptime)",
                    "IAM Access Controls & Disaster Recovery",
                    "Architecture Diagrams & SOPs",
                ],
            },
        ]
        matrix = SkillsMatrix.from_dict(raw_categories)
        assert len(matrix.observability_monitoring) == 5
        assert "SLI / SLO / SLA Compliance (99.9% Uptime)" in matrix.observability_monitoring
        assert len(matrix.dev_sec_ops) == 2  # Not bloated by category 6 items

    def test_skills_matrix_dict_protocol_methods(self):
        """SkillsMatrix satisfies dict mapping protocol: items, keys, values, get, __iter__, __len__, in."""
        matrix = SkillsMatrix(
            cloud_architecture=["AWS", "Azure"],
            dev_sec_ops=["SonarQube"],
            iac_automation=["Terraform"],
            systems_linux_windows=["Linux"],
            containerization_kubernetes=["Kubernetes"],
            observability_monitoring=["Prometheus"],
        )

        # __len__
        assert len(matrix) == 6

        # keys, values, items
        keys = list(matrix.keys())
        assert len(keys) == 6
        assert "cloud_architecture" in keys
        assert "observability_monitoring" in keys

        items = list(matrix.items())
        assert len(items) == 6
        assert ("cloud_architecture", ["AWS", "Azure"]) in items

        values = list(matrix.values())
        assert len(values) == 6
        assert ["AWS", "Azure"] in values

        # get method
        assert matrix.get("cloud_architecture") == ["AWS", "Azure"]
        assert matrix.get("cloudArchitecture") == ["AWS", "Azure"]
        assert matrix.get("unknown_domain", "default_val") == "default_val"
        assert matrix.get("unknown_domain") is None

        # __iter__ and dict conversion
        d = dict(matrix)
        assert isinstance(d, dict)
        assert d["cloud_architecture"] == ["AWS", "Azure"]
        assert d["observability_monitoring"] == ["Prometheus"]

        # __contains__
        assert "cloud_architecture" in matrix
        assert "cloudArchitecture" in matrix
        assert "observability_monitoring" in matrix
        assert "nonexistent_domain" not in matrix

    def test_candidate_profile_certifications_fallback_priority(self):
        """Top-level certifications take priority when candidate dict contains empty certs list."""
        payload = {
            "candidate": {
                "first_name": "John",
                "last_name": "Aniekwe",
                "certifications": [],  # Empty in candidate sub-dict
            },
            "certifications": [
                {
                    "name": "Kubernetes and Cloud Native Associate (KCNA)",
                    "issuer": "CNCF",
                    "status": "Active",
                    "tags": ["all", "devops"],
                },
                {
                    "name": "AWS Certified Solutions Architect",
                    "issuer": "AWS",
                    "status": "Active",
                    "tags": ["all", "architect"],
                },
            ],
        }
        profile = CandidateProfile.from_dict(payload)
        assert len(profile.certifications) == 2
        assert profile.certifications[0].name == "Kubernetes and Cloud Native Associate (KCNA)"
        assert len(profile.candidate.certifications) == 2

    def test_get_role_lens_slash_and_whitespace_normalization_all_8_roles(self):
        """CandidateProfile.get_role_lens() maps all 8 target roles across whitespace & slash permutations."""
        profile = CandidateProfile()

        # The 8 target roles from ORIGINAL_REQUEST.md:23
        role_expectations = [
            ("Cloud Solutions Architect", "architect"),
            ("Cloud Infrastructure Engineer", "infra"),
            ("Cloud Engineer", "architect"),
            ("Dev(Sec)Ops Engineer", "devops"),
            ("System Administrator", "infra"),
            ("IT Specialist/Administrator", "support"),
            ("Technical Support Engineer", "support"),
            ("Azure/AWS DevOps Engineer", "devops"),
        ]
        for role_title, expected_lens in role_expectations:
            lens = profile.get_role_lens(role_title)
            assert lens["role_key"] == expected_lens, f"Failed for target role: '{role_title}', expected '{expected_lens}', got '{lens['role_key']}'"

        # Formatting permutations: slashes with/without spaces and extra internal whitespace
        permutations = [
            ("IT Specialist / Administrator", "support"),
            ("IT Specialist/Administrator", "support"),
            ("IT Specialist   /   Administrator", "support"),
            ("IT Administrator", "support"),
            ("IT Specialist", "support"),
            ("Azure / AWS DevOps Engineer", "devops"),
            ("Azure/AWS DevOps Engineer", "devops"),
            ("Azure   /   AWS DevOps Engineer", "devops"),
            ("Dev (Sec) Ops Engineer", "devops"),
            ("DevSecOps Engineer", "devops"),
            ("DevOps Engineer", "devops"),
        ]
        for perm_title, expected_lens in permutations:
            lens = profile.get_role_lens(perm_title)
            assert lens["role_key"] == expected_lens, f"Failed for permutation: '{perm_title}', expected '{expected_lens}', got '{lens['role_key']}'"

    def test_sanitize_ligatures_bullet_double_space_elimination(self):
        """Bullets followed by whitespace do not produce double spaces; varied bullet markers handled."""
        bullet_cases = [
            ("\u2022 Provisioned AKS", "- Provisioned AKS"),
            ("\u2022Provisioned AKS", "- Provisioned AKS"),
            ("\u2022   Provisioned AKS", "- Provisioned AKS"),
            ("\u25CF Configured Terraform", "- Configured Terraform"),
            ("\u25E6 Deployed Helm charts", "- Deployed Helm charts"),
            ("\u25AA Automated CI/CD", "- Automated CI/CD"),
            ("\u25AB Secured IAM policies", "- Secured IAM policies"),
            ("\u2043 Established SLOs", "- Established SLOs"),
            ("\u2219 Monitored metrics", "- Monitored metrics"),
            ("\u2023 Scaled microservices", "- Scaled microservices"),
        ]
        for raw, expected in bullet_cases:
            assert sanitize_ligatures(raw) == expected, f"Failed for bullet input: {raw!r}"

    def test_sanitize_ligatures_presentation_ligatures_adjacent_to_nbsp(self):
        """Presentation ligatures adjacent to NBSP are repaired cleanly without stray spaces."""
        text = "o\uFB00\u00A0ice"
        assert sanitize_ligatures(text) == "office"

        complex_text = "The o\uFB00\u00A0ice demonstrated e\uFB03cient diƯerence in traƯic"
        assert sanitize_ligatures(complex_text) == "The office demonstrated efficient difference in traffic"

    def test_safe_filename_adversarial_extension_clamping(self):
        """safe_filename clamps extensions > 10 chars and guarantees total length <= 200 chars."""
        # Adversarial extension with 300 characters
        filename = safe_filename("John Victor", "Aniekwe", "Cloud Solutions Architect", "CV", ext="A" * 300)
        assert len(filename) <= 200
        # Extension should be clamped to 10 'a's
        assert filename.endswith(".aaaaaaaaaa")
        assert not filename.endswith(".aaaaaaaaaaa")

        # Standard extensions unaffected
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext="pdf") == "John_Aniekwe_DevOps_CV.pdf"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext=".PDF") == "John_Aniekwe_DevOps_CV.pdf"
        assert safe_filename("John", "Aniekwe", "DevOps", "CV", ext="docx") == "John_Aniekwe_DevOps_CV.docx"

