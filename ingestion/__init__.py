"""
Candidate profile data ingestion, schema validation, and ATS text normalization.
Package: ingestion
"""

from ingestion.models import (
    BulletPoint,
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
from ingestion.parser import (
    ProfileError,
    ProfileNotFoundError,
    ProfileParseError,
    ProfileValidationError,
    find_profile_data_path,
    load_profile,
    load_profile_from_dict,
    load_profile_from_file,
    load_source_of_truth,
    normalize_profile_dict,
    validate_profile_completeness,
)
from ingestion.text_utils import (
    clean_ats_text,
    extract_clean_words,
    normalize_whitespace,
    safe_filename,
    sanitize_ligatures,
    strip_markdown,
)

__all__ = [
    # Models
    "BulletPoint",
    "CandidateInfo",
    "CandidateProfile",
    "Certification",
    "Education",
    "KpiMetric",
    "RoleCategory",
    "SkillsMatrix",
    "StepconProfile",
    "WorkExperience",
    # Parser
    "ProfileError",
    "ProfileNotFoundError",
    "ProfileParseError",
    "ProfileValidationError",
    "find_profile_data_path",
    "load_profile",
    "load_profile_from_dict",
    "load_profile_from_file",
    "load_source_of_truth",
    "normalize_profile_dict",
    "validate_profile_completeness",
    # Text Utils
    "clean_ats_text",
    "extract_clean_words",
    "normalize_whitespace",
    "safe_filename",
    "sanitize_ligatures",
    "strip_markdown",
]
