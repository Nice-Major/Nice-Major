"""
Job Discovery, Geo-Filtering & Verification Engine.
Package: discovery
Milestone: M3 (Features F08, F09, F10)
"""

from __future__ import annotations

from discovery.models import (
    JobOpportunity,
    Opportunity,
    JobQueryParams,
)
from discovery.sources import (
    BaseSourceAdapter,
    RemoteOKAdapter,
    WeWorkRemotelyAdapter,
    JobicyAdapter,
    RssFeedAdapter,
    CompanyCareerPageAdapter,
    SyntheticSourceAdapter,
    AdapterRegistry,
    registry,
    fetch_opportunities,
    search_opportunities,
    get_synthetic_opportunities,
    normalize_opportunities,
    deduplicate_opportunities,
    CANONICAL_TARGET_ROLES,
)
from discovery.filters import (
    EligibilityResult,
    filter_opportunities,
    is_remote_eligible,
    detect_visa_sponsorship,
    detect_contract_c2c,
    detect_contract_consultancy,
    detect_research_fellowship,
    detect_fellowship_research,
    has_disqualifiers,
    evaluate_location_mobility,
    evaluate_opportunity_eligibility,
    categorize_opportunity,
)
from discovery.verifier import (
    VerificationResult,
    verify_job_link,
    verify_url_status,
    detect_closed_phrase,
    is_fresh_date,
    generate_fingerprint,
    check_redirect_depth,
    verify_opportunities,
)

__all__ = [
    # Models
    "JobOpportunity",
    "Opportunity",
    "JobQueryParams",
    # Sources (F08)
    "BaseSourceAdapter",
    "RemoteOKAdapter",
    "WeWorkRemotelyAdapter",
    "JobicyAdapter",
    "RssFeedAdapter",
    "CompanyCareerPageAdapter",
    "SyntheticSourceAdapter",
    "AdapterRegistry",
    "registry",
    "fetch_opportunities",
    "search_opportunities",
    "get_synthetic_opportunities",
    "normalize_opportunities",
    "deduplicate_opportunities",
    "CANONICAL_TARGET_ROLES",
    # Filters (F09)
    "EligibilityResult",
    "filter_opportunities",
    "is_remote_eligible",
    "detect_visa_sponsorship",
    "detect_contract_c2c",
    "detect_contract_consultancy",
    "detect_research_fellowship",
    "detect_fellowship_research",
    "has_disqualifiers",
    "evaluate_location_mobility",
    "evaluate_opportunity_eligibility",
    "categorize_opportunity",
    # Verifier (F10)
    "VerificationResult",
    "verify_job_link",
    "verify_url_status",
    "detect_closed_phrase",
    "is_fresh_date",
    "generate_fingerprint",
    "check_redirect_depth",
    "verify_opportunities",
]
