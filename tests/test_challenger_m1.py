"""
Empirical Challenger Test Harness for Milestone 1.
Module: tests/test_challenger_m1.py
Feature: M1 Empirical Stress Testing

Covers:
1. Hostile inputs: missing file path, empty file, invalid JSON syntax, non-dict JSON (array/number/string/bool/null),
   dictionary missing required fields.
2. 5-tier discovery hierarchy verification: load_profile() resolution, fallback to embedded default,
   explicit non-existent path raising ProfileNotFoundError.
3. SkillsMatrix flat extraction: zero duplicates, case-insensitive deduplication, 6-domain coverage.
4. Model serialization round-trip: to_dict / from_dict / to_json / from_json.
5. ATS text utilities & typography edge cases.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from config.settings import Settings, get_settings, parse_bool, parse_port
from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
    Education,
    KpiMetric,
    RoleCategory,
    RoleLens,
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


class TestObjective1HostileInputs:
    """Adversarial Objective 1: Test profile loader against hostile inputs."""

    def test_missing_file_path_explicit(self, tmp_path):
        """Explicitly passing a non-existent file path must raise ProfileNotFoundError."""
        non_existent = tmp_path / "phantom_candidate_data.json"
        with pytest.raises(ProfileNotFoundError):
            load_profile_from_file(non_existent, allow_fallback=False)

        with pytest.raises(ProfileNotFoundError):
            load_profile(str(non_existent), allow_fallback=True)

    def test_empty_file(self, tmp_path):
        """An empty or whitespace-only file must raise ProfileValidationError."""
        empty_file = tmp_path / "empty_profile.json"
        empty_file.write_text("", encoding="utf-8")
        with pytest.raises(ProfileValidationError):
            load_profile_from_file(empty_file, allow_fallback=False)

        ws_file = tmp_path / "whitespace_profile.json"
        ws_file.write_text("   \n\t  \r\n   ", encoding="utf-8")
        with pytest.raises(ProfileValidationError):
            load_profile_from_file(ws_file, allow_fallback=False)

    def test_invalid_json_syntax(self, tmp_path):
        """Malformed JSON syntax must raise ProfileParseError."""
        syntax_cases = [
            "{candidate: unquoted_key}",
            '{"candidate": {"name": "John", missing_quote}}',
            '{"candidate": {"name": "John"}',  # unclosed brace
            '{"candidate": [1, 2, 3,]}',      # trailing comma
            '<<<NOT JSON AT ALL>>>',
            '\x00\x01\x02\x03',
        ]
        for idx, malformed in enumerate(syntax_cases):
            bad_file = tmp_path / f"bad_syntax_{idx}.json"
            bad_file.write_text(malformed, encoding="utf-8")
            with pytest.raises(ProfileParseError):
                load_profile_from_file(bad_file, allow_fallback=False)

    def test_non_dict_json_primitives_and_arrays(self, tmp_path):
        """Top-level JSON arrays, numbers, strings, booleans, and null must raise ProfileValidationError."""
        non_dict_cases = [
            ("array.json", "[1, 2, 3, 4]"),
            ("number.json", "4294967295"),
            ("float.json", "3.1415926535"),
            ("string.json", '"John Victor Aniekwe"'),
            ("bool_true.json", "true"),
            ("bool_false.json", "false"),
            ("null.json", "null"),
        ]
        for fname, content in non_dict_cases:
            file_path = tmp_path / fname
            file_path.write_text(content, encoding="utf-8")
            with pytest.raises(ProfileValidationError):
                load_profile_from_file(file_path, allow_fallback=False)

        # In-memory equivalents
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(["array", "of", "items"])
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(12345)
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict("string")
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(True)
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(None)

    def test_dict_missing_required_fields(self):
        """Dictionaries missing required candidate section must raise ProfileValidationError."""
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict({})

        with pytest.raises(ProfileValidationError):
            load_profile_from_dict({"unrelated": 123, "data": ["a", "b"]})

        with pytest.raises(ProfileValidationError):
            load_profile_from_dict({"stepconSolutions": {"companyName": "Stepcon"}})


class TestObjective2DiscoveryHierarchy:
    """Adversarial Objective 2: Verify 5-tier discovery hierarchy."""

    def test_tier1_explicit_file_and_dir(self, tmp_path):
        """Tier 1: Explicit file and explicit directory containing profile-data.json."""
        dummy_profile = get_embedded_default_profile()
        target_file = tmp_path / "custom_named_profile.json"
        target_file.write_text(json.dumps(dummy_profile), encoding="utf-8")

        p = find_profile_data_path(target_file)
        assert p == target_file.resolve()

        # Explicit directory
        sub_dir = tmp_path / "sub_folder"
        sub_dir.mkdir()
        dir_profile = sub_dir / "profile-data.json"
        dir_profile.write_text(json.dumps(dummy_profile), encoding="utf-8")

        p_dir = find_profile_data_path(sub_dir)
        assert p_dir == dir_profile.resolve()

    def test_tier2_env_var_override(self, tmp_path, monkeypatch):
        """Tier 2: Environment variables CAREER_PROFILE_PATH and CANDIDATE_PROFILE_PATH."""
        dummy_profile = get_embedded_default_profile()
        env_file = tmp_path / "env_profile.json"
        env_file.write_text(json.dumps(dummy_profile), encoding="utf-8")

        monkeypatch.setenv("CAREER_PROFILE_PATH", str(env_file))
        p = find_profile_data_path(None)
        assert p == env_file.resolve()

        monkeypatch.delenv("CAREER_PROFILE_PATH")
        monkeypatch.setenv("CANDIDATE_PROFILE_PATH", str(env_file))
        p2 = find_profile_data_path(None)
        assert p2 == env_file.resolve()

    def test_tier5_fallback_when_none_provided(self, monkeypatch):
        """When no path is given and no file exists, load_profile() falls back to embedded default."""
        monkeypatch.delenv("CAREER_PROFILE_PATH", raising=False)
        monkeypatch.delenv("CANDIDATE_PROFILE_PATH", raising=False)

        # Force find_profile_data_path to return None
        import ingestion.parser as parser_mod
        orig_find = parser_mod.find_profile_data_path
        parser_mod.find_profile_data_path = lambda custom_path=None: None
        try:
            profile = load_profile(None, allow_fallback=True)
            assert isinstance(profile, CandidateProfile)
            assert "John Victor Aniekwe" in profile.full_name
            assert profile.stepcon_solutions.cac_number == "RC - 8284984"

            # When allow_fallback=False, it must raise ProfileNotFoundError
            with pytest.raises(ProfileNotFoundError):
                load_profile(None, allow_fallback=False)
        finally:
            parser_mod.find_profile_data_path = orig_find

    def test_explicit_nonexistent_path_never_silently_falls_back(self):
        """If user explicitly provides a non-existent path, load_profile MUST NOT fall back silently."""
        bogus_path = "C:/totally/fake/path/to/profile.json"
        with pytest.raises(ProfileNotFoundError):
            load_profile(bogus_path, allow_fallback=True)


class TestObjective3SkillsMatrixFlatExtraction:
    """Adversarial Objective 3: Test SkillsMatrix flat extraction without duplicates across all 6 domains."""

    def test_all_6_domains_represented_in_embedded_default(self):
        """Default profile must represent all 6 canonical domains."""
        profile = load_profile(None, allow_fallback=True)
        sm = profile.skills_matrix
        assert len(sm.cloud_architecture) > 0, "Domain 1 missing"
        assert len(sm.dev_sec_ops) > 0, "Domain 2 missing"
        assert len(sm.containerization_kubernetes) > 0, "Domain 3 missing"
        assert len(sm.iac_automation) > 0, "Domain 4 missing"
        assert len(sm.systems_linux_windows) > 0, "Domain 5 missing"
        assert len(sm.observability_monitoring) > 0, "Domain 6 missing"

    def test_zero_duplicates_flat_extraction(self):
        """get_skills_flat() must have zero duplicates (case-insensitive deduplication)."""
        skills = SkillsMatrix(
            cloud_architecture=["AWS", "Microsoft Azure", "Terraform", "aws"],
            dev_sec_ops=["GitHub Actions", "Docker", "shift-left security"],
            iac_automation=["Terraform", "terraform", "TERRAFORM", "Bicep"],
            systems_linux_windows=["Linux", "Ubuntu", "linux"],
            containerization_kubernetes=["Kubernetes", "Docker", "kubernetes", "KUBERNETES"],
            observability_monitoring=["Prometheus", "Grafana", "AWS CloudWatch", "aws"],
        )
        flat = skills.get_skills_flat()
        # Verify deduplication
        lower_skills = [s.lower() for s in flat]
        assert len(lower_skills) == len(set(lower_skills)), f"Duplicates found in flat skills: {lower_skills}"

        # Ensure first occurrence casing is preserved
        assert "AWS" in flat
        assert "Terraform" in flat
        assert "Docker" in flat
        assert "Kubernetes" in flat

    def test_empty_domains_handling(self):
        """SkillsMatrix with empty domains must return empty flat list without error."""
        sm = SkillsMatrix()
        assert sm.get_skills_flat() == []


class TestObjective4RoundtripSerialization:
    """Stress test serialization roundtrip: to_dict -> from_dict and to_json -> from_json."""

    def test_to_dict_from_dict_roundtrip(self):
        """CandidateProfile to_dict -> from_dict roundtrip."""
        profile = load_profile(None, allow_fallback=True)
        dumped = profile.to_dict()
        assert isinstance(dumped, dict)

        # Roundtrip reconstruction
        reconstructed = CandidateProfile.from_dict(dumped)
        assert reconstructed.full_name == profile.full_name
        assert reconstructed.candidate.email == profile.candidate.email
        assert len(reconstructed.experience) == len(profile.experience)
        assert len(reconstructed.certifications) == len(profile.certifications)

    def test_to_json_from_json_roundtrip(self):
        """CandidateProfile to_json -> from_json roundtrip."""
        profile = load_profile(None, allow_fallback=True)
        json_str = profile.to_json()
        assert isinstance(json_str, str)

        reconstructed = CandidateProfile.from_json(json_str)
        assert reconstructed.full_name == profile.full_name
        assert reconstructed.stepcon_solutions.cac_number == "RC - 8284984"


class TestObjective5TextUtilitiesEdgeCases:
    """Stress test ATS text utilities against typography, spacing, and ligature glitches."""

    def test_bullet_spacing_normalization(self):
        """Bullet character followed by space must not produce double spaces."""
        cleaned = sanitize_ligatures("\u2022 Provisioned AKS")
        assert cleaned == "- Provisioned AKS"

    def test_nested_ligatures_with_nbsp(self):
        """Sequences combining Unicode presentation ligatures and non-breaking spaces."""
        text = "o\uFB00\u00A0ice"
        cleaned = sanitize_ligatures(text)
        assert "office" in cleaned



# ============================================================================
# Gate Defect Verification & Dictionary Protocol Stress Tests (Iteration 2)
# ============================================================================

class TestGateDefect1RoleCategoryRoundtripEmpirical:
    """Empirical adversarial verification of Defect 1: RoleCategory roundtrip TypeError."""

    def test_role_category_to_dict_from_dict_50_cycles(self):
        """50 consecutive roundtrips must succeed without TypeError or data corruption."""
        rc = RoleCategory(
            title="Senior DevOps Engineer",
            level="Lead",
            summary="Extensive cloud automation experience",
            core_keywords=["Azure", "Terraform", "Kubernetes", "CI/CD"],
            target_titles=["DevOps Engineer", "Cloud Architect"],
            headline="Expert Cloud & DevOps Engineer",
            key="devops",
        )
        current = rc
        for cycle in range(50):
            d = current.to_dict()
            assert isinstance(d, dict)
            assert d["key"] == "devops"
            current = RoleCategory.from_dict(d, key="devops")
            assert current.title == "Senior DevOps Engineer"
            assert current.key == "devops"
            assert current.level == "Lead"
            assert current.core_keywords == ["Azure", "Terraform", "Kubernetes", "CI/CD"]
            assert current.target_titles == ["DevOps Engineer", "Cloud Architect"]

    def test_role_category_explicit_key_and_dict_key_simultaneous(self):
        """Passing explicit key kwarg to from_dict when dict already has 'key' must not raise TypeError."""
        payload = {
            "title": "Cloud Architect",
            "categoryTitle": "Cloud Architect",
            "key": "dict_key",
            "coreKeywords": ["AWS", "Azure"],
        }
        # Explicit key matches
        rc1 = RoleCategory.from_dict(payload, key="dict_key")
        assert rc1.key == "dict_key"

        # Explicit key overrides dict key
        rc2 = RoleCategory.from_dict(payload, key="override_key")
        assert rc2.key == "override_key"

        # No explicit key passed - dict key used
        rc3 = RoleCategory.from_dict(payload)
        assert rc3.key == "dict_key"

    def test_role_category_all_field_combinations_and_aliases(self):
        """Verify seamless parsing of camelCase and snake_case field aliases simultaneously."""
        payload = {
            "title": "Systems Administrator",
            "categoryTitle": "Systems Administrator Alias",
            "category_title": "Systems Administrator Snake",
            "coreKeywords": ["Linux", "Bash"],
            "core_keywords": ["Linux", "Bash", "PowerShell"],
            "targetTitles": ["SysAdmin"],
            "target_titles": ["SysAdmin", "Systems Engineer"],
            "level": "Staff",
            "summary": "Enterprise sysadmin",
            "headline": "Linux & Windows admin",
            "key": "sysadmin",
        }
        rc = RoleCategory.from_dict(payload, key="sysadmin")
        assert rc.key == "sysadmin"
        assert rc.level == "Staff"
        assert rc.summary == "Enterprise sysadmin"
        assert rc.headline == "Linux & Windows admin"
        assert rc.title in ["Systems Administrator", "Systems Administrator Alias", "Systems Administrator Snake"]

    def test_role_category_empty_and_corrupt_handling(self):
        """Non-dict and empty inputs must safely yield default RoleCategory without crash."""
        rc_none = RoleCategory.from_dict(None, key="fallback")
        assert rc_none.key == "fallback"
        assert rc_none.title == ""

        rc_empty = RoleCategory.from_dict({}, key="empty_key")
        assert rc_empty.key == "empty_key"

        rc_non_dict = RoleCategory.from_dict("not_a_dict", key="safe_key")
        assert rc_non_dict.key == "safe_key"

    def test_candidate_profile_all_4_role_categories_roundtrip(self):
        """CandidateProfile with all 4 canonical role categories survives full serialization roundtrip."""
        profile = load_profile(None, allow_fallback=True)
        assert len(profile.role_categories) >= 4
        assert "devops" in profile.role_categories
        assert "architect" in profile.role_categories
        assert "infra" in profile.role_categories
        assert "support" in profile.role_categories

        dumped = profile.to_dict()
        reconstructed = CandidateProfile.from_dict(dumped)

        assert len(reconstructed.role_categories) == len(profile.role_categories)
        for cat_key in profile.role_categories:
            assert cat_key in reconstructed.role_categories
            orig_cat = profile.role_categories[cat_key]
            recon_cat = reconstructed.role_categories[cat_key]
            assert recon_cat.title == orig_cat.title
            assert recon_cat.key == orig_cat.key
            assert recon_cat.level == orig_cat.level



class TestGateDefect2SkillsMatrixDomain6StarvationEmpirical:
    """Empirical adversarial verification of Defect 2: Domain 6 starvation in SkillsMatrix."""

    def test_default_profile_domain_6_populated(self):
        """Default embedded profile must contain verified Domain 6 observability skills."""
        profile = load_profile(None, allow_fallback=True)
        d6 = profile.skills_matrix.observability_monitoring
        assert len(d6) >= 5, f"Expected at least 5 skills in Domain 6, got {len(d6)}"
        # Verify characteristic observability skills are present
        d6_lower = [s.lower() for s in d6]
        assert any("prometheus" in s or "grafana" in s or "monitor" in s or "cloudwatch" in s for s in d6_lower)

    def test_category_name_variants_classified_into_domain_6(self):
        """Various category titles for Domain 6 must be correctly routed to observability_monitoring."""
        test_variants = [
            ("Observability, SRE & DevSecOps Governance", ["Prometheus", "Grafana"]),
            ("SRE & Site Reliability Engineering", ["SLOs", "Error Budgets"]),
            ("Monitoring, Alerting and Metrics", ["Datadog", "New Relic"]),
            ("Cloud Observability & Tracing", ["OpenTelemetry", "Jaeger"]),
            ("Cloud Governance, Compliance & SRE", ["Azure Policy", "Audit Logs"]),
            ("OBSERVABILITY AND SRE", ["Dynatrace", "Splunk"]),
        ]
        for cat_name, items in test_variants:
            raw_payload = [{"category": cat_name, "items": items}]
            sm = SkillsMatrix.from_dict(raw_payload)
            assert sm.observability_monitoring == items, f"Failed for category name: {cat_name}"

    def test_domain_2_and_domain_6_coexistence_no_starvation(self):
        """When both Domain 2 (DevSecOps) and Domain 6 (Observability) are present, neither starves."""
        raw_payload = [
            {
                "category": "DevSecOps & Platform Engineering",
                "items": ["SonarQube", "Trivy", "Snyk", "Aqua Security", "SAST/DAST"],
            },
            {
                "category": "Observability, SRE & DevSecOps Governance",
                "items": ["Prometheus", "Grafana", "CloudWatch", "Datadog", "OpenTelemetry"],
            },
        ]
        sm = SkillsMatrix.from_dict(raw_payload)
        assert len(sm.dev_sec_ops) == 5, f"Domain 2 starved or distorted: {sm.dev_sec_ops}"
        assert len(sm.observability_monitoring) == 5, f"Domain 6 starved: {sm.observability_monitoring}"
        assert "SonarQube" in sm.dev_sec_ops
        assert "Prometheus" in sm.observability_monitoring

    def test_cumulative_domain_6_multi_entry_aggregation(self):
        """Multiple categories matching Domain 6 must cumulatively aggregate skills."""
        raw_payload = [
            {"category": "Observability & SRE", "items": ["Prometheus", "Grafana"]},
            {"category": "Monitoring & Metrics", "items": ["CloudWatch", "Datadog"]},
            {"category": "Governance & Compliance", "items": ["FinOps", "Audit Logs"]},
        ]
        sm = SkillsMatrix.from_dict(raw_payload)
        assert len(sm.observability_monitoring) == 6
        assert "Prometheus" in sm.observability_monitoring
        assert "CloudWatch" in sm.observability_monitoring
        assert "FinOps" in sm.observability_monitoring


class TestGateDefect3BulletDoubleSpaceEmpirical:
    """Empirical adversarial verification of Defect 3: Bullet point double spaces."""

    @pytest.mark.parametrize("bullet_char", [
        "\u2022",  # bullet
        "\u25CF",  # black circle
        "\u25E6",  # white bullet
        "\u25AA",  # black small square
        "\u25AB",  # white small square
        "\u2043",  # hyphen bullet
        "\u2219",  # bullet operator
        "\u2023",  # triangular bullet
    ])
    def test_all_bullet_glyphs_single_space(self, bullet_char):
        """Every supported Unicode bullet followed by standard single space maps to '- Word' without double space."""
        raw = f"{bullet_char} Provisioned AKS clusters across 3 regions"
        cleaned = sanitize_ligatures(raw)
        assert cleaned == "- Provisioned AKS clusters across 3 regions"
        assert not cleaned.startswith("-  ")

    @pytest.mark.parametrize("spacing", [
        " ",
        "  ",
        "   ",
        "    ",
        "\t",
        "\t\t",
        " \t ",
        "\u00A0",
        "\u00A0\u00A0",
        " \u00A0 ",
    ])
    def test_bullet_irregular_and_multiple_horizontal_whitespace(self, spacing):
        """Bullets followed by 1, 2, 3, 4 spaces, tabs, or NBSP must all normalize to strictly '- Word'."""
        raw = f"\u2022{spacing}Automated deployment pipelines"
        cleaned = sanitize_ligatures(raw)
        assert cleaned == "- Automated deployment pipelines"
        assert not cleaned.startswith("-  ")

    def test_bullet_zero_spacing(self):
        """Bullet directly glued to word with zero whitespace must separate into '- Word'."""
        raw = "\u2022Engineered zero-downtime database failover"
        cleaned = sanitize_ligatures(raw)
        assert cleaned == "- Engineered zero-downtime database failover"

    def test_multiline_resume_experience_bullet_points(self):
        """Realistic multi-line work experience block with mixed bullets and spacing."""
        raw_resume_snippet = (
            "Professional Experience:\n"
            "• Provisioned 15+ AKS and EKS production clusters\n"
            "•  Architected CI/CD workflows utilizing GitHub Actions\n"
            "•   Enforced Shift-Left DevSecOps security gates\n"
            "•\tAchieved 99.9% uptime across critical banking services\n"
            "•\u00A0Cut cloud infrastructure monthly expenditure by 35%"
        )
        cleaned = sanitize_ligatures(raw_resume_snippet)
        for line in cleaned.splitlines():
            if line.startswith("-"):
                assert not line.startswith("-  "), f"Double space detected on line: {line!r}"
                assert line.startswith("- "), f"Line does not start with standard bullet: {line!r}"


class TestGateDefect4NBSPLigatureAdjacentEmpirical:
    """Empirical adversarial verification of Defect 4: NBSP ligature adjacent characters."""

    @pytest.mark.parametrize("corrupted,expected_word", [
        # ff ligature (\uFB00)
        ("o\uFB00\u00A0ice", "office"),
        ("o\u00A0\uFB00ice", "office"),
        ("o\u00A0\uFB00\u00A0ice", "office"),
        ("di\uFB00\u00A0erent", "different"),
        ("di\u00A0\uFB00erent", "different"),
        ("e\uFB00\u00A0ect", "effect"),
        ("sta\u00A0\uFB00", "staff"),
        # fi ligature (\uFB01)
        ("con\uFB01\u00A0gure", "configure"),
        ("con\u00A0\uFB01gure", "configure"),
        ("de\uFB01\u00A0nition", "definition"),
        ("\uFB01\u00A0rst", "first"),
        # fl ligature (\uFB02)
        ("work\uFB02\u00A0ow", "workflow"),
        ("work\u00A0\uFB02ow", "workflow"),
        ("in\uFB02\u00A0uence", "influence"),
        # ffi ligature (\uFB03)
        ("e\uFB03\u00A0cient", "efficient"),
        ("e\u00A0\uFB03cient", "efficient"),
        ("tra\uFB03\u00A0c", "traffic"),
        ("tra\u00A0\uFB03\u00A0c", "traffic"),
        # ffl ligature (\uFB04)
        ("a\uFB04\u00A0uent", "affluent"),
        ("a\u00A0\uFB04uent", "affluent"),
    ])
    def test_all_ligature_types_adjacent_to_nbsp(self, corrupted, expected_word):
        """All standard typographic ligatures adjacent to NBSP are repaired cleanly."""
        cleaned = sanitize_ligatures(corrupted)
        assert cleaned == expected_word, f"Corrupted {corrupted!r} resulted in {cleaned!r}, expected {expected_word!r}"

    def test_complex_sentence_with_mixed_ligatures_and_nbsp(self):
        """Full enterprise paragraph containing multiple corrupted ligatures and NBSPs."""
        text = (
            "The regional o\uFB00\u00A0ice con\uFB01\u00A0gured e\uFB03\u00A0cient work\uFB02\u00A0ows "
            "with zero di\uFB00\u00A0erence in network tra\uFB03\u00A0c."
        )
        cleaned = sanitize_ligatures(text)
        expected = (
            "The regional office configured efficient workflows "
            "with zero difference in network traffic."
        )
        assert cleaned == expected

    def test_ligatures_with_adjacent_punctuation_and_apostrophes(self):
        """Words with ligatures, NBSP, and trailing apostrophes or punctuation."""
        cases = [
            ("o\uFB00\u00A0ice's", "office's"),
            ("e\uFB03\u00A0cient!", "efficient!"),
            ("con\uFB01\u00A0guration,", "configuration,"),
            ("(di\uFB00\u00A0erence)", "(difference)"),
        ]
        for src, expected in cases:
            cleaned = sanitize_ligatures(src)
            assert cleaned == expected


class TestSkillsMatrixDictionaryProtocolEmpirical:
    """Empirical stress-testing of SkillsMatrix dictionary protocol:
    .items(), .keys(), .values(), .get(), __iter__(), __len__(), __contains__()
    verifying 100% equivalence to standard Python dictionaries.
    """

    @pytest.fixture
    def matrix_and_dict(self):
        """Provides a populated SkillsMatrix and an equivalent standard Python dict."""
        data = {
            "cloud_architecture": ["AWS", "Microsoft Azure", "GCP"],
            "dev_sec_ops": ["Docker", "GitHub Actions", "SonarQube"],
            "iac_automation": ["Terraform", "Bicep", "Ansible"],
            "systems_linux_windows": ["Ubuntu", "RHEL", "Active Directory"],
            "containerization_kubernetes": ["Kubernetes", "Helm", "AKS"],
            "observability_monitoring": ["Prometheus", "Grafana", "Datadog"],
        }
        sm = SkillsMatrix(**data)
        std_dict = dict(data)
        return sm, std_dict

    def test_items_method_view_and_iteration(self, matrix_and_dict):
        """SkillsMatrix.items() returns an iterable of 6 (key, value) pairs identical to dict.items()."""
        sm, std_dict = matrix_and_dict
        sm_items = list(sm.items())
        std_items = list(std_dict.items())

        assert len(sm_items) == 6
        assert len(sm_items) == len(std_items)
        assert sm_items == std_items

        # Verify iteration unpacking
        for (k_sm, v_sm), (k_std, v_std) in zip(sm.items(), std_dict.items()):
            assert k_sm == k_std
            assert v_sm == v_std
            assert isinstance(k_sm, str)
            assert isinstance(v_sm, list)

        # Reconstruct standard dict from .items()
        reconstructed = dict(sm.items())
        assert reconstructed == std_dict

    def test_keys_method_view_and_set_operations(self, matrix_and_dict):
        """SkillsMatrix.keys() yields all 6 canonical keys in identical order to standard dict."""
        sm, std_dict = matrix_and_dict
        assert list(sm.keys()) == list(std_dict.keys())
        assert set(sm.keys()) == set(std_dict.keys())
        assert len(sm.keys()) == 6

        expected_keys = [
            "cloud_architecture",
            "dev_sec_ops",
            "iac_automation",
            "systems_linux_windows",
            "containerization_kubernetes",
            "observability_monitoring",
        ]
        assert list(sm.keys()) == expected_keys

    def test_values_method_view(self, matrix_and_dict):
        """SkillsMatrix.values() returns all 6 skill lists identical to dict.values()."""
        sm, std_dict = matrix_and_dict
        sm_values = list(sm.values())
        std_values = list(std_dict.values())

        assert len(sm_values) == 6
        assert sm_values == std_values
        assert sm_values[0] == ["AWS", "Microsoft Azure", "GCP"]
        assert sm_values[5] == ["Prometheus", "Grafana", "Datadog"]

    def test_get_method_canonical_camel_and_defaults(self, matrix_and_dict):
        """SkillsMatrix.get() matches dict.get() for existing, default, and camelCase keys."""
        sm, std_dict = matrix_and_dict

        # Existing canonical keys
        for key in std_dict:
            assert sm.get(key) == std_dict.get(key)
            assert sm.get(key, ["fallback"]) == std_dict.get(key, ["fallback"])

        # CamelCase alias lookups supported via get
        assert sm.get("cloudArchitecture") == ["AWS", "Microsoft Azure", "GCP"]
        assert sm.get("devSecOps") == ["Docker", "GitHub Actions", "SonarQube"]
        assert sm.get("iacAutomation") == ["Terraform", "Bicep", "Ansible"]
        assert sm.get("systemsLinuxWindows") == ["Ubuntu", "RHEL", "Active Directory"]
        assert sm.get("containerizationKubernetes") == ["Kubernetes", "Helm", "AKS"]
        assert sm.get("observabilityMonitoring") == ["Prometheus", "Grafana", "Datadog"]

        # Non-existent keys default handling
        assert sm.get("quantum_computing") is None
        assert sm.get("quantum_computing", ["fallback"]) == ["fallback"]
        assert sm.get("unknown_key", 42) == 42
        assert sm.get("", "empty_default") == "empty_default"

    def test_iter_dunder_protocol(self, matrix_and_dict):
        """iter(sm) iterates over the 6 canonical keys identically to standard dict."""
        sm, std_dict = matrix_and_dict

        # list(sm) must match list(std_dict)
        assert list(sm) == list(std_dict)

        # Generator comprehension
        comprehended_keys = [k for k in sm]
        assert comprehended_keys == list(std_dict.keys())

        # Manual iterator next() protocol
        it = iter(sm)
        assert next(it) == "cloud_architecture"
        assert next(it) == "dev_sec_ops"
        assert next(it) == "iac_automation"
        assert next(it) == "systems_linux_windows"
        assert next(it) == "containerization_kubernetes"
        assert next(it) == "observability_monitoring"
        with pytest.raises(StopIteration):
            next(it)

    def test_len_dunder_protocol(self, matrix_and_dict):
        """len(sm) returns exactly 6."""
        sm, std_dict = matrix_and_dict
        assert len(sm) == 6
        assert len(sm) == len(std_dict)

        # Empty matrix still represents the 6 canonical domains
        empty_sm = SkillsMatrix()
        assert len(empty_sm) == 6

    def test_contains_dunder_protocol_and_type_safety(self, matrix_and_dict):
        """key in sm behaves identically to standard dict."""
        sm, std_dict = matrix_and_dict

        # All canonical keys are in sm
        for k in std_dict:
            assert k in sm
            assert (k in sm) == (k in std_dict)

        # CamelCase aliases are in sm
        assert "cloudArchitecture" in sm
        assert "observabilityMonitoring" in sm

        # Missing keys are NOT in sm
        assert "nonexistent_domain" not in sm
        assert "" not in sm
        assert "random_string" not in sm

        # Non-string keys: safe check without unhandled exceptions
        assert None not in sm
        assert 12345 not in sm
        assert 3.14 not in sm

        # Unhashable types raise TypeError identically to standard dict
        with pytest.raises(TypeError):
            _ = [] in sm
        with pytest.raises(TypeError):
            _ = [] in std_dict

    def test_dict_conversion_and_kwargs_unpacking_interop(self, matrix_and_dict):
        """dict(sm) and **sm interoperability."""
        sm, std_dict = matrix_and_dict

        # dict(sm) directly converts to standard python dict
        as_dict = dict(sm)
        assert isinstance(as_dict, dict)
        assert as_dict == std_dict

        # kwargs unpacking: dict(**sm)
        unpacked_dict = dict(**sm)
        assert unpacked_dict == std_dict

        # JSON serialization of dict(sm)
        json_str = json.dumps(dict(sm))
        assert isinstance(json_str, str)
        reloaded = json.loads(json_str)
        assert reloaded == std_dict

        # SkillsMatrix construction from dict(sm)
        sm_reconstructed = SkillsMatrix(**dict(sm))
        assert sm_reconstructed.cloud_architecture == sm.cloud_architecture
        assert sm_reconstructed.observability_monitoring == sm.observability_monitoring

    def test_attribute_and_item_parity(self, matrix_and_dict):
        """For every canonical key, sm[k] == getattr(sm, k)."""
        sm, _ = matrix_and_dict
        canonical_keys = [
            "cloud_architecture",
            "dev_sec_ops",
            "iac_automation",
            "systems_linux_windows",
            "containerization_kubernetes",
            "observability_monitoring",
        ]
        for key in canonical_keys:
            assert sm[key] == getattr(sm, key)
            assert sm.get(key) == getattr(sm, key)

    def test_collections_abc_protocols_compliance(self, matrix_and_dict):
        """SkillsMatrix satisfies collections.abc Iterable, Sized, and Container protocols."""
        from collections.abc import Container, Iterable, Sized
        sm, _ = matrix_and_dict
        assert isinstance(sm, Iterable)
        assert isinstance(sm, Sized)
        assert isinstance(sm, Container)


if __name__ == "__main__":
    pytest.main(["-v", __file__])

