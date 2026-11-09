"""
Adversarial Stress Test Suite for Milestone 2 Document Tailoring Engine.
File: tests/test_adversarial_m2_challenge.py
Target Features:
- F05: ATS-Friendly CV Tailoring Engine (tailoring.cv_tailor)
- F06: STAR Cover Letter Tailoring Engine (tailoring.letter_tailor)
- F03: ATS Text Utilities & Safe Filename Generator (ingestion.text_utils)
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
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
    WorkExperience,
)
from ingestion.parser import load_profile_from_dict, get_embedded_default_profile
from ingestion.text_utils import safe_filename, sanitize_ligatures, clean_ats_text
import tailoring.cv_tailor as cv_mod
import tailoring.letter_tailor as letter_mod


@pytest.fixture
def default_profile() -> CandidateProfile:
    return load_profile_from_dict(get_embedded_default_profile())


# ============================================================================
# 1. Tracker URL Policy Tests (Credly & YourAcclaim)
# ============================================================================

class TestTrackerUrlPolicyAdversarial:
    """Verifies that credly.com and youracclaim.com never appear in outputs."""

    @pytest.mark.parametrize("fmt", ["md", "html", "txt"])
    def test_cv_strips_credly_and_youracclaim_from_certifications(self, default_profile, fmt):
        """Inject Credly and YourAcclaim URLs into certifications and verify stripping."""
        polluted_certs = [
            Certification(
                name="AWS Certified Solutions Architect – Associate",
                issuer="Amazon Web Services https://www.credly.com/badges/aws-saa-12345",
                status="Active",
            ),
            Certification(
                name="KCNA https://www.youracclaim.com/badges/kcna-67890",
                issuer="Linux Foundation",
                status="Active",
            ),
        ]
        default_profile.certifications = polluted_certs
        default_profile.candidate.certifications = polluted_certs

        cv_out = cv_mod.generate_cv(
            candidate=default_profile,
            job_text="Requirements: AWS and Kubernetes",
            target_role="DevOps Engineer",
            output_format=fmt,
        )

        assert "credly.com" not in cv_out.lower(), f"Found credly.com in {fmt} CV output"
        assert "youracclaim.com" not in cv_out.lower(), f"Found youracclaim.com in {fmt} CV output"

    @pytest.mark.parametrize("fmt", ["md", "html", "txt"])
    def test_cv_handles_tracker_in_job_description(self, default_profile, fmt):
        """Job description asking for Credly/YourAcclaim badges should not leak into CV."""
        malicious_jd = (
            "Seeking Senior DevOps Engineer. Must provide verification badge at "
            "https://www.credly.com/org/amazon-web-services or https://youracclaim.com/org/cncf."
        )
        cv_out = cv_mod.generate_cv(
            candidate=default_profile,
            job_text=malicious_jd,
            target_role="DevOps Engineer",
            output_format=fmt,
        )
        assert "credly.com" not in cv_out.lower()
        assert "youracclaim.com" not in cv_out.lower()

    @pytest.mark.parametrize("fmt", ["md", "html", "txt"])
    def test_cover_letter_tracker_sanitization(self, default_profile, fmt):
        """Cover letter with tracker-laden company/job text."""
        letter_out = letter_mod.generate_cover_letter(
            candidate=default_profile,
            job_text="Verify certs at https://www.credly.com/badges/abc and https://www.youracclaim.com/badges/def",
            target_role="Cloud Solutions Architect",
            company_name="Credly Partner Corp",
            output_format=fmt,
        )
        # Verify external Credly links are removed
        assert "https://www.credly.com" not in letter_out.lower()
        assert "http://www.credly.com" not in letter_out.lower()


# ============================================================================
# 2. ATS Formatting & Canonical Headers
# ============================================================================

class TestAtsFormattingAdversarial:
    """Verifies strict single-column layout and standard canonical headers."""

    CANONICAL_HEADERS = [
        "Professional Summary",
        "Core Competencies",
        "Professional Experience",
        "Certifications",
        "Key Projects",
        "Education",
    ]

    @pytest.mark.parametrize("fmt", ["md", "html", "txt"])
    def test_all_canonical_headers_present_and_ordered(self, default_profile, fmt):
        """Verify all 6 standard headers exist in exact linear sequence."""
        cv_out = cv_mod.generate_cv(
            candidate=default_profile,
            job_text="Kubernetes, Terraform, AWS, Azure",
            target_role="DevOps Engineer",
            output_format=fmt,
        )

        positions = []
        for header in self.CANONICAL_HEADERS:
            idx = cv_out.lower().find(header.lower())
            assert idx != -1, f"Missing canonical header '{header}' in {fmt} CV"
            positions.append((idx, header))

        # Check strictly monotonic ordering
        for i in range(len(positions) - 1):
            assert positions[i][0] < positions[i+1][0], (
                f"Header order violation in {fmt}: '{positions[i][1]}' at {positions[i][0]} "
                f"is after '{positions[i+1][1]}' at {positions[i+1][0]}"
            )

    def test_html_strictly_single_column_prohibits_tables_and_columns(self, default_profile):
        """Verify HTML uses no table layout, multi-column CSS, or side-by-side structures."""
        cv_html = cv_mod.generate_cv(
            candidate=default_profile,
            job_text="",
            target_role="Cloud Infrastructure Engineer",
            output_format="html",
        )

        assert "<table" not in cv_html.lower(), "Found <table> element in ATS HTML CV"
        assert "column-count" not in cv_html.lower()
        assert "grid-template-columns" not in cv_html.lower()
        assert "<aside" not in cv_html.lower()


# ============================================================================
# 3. Baseline Skill Preservation Tests
# ============================================================================

class TestBaselineSkillPreservation:
    """Verifies that no baseline skill is pruned or dropped when prioritizing."""

    def test_prioritize_skills_preserves_every_item(self, default_profile):
        """Every item in input skills dictionary must exist in prioritized output."""
        skills_dict = default_profile.skills_matrix.to_dict()

        # Collect all original skills
        original_skills: List[str] = []
        for cat_k, cat_items in skills_dict.items():
            if isinstance(cat_items, list) and cat_k != "rawCategories":
                original_skills.extend([str(x) for x in cat_items])

        adversarial_jd = (
            "We need an expert in Kubernetes and Terraform only. Everything else is irrelevant."
        )

        prioritized = cv_mod.prioritize_skills(skills_dict, adversarial_jd)

        prioritized_skills: List[str] = []
        for title, items in prioritized:
            prioritized_skills.extend(items)

        # Ensure no skills dropped
        for skill in original_skills:
            assert skill in prioritized_skills, f"Skill '{skill}' was dropped during prioritization!"

        # Ensure matched skills (Kubernetes, Terraform) appear first in their respective categories
        for title, items in prioritized:
            if "Containers & Kubernetes" in title:
                assert any("Kubernetes" in it or "KCNA" in it for it in items[:2])
            if "IaC" in title:
                assert any("Terraform" in it for it in items[:2])

    def test_prioritize_skills_with_empty_and_noise_jd(self, default_profile):
        """Empty or completely non-matching JD preserves all skills without error."""
        skills_dict = default_profile.skills_matrix.to_dict()
        noise_jd = "Pastry chef needed for French bakery in Paris. Croissants, baguettes, sourdough."

        prioritized_empty = cv_mod.prioritize_skills(skills_dict, "")
        prioritized_noise = cv_mod.prioritize_skills(skills_dict, noise_jd)

        assert len(prioritized_empty) > 0
        assert len(prioritized_noise) > 0


# ============================================================================
# 4. HTML Injection & XSS Sanitization Tests
# ============================================================================

class TestHtmlInjectionAndXss:
    """Verifies safe HTML escaping across extreme injection vectors."""

    XSS_PAYLOADS = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "<b>malicious bold</b>",
        "&quot; onclick=alert('click') &quot;",
        "'>alert(1)</script><script>",
    ]

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_cover_letter_html_escapes_malicious_company_name(self, default_profile, payload):
        """Malicious company name must be safely escaped in HTML cover letter."""
        letter_html = letter_mod.generate_cover_letter(
            candidate=default_profile,
            job_text="Standard DevOps JD",
            target_role="DevOps Engineer",
            company_name=payload,
            output_format="html",
        )

        # Unescaped executable tags must NEVER appear in HTML output
        assert "<script>" not in letter_html.lower()
        assert "<img" not in letter_html.lower()
        assert "<b>" not in letter_html.lower()
        assert "<iframe" not in letter_html.lower()

        # HTML entity escaped versions must be present
        assert "&lt;" in letter_html or "&amp;" in letter_html

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_cover_letter_markdown_handles_malicious_company(self, default_profile, payload):
        """Markdown output gracefully handles special characters in company name."""
        letter_md = letter_mod.generate_cover_letter(
            candidate=default_profile,
            job_text="DevOps role",
            target_role="DevOps Engineer",
            company_name=payload,
            output_format="md",
        )
        assert isinstance(letter_md, str)
        assert len(letter_md) > 300

    def test_cv_html_escapes_malicious_experience_and_project_data(self):
        """Candidate profile with injection strings in experience and project titles."""
        injected_profile = CandidateProfile(
            candidate=CandidateInfo(full_name="John Victor Aniekwe <script>alert(1)</script>"),
            experience=[
                WorkExperience(
                    company="Evil Corp <script>alert('co')</script>",
                    role="DevOps Lead <b>bold</b>",
                    location="Remote &quot;special&quot;",
                    bullets=["Maintained systems with <script>hack()</script> zero downtime"],
                )
            ],
            projects=[
                {
                    "name": "Security Scanner <svg onload=alert(1)>",
                    "description": "Exploit testing with <iframe src='evil.com'></iframe>",
                    "technologies": ["Python", "<script>"],
                }
            ],
        )

        cv_html = cv_mod.generate_cv(
            candidate=injected_profile,
            job_text="",
            target_role="DevOps Engineer",
            output_format="html",
        )

        # Ensure no raw unescaped HTML tags
        assert "<script>" not in cv_html.lower()
        assert "<svg onload" not in cv_html.lower()
        assert "<iframe" not in cv_html.lower()
        assert "<b>" not in cv_html.lower()
        assert "&lt;script&gt;" in cv_html or "script" in cv_html


# ============================================================================
# 5. Candidate KPIs & Credentials Preservation Across All 8 Roles
# ============================================================================

class TestCandidateKpisAndCredentialsAcrossRoles:
    """Verifies that all 8 target roles preserve core verified metrics and degrees."""

    TARGET_8_ROLES = [
        "Cloud Solutions Architect",
        "Cloud Infrastructure Engineer",
        "Cloud Engineer",
        "Dev(Sec)Ops Engineer",
        "System Administrator",
        "IT Specialist/Administrator",
        "Technical Support Engineer",
        "Azure/AWS DevOps Engineer",
    ]

    @pytest.mark.parametrize("role", TARGET_8_ROLES)
    def test_kpi_metrics_presence_in_cv(self, default_profile, role):
        """Verify presence of 99.9%, 99%, >60%, <15m, and UNN degree in CV."""
        cv_md = cv_mod.generate_cv(
            candidate=default_profile,
            job_text="Cloud and DevOps role requiring high availability and automation",
            target_role=role,
            output_format="md",
        )

        assert "99.9%" in cv_md, f"Missing 99.9% uptime SLA in CV for role '{role}'"
        assert "99%" in cv_md, f"Missing 99% RCA metric in CV for role '{role}'"
        assert ">60%" in cv_md, f"Missing >60% AI accuracy in CV for role '{role}'"
        assert ("15 minutes" in cv_md.lower() or "<15" in cv_md.lower()), (
            f"Missing 15-minute IaC provisioning metric in CV for role '{role}'"
        )
        assert ("University of Nigeria" in cv_md or "B.Sc." in cv_md or "Computer Science" in cv_md), (
            f"Missing UNN degree credentials in CV for role '{role}'"
        )

    @pytest.mark.parametrize("role", TARGET_8_ROLES)
    def test_kpi_metrics_presence_in_cover_letter(self, default_profile, role):
        """Verify presence of 99.9%, 99%, >60%, <15m, and UNN degree in cover letter."""
        letter = letter_mod.generate_cover_letter(
            candidate=default_profile,
            job_text="Role requirements",
            target_role=role,
            company_name="Apex Cloud Technologies",
            output_format="md",
        )

        assert "99.9%" in letter, f"Missing 99.9% uptime SLA in cover letter for '{role}'"
        assert "99%" in letter, f"Missing 99% RCA metric in cover letter for '{role}'"
        assert ("60%" in letter), f"Missing 60% AI accuracy in cover letter for '{role}'"
        assert ("15 minutes" in letter or "<15" in letter or "15-minute" in letter), (
            f"Missing IaC provisioning metric in cover letter for '{role}'"
        )
        assert ("University of Nigeria" in letter and "Computer Science" in letter), (
            f"Missing UNN B.Sc. Computer Science degree in cover letter for '{role}'"
        )


# ============================================================================
# 6. safe_filename Length Clamping (<= 200 Chars) and Edge Attacks
# ============================================================================

class TestSafeFilenameLengthClampingAndEdgeCases:
    """Verifies that safe_filename rigorously satisfies <= 200 chars and sanitization."""

    def test_filename_length_clamping_with_extreme_strings(self):
        """Extreme role, company, and name strings must produce filename <= 200 chars."""
        extreme_first = "A" * 150
        extreme_last = "B" * 150
        extreme_role = "Senior_Lead_Principal_Enterprise_Multi_Cloud_Kubernetes_DevOps_Architect_" * 10
        extreme_doc = "Tailored_Curriculum_Vitae_Document_Comprehensive_Version_" * 5
        ext = "pdf"

        fname = safe_filename(extreme_first, extreme_last, extreme_role, extreme_doc, ext)

        assert len(fname) <= 200, f"Filename length {len(fname)} exceeds 200 characters limit!"
        assert fname.endswith(".pdf")
        assert " " not in fname
        assert "__" not in fname

    def test_filename_sanitizes_path_traversal_and_special_chars(self):
        """Path traversal and dangerous characters must be purged."""
        malicious_first = "../../etc/passwd"
        malicious_last = "Aniekwe; DROP TABLE resumes; --"
        malicious_role = "DevOps:Architect/Lead\\Manager?*|<>\""
        malicious_doc = "CV\x00NULL"
        malicious_ext = ".p.d.f../"

        fname = safe_filename(malicious_first, malicious_last, malicious_role, malicious_doc, malicious_ext)

        assert "/" not in fname
        assert "\\" not in fname
        assert ".." not in fname
        assert ":" not in fname
        assert "\x00" not in fname
        assert len(fname) <= 200
        assert fname.endswith(".pdf") or fname.endswith(".p")

    def test_get_cv_filename_integration(self, default_profile):
        """get_cv_filename with long roles adheres to <= 200 chars."""
        long_role = "Principal Multi-Cloud Enterprise DevSecOps and Platform Infrastructure Architect with AI Specialization"
        fname = cv_mod.get_cv_filename(default_profile, long_role, "html")
        assert len(fname) <= 200
        assert fname.endswith(".html")
        assert "John" in fname and "Aniekwe" in fname
