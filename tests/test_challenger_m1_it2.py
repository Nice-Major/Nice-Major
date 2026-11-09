"""
Milestone 1 Iteration 2 Challenger Adversarial Stress Suite.
Module: tests.test_challenger_m1_it2
Author: teamwork_challenger (challenger_m1_it2_1)

Empirically tests and stress-tests:
1. CandidateProfile roundtrip serialization across multiple nested and stripped variants (zero TypeErrors on RoleCategory).
2. SkillsMatrix domain classification: all 6 domains receive non-zero skills, Domain 6 contains all 5 canonical skills.
3. CandidateProfile.get_role_lens() with all 8 target roles and messy formatting (zero persona inversions).
4. sanitize_ligatures with bullet characters and NBSP (zero double spaces).
"""

from __future__ import annotations

import itertools
import json
import random
import re
from typing import Any, Dict, List

import pytest

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
from ingestion.parser import get_embedded_default_profile, load_profile
from ingestion.text_utils import sanitize_ligatures


# ============================================================================
# Task 1: CandidateProfile & RoleCategory Serialization Roundtrip
# ============================================================================

class TestTask1CandidateProfileRoundtrip:
    """Stress tests CandidateProfile.from_dict(profile.to_dict()) and RoleCategory serialization."""

    def test_roundtrip_default_profile_preservation(self):
        """Full default candidate profile roundtrips without loss or TypeError."""
        profile = load_profile(None, allow_fallback=True)
        exported = profile.to_dict()
        reconstructed = CandidateProfile.from_dict(exported)

        assert reconstructed.full_name == profile.full_name
        assert reconstructed.candidate.email == profile.candidate.email
        assert len(reconstructed.role_categories) == len(profile.role_categories)
        assert len(reconstructed.certifications) == len(profile.certifications)
        assert len(reconstructed.kpi_metrics) == len(profile.kpi_metrics)
        assert reconstructed.stepcon_solutions.cac_number == profile.stepcon_solutions.cac_number

        for k, original_rc in profile.role_categories.items():
            assert k in reconstructed.role_categories
            recon_rc = reconstructed.role_categories[k]
            assert recon_rc.title == original_rc.title
            assert recon_rc.key == original_rc.key
            assert recon_rc.level == original_rc.level

    def test_roundtrip_multi_generation_10_cycles(self):
        """10 sequential serialization and deserialization cycles maintain 100% data integrity."""
        current = load_profile(None, allow_fallback=True)
        baseline = current.to_dict()

        for gen in range(10):
            d = current.to_dict()
            current = CandidateProfile.from_dict(d)

        final_dict = current.to_dict()
        assert len(final_dict["role_categories"]) == len(baseline["role_categories"])
        for k in baseline["role_categories"]:
            assert final_dict["role_categories"][k]["title"] == baseline["role_categories"][k]["title"]
            assert final_dict["role_categories"][k]["key"] == baseline["role_categories"][k]["key"]

    def test_roundtrip_empty_and_minimal_variants(self):
        """CandidateProfile.from_dict() handles empty and minimal dicts gracefully."""
        # Empty dict
        p_empty = CandidateProfile.from_dict({})
        assert isinstance(p_empty, CandidateProfile)
        assert len(p_empty.role_categories) == 0

        # Roundtrip empty profile
        d_empty = p_empty.to_dict()
        p_empty2 = CandidateProfile.from_dict(d_empty)
        assert isinstance(p_empty2, CandidateProfile)

        # None / non-dict input
        p_none = CandidateProfile.from_dict(None)  # type: ignore
        assert isinstance(p_none, CandidateProfile)

    def test_role_category_stripped_and_hostile_variants(self):
        """Zero TypeErrors on RoleCategory when given various stripped or extra fields."""
        variants: List[Dict[str, Any]] = [
            {},
            {"title": "DevOps Engineer"},
            {"categoryTitle": "DevOps Engineer"},
            {"key": "devops"},
            {"key": "devops", "title": "DevOps Engineer"},
            {"key": "devops", "categoryTitle": "DevOps Engineer"},
            {"key": "devops", "title": "DevOps", "categoryTitle": "DevOps"},
            {"key": "devops", "level": "Principal", "summary": "Architect lead"},
            {"title": "DevOps", "unknown_field_1": 123, "extra_nested": {"a": "b"}},
            {"key": "arch", "target_titles": ["Architect", "Cloud Engineer"]},
            {"key": "arch", "targetTitles": ["Architect", "Cloud Engineer"]},
            {"key": "arch", "core_keywords": ["AWS", "Azure"]},
            {"key": "arch", "coreKeywords": ["AWS", "Azure"]},
        ]

        for i, var in enumerate(variants):
            # Test direct from_dict with key parameter
            rc1 = RoleCategory.from_dict(var, key="devops")
            assert isinstance(rc1, RoleCategory)
            assert rc1.key == "devops"

            # Test direct from_dict without key parameter
            rc2 = RoleCategory.from_dict(var)
            assert isinstance(rc2, RoleCategory)

            # Test CandidateProfile roundtrip with this variant
            profile_dict = {"roleCategories": {"devops": var}}
            cp = CandidateProfile.from_dict(profile_dict)
            assert "devops" in cp.role_categories
            assert isinstance(cp.role_categories["devops"], RoleCategory)

            # Re-export and re-deserialize
            exported = cp.to_dict()
            cp_reconstructed = CandidateProfile.from_dict(exported)
            assert "devops" in cp_reconstructed.role_categories
            assert cp_reconstructed.role_categories["devops"].key == "devops"

    def test_role_category_direct_hostile_inputs(self):
        """RoleCategory.from_dict handles non-dict primitives safely."""
        rc_none = RoleCategory.from_dict(None, key="fallback")  # type: ignore
        assert rc_none.key == "fallback"

        rc_str = RoleCategory.from_dict("invalid_string", key="fallback")  # type: ignore
        assert rc_str.key == "fallback"

        rc_int = RoleCategory.from_dict(12345, key="fallback")  # type: ignore
        assert rc_int.key == "fallback"


# ============================================================================
# Task 2: SkillsMatrix Domain Classification
# ============================================================================

class TestTask2SkillsMatrixDomainClassification:
    """Stress tests 6-domain classification and canonical skills routing."""

    CANONICAL_DOMAIN_6_SKILLS = [
        "Azure Monitor, Application Insights & Log Analytics Workspaces",
        "AWS CloudWatch & Distributed Tracing",
        "Prometheus & Grafana Dashboarding",
        "SLI/SLO/SLA Performance Auditing (99.9% Platform SLA)",
        "Incident Management & Structured Root Cause Analysis (99% Resolution Rate)",
    ]

    def test_all_6_domains_receive_skills_from_embedded_default(self):
        """In embedded default profile, all 6 domains receive non-zero skills."""
        raw = get_embedded_default_profile()["skillsMatrix"]
        sm = SkillsMatrix.from_dict(raw)

        assert len(sm.cloud_architecture) > 0, "Domain 1 is empty"
        assert len(sm.dev_sec_ops) > 0, "Domain 2 is empty"
        assert len(sm.iac_automation) > 0, "Domain 3 is empty"
        assert len(sm.systems_linux_windows) > 0, "Domain 4 is empty"
        assert len(sm.containerization_kubernetes) > 0, "Domain 5 is empty"
        assert len(sm.observability_monitoring) > 0, "Domain 6 is empty"

    def test_domain_6_has_all_5_canonical_skills_in_embedded_default(self):
        """In embedded default profile, Domain 6 contains all 5 canonical skills."""
        raw = get_embedded_default_profile()["skillsMatrix"]
        sm = SkillsMatrix.from_dict(raw)

        assert len(sm.observability_monitoring) == 5
        for skill in self.CANONICAL_DOMAIN_6_SKILLS:
            assert skill in sm.observability_monitoring, f"Missing canonical skill in Domain 6: {skill}"

    def test_category_6_observability_sre_devsecops_governance_routing(self):
        """
        Category 'Observability, SRE & DevSecOps Governance' routes to Domain 6 (observability_monitoring)
        and does NOT get hijacked by Domain 2 (dev_sec_ops).
        """
        categories = [
            {
                "category": "AI-Augmented Engineering & MLOps",
                "items": ["MLOps Pipeline", "Model Tuning"],
            },
            {
                "category": "Observability, SRE & DevSecOps Governance",
                "items": list(self.CANONICAL_DOMAIN_6_SKILLS),
            },
        ]
        sm = SkillsMatrix.from_dict(categories)

        assert len(sm.observability_monitoring) == 5
        for skill in self.CANONICAL_DOMAIN_6_SKILLS:
            assert skill in sm.observability_monitoring

        # DevSecOps only has its own items, not bloated by category 6
        assert len(sm.dev_sec_ops) == 2
        assert "MLOps Pipeline" in sm.dev_sec_ops
        for skill in self.CANONICAL_DOMAIN_6_SKILLS:
            assert skill not in sm.dev_sec_ops

    def test_category_6_hostile_naming_variants(self):
        """Hostile casing and formatting variations of category 6 still route to Domain 6."""
        names = [
            "Observability, SRE & DevSecOps Governance",
            "OBSERVABILITY, SRE & DEVSECOPS GOVERNANCE",
            "  observability, sre & devsecops governance  ",
            "Observability & SRE",
            "Site Reliability Engineering (SRE) & Monitoring",
            "Monitoring & Metrics",
            "Enterprise Observability & DevSecOps Governance",
        ]

        for name in names:
            categories = [
                {
                    "category": name,
                    "items": ["Skill A", "Skill B"],
                }
            ]
            sm = SkillsMatrix.from_dict(categories)
            assert "Skill A" in sm.observability_monitoring, f"Failed for category name: {name}"
            assert "Skill B" in sm.observability_monitoring, f"Failed for category name: {name}"
            assert len(sm.dev_sec_ops) == 0

    def test_skills_matrix_order_permutation_invariance(self):
        """Random permutations of categories yield identical classification results."""
        raw = get_embedded_default_profile()["skillsMatrix"]
        baseline_sm = SkillsMatrix.from_dict(raw)

        rng = random.Random(42)
        for _ in range(20):
            shuffled = list(raw)
            rng.shuffle(shuffled)
            sm = SkillsMatrix.from_dict(shuffled)

            assert sm.cloud_architecture == baseline_sm.cloud_architecture
            assert sm.dev_sec_ops == baseline_sm.dev_sec_ops
            assert sm.iac_automation == baseline_sm.iac_automation
            assert sm.systems_linux_windows == baseline_sm.systems_linux_windows
            assert sm.containerization_kubernetes == baseline_sm.containerization_kubernetes
            assert sm.observability_monitoring == baseline_sm.observability_monitoring

    def test_skills_matrix_dict_format_and_protocol(self):
        """SkillsMatrix supports dict constructor and dict protocol methods."""
        dict_input = {
            "cloud_architecture": ["AWS", "Azure"],
            "dev_sec_ops": ["SonarQube"],
            "iac_automation": ["Terraform"],
            "systems_linux_windows": ["Linux"],
            "containerization_kubernetes": ["Kubernetes"],
            "observability_monitoring": list(self.CANONICAL_DOMAIN_6_SKILLS),
        }
        sm = SkillsMatrix.from_dict(dict_input)
        assert len(sm) == 6
        assert "observability_monitoring" in sm
        assert "observabilityMonitoring" in sm
        assert sm["observability_monitoring"] == self.CANONICAL_DOMAIN_6_SKILLS
        assert sm.get("observability_monitoring") == self.CANONICAL_DOMAIN_6_SKILLS
        assert len(list(sm.keys())) == 6
        assert len(list(sm.values())) == 6
        assert len(list(sm.items())) == 6


# ============================================================================
# Task 3: CandidateProfile.get_role_lens() 8 Target Roles & Persona Stability
# ============================================================================

class TestTask3RoleLensPersonaStability:
    """Stress tests CandidateProfile.get_role_lens() against persona inversion."""

    TARGET_ROLES_MAP = {
        "Cloud Solutions Architect": "architect",
        "Cloud Infrastructure Engineer": "infra",
        "Cloud Engineer": "architect",
        "Dev(Sec)Ops Engineer": "devops",
        "System Administrator": "infra",
        "IT Specialist/Administrator": "support",
        "Technical Support Engineer": "support",
        "Azure/AWS DevOps Engineer": "devops",
    }

    def test_all_8_target_roles_canonical_lens_mapping(self):
        """All 8 target roles map to their correct canonical lens."""
        profile = load_profile(None, allow_fallback=True)
        for role, expected_lens in self.TARGET_ROLES_MAP.items():
            lens = profile.get_role_lens(role)
            assert lens.role_key == expected_lens, f"Role '{role}' mapped to '{lens.role_key}', expected '{expected_lens}'"

    def test_it_specialist_administrator_never_inverts_to_devops(self):
        """IT Specialist/Administrator must NEVER invert to devops persona lens."""
        profile = load_profile(None, allow_fallback=True)
        variants = [
            "IT Specialist/Administrator",
            "IT Specialist / Administrator",
            "it specialist / administrator",
            "IT SPECIALIST/ADMINISTRATOR",
            "it specialist/administrator",
            "   IT Specialist  /  Administrator   ",
            "IT Specialist",
            "IT Administrator",
            "Technical Support Engineer",
        ]
        for v in variants:
            lens = profile.get_role_lens(v)
            assert lens.role_key == "support", f"Variant '{v}' inverted to '{lens.role_key}'!"
            assert "devops" not in lens.role_key.lower()
            # Category title must reflect support / IT specialist
            assert "Support" in lens.category_title or "IT Specialist" in lens.category_title
            assert "Senior DevOps" not in lens.category_title

    def test_azure_aws_devops_engineer_maps_to_devops(self):
        """Azure/AWS DevOps Engineer maps to devops persona lens across spacing variants."""
        profile = load_profile(None, allow_fallback=True)
        variants = [
            "Azure/AWS DevOps Engineer",
            "Azure / AWS DevOps Engineer",
            "azure/aws devops engineer",
            "AZURE/AWS DEVOPS ENGINEER",
            "   azure   /   aws   devops   engineer   ",
            "Azure DevOps Engineer",
            "AWS DevOps Engineer",
        ]
        for v in variants:
            lens = profile.get_role_lens(v)
            assert lens.role_key == "devops", f"Variant '{v}' mapped to '{lens.role_key}', expected 'devops'!"

    def test_devsecops_engineer_parentheses_and_spacing_variants(self):
        """Dev(Sec)Ops variations map to devops persona lens."""
        profile = load_profile(None, allow_fallback=True)
        variants = [
            "Dev(Sec)Ops Engineer",
            "dev(sec)ops engineer",
            "DEV(SEC)OPS ENGINEER",
            "Dev (Sec) Ops Engineer",
            "dev (sec) ops engineer",
            "DevSecOps Engineer",
            "DevOps Engineer",
        ]
        for v in variants:
            lens = profile.get_role_lens(v)
            assert lens.role_key == "devops", f"Variant '{v}' mapped to '{lens.role_key}', expected 'devops'!"

    def test_exhaustive_messy_formatting_combinations(self):
        """Exhaustive matrix of messy formatting (slashes, whitespace, casing) for all 8 roles."""
        profile = load_profile(None, allow_fallback=True)

        transforms = [
            lambda s: s,
            lambda s: s.lower(),
            lambda s: s.upper(),
            lambda s: s.title(),
            lambda s: f"   {s}   ",
            lambda s: "  ".join(s.split()),
            lambda s: s.replace("/", " / "),
            lambda s: s.replace("/", "   /   "),
            lambda s: s.replace("/", "/ "),
            lambda s: s.replace("/", " /"),
            lambda s: "  " + s.lower().replace("/", "  /  ") + "  ",
            lambda s: "  " + s.upper().replace("/", " / ") + "  ",
            lambda s: "   " + "   ".join(s.lower().replace("/", " / ").split()) + "   ",
        ]

        total_tested = 0
        for role, expected_lens in self.TARGET_ROLES_MAP.items():
            for t in transforms:
                messy = t(role)
                lens = profile.get_role_lens(messy)
                assert lens.role_key == expected_lens, (
                    f"Messy role '{messy}' (base: '{role}') projected to '{lens.role_key}', expected '{expected_lens}'"
                )
                total_tested += 1

        assert total_tested == 8 * len(transforms)

    def test_empty_role_categories_graceful_fallback(self):
        """When role_categories is completely empty, get_role_lens provides robust defaults."""
        profile = CandidateProfile.from_dict({})
        lens = profile.get_role_lens("IT Specialist/Administrator")
        assert lens.role_key == "support"
        assert lens.title == "Senior Engineer"
        assert lens.category_title == "Senior Engineer"


# ============================================================================
# Task 4: sanitize_ligatures with Bullet Characters & NBSP
# ============================================================================

class TestTask4SanitizeLigaturesBulletsAndSpaces:
    """Stress tests sanitize_ligatures for bullet spacing and NBSP normalization."""

    BULLET_GLYPHS = [
        "\u2022",  # • Bullet
        "\u25CF",  # ● Black Circle
        "\u25E6",  # ◦ White Bullet
        "\u25AA",  # ▪ Black Small Square
        "\u25AB",  # ▫ White Small Square
        "\u2043",  # ⁃ Hyphen Bullet
        "\u2219",  # ∙ Bullet Operator
        "\u2023",  # ‣ Triangular Bullet
    ]

    SPACINGS = [
        " ",
        "  ",
        "   ",
        "\u00A0",          # NBSP
        "\u00A0\u00A0",      # Double NBSP
        " \u00A0",          # Space + NBSP
        "\u00A0 ",          # NBSP + Space
        "\u00A0 \u00A0",    # Mixed
        "\t",               # Tab
        "",                 # Zero space
    ]

    def test_all_bullet_glyphs_and_spacings_produce_single_space(self):
        """Every bullet glyph followed by any spacing produces exactly '- ' without double spaces."""
        for b in self.BULLET_GLYPHS:
            for sp in self.SPACINGS:
                raw = f"{b}{sp}Provisioned AKS clusters with 99.9% uptime"
                cleaned = sanitize_ligatures(raw)

                assert cleaned.startswith("- "), f"Failed for {repr(b)} + {repr(sp)}: {repr(cleaned)}"
                assert not cleaned.startswith("-  "), f"Double space detected for {repr(b)} + {repr(sp)}: {repr(cleaned)}"
                assert cleaned == "- Provisioned AKS clusters with 99.9% uptime"

    def test_bullets_with_ligatures_and_nbsp(self):
        """Bullets combined with NBSP and corrupted ligatures repair cleanly with zero double spaces."""
        for b in self.BULLET_GLYPHS:
            raw = f"{b}\u00A0Demonstrated eƯiciency in o\uFB00\u00A0ice operations"
            cleaned = sanitize_ligatures(raw)
            assert cleaned == "- Demonstrated efficiency in office operations"
            assert not cleaned.startswith("-  ")

    def test_multiline_resume_bullet_points(self):
        """Multi-line resume with mixed bullets, NBSPs, and ligatures standardizes completely."""
        raw = (
            "\u2022\u00A0 Provisioned AKS clusters with 99.9% uptime SLA.\n"
            "\u25CF  Configured CI/CD pipelines with high eƯiciency.\n"
            "\u25E6\u00A0Architected multi-cloud networks across AWS and Azure.\n"
            "\u25AA   Demonstrated 99% first-day resolution rate in o\uFB00\u00A0ice incidents.\n"
        )
        cleaned = sanitize_ligatures(raw)
        lines = [ln.strip() for ln in cleaned.strip().splitlines() if ln.strip()]

        assert len(lines) == 4
        for ln in lines:
            assert ln.startswith("- ")
            assert not ln.startswith("-  ")
            assert "eƯ" not in ln
            assert "o\uFB00" not in ln

        assert lines[0] == "- Provisioned AKS clusters with 99.9% uptime SLA."
        assert lines[1] == "- Configured CI/CD pipelines with high efficiency."
        assert lines[2] == "- Architected multi-cloud networks across AWS and Azure."
        assert lines[3] == "- Demonstrated 99% first-day resolution rate in office incidents."

    def test_bullet_in_mid_sentence_not_corrupted(self):
        """Bullets inside text lines are normalized cleanly without erratic spacing."""
        raw = "Key skills: \u2022\u00A0Kubernetes \u2022 Azure \u2022\u00A0\u00A0AWS"
        cleaned = sanitize_ligatures(raw)
        assert "- " in cleaned
        assert "-  " not in cleaned
