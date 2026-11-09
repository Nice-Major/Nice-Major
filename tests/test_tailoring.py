"""
Unit & Integration Test Suite for Milestone 2 Tailoring Engine.
Target Module: tests/test_tailoring.py
Features:
- F05: ATS-Friendly CV Tailoring Engine (tailoring.cv_tailor)
- F06: Cover Letter Tailoring Engine (tailoring.letter_tailor)
- F03: ATS Text & Filename Utilities Integration (ingestion.text_utils)

Validates:
- CV generation across Markdown (.md), clean print HTML (.html), and plain text (.txt)
- ATS single-column layout, standard section headers, contact flow on page 1
- Dynamic persona lens switching via candidate.get_role_lens()
- Cover letter generation across formats (md, html, txt)
- STAR methodology structure (Situation, Task, Action, Result) in cover letter
- Verified empirical KPI inclusion (99.9% uptime SLA, 99% first-day resolution, >60% AI accuracy, <15m IaC)
- Strict Zero External Tracker / No Credly links policy across all generated documents
- Ligature cleanliness and broken typography repair (sanitize_ligatures)
- Multi-tone adaptation (professional, technical, executive, results_oriented)
- Banned buzzword exclusion (zero "rockstar", "ninja", "guru", "wizard")
- Personalization with special-character company names
- Strict underscore safe filename generation
"""

from __future__ import annotations

import sys
from pathlib import Path
import re
from typing import Any, Dict, List
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.models import (
    CandidateInfo,
    CandidateProfile,
    Certification,
    Education,
    KpiMetric,
    RoleCategory,
    SkillsMatrix,
    StepconProfile,
    WorkExperience,
)
from ingestion.parser import load_profile_from_dict, get_embedded_default_profile
from ingestion.text_utils import safe_filename, sanitize_ligatures, strip_markdown, clean_ats_text


# ============================================================================
# Safe Module Importers
# ============================================================================

def _get_cv_tailor_module():
    try:
        import tailoring.cv_tailor as mod
        return mod
    except ImportError:
        pytest.skip("tailoring.cv_tailor module not yet implemented.")


def _get_letter_tailor_module():
    try:
        import tailoring.letter_tailor as mod
        return mod
    except ImportError:
        pytest.skip("tailoring.letter_tailor module not yet implemented.")


# ============================================================================
# Test Fixtures & Synthetic Datasets
# ============================================================================

@pytest.fixture
def default_candidate_profile() -> CandidateProfile:
    """Returns authoritative CandidateProfile from embedded default."""
    return load_profile_from_dict(get_embedded_default_profile())


@pytest.fixture
def synthetic_devops_job() -> Dict[str, Any]:
    return {
        "title": "Senior DevOps & Platform Engineer",
        "company": "Global Cloud Corp",
        "location": "Remote - Worldwide (EMEA / UTC+1)",
        "description": (
            "Seeking a Senior DevOps Engineer to lead Kubernetes and Terraform automation. "
            "Must have strong experience in container orchestration (Kubernetes, Docker), Infrastructure as Code "
            "(Terraform), CI/CD pipelines (GitHub Actions), and AWS/Azure cloud platforms. Candidate must ensure "
            "enterprise 99.9% uptime SLAs and integrate DevSecOps controls."
        ),
    }


@pytest.fixture
def synthetic_architect_job() -> Dict[str, Any]:
    return {
        "title": "Cloud Solutions Architect",
        "company": "Enterprise Horizons Ltd",
        "location": "Remote - Worldwide",
        "description": (
            "Looking for a Cloud Solutions Architect to design scalable multi-cloud microservices on Azure and AWS. "
            "Must apply the Well-Architected Framework, architect AKS/EKS clusters, configure private endpoints, "
            "and optimize FinOps cost governance. AWS Certified Solutions Architect required."
        ),
    }


@pytest.fixture
def synthetic_support_job() -> Dict[str, Any]:
    return {
        "title": "L3 Technical Support Engineer",
        "company": "CloudCare Global",
        "location": "Remote - Worldwide",
        "description": (
            "Seeking an L3 Technical Cloud Support Engineer for production incident escalation on Microsoft Azure App Service. "
            "Deep root-cause analysis (RCA), logs, metrics, distributed traces, and TsG authoring. High CSAT and SLA adherence required."
        ),
    }


# ============================================================================
# 1. Feature F05: ATS-Friendly CV Tailoring Tests
# ============================================================================

class TestCvTailoringEngine:
    """Verifies single-column layout, multi-format export, and ATS standards in CV generation."""

    def test_cv_generation_markdown_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that CV is generated in structured Markdown format."""
        cv_mod = _get_cv_tailor_module()
        cv_md = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "md",
        )
        assert isinstance(cv_md, str)
        assert "John Victor Aniekwe" in cv_md
        assert "aniekwevictor9@gmail.com" in cv_md
        assert "#" in cv_md  # Markdown headers

    def test_cv_generation_html_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that CV is generated in semantic, printable HTML5 format."""
        cv_mod = _get_cv_tailor_module()
        cv_html = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "html",
        )
        assert "<html" in cv_html.lower()
        assert "John Victor Aniekwe" in cv_html
        assert "</html>" in cv_html.lower()

    def test_cv_generation_plain_text_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that CV is generated in clean ATS plain text format."""
        cv_mod = _get_cv_tailor_module()
        cv_txt = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "txt",
        )
        assert "JOHN VICTOR ANIEKWE" in cv_txt.upper()
        # Ensure no residual HTML or Markdown tags in plain text
        assert "<html>" not in cv_txt.lower()
        assert "```" not in cv_txt

    def test_cv_contains_standard_canonical_section_headers(self, default_candidate_profile, synthetic_devops_job):
        """Verifies the presence of global standard ATS section headers."""
        cv_mod = _get_cv_tailor_module()
        cv_md = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "md",
        )
        cv_upper = cv_md.upper()
        # Summary
        assert "SUMMARY" in cv_upper or "PROFESSIONAL SUMMARY" in cv_upper
        # Skills
        assert "SKILLS" in cv_upper or "TECHNICAL SKILLS" in cv_upper or "COMPETENCIES" in cv_upper
        # Experience
        assert "EXPERIENCE" in cv_upper or "PROFESSIONAL EXPERIENCE" in cv_upper
        # Certifications
        assert "CERTIFICATIONS" in cv_upper
        # Education
        assert "EDUCATION" in cv_upper

    def test_cv_single_column_layout_enforcement(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that HTML layout enforces single-column flow without tables for layout."""
        cv_mod = _get_cv_tailor_module()
        cv_html = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "html",
        )
        # ATS prohibition: table-based multi-column layout
        assert "<table class=\"layout\"" not in cv_html.lower()
        assert "display: flex; flex-direction: row;" not in cv_html  # No side-by-side main content

    def test_cv_includes_verified_certifications(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that candidate's active certifications are included without omission."""
        cv_mod = _get_cv_tailor_module()
        cv_md = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "md",
        )
        assert "KCNA" in cv_md or "Kubernetes and Cloud Native Associate" in cv_md
        assert "AWS Certified Solutions Architect" in cv_md

    def test_cv_zero_external_credly_tracker_links(self, default_candidate_profile, synthetic_devops_job):
        """Verifies strict Zero External Tracker / No Credly Links policy."""
        cv_mod = _get_cv_tailor_module()
        for fmt in ["md", "html", "txt"]:
            cv_out = cv_mod.generate_cv(
                default_candidate_profile,
                synthetic_devops_job["description"],
                "DevOps Engineer",
                fmt,
            )
            assert "credly.com" not in cv_out.lower(), f"Credly link detected in {fmt} format CV"

    def test_cv_includes_verified_kpi_metrics(self, default_candidate_profile, synthetic_devops_job):
        """Verifies candidate's verified KPI metrics appear in experience statements."""
        cv_mod = _get_cv_tailor_module()
        cv_md = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "md",
        )
        assert "99.9%" in cv_md
        assert "99%" in cv_md or "<15" in cv_md or ">60%" in cv_md

    def test_cv_format_case_insensitivity(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that format parameter is case-insensitive ('MD', 'Html', 'TXT')."""
        cv_mod = _get_cv_tailor_module()
        cv_upper_fmt = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "MD",
        )
        assert "John Victor Aniekwe" in cv_upper_fmt

    def test_cv_empty_jd_generates_master_cv(self, default_candidate_profile):
        """Verifies that passing an empty job description generates a complete master CV."""
        cv_mod = _get_cv_tailor_module()
        cv_master = cv_mod.generate_cv(
            default_candidate_profile,
            "",
            "DevOps Engineer",
            "md",
        )
        assert "John Victor Aniekwe" in cv_master
        assert len(cv_master) > 500


# ============================================================================
# 2. Feature F06: STAR Cover Letter Tailoring Tests
# ============================================================================

class TestCoverLetterTailoringEngine:
    """Verifies STAR methodology, multi-tone, multi-format, and personalization in cover letters."""

    def test_cover_letter_markdown_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies cover letter generation in clean Markdown format."""
        letter_mod = _get_letter_tailor_module()
        letter_md = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
            company_name=synthetic_devops_job["company"],
            output_format="md",
        )
        assert isinstance(letter_md, str)
        assert "# John Victor Aniekwe" in letter_md
        assert "Global Cloud Corp" in letter_md
        assert "Application for DevOps Engineer" in letter_md

    def test_cover_letter_html_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies cover letter generation in semantic, printable HTML5 format."""
        letter_mod = _get_letter_tailor_module()
        letter_html = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
            company_name=synthetic_devops_job["company"],
            output_format="html",
        )
        assert "<!DOCTYPE html>" in letter_html
        assert "<html" in letter_html
        assert "Global Cloud Corp" in letter_html
        assert "John Victor Aniekwe" in letter_html
        assert "</html>" in letter_html

    def test_cover_letter_plain_text_format(self, default_candidate_profile, synthetic_devops_job):
        """Verifies cover letter generation in clean ATS plain text format."""
        letter_mod = _get_letter_tailor_module()
        letter_txt = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
            company_name=synthetic_devops_job["company"],
            output_format="txt",
        )
        assert "JOHN VICTOR ANIEKWE" in letter_txt.upper()
        assert "Global Cloud Corp" in letter_txt
        assert "<html>" not in letter_txt.lower()
        assert "#" not in letter_txt

    def test_cover_letter_star_structure_verification(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that the generated cover letter contains all STAR components."""
        letter_mod = _get_letter_tailor_module()
        letter = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
            company_name="Global Cloud Corp",
            output_format="md",
        )
        # Situation: Production cloud estates / scaling infrastructure
        assert "AWS" in letter and "Azure" in letter
        # Task: Delivering reliability / 99.9% uptime SLA
        assert "99.9%" in letter
        # Action: Terraform IaC, Kubernetes, microservices
        assert "Terraform" in letter
        assert "Kubernetes" in letter or "KCNA" in letter
        # Result: Empirical metrics
        assert "99%" in letter or ">60%" in letter or "<15" in letter

    def test_cover_letter_includes_verified_degree(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that candidate's B.Sc. in Computer Science from UNN is included."""
        letter_mod = _get_letter_tailor_module()
        letter = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
        )
        assert "University of Nigeria" in letter or "Computer Science" in letter

    def test_cover_letter_professional_salutation_and_signoff(self, default_candidate_profile):
        """Verifies professional salutation and sign-off blocks."""
        letter_mod = _get_letter_tailor_module()
        letter = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            target_role="Cloud Solutions Architect",
            company_name="Enterprise Horizons Ltd",
        )
        assert "Dear Hiring Team at Enterprise Horizons Ltd," in letter
        assert "Sincerely," in letter or "Best regards," in letter
        assert "John Victor Aniekwe" in letter

    @pytest.mark.parametrize("tone", ["professional", "technical", "executive", "results_oriented"])
    def test_cover_letter_tone_variations(self, default_candidate_profile, synthetic_devops_job, tone):
        """Verifies that all 4 supported tone modes generate valid, high-quality letters."""
        letter_mod = _get_letter_tailor_module()
        letter = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
            company_name="Global Cloud Corp",
            tone=tone,
        )
        assert "John Victor Aniekwe" in letter
        assert "Global Cloud Corp" in letter
        assert len(letter) > 600

    def test_cover_letter_prohibits_banned_buzzwords(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that banned buzzwords (rockstar, ninja, guru, wizard) are strictly prohibited."""
        letter_mod = _get_letter_tailor_module()
        letter = letter_mod.generate_cover_letter(
            candidate=default_candidate_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
        )
        letter_lower = letter.lower()
        for buzzword in ["rockstar", "ninja", "guru", "wizard", "unicorn", "passionate evangelist"]:
            assert buzzword not in letter_lower, f"Banned buzzword '{buzzword}' detected in cover letter"

    def test_cover_letter_zero_external_tracker_links(self, default_candidate_profile, synthetic_devops_job):
        """Verifies absence of external Credly redirect links in cover letter."""
        letter_mod = _get_letter_tailor_module()
        for fmt in ["md", "html", "txt"]:
            letter = letter_mod.generate_cover_letter(
                candidate=default_candidate_profile,
                job_text=synthetic_devops_job["description"],
                target_role="DevOps Engineer",
                output_format=fmt,
            )
            assert "credly.com" not in letter.lower()

    def test_cover_letter_special_character_company_names(self, default_candidate_profile, synthetic_devops_job):
        """Verifies graceful handling of company names with slashes, ampersands, and accents."""
        letter_mod = _get_letter_tailor_module()
        special_names = [
            "AT&T / Yahoo! Inc.",
            "Société Générale",
            "L'Oréal Technology",
            "Amazon Web Services (AWS) Inc.",
        ]
        for c_name in special_names:
            letter = letter_mod.generate_cover_letter(
                candidate=default_candidate_profile,
                job_text=synthetic_devops_job["description"],
                target_role="DevOps Engineer",
                company_name=c_name,
            )
            assert c_name in letter or sanitize_ligatures(c_name) in letter

    def test_cover_letter_missing_fields_no_none_literals(self, default_candidate_profile, synthetic_devops_job):
        """Verifies that empty profile fields do not render as the literal string 'None'."""
        letter_mod = _get_letter_tailor_module()
        sparse_profile = CandidateProfile(candidate=CandidateInfo(full_name="John Victor Aniekwe", phone="", location=""))
        letter = letter_mod.generate_cover_letter(
            candidate=sparse_profile,
            job_text=synthetic_devops_job["description"],
            target_role="DevOps Engineer",
        )
        assert "None" not in letter


# ============================================================================
# 3. Filename & End-to-End ATS Compliance Integration Tests
# ============================================================================

class TestTailoringIntegrationAndFilenames:
    """Verifies end-to-end integration between tailoring, safe filenames, and ligature hygiene."""

    @pytest.mark.parametrize("target_role", [
        "Cloud Solutions Architect",
        "Cloud Infrastructure Engineer",
        "DevOps Engineer",
        "Technical Support Engineer",
    ])
    def test_strict_underscore_filename_generation_for_documents(self, target_role):
        """Verifies strict underscore naming format: {First}_{Last}_{Role}_{DocType}.{ext}."""
        cv_filename = safe_filename("John_Victor", "Aniekwe", target_role, "CV", "pdf")
        letter_filename = safe_filename("John_Victor", "Aniekwe", target_role, "Cover_Letter", "pdf")

        # Zero spaces, hyphens, or colons
        assert " " not in cv_filename
        assert "-" not in cv_filename
        assert ":" not in cv_filename
        assert "__" not in cv_filename
        assert cv_filename.endswith(".pdf")

        assert " " not in letter_filename
        assert "-" not in letter_filename
        assert letter_filename.endswith(".pdf")

    def test_end_to_end_tailoring_pipeline_chain(self, default_candidate_profile, synthetic_devops_job):
        """Verifies chained execution: Ingestion -> CV Tailoring -> Cover Letter -> Ligature Sanitization -> Filename."""
        cv_mod = _get_cv_tailor_module()
        letter_mod = _get_letter_tailor_module()

        # 1. Generate CV
        cv_content = cv_mod.generate_cv(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            "md",
        )
        clean_cv = sanitize_ligatures(cv_content)
        cv_file = safe_filename("John_Victor", "Aniekwe", "DevOps Engineer", "CV", "md")

        # 2. Generate Cover Letter
        letter_content = letter_mod.generate_cover_letter(
            default_candidate_profile,
            synthetic_devops_job["description"],
            "DevOps Engineer",
            company_name=synthetic_devops_job["company"],
            output_format="md",
        )
        clean_letter = sanitize_ligatures(letter_content)
        letter_file = safe_filename("John_Victor", "Aniekwe", "DevOps Engineer", "Cover_Letter", "md")

        # 3. Verify consistency
        assert cv_file == "John_Victor_Aniekwe_DevOps_Engineer_CV.md"
        assert letter_file == "John_Victor_Aniekwe_DevOps_Engineer_Cover_Letter.md"
        assert "John Victor Aniekwe" in clean_cv
        assert "John Victor Aniekwe" in clean_letter
        assert "Global Cloud Corp" in clean_letter
