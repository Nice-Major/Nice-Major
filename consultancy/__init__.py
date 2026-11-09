"""
Stepcon Solutions (RC - 8284984) IT Consultancy Pipeline.
Module: consultancy
Feature: F14 (Stepcon Solutions Consultancy Pipeline)
Milestone: M5 (Interactive CLI & Stepcon Solutions Pipeline)

Statutory Corporate Entity:
Stepcon Solutions, registered with the Corporate Affairs Commission (CAC),
Federal Republic of Nigeria under RC - 8284984.
"""

from __future__ import annotations

from consultancy.proposals import generate_proposal, get_proposal_filename
from consultancy.tenders import (
    evaluate_tender,
    fetch_tenders,
    TenderMatchResult,
    TenderOpportunity,
)

__all__ = [
    "evaluate_tender",
    "fetch_tenders",
    "generate_proposal",
    "get_proposal_filename",
    "TenderOpportunity",
    "TenderMatchResult",
]
