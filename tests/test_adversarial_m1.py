"""
Adversarial Stress Test Suite for Milestone 1: Ingestion, Modeling, and ATS Text Utilities.
Target Module: tests/test_adversarial_m1.py
Feature: M1 Hardening & Adversarial Verification

Adversarial Objectives:
1. Test ligature sanitizer with extreme inputs: nested ligatures, mixed case (EƯICIENCY, eƯective),
   multiple non-breaking spaces, zero-width chars, soft hyphens. Verify sanitize_ligatures repairs
   them all without throwing exceptions.
2. Test safe filename generator with edge cases: empty strings, pure whitespace, strings with 500+ characters,
   slashes, backslashes, colons, Windows reserved names (CON, PRN, AUX, NUL). Verify length <= 200 and zero invalid chars.
3. Test schema robustness: load profile from corrupted JSON dicts, test StepconProfile CAC validation
   rejection of 'RC - 0000000', test get_role_lens with unknown role fallback.
"""

from __future__ import annotations

import json
import pytest
from typing import Any, Dict

from config.settings import get_settings, parse_bool, parse_port
from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
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
# Objective 1: Ligature Sanitizer Extreme Inputs
# ============================================================================

class TestAdversarialLigatureSanitizer:
    """Stress tests sanitize_ligatures against extreme and adversarial Unicode inputs."""

    def test_extreme_mixed_case_efficiency(self):
        """Mixed-case variations of EƯICIENCY / eƯective must normalize without exceptions."""
        cases = [
            ("EƯICIENCY", "EFFICIENCY"),
            ("eƯective", "effective"),
            ("EƯective", "Effective"),
            ("EƯECTIVE", "EFFECTIVE"),
            ("EƯiciency", "Efficiency"),
            ("eƯiciency", "efficiency"),
            ("EƯort", "Effort"),
            ("eƯort", "effort"),
            ("HIGH EƯICIENCY CLOUD ARCHITECTURE", "HIGH EFFICIENCY CLOUD ARCHITECTURE"),
            ("EƯective leadership and EƯicient delivery", "Effective leadership and efficient delivery"),
        ]
        for corrupted, expected in cases:
            repaired = sanitize_ligatures(corrupted)
            assert repaired == expected, f"Failed for input: {corrupted!r}, got: {repaired!r}"

    def test_multiple_non_breaking_spaces(self):
        """Runs of varied non-breaking, thin, em, and ideographic spaces must convert cleanly."""
        text_with_spaces = (
            "AWS\u00A0\u00A0Certified\u202FSolutions\u2007Architect\u2000and\u2001Kubernetes"
            "\u2002KCNA\u2003Administrator\u2004in\u2005Lagos\u2006Nigeria\u3000(UTC+1)"
        )
        repaired = sanitize_ligatures(text_with_spaces)
        assert "\u00A0" not in repaired
        assert "\u202F" not in repaired
        assert "\u2007" not in repaired
        assert "\u2000" not in repaired
        assert "\u2001" not in repaired
        assert "\u2002" not in repaired
        assert "\u2003" not in repaired
        assert "\u3000" not in repaired
        assert "AWS  Certified Solutions Architect and Kubernetes KCNA Administrator in Lagos Nigeria (UTC+1)" == repaired

    def test_zero_width_chars_and_soft_hyphens(self):
        """Zero-width spaces, ZWNJ, ZWJ, soft hyphens, and BOM must be completely purged."""
        malicious = (
            "\uFEFFKuber\u200Bnetes\u200C \u200Dinfra\u00ADstructure "
            "e\u00ADƯ\u00ADiciency and con\u00AD\u200Bfig\u00ADuration"
        )
        repaired = sanitize_ligatures(malicious)
        assert "\uFEFF" not in repaired
        assert "\u200B" not in repaired
        assert "\u200C" not in repaired
        assert "\u200D" not in repaired
        assert "\u00AD" not in repaired
        assert "Kubernetes infrastructure efficiency and configuration" == repaired

    def test_nested_ligatures_and_presentation_forms(self):
        """Nested sequences combining Unicode presentation forms, NBSP, and horn glyphs."""
        nested = "The o\uFB00\u00A0ice demonstrated e\uFB03cient diƯerence in traƯic"
        repaired = sanitize_ligatures(nested)
        assert "office" in repaired
        assert "efficient" in repaired
        assert "difference" in repaired
        assert "traffic" in repaired
        assert "\uFB00" not in repaired
        assert "\uFB03" not in repaired
        assert "Ư" not in repaired

    def test_no_exception_on_bizarre_inputs(self):
        """Sanitizer must be resilient to None, integers, empty string, pure control codes."""
        assert sanitize_ligatures(None) == ""
        assert sanitize_ligatures("") == ""
        assert sanitize_ligatures(999999) == "999999"
        assert sanitize_ligatures("\x00\x01\x02\x03") == "\x00\x01\x02\x03"
        # Giant string stress test
        giant = "eƯiciency " * 10000
        repaired_giant = sanitize_ligatures(giant)
        assert "Ư" not in repaired_giant
        assert repaired_giant.startswith("efficiency ")


# ============================================================================
# Objective 2: Safe Filename Generator Edge Cases
# ============================================================================

class TestAdversarialSafeFilename:
    """Stress tests safe_filename against filesystem boundary and injection cases."""

    INVALID_FS_CHARS = set(r'<>:"/\|?*' + "\0")

    def test_empty_and_pure_whitespace(self):
        """Empty strings and pure whitespace must safely fall back to canonical defaults."""
        fn1 = safe_filename("", "", "", "", "")
        assert fn1 == "Candidate_Profile_General_Document.pdf"
        assert len(fn1) <= 200

        fn2 = safe_filename("   \t  ", "\n\r  ", "   ", "   ", "   ")
        assert fn2 == "Candidate_Profile_General_Document.pdf"
        assert len(fn2) <= 200

    def test_slashes_backslashes_colons_and_wildcards(self):
        """Filesystem illegal characters must be eradicated with zero residual invalid chars."""
        malicious_input = {
            "first": "John/..\\Victor:Major",
            "last": "Aniekwe*Senior?Lead",
            "role": 'Cloud<Solutions>"Architect"|DevOps',
            "doc_type": "CV/Resume:v1.0",
            "ext": "..\\//PDF",
        }
        fn = safe_filename(**malicious_input)
        assert not any(c in self.INVALID_FS_CHARS for c in fn)
        assert "/" not in fn
        assert "\\" not in fn
        assert ":" not in fn
        assert "*" not in fn
        assert "?" not in fn
        assert "<" not in fn
        assert ">" not in fn
        assert "|" not in fn
        assert '"' not in fn
        assert " " not in fn
        assert len(fn) <= 200
        assert fn.endswith(".pdf")

    def test_strings_with_500_plus_characters(self):
        """Extreme length inputs (500+ characters) must be bounded strictly to <= 200 chars."""
        huge_first = "A" * 600
        huge_last = "B" * 600
        huge_role = "C" * 600
        huge_doc = "D" * 600
        fn = safe_filename(huge_first, huge_last, huge_role, huge_doc, "pdf")
        assert len(fn) <= 200
        assert not any(c in self.INVALID_FS_CHARS for c in fn)
        assert fn.endswith(".pdf")

    def test_windows_reserved_device_names(self):
        """Windows reserved device names (CON, PRN, AUX, NUL) must never produce bare devices."""
        reserved_tokens = ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"]
        for token in reserved_tokens:
            fn = safe_filename(token, "Aniekwe", "DevOps", "CV", "pdf")
            assert len(fn) <= 200
            assert not any(c in self.INVALID_FS_CHARS for c in fn)
            # Base name must not equal the bare reserved device name
            base = fn.rsplit(".", 1)[0]
            assert base.upper() != token.upper()
            assert fn.startswith(f"{token}_")


# ============================================================================
# Objective 3: Schema Robustness, CAC Rejection & RoleLens Fallback
# ============================================================================

class TestAdversarialSchemaRobustness:
    """Stress tests model schemas, statutory CAC validation, and loader error handling."""

    def test_stepcon_profile_cac_rejection(self):
        """StepconProfile must strictly reject invalid CAC registration numbers."""
        # Rejection of RC - 0000000
        with pytest.raises(ValueError) as excinfo:
            StepconProfile(company_name="Stepcon Solutions", cac_number="RC - 0000000")
        assert "Invalid CAC registration number" in str(excinfo.value)
        assert "RC - 0000000" in str(excinfo.value)

        # Rejection of empty CAC
        with pytest.raises(ValueError):
            StepconProfile(cac_number="")

        # Rejection of bogus strings
        with pytest.raises(ValueError):
            StepconProfile(cac_number="RC - 1234567")

        # Successful acceptance of valid statutory CAC
        stepcon = StepconProfile(cac_number="RC - 8284984")
        assert stepcon.cac_number == "RC - 8284984"

    def test_get_role_lens_unknown_role_fallback(self, minimal_candidate_dict):
        """CandidateProfile.get_role_lens must fall back safely to 'devops' for unknown roles."""
        profile = load_profile_from_dict(minimal_candidate_dict)
        
        # Test unknown role keys
        unknown_keys = [
            "quantum_mechanic_9999",
            "Astronaut",
            "",
            "   ",
            "unknown_architectural_specialist",
        ]
        for key in unknown_keys:
            lens = profile.get_role_lens(key)
            assert isinstance(lens, RoleLens)
            assert lens.role_key == "devops"
            # Dual dictionary and attribute access
            assert lens.category_title == lens["category_title"]
            assert len(lens.experience) >= 1
            assert len(lens.certifications) >= 1

    def test_load_profile_corrupted_json_dicts(self):
        """load_profile_from_dict must reject corrupted, empty, or missing candidate blocks."""
        # None input
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(None)

        # Non-dict input
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict(["not", "a", "dict"])

        # Empty dict
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict({})

        # Missing candidate block and aliases
        with pytest.raises(ProfileValidationError):
            load_profile_from_dict({"unrelated_payload": {"key": "val"}})

    def test_load_profile_file_error_hierarchy(self, tmp_path):
        """Verify strict error hierarchy: ProfileNotFoundError, ProfileParseError, ProfileValidationError."""
        # 1. Non-existent file with allow_fallback=False
        with pytest.raises(ProfileNotFoundError):
            load_profile_from_file(tmp_path / "does_not_exist.json", allow_fallback=False)

        # 2. Corrupted JSON syntax
        bad_json = tmp_path / "syntax_error.json"
        bad_json.write_text("{candidate: [unclosed", encoding="utf-8")
        with pytest.raises(ProfileParseError):
            load_profile_from_file(bad_json)

        # 3. Empty file
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("   ", encoding="utf-8")
        with pytest.raises(ProfileValidationError):
            load_profile_from_file(empty_file)


# ============================================================================
# Auxiliary Robustness: Settings & Dry-Run Guarantees
# ============================================================================

class TestAdversarialSettingsRobustness:
    """Stress tests configuration settings, boolean coercion, and safe port resolution."""

    def test_parse_bool_edge_cases(self):
        """parse_bool must handle truthy, falsy, and unexpected types."""
        assert parse_bool("true") is True
        assert parse_bool("TRUE") is True
        assert parse_bool("1") is True
        assert parse_bool("yes") is True
        assert parse_bool("on") is True
        assert parse_bool(True) is True
        assert parse_bool(1) is True

        assert parse_bool("false") is False
        assert parse_bool("0") is False
        assert parse_bool("no") is False
        assert parse_bool("off") is False
        assert parse_bool("") is False
        assert parse_bool(False) is False
        assert parse_bool(0) is False

        # Fallback for gibberish
        assert parse_bool("gibberish", default=True) is True
        assert parse_bool("gibberish", default=False) is False
        assert parse_bool(None, default=True) is True

    def test_parse_port_edge_cases(self):
        """parse_port must validate valid ranges 1..65535 and fall back on out-of-range/gibberish."""
        assert parse_port("587") == 587
        assert parse_port(465) == 465
        assert parse_port(25) == 25
        assert parse_port("invalid_string", default=587) == 587
        assert parse_port(0, default=587) == 587
        assert parse_port(70000, default=587) == 587
        assert parse_port(-1, default=587) == 587
        assert parse_port(None, default=587) == 587

    def test_settings_dry_run_default_safety(self):
        """Settings must default to dry_run=True and offline_mode=True."""
        s = get_settings(env_file="non_existent_env_file.env")
        assert s.dry_run is True
        assert s.offline_mode is True
        assert s.notification_email == "aniekwevictor9@gmail.com"
