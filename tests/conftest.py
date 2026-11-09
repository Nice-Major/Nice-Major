"""
Pytest Fixtures for Career Automation Test Suite.
File: tests/conftest.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.models import CandidateProfile, StepconProfile
from ingestion.parser import load_profile_from_dict


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Returns absolute Path to project root."""
    return PROJECT_ROOT


@pytest.fixture
def minimal_candidate_dict() -> Dict[str, Any]:
    """Returns a minimal valid dictionary adhering to CandidateProfile schema."""
    return {
        "candidate": {
            "first_name": "John",
            "last_name": "Aniekwe",
            "full_name": "John Victor Aniekwe",
            "email": "aniekwevictor9@gmail.com",
            "phone": "+2348130004114",
            "location": "Lagos, Nigeria (UTC+1 / CET Synchronous)",
            "time_zone": "UTC+1 / CET Synchronous",
            "linkedin": "https://www.linkedin.com/in/victor-aniekwe",
            "github_profile": "https://github.com/Nice-Major",
            "portfolio_url": "https://nice-major.github.io/Nice-Major/",
            "certifications": [
                {
                    "name": "Kubernetes and Cloud Native Associate (KCNA)",
                    "issuer": "The Linux Foundation / CNCF",
                    "status": "Active",
                    "tags": ["all", "devops", "architect"],
                },
                {
                    "name": "AWS Certified Solutions Architect – Associate",
                    "issuer": "Amazon Web Services",
                    "status": "Active",
                    "tags": ["all", "architect", "infra"],
                },
            ],
            "mobility_categories": [
                "Global Remote from Anywhere (Nigeria / UTC+1 / CET / EMEA Synchronous)",
                "Visa-Sponsored Relocation",
                "B2B Corp-to-Corp Contractor via Stepcon Solutions (Nigerian CAC: RC - 8284984)",
            ],
            "education": {
                "degree": "Bachelor of Science (B.Sc.) in Computer Science",
                "institution": "University of Nigeria",
                "period": "2014 – 2018",
            },
        },
        "kpi_metrics": [
            {"value": "99.9%", "label": "Enterprise Cloud Uptime SLA", "context": "Sustained SLA across AWS/Azure"},
            {"value": "99%", "label": "First-Day L3 Issue Resolution", "context": "L3 resolution rate via RCA"},
        ],
        "role_categories": {
            "devops": {
                "title": "Senior DevOps & AI Platform Engineer",
                "category_title": "Dev(Sec)Ops & AI Platform Engineer",
                "target_titles": ["DevOps Engineer", "Platform Engineer"],
                "headline": "Senior DevOps Engineer",
                "summary": "5+ years experience in AWS, Azure, Kubernetes.",
            },
            "architect": {
                "title": "Cloud Solutions & Platform Architect",
                "category_title": "Cloud Solutions & Platform Architect",
                "target_titles": ["Cloud Solutions Architect", "Cloud Engineer"],
                "headline": "Cloud Solutions Architect",
                "summary": "Enterprise cloud architect.",
            },
        },
        "skills_matrix": [
            {
                "category": "Cloud Platforms (AWS & Azure)",
                "items": ["AWS", "Microsoft Azure", "Multi-Cloud"],
                "tags": ["devops", "architect"],
            },
            {
                "category": "Containers & Kubernetes Orchestration",
                "items": ["Kubernetes", "Docker", "AKS"],
                "tags": ["devops", "architect"],
            },
        ],
        "experience": [
            {
                "company": "GVOC",
                "location": "Remote, UK",
                "period": "December 2025 – Present",
                "titles": {
                    "devops": "DevOps Engineer / Platform Architect",
                    "architect": "Cloud Solutions & Platform Architect",
                },
                "bullets": [
                    {"text": "Architected Azure OpenAI on AKS sustaining SLA.", "tags": ["devops", "architect"]},
                    {"text": "Automated Terraform CI/CD pipelines.", "tags": ["devops"]},
                ],
            }
        ],
        "stepcon_solutions": {
            "company_name": "Stepcon Solutions",
            "cac_number": "RC - 8284984",
            "jurisdiction": "Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
            "b2b_consultancy_pitch": (
                "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) "
                "Cloud Architecture pods."
            ),
            "hardware_division": "Enterprise & Custom Computing Hardware Division.",
        },
    }


@pytest.fixture
def sample_profile(minimal_candidate_dict) -> CandidateProfile:
    """Returns an instantiated CandidateProfile from minimal_candidate_dict."""
    return load_profile_from_dict(minimal_candidate_dict)


@pytest.fixture
def sample_stepcon_profile() -> StepconProfile:
    """Returns a valid StepconProfile with verified CAC number."""
    return StepconProfile(
        company_name="Stepcon Solutions",
        cac_number="RC - 8284984",
    )
