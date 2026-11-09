"""
Comprehensive Unit Test Suite for Stepcon Solutions IT Consultancy Pipeline.
Module: tests.test_consultancy
Feature: F14 (Stepcon Solutions Consultancy Pipeline)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from consultancy.proposals import generate_proposal, get_proposal_filename
from consultancy.tenders import (
    evaluate_tender,
    fetch_tenders,
    TenderMatchResult,
    TenderOpportunity,
)
from ingestion.models import StepconProfile


@pytest.fixture
def stepcon_profile_obj() -> StepconProfile:
    return StepconProfile(
        company_name="Stepcon Solutions",
        cac_number="RC - 8284984",
    )


@pytest.fixture
def matching_cloud_tender() -> dict:
    return {
        "tender_id": "TND-2026-088",
        "title": "Enterprise Multi-Cloud Infrastructure & DevSecOps Modernization",
        "client": "Pan-African Financial Services Group",
        "description": (
            "RFP for turnkey cloud engineering pod to design declarative Infrastructure as Code (Terraform), "
            "automate CI/CD pipelines, and deploy Kubernetes microservices on AWS and Azure under 99.9% availability SLA. "
            "B2B Corp-to-Corp contracting with synchronous EMEA/CET working hours required."
        ),
        "budget": "$120,000 USD",
        "deadline": "2026-12-15",
    }


@pytest.fixture
def civil_non_matching_tender() -> dict:
    return {
        "tender_id": "TND-CIVIL-009",
        "title": "Construction and Road Asphalt Paving Tender",
        "client": "Regional Transport Authority",
        "description": "Supply of asphalt concrete, road grading equipment, and civil engineering drainage maintenance.",
        "budget": "$500,000 USD",
        "deadline": "2026-12-01",
    }


class TestStepconTenderEvaluation:
    """Verifies tender scoring, offerings matching, and domain discrimination."""

    def test_matching_cloud_tender_scores_above_70(self, stepcon_profile_obj, matching_cloud_tender):
        res = evaluate_tender(stepcon_profile_obj, matching_cloud_tender["description"])
        assert isinstance(res, TenderMatchResult)
        assert res.overall_score >= 70.0
        assert "offerings" in res.breakdown
        assert "sla" in res.breakdown
        assert "commercial" in res.breakdown
        assert "credentials" in res.breakdown

    def test_civil_non_it_tender_scores_below_35(self, stepcon_profile_obj, civil_non_matching_tender):
        res = evaluate_tender(stepcon_profile_obj, civil_non_matching_tender["description"])
        assert res.overall_score < 35.0
        assert "Civil/public works" in res.rationale or "outside" in res.rationale

    def test_minimalist_tender_text_bounded(self, stepcon_profile_obj):
        res = evaluate_tender(stepcon_profile_obj, "Cloud.")
        assert 0.0 <= res.overall_score <= 100.0

    def test_empty_tender_text_scores_zero(self, stepcon_profile_obj):
        res = evaluate_tender(stepcon_profile_obj, "")
        assert res.overall_score == 0.0

    def test_tender_result_subscript_and_attribute_access(self, stepcon_profile_obj, matching_cloud_tender):
        res = evaluate_tender(stepcon_profile_obj, matching_cloud_tender["description"])
        assert res["overall_score"] == res.overall_score
        assert "breakdown" in res
        assert res.get("target_offering") is not None

    def test_tender_evaluation_handles_none_description_safely(self, stepcon_profile_obj):
        res_dict_none = evaluate_tender(stepcon_profile_obj, {"description": None})
        assert isinstance(res_dict_none, TenderMatchResult)
        assert res_dict_none.overall_score == 0.0

        res_obj_none = evaluate_tender(stepcon_profile_obj, TenderOpportunity(description=None))
        assert isinstance(res_obj_none, TenderMatchResult)
        assert res_obj_none.overall_score == 0.0

        res_none = evaluate_tender(stepcon_profile_obj, None)
        assert isinstance(res_none, TenderMatchResult)
        assert res_none.overall_score == 0.0


class TestStepconTenderDiscovery:
    """Verifies tender discovery and data modeling."""

    def test_fetch_tenders_dry_run_returns_opportunities(self):
        tenders = fetch_tenders(dry_run=True)
        assert len(tenders) >= 3
        first = tenders[0]
        assert isinstance(first, TenderOpportunity)
        assert first.id
        assert first.title
        assert first.description

    def test_tender_opportunity_dictionary_subscript_compatibility(self):
        opp = TenderOpportunity(id="TND-1", title="Cloud RFP", description="AWS Azure")
        assert opp["id"] == "TND-1"
        assert opp.get("description") == "AWS Azure"
        assert "title" in opp

    def test_fetch_tenders_category_filtering(self):
        tenders = fetch_tenders(dry_run=True, query_categories=["hardware"])
        assert len(tenders) >= 1
        assert any(t.category == "hardware" for t in tenders)


class TestStepconProposalGeneration:
    """Verifies corporate proposal synthesis and contract compliance."""

    def test_proposal_contains_mandatory_corporate_identity(self, stepcon_profile_obj, matching_cloud_tender):
        prop = generate_proposal(stepcon_profile_obj, matching_cloud_tender)
        assert "Stepcon Solutions" in prop
        assert "RC - 8284984" in prop

    def test_proposal_contains_lead_architect_and_certifications(self, stepcon_profile_obj, matching_cloud_tender):
        prop = generate_proposal(stepcon_profile_obj, matching_cloud_tender)
        assert "John Victor Aniekwe" in prop
        assert "KCNA" in prop
        assert "AWS" in prop

    def test_proposal_specifies_c2c_and_sla(self, stepcon_profile_obj, matching_cloud_tender):
        prop = generate_proposal(stepcon_profile_obj, matching_cloud_tender)
        assert "Corp-to-Corp" in prop or "C2C" in prop
        assert "99.9%" in prop

    def test_proposal_multi_currency_options(self, stepcon_profile_obj, matching_cloud_tender):
        prop = generate_proposal(stepcon_profile_obj, matching_cloud_tender)
        assert any(c in prop for c in ["USD", "$", "GBP", "£", "EUR", "€", "NGN", "₦"])

    def test_missing_client_name_uses_placeholder_no_none_string(self, stepcon_profile_obj):
        minimal = {"title": "Cloud Migration", "description": "AWS & Kubernetes migration."}
        prop = generate_proposal(stepcon_profile_obj, minimal)
        assert "Stepcon Solutions" in prop
        assert "None" not in prop

    def test_proposal_filename_generation(self, matching_cloud_tender):
        fn = get_proposal_filename(matching_cloud_tender)
        assert fn.startswith("Proposal_Stepcon_")
        assert fn.endswith(".md")

    def test_proposal_contains_no_uninterpolated_placeholders(self, stepcon_profile_obj, matching_cloud_tender):
        prop = generate_proposal(stepcon_profile_obj, matching_cloud_tender)
        assert "{cac_reg}" not in prop
        assert "{company_name}" not in prop
        assert "{lead_name}" not in prop
        assert "RC - 8284984" in prop
        uninterpolated = re.findall(r"\{[a-zA-Z_]+\}", prop)
        assert len(uninterpolated) == 0, f"Found raw placeholders: {uninterpolated}"

    def test_proposal_filename_with_none_id_prevents_none_leak(self):
        fn = get_proposal_filename({"id": None})
        assert "None" not in fn
        assert fn.startswith("Proposal_Stepcon_Tender_")
        assert fn.endswith(".md")

    def test_proposal_filename_sanitizes_special_characters(self):
        fn = get_proposal_filename({"id": "TND/2026/088 #1 (Confidential)"})
        assert "/" not in fn and "\\" not in fn and "#" not in fn and " " not in fn
        assert fn.startswith("Proposal_Stepcon_TND_2026_088")
