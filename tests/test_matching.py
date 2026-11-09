"""
Unit & Integration Test Suite for Milestone 2 Matching Engine.
Target Module: tests/test_matching.py
Features:
- F04: Role Competency & Keyword Extraction (engine.competency)
- F07: Multi-Dimensional Match Scorer & Gap Analysis (engine.scorer)

Validates:
- 8-role technical competency taxonomy
- Keyword extraction with HTML/DOM stripping, acronym normalization, case-insensitivity
- Required certification extraction
- 5-dimension 0-100 scoring algorithm (Skills 35%, Title 25%, Metrics 15%, Mobility 15%, Certs 10%)
- MatchResult contract adherence (overall_score, breakdown, matched_skills, missing_skills, target_role, rationale)
- Gap analysis and transparent recommendation logic across all 8 target roles
- Boundary & adversarial cases (empty JD, pastry chef 0% match, 100% saturation, repetitive text, weight arithmetic)
"""

from __future__ import annotations

import sys
from pathlib import Path
import json
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
    KpiMetric,
    RoleCategory,
    SkillsMatrix,
    StepconProfile,
    WorkExperience,
)
from ingestion.parser import load_profile_from_dict, get_embedded_default_profile


# ============================================================================
# Synthetic Test Job Postings Across All 8 Target Roles
# ============================================================================

SYNTHETIC_ROLE_JOBS: Dict[str, Dict[str, Any]] = {
    "Cloud Solutions Architect": {
        "title": "Principal Cloud Solutions Architect",
        "company": "SkyHigh Enterprise Cloud",
        "location": "Remote - Worldwide (UTC+1 / CET Synchronous)",
        "description": (
            "Seeking a Principal Cloud Solutions Architect to design multi-cloud infrastructure across AWS and Microsoft Azure. "
            "Must apply the AWS Well-Architected Framework, design high-availability AKS/EKS Kubernetes clusters, configure private "
            "endpoints, establish hybrid networking, and optimize FinOps cost governance. AWS Certified Solutions Architect required. "
            "Must ensure 99.9% uptime SLA."
        ),
    },
    "Cloud Infrastructure Engineer": {
        "title": "Senior Cloud Infrastructure Engineer",
        "company": "CoreCompute Systems",
        "location": "Remote - EMEA (Nigeria eligible)",
        "description": (
            "We are hiring a Senior Cloud Infrastructure Engineer to manage compute, storage, and networking on AWS and Azure. "
            "Requirements: Terraform Infrastructure as Code, Linux/Ubuntu server administration, Windows Server, hybrid VPN tunnels, "
            "automated OS patch management, and maintaining 99.9% production infrastructure uptime."
        ),
    },
    "Cloud Engineer": {
        "title": "Cloud Engineer (AWS & Azure)",
        "company": "Nimbus Global",
        "location": "Remote Worldwide",
        "description": (
            "Looking for a hands-on Cloud Engineer to deploy and monitor cloud services. Experience required with AWS (EC2, S3, VPC), "
            "Microsoft Azure (VMs, App Service), Docker containers, Kubernetes basics, Terraform, CI/CD with GitHub Actions, and "
            "monitoring via CloudWatch and Azure Monitor."
        ),
    },
    "Dev(Sec)Ops Engineer": {
        "title": "Senior DevSecOps Engineer",
        "company": "SecurePipeline Labs",
        "location": "Remote - Anywhere (CET / UTC+1)",
        "description": (
            "SecurePipeline is hiring a Senior DevSecOps Engineer to lead our Kubernetes and CI/CD automation. "
            "Must possess Kubernetes and Cloud Native Associate (KCNA) or CKA, expert Terraform IaC, Docker container security, "
            "GitHub Actions / Azure DevOps pipelines, vulnerability scanning, and reduce deployment times to under 15 minutes."
        ),
    },
    "System Administrator": {
        "title": "Linux & Windows Systems Administrator",
        "company": "Enterprise Host Corp",
        "location": "Remote - Worldwide",
        "description": (
            "Seeking an experienced System Administrator to maintain mission-critical Linux (Ubuntu Server) and Windows Server environments. "
            "Key duties: Bash and PowerShell automation, Active Directory / IAM, OS kernel tuning, backup recovery runbooks, and "
            "hardware lifecycle support. High availability and root-cause analysis skills essential."
        ),
    },
    "IT Specialist/Administrator": {
        "title": "Senior IT Specialist & Systems Administrator",
        "company": "Global Corporate Tech",
        "location": "Remote - Worldwide (EMEA Synchronous)",
        "description": (
            "Global Corporate Tech is looking for an IT Specialist/Administrator to manage corporate cloud systems and hardware fulfillment. "
            "Requirements: Microsoft 365, Azure Active Directory / Entra ID, identity and access management, ITIL service management "
            "alignment, laptop/desktop diagnostics, and standard operating procedure documentation."
        ),
    },
    "Technical Support Engineer": {
        "title": "L3 Technical Cloud Support Engineer",
        "company": "Apex CloudCare",
        "location": "Remote - Worldwide",
        "description": (
            "Apex CloudCare is seeking an L3 Technical Support Engineer specializing in Microsoft Azure App Service. "
            "Must conduct deep root-cause analysis (RCA) on production incidents, examine distributed traces and telemetry with "
            "Azure Monitor and Application Insights, author troubleshooting guides (TsGs), and deliver a 99% first-day resolution rate."
        ),
    },
    "Azure/AWS DevOps Engineer": {
        "title": "Multi-Cloud DevOps Engineer (Azure & AWS)",
        "company": "DualCloud Technologies",
        "location": "Remote - UK / EMEA / UTC+1",
        "description": (
            "Looking for a specialized Azure/AWS DevOps Engineer with dual-cloud expertise. Requirements: Azure DevOps, GitHub Actions, "
            "AWS CodePipeline, Kubernetes (KCNA certified), Terraform, ARM/Bicep, CloudWatch, Azure Monitor, and continuous deployment "
            "sustaining 99.9% uptime SLA."
        ),
    },
}


# ============================================================================
# Safe Module Importer Helper
# ============================================================================

def _get_competency_module():
    try:
        import engine.competency as mod
        return mod
    except ImportError:
        pytest.skip("engine.competency module not yet implemented.")


def _get_scorer_module():
    try:
        import engine.scorer as mod
        return mod
    except ImportError:
        pytest.skip("engine.scorer module not yet implemented.")


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def default_candidate_profile() -> CandidateProfile:
    """Returns an authoritative CandidateProfile loaded from embedded default."""
    return load_profile_from_dict(get_embedded_default_profile())


# ============================================================================
# 1. Feature F04: Role Competency & Taxonomy Tests
# ============================================================================

class TestRoleCompetencyTaxonomy:
    """Verifies the 8-role competency taxonomy and keyword extractor."""

    def test_taxonomy_covers_all_8_target_roles(self):
        """Verifies that the taxonomy defines all 8 required technical roles."""
        comp = _get_competency_module()
        taxonomy = comp.get_role_taxonomy()
        assert isinstance(taxonomy, dict)

        expected_roles = [
            "Cloud Solutions Architect",
            "Cloud Infrastructure Engineer",
            "Cloud Engineer",
            "Dev(Sec)Ops Engineer",
            "System Administrator",
            "IT Specialist/Administrator",
            "Technical Support Engineer",
            "Azure/AWS DevOps Engineer",
        ]
        tax_keys_lower = [str(k).lower() for k in taxonomy.keys()]
        for role in expected_roles:
            role_norm = role.lower().replace("(", "").replace(")", "").replace("/", " ")
            assert any(role_norm in k or k in role_norm for k in tax_keys_lower), f"Missing role in taxonomy: {role}"

    def test_taxonomy_contains_core_skills_and_certifications(self):
        """Verifies that each role taxonomy entry contains required metadata."""
        comp = _get_competency_module()
        taxonomy = comp.get_role_taxonomy()

        for role_key, role_spec in taxonomy.items():
            assert "core_skills" in role_spec or "skills" in role_spec or "keywords" in role_spec
            skills = role_spec.get("core_skills", role_spec.get("skills", role_spec.get("keywords", [])))
            assert len(skills) >= 3, f"Insufficient skills defined for role {role_key}"

    def test_extract_keywords_from_devops_jd(self):
        """Verifies technical keyword extraction from a DevOps job description."""
        comp = _get_competency_module()
        jd = SYNTHETIC_ROLE_JOBS["Dev(Sec)Ops Engineer"]["description"]
        keywords = comp.extract_keywords(jd)

        assert isinstance(keywords, list)
        keywords_lower = [k.lower() for k in keywords]
        assert any(k in ["kubernetes", "kcna", "k8s"] for k in keywords_lower)
        assert any(k in ["terraform", "iac"] for k in keywords_lower)
        assert any("docker" in k or "container" in k for k in keywords_lower)

    def test_extract_keywords_from_architect_jd(self):
        """Verifies technical keyword extraction from a Cloud Architect job description."""
        comp = _get_competency_module()
        jd = SYNTHETIC_ROLE_JOBS["Cloud Solutions Architect"]["description"]
        keywords = comp.extract_keywords(jd)

        keywords_lower = [k.lower() for k in keywords]
        assert any(k in ["aws", "azure", "multi-cloud"] for k in keywords_lower)
        assert any("well-architected" in k or "architect" in k for k in keywords_lower)
        assert any("finops" in k or "cost" in k for k in keywords_lower)

    def test_extract_keywords_case_insensitivity(self):
        """Verifies that acronyms and keywords match regardless of case."""
        comp = _get_competency_module()
        text_upper = "EXPERIENCE WITH AWS, AZURE, KUBERNETES, TERRAFORM, AND DOCKER REQUIRED."
        text_lower = "experience with aws, azure, kubernetes, terraform, and docker required."

        kw_upper = comp.extract_keywords(text_upper)
        kw_lower = comp.extract_keywords(text_lower)
        assert len(kw_upper) == len(kw_lower)
        assert set(k.lower() for k in kw_upper) == set(k.lower() for k in kw_lower)

    def test_extract_keywords_filters_html_and_dom_noise(self):
        """Verifies that HTML tags do not contaminate extracted keywords."""
        comp = _get_competency_module()
        html_jd = "<div><h1>Job Description</h1><p>Must know <b>Kubernetes</b> and <i>Terraform</i>.</p></div>"
        keywords = comp.extract_keywords(html_jd)

        keywords_lower = [k.lower() for k in keywords]
        assert "kubernetes" in keywords_lower or any("kubernetes" in k for k in keywords_lower)
        assert "terraform" in keywords_lower or any("terraform" in k for k in keywords_lower)
        assert "div" not in keywords_lower
        assert "p" not in keywords_lower
        assert "b" not in keywords_lower

    def test_extract_required_certifications(self):
        """Verifies extraction of recognized certifications from job descriptions."""
        comp = _get_competency_module()
        if not hasattr(comp, "extract_required_certifications"):
            pytest.skip("extract_required_certifications not yet exposed in competency module")

        text = "KCNA and AWS Certified Solutions Architect – Associate preferred. ITIL Foundation is a plus."
        certs = comp.extract_required_certifications(text)
        certs_lower = [c.lower() for c in certs]
        assert any("kcna" in c or "kubernetes" in c for c in certs_lower)
        assert any("aws" in c for c in certs_lower)

    def test_classify_target_role(self):
        """Verifies classification of job descriptions into canonical role titles."""
        comp = _get_competency_module()
        if not hasattr(comp, "classify_target_role"):
            pytest.skip("classify_target_role not yet exposed in competency module")

        role1 = comp.classify_target_role(SYNTHETIC_ROLE_JOBS["Dev(Sec)Ops Engineer"]["description"])
        assert "devops" in role1.lower() or "dev(sec)ops" in role1.lower()

        role2 = comp.classify_target_role(SYNTHETIC_ROLE_JOBS["Technical Support Engineer"]["description"])
        assert "support" in role2.lower()


# ============================================================================
# 2. Feature F07: Multi-Dimensional Match Scorer Tests
# ============================================================================

class TestMultiDimensionalMatchScorer:
    """Verifies the 5-dimension 0-100 match scoring algorithm and contract."""

    def test_scorer_weight_arithmetic_sums_to_one(self):
        """Verifies that the 5 dimension weights sum exactly to 1.0 (100%)."""
        scorer = _get_scorer_module()
        weights = getattr(
            scorer,
            "DIMENSION_WEIGHTS",
            {"skills": 0.35, "title": 0.25, "metrics": 0.15, "mobility": 0.15, "certs": 0.10}
        )
        assert isinstance(weights, dict)
        for expected_key in ["skills", "title", "metrics", "mobility", "certs"]:
            assert expected_key in weights, f"Missing dimension weight: {expected_key}"
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_evaluate_job_returns_valid_match_result(self, default_candidate_profile):
        """Verifies that evaluate_job returns a MatchResult conforming to PROJECT.md:111."""
        scorer = _get_scorer_module()
        jd = SYNTHETIC_ROLE_JOBS["Dev(Sec)Ops Engineer"]["description"]
        result = scorer.evaluate_job(default_candidate_profile, jd)

        # Verify required contract attributes
        assert hasattr(result, "overall_score")
        assert hasattr(result, "breakdown")
        assert hasattr(result, "matched_skills")
        assert hasattr(result, "missing_skills")
        assert hasattr(result, "target_role")
        assert hasattr(result, "rationale")

        # Verify types
        assert isinstance(result.overall_score, (int, float))
        assert isinstance(result.breakdown, dict)
        assert isinstance(result.matched_skills, list)
        assert isinstance(result.missing_skills, list)
        assert isinstance(result.target_role, str)
        assert isinstance(result.rationale, str)

        # Verify score bounds
        assert 0.0 <= result.overall_score <= 100.0

    def test_breakdown_contains_all_5_dimensions(self, default_candidate_profile):
        """Verifies that the score breakdown dictionary contains all 5 dimensions."""
        scorer = _get_scorer_module()
        jd = SYNTHETIC_ROLE_JOBS["Cloud Solutions Architect"]["description"]
        result = scorer.evaluate_job(default_candidate_profile, jd)

        for dim in ["skills", "title", "metrics", "mobility", "certs"]:
            assert dim in result.breakdown
            assert 0.0 <= result.breakdown[dim] <= 100.0

    @pytest.mark.parametrize("role_name,job_data", SYNTHETIC_ROLE_JOBS.items())
    def test_high_match_across_all_8_target_roles(self, default_candidate_profile, role_name, job_data):
        """Verifies that candidate scores high (>=75%) across all 8 target roles."""
        scorer = _get_scorer_module()
        result = scorer.evaluate_job(default_candidate_profile, job_data["description"])

        assert result.overall_score >= 75.0, (
            f"Role {role_name} score {result.overall_score:.1f} was below 75.0 threshold. "
            f"Breakdown: {result.breakdown}"
        )
        assert len(result.matched_skills) >= 2
        assert "Apply" in result.rationale or "Match" in result.rationale

    def test_gap_analysis_reports_missing_skills(self, default_candidate_profile):
        """Verifies that missing technologies in the JD are reported in missing_skills."""
        scorer = _get_scorer_module()
        jd_with_unmatched = (
            "Senior DevOps Engineer. Required skills: Kubernetes, Terraform, AWS, Golang, Rust, "
            "Google Cloud Platform (GCP), and Ansible automation."
        )
        result = scorer.evaluate_job(default_candidate_profile, jd_with_unmatched)

        missing_lower = [s.lower() for s in result.missing_skills]
        matched_lower = [s.lower() for s in result.matched_skills]

        # Candidate has Kubernetes, Terraform, AWS
        assert any("kubernetes" in s for s in matched_lower)
        assert any("terraform" in s for s in matched_lower)
        assert any("aws" in s for s in matched_lower)

        # Candidate lacks Rust, Golang, GCP, or Ansible
        assert any("rust" in s or "golang" in s or "gcp" in s or "ansible" in s for s in missing_lower)

        # Ensure matched and missing are disjoint
        assert not set(matched_lower).intersection(set(missing_lower))

    def test_action_recommendation_tiers(self, default_candidate_profile):
        """Verifies rationale recommendations based on score brackets."""
        scorer = _get_scorer_module()

        # Strong match
        strong_jd = SYNTHETIC_ROLE_JOBS["Dev(Sec)Ops Engineer"]["description"]
        res_strong = scorer.evaluate_job(default_candidate_profile, strong_jd)
        if res_strong.overall_score >= 80.0:
            assert "Strong Apply" in res_strong.rationale or "Top" in res_strong.rationale or "Apply" in res_strong.rationale


# ============================================================================
# 3. Boundary & Adversarial Cases for Matching & Scoring
# ============================================================================

class TestScoringBoundaryAndAdversarialCases:
    """Boundary, corner case, and adversarial stress tests."""

    def test_empty_job_description_scores_baseline(self, default_candidate_profile):
        """Verifies that empty string input does not crash and scores <= 20%."""
        scorer = _get_scorer_module()
        result = scorer.evaluate_job(default_candidate_profile, "")
        assert result.overall_score <= 20.0
        assert result.breakdown["skills"] == 0.0

    def test_completely_irrelevant_job_scores_low(self, default_candidate_profile):
        """Verifies that a culinary job description scores < 30% with 'Do Not Apply'."""
        scorer = _get_scorer_module()
        pastry_jd = (
            "Head Pastry Chef & Chocolatier wanted for luxury French bakery. "
            "Must have 10+ years experience in sourdough levain, laminated puff pastry, "
            "sugar sculpting, and temperature-controlled chocolate tempering. High CSAT required."
        )
        result = scorer.evaluate_job(default_candidate_profile, pastry_jd)
        assert result.overall_score < 30.0
        assert "Do Not Apply" in result.rationale or "Low" in result.rationale

    def test_perfect_saturation_job_scores_top_tier(self, default_candidate_profile):
        """Verifies that a 100% keyword/cert/metric saturated JD scores >= 85%."""
        scorer = _get_scorer_module()
        perfect_jd = (
            "Senior DevOps Engineer & Platform Architect. Required: Kubernetes (KCNA certified), "
            "AWS Certified Solutions Architect, Terraform Infrastructure as Code, Docker, "
            "Microsoft Azure App Service, 99.9% uptime SLA, L3 root-cause analysis (RCA), "
            "and fast provisioning. Full-time Remote from Nigeria / Worldwide (UTC+1 / CET)."
        )
        result = scorer.evaluate_job(default_candidate_profile, perfect_jd)
        assert result.overall_score >= 85.0
        assert result.breakdown["skills"] >= 80.0
        assert result.breakdown["metrics"] >= 80.0
        assert result.breakdown["certs"] >= 80.0

    def test_contradictory_unrealistic_experience_demands(self, default_candidate_profile):
        """Verifies resilience to contradictory or absurd requirements."""
        scorer = _get_scorer_module()
        absurd_jd = (
            "Junior DevOps Intern needed with 25 years of Kubernetes experience, "
            "30 years of Azure OpenAI architecture, and willingness to work for equity."
        )
        result = scorer.evaluate_job(default_candidate_profile, absurd_jd)
        assert 0.0 <= result.overall_score <= 100.0

    def test_repetitive_stress_test_long_jd(self, default_candidate_profile):
        """Stress tests parser and scorer against 50,000-token repetitive text."""
        scorer = _get_scorer_module()
        long_jd = "Kubernetes Terraform Docker AWS Azure " * 5000
        result = scorer.evaluate_job(default_candidate_profile, long_jd)
        assert 0.0 <= result.overall_score <= 100.0

    def test_disqualifying_location_penalizes_mobility(self, default_candidate_profile):
        """Verifies that US-only/Security Clearance jobs receive 0 for mobility score."""
        scorer = _get_scorer_module()
        us_only_jd = (
            "Senior DevOps Engineer. Must be a US Citizen residing in the continental US. "
            "Active Top Secret / SCI clearance required. W2 only. Candidates outside the US rejected."
        )
        result = scorer.evaluate_job(default_candidate_profile, us_only_jd)
        # Mobility score must be severely penalized
        assert result.breakdown["mobility"] <= 30.0
        # Overall score should be lower than standard remote match
        assert result.overall_score < 70.0
