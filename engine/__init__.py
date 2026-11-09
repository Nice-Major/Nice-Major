"""
Career Automation Core Scoring & Competency Engine.
Module: engine
"""

from engine.competency import (
    clean_html,
    classify_target_role,
    detect_target_role,
    extract_certifications,
    extract_keywords,
    extract_required_certifications,
    get_role_taxonomy,
    ROLE_TAXONOMY,
    RoleTaxonomyEntry,
)
from engine.scorer import (
    DIMENSION_WEIGHTS,
    evaluate_job,
    MatchResult,
)

__all__ = [
    "clean_html",
    "classify_target_role",
    "detect_target_role",
    "extract_certifications",
    "extract_keywords",
    "extract_required_certifications",
    "get_role_taxonomy",
    "ROLE_TAXONOMY",
    "RoleTaxonomyEntry",
    "DIMENSION_WEIGHTS",
    "evaluate_job",
    "MatchResult",
]
