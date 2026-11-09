"""
Career Automation Document Tailoring Engine (CV & Cover Letter).
Module: tailoring
"""

from tailoring.cv_tailor import (
    generate_cv,
    get_cv_filename,
    prioritize_skills,
)
from tailoring.letter_tailor import (
    generate_cover_letter,
)

__all__ = [
    "generate_cv",
    "get_cv_filename",
    "prioritize_skills",
    "generate_cover_letter",
]
