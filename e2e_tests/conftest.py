"""
Pytest configuration and shared fixtures for the E2E Test Suite.
Supports dual execution: standard pytest and custom standalone runner.
"""
import os
import sys
import json
import importlib
import tempfile
import pathlib
try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return decorator

        @staticmethod
        def skip(reason=""):
            raise NotImplementedError(reason)
    pytest = _MockPytest()

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Candidate assets directory
CANDIDATE_ASSET_DIR = pathlib.Path(r"C:\Users\user\Downloads\Nice_Major_Portfolio_and_Automation_Suite")
CANONICAL_PROFILE_PATH = CANDIDATE_ASSET_DIR / "profile-data.json"


class FeatureNotImplementedError(NotImplementedError):
    """Raised when an implementation module is not yet present during milestone development."""
    def __init__(self, feature_id: str, module_name: str, milestone: str):
        super().__init__(f"[{milestone} Pending] Feature {feature_id}: Module '{module_name}' is not yet implemented.")
        self.feature_id = feature_id
        self.module_name = module_name
        self.milestone = milestone


def get_module_or_skip(module_name: str, feature_id: str = "F00", milestone: str = "TBD"):
    """
    Safely load a module. If not implemented yet, skip test via pytest.skip or raise FeatureNotImplementedError.
    """
    try:
        return importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as err:
        # Check if the missing module is indeed part of the project
        err_msg = str(err)
        if any(pkg in err_msg for pkg in ["ingestion", "engine", "tailoring", "discovery", "dispatch", "cli", "consultancy", "scheduler", "config"]):
            skip_msg = f"[{milestone} Pending] Feature {feature_id}: Module '{module_name}' not yet implemented ({err_msg})"
            try:
                pytest.skip(skip_msg)
            except Exception:
                raise FeatureNotImplementedError(feature_id, module_name, milestone) from err
            except BaseException as b_err:
                if type(b_err).__name__ == "Skipped":
                    raise
                raise FeatureNotImplementedError(feature_id, module_name, milestone) from err
        raise


@pytest.fixture(scope="session")
def project_root() -> pathlib.Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def canonical_profile_data() -> dict:
    if CANONICAL_PROFILE_PATH.exists():
        with open(CANONICAL_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Synthetic fallback if external directory is unavailable
    return {
        "candidate": {
            "firstName": "John",
            "middleName": "Victor",
            "lastName": "Aniekwe",
            "fullName": "John Victor Aniekwe",
            "email": "aniekwevictor9@gmail.com",
            "phone": "+2348130004114",
            "location": "Lagos, Nigeria (UTC+1 / CET Synchronous)",
            "linkedin": "https://www.linkedin.com/in/victor-aniekwe",
            "githubProfile": "https://github.com/Nice-Major",
            "education": {
                "degree": "Bachelor of Science (B.Sc.) in Computer Science",
                "institution": "University of Nigeria",
                "period": "2014 – 2018"
            },
            "certifications": [
                {"name": "Kubernetes and Cloud Native Associate (KCNA)", "issuer": "Linux Foundation / CNCF", "status": "Active", "tags": ["all", "devops"]},
                {"name": "AWS Certified Solutions Architect – Associate", "issuer": "Amazon Web Services", "status": "Active", "tags": ["all", "architect"]},
                {"name": "AWS Certified Developer – Associate", "issuer": "Amazon Web Services", "status": "Active", "tags": ["all", "devops"]},
                {"name": "AWS Certified Cloud Practitioner", "issuer": "Amazon Web Services", "status": "Active", "tags": ["all", "cloud"]},
                {"name": "ITIL Foundation (Pursuing — Committed within 3 Months)", "issuer": "AXELOS / PeopleCert", "status": "In Progress", "tags": ["all", "support"]}
            ]
        },
        "kpiMetrics": [
            {"value": "99.9%", "label": "Enterprise Cloud Uptime SLA"},
            {"value": "99%", "label": "First-Day L3 Issue Resolution"},
            {"value": ">60%", "label": "AI Prediction Engine Accuracy"},
            {"value": "<15 Min", "label": "Multi-Environment Provisioning Time"}
        ],
        "roleCategories": {
            "devops": {
                "categoryTitle": "Dev(Sec)Ops & AI Platform Engineer",
                "targetTitles": ["DevOps Engineer", "DevSecOps Engineer", "Platform Engineer", "Kubernetes Administrator"],
                "headline": "DevOps Engineer & AI Platform Architect",
                "summary": "DevOps Engineer with 5+ years experience specializing in Kubernetes, Terraform, and CI/CD."
            },
            "architect": {
                "categoryTitle": "Cloud Solutions Architect & Multi-Cloud",
                "targetTitles": ["Cloud Solutions Architect", "Enterprise Cloud Architect"],
                "headline": "Cloud Solutions Architect",
                "summary": "Multi-Cloud Architect designing enterprise solutions across AWS and Azure."
            },
            "infra": {
                "categoryTitle": "Cloud Infrastructure & Linux Systems Engineer",
                "targetTitles": ["Cloud Infrastructure Engineer", "System Administrator"],
                "headline": "Cloud Infrastructure Engineer",
                "summary": "Infrastructure engineer managing Linux and Windows environments with 99.9% uptime SLA."
            },
            "support": {
                "categoryTitle": "L3 Technical Cloud Support Engineer & IT Specialist",
                "targetTitles": ["Technical Support Engineer", "L3 Cloud Escalation Engineer", "IT Specialist"],
                "headline": "L3 Cloud Escalation Support Engineer",
                "summary": "Technical Support Lead achieving 99% first-day resolution rate on Azure App Service."
            }
        },
        "stepconSolutions": {
            "companyName": "Stepcon Solutions",
            "cacNumber": "RC - 8284984",
            "jurisdiction": "Corporate Affairs Commission (CAC), Federal Republic of Nigeria",
            "b2bConsultancyPitch": "Stepcon Solutions (RC - 8284984) provides immediate Corp-to-Corp (C2C) Cloud Architecture and DevSecOps pods.",
            "hardwareDivision": "Enterprise computing hardware procurement, QA diagnostics, and logistics."
        }
    }


@pytest.fixture
def synthetic_jobs() -> dict:
    return {
        "devops": {
            "title": "Senior DevOps Engineer",
            "company": "Global Cloud Corp",
            "location": "Remote - Worldwide (EMEA / UTC+1)",
            "description": (
                "We are seeking a Senior DevOps Engineer to lead our Kubernetes and Terraform automation. "
                "Must have strong experience in container orchestration (Kubernetes, Docker), Infrastructure as Code "
                "(Terraform), CI/CD pipelines (GitHub Actions), and AWS/Azure cloud platforms. Candidate must ensure "
                "enterprise 99.9% uptime SLAs and integrate DevSecOps controls."
            ),
            "url": "https://careers.globalcloud.example/jobs/devops-101",
            "posted_date": "2026-11-01"
        },
        "architect": {
            "title": "Cloud Solutions Architect",
            "company": "Enterprise Horizons Ltd",
            "location": "Worldwide Remote / CET Synchronous",
            "description": (
                "Looking for a Cloud Solutions Architect to design scalable multi-cloud microservices on Azure and AWS. "
                "Must apply the Well-Architected Framework, architect AKS/EKS clusters, configure private endpoints, "
                "and optimize FinOps cost governance."
            ),
            "url": "https://careers.enterprisehorizons.example/jobs/csa-202",
            "posted_date": "2026-11-03"
        },
        "support": {
            "title": "L3 Technical Support Engineer",
            "company": "CloudCare Global",
            "location": "Remote (Anywhere)",
            "description": (
                "Seeking an L3 Technical Cloud Support Engineer for production incident escalation on Microsoft Azure App Service. "
                "Deep root-cause analysis (RCA), logs, metrics, distributed traces, and TsG authoring. High CSAT and SLA adherence required."
            ),
            "url": "https://careers.cloudcare.example/jobs/supp-303",
            "posted_date": "2026-11-04"
        },
        "us_only": {
            "title": "DevOps Engineer (US Only)",
            "company": "American Defense Systems",
            "location": "Remote - US",
            "description": (
                "Must be a US Citizen residing in the continental United States. Requires active Secret Clearance. "
                "W2 Only. Candidates outside the US will not be considered."
            ),
            "url": "https://careers.usdefense.example/jobs/us-404",
            "posted_date": "2026-11-02"
        },
        "stale": {
            "title": "Infrastructure Engineer",
            "company": "Legacy Tech Ltd",
            "location": "Worldwide",
            "description": "Maintain legacy Linux servers. Closed listing.",
            "url": "https://careers.legacytech.example/jobs/stale-505",
            "posted_date": "2026-08-01"
        },
        "closed": {
            "title": "Cloud Engineer",
            "company": "QuickFill Inc",
            "location": "Remote Worldwide",
            "description": "This position has been filled. Applications are now closed.",
            "url": "https://careers.quickfill.example/jobs/closed-606",
            "posted_date": "2026-11-05"
        }
    }


@pytest.fixture
def synthetic_tenders() -> dict:
    return {
        "matching": {
            "tender_id": "TND-2026-088",
            "title": "Enterprise Multi-Cloud Infrastructure & DevSecOps Modernization",
            "client": "Pan-African Financial Services Group",
            "description": (
                "RFP for turnkey cloud engineering pod to design declarative Infrastructure as Code (Terraform), "
                "automate CI/CD pipelines, and deploy Kubernetes microservices on AWS and Azure under 99.9% availability SLA. "
                "B2B Corp-to-Corp contracting with synchronous EMEA/CET working hours required."
            ),
            "budget": "$120,000 USD",
            "deadline": "2026-12-15"
        },
        "non_matching": {
            "tender_id": "TND-CIVIL-009",
            "title": "Construction and Road Asphalt Paving Tender",
            "client": "Regional Transport Authority",
            "description": "Supply of asphalt concrete, road grading equipment, and civil engineering drainage maintenance.",
            "budget": "$500,000 USD",
            "deadline": "2026-12-01"
        }
    }


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield pathlib.Path(tmp_dir)
