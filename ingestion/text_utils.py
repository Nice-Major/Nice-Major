"""
ATS Text & Filename Utilities for Career Automation Suite.
Module: ingestion.text_utils
Feature: F03 (ATS Text & Filename Utilities)

Features:
- sanitize_ligatures: Multi-stage font ligature repair, space normalization, and invisible artifact purging.
- safe_filename: Strict underscore filename generation adhering to ATS standards and Windows MAX_PATH limits.
- clean_ats_text: Full-spectrum ATS text pre-processor for plain-text resume scoring.
- normalize_whitespace: Collapses non-standard spaces and excessive whitespace while preserving layout.
- strip_markdown: Converts Markdown formatting to clean plain text.
- extract_clean_words: Tokenizes text into normalized words for keyword analysis.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# ============================================================================
# 1. Ligature & Glitch Lookup Tables
# ============================================================================

# Direct Unicode presentation ligatures map to standard ASCII
UNICODE_LIGATURE_MAP: Dict[str, str] = {
    "\uFB00": "ff",     # ﬀ
    "\uFB01": "fi",     # ﬁ
    "\uFB02": "fl",     # ﬂ
    "\uFB03": "ffi",    # ﬃ
    "\uFB04": "ffl",    # ﬄ
    "\uFB05": "ft",     # ﬅ
    "\uFB06": "st",     # ﬆ
    "\u0132": "IJ",     # Ĳ
    "\u0133": "ij",     # ĳ
    "\u0152": "OE",     # Œ
    "\u0153": "oe",     # œ
    "\u00C6": "AE",     # Æ
    "\u00E6": "ae",     # æ
}

# Typographic quotes, dashes, and ellipses to clean ASCII (bullets handled by BULLET_REGEX)
TYPOGRAPHIC_MAP: Dict[str, str] = {
    "\u2018": "'",      # ‘ Left single quote
    "\u2019": "'",      # ’ Right single quote / apostrophe
    "\u201A": "'",      # ‚ Single low-9 quote
    "\u201B": "'",      # ‛ Single high-reversed-9 quote
    "\u2032": "'",      # ′ Prime
    "\u201C": '"',      # “ Left double quote
    "\u201D": '"',      # ” Right double quote
    "\u201E": '"',      # „ Double low-9 quote
    "\u201F": '"',      # ‟ Double high-reversed-9 quote
    "\u2033": '"',      # ″ Double prime
    "\u2013": "-",      # – En dash
    "\u2014": "--",     # — Em dash
    "\u2015": "--",     # ― Horizontal bar
    "\u2212": "-",      # − Minus sign
    "\u2026": "...",    # … Horizontal ellipsis
}

# Bullet point regex: matches bullet markers followed by optional horizontal whitespace
BULLET_REGEX = re.compile(r"[\u2022\u25CF\u25E6\u25AA\u25AB\u2043\u2219\u2023][^\S\r\n]*")

# Non-standard spaces to standard ASCII space (0x20)
SPACE_NORMALIZATION_MAP: Dict[str, str] = {
    "\u00A0": " ",      # Non-breaking space (NBSP)
    "\u202F": " ",      # Narrow no-break space (NNBSP)
    "\u2007": " ",      # Figure space
    "\u2000": " ",      # En quad
    "\u2001": " ",      # Em quad
    "\u2002": " ",      # En space
    "\u2003": " ",      # Em space
    "\u2004": " ",      # Three-per-em space
    "\u2005": " ",      # Four-per-em space
    "\u2006": " ",      # Six-per-em space
    "\u2008": " ",      # Punctuation space
    "\u2009": " ",      # Thin space
    "\u200A": " ",      # Hair space
    "\u3000": " ",      # Ideographic space
}

# Invisible characters to purge completely
INVISIBLE_CHARS_REGEX = re.compile(
    r"[\u200B\u200C\u200D\uFEFF\u00AD]"
)  # Zero-width space, ZWNJ, ZWJ, BOM, Soft Hyphen

# Forensic PDF extraction horn glyph corruptions (Ư / ư mapping to ff / ffi)
LIGATURE_HORN_GLITCHES: List[Tuple[re.Pattern, str]] = [
    # Efficiency family
    (re.compile(r"\b([Ee])[Ưư]icien(cy|t|tly|cies)\b"), r"\1fficien\2"),
    (re.compile(r"\b([Ee])[Ưư]iciency\b", re.IGNORECASE), "efficiency"),
    (re.compile(r"\b([Ee])[Ưư]icient\b", re.IGNORECASE), "efficient"),
    (re.compile(r"\b([Ee])[Ưư]iciently\b", re.IGNORECASE), "efficiently"),
    # Effective family
    (re.compile(r"\b([Ee])[Ưư]ect(ive|ively|iveness|s|ual)?\b"), r"\1ffect\2"),
    # Difference / Sufficient / Office / Traffic
    (re.compile(r"\b([Dd]i)[Ưư]eren(ce|t|tly|ces|tial)\b"), r"\1fferen\2"),
    (re.compile(r"\b([Ss]u)[Ưư]icien(cy|t|tly)\b"), r"\1fficien\2"),
    (re.compile(r"\b([Oo])[Ưư]ic(e|er|ial|ially|es)\b"), r"\1ffic\2"),
    (re.compile(r"\b([Tt]ra)[Ưư]ic\b"), r"\1ffic"),
    (re.compile(r"\b([Ee])[Ưư]ort(s)?\b"), r"\1ffort\2"),
    (re.compile(r"\b([Aa])[Ưư]ect(ive|ed|ing|s)?\b"), r"\1ffect\2"),
    (re.compile(r"\b([Aa])[Ưư]ord(able|ability|ed|ing)?\b"), r"\1fford\2"),
    # General fallback: any Ư or ư surrounded by ASCII word characters
    (re.compile(r"(?<=[a-zA-Z])[Ưư](?=[a-zA-Z])"), "ff"),
]

# Broken whitespace repairs where ligature was dropped and replaced by spaces
BROKEN_SPACE_GLITCHES: List[Tuple[re.Pattern, Any]] = [
    # effective / effectively
    (re.compile(r"\b([Ee](?:ff)?)\s+([Ee]ct(?:ive|ively|iveness|s)?)\b", re.IGNORECASE), r"\1ff\2"),
    # efficient / efficiency / efficiently
    (re.compile(r"\b([Ee](?:ff)?)\s+([Ii]cien(?:cy|t|tly|cies))\b", re.IGNORECASE), r"\1ff\2"),
    # effort / efforts
    (re.compile(r"\b([Ee](?:ff)?)\s+([Oo]rt(?:s)?)\b", re.IGNORECASE), r"\1ff\2"),
    # difference / different
    (re.compile(r"\b([Dd]i(?:ff)?)\s+([Ee]ren(?:ce|t|tly|ces))\b", re.IGNORECASE), r"\1ff\2"),
    # sufficient / sufficiently
    (re.compile(r"\b([Ss]u(?:ff)?)\s+([Ii]cien(?:cy|t|tly))\b", re.IGNORECASE), r"\1ff\2"),
    # office / officer / official
    (re.compile(r"\b([Oo](?:ff)?)\s+([Ii]c(?:e|er|ial|ially|es))\b", re.IGNORECASE), r"\1ff\2"),
    # traffic
    (re.compile(r"\b([Tt]ra(?:ff)?)\s+([Ii]c)\b", re.IGNORECASE), r"\1ff\2"),
    # defined / definition (dropped 'fi')
    (re.compile(r"\b([Dd]e(?:f)?)\s+([Ii]n(?:ed|ition|ing|es)?)\b", re.IGNORECASE), r"\1f\2"),
    # configure / configuration (dropped 'fi')
    (re.compile(r"\b([Cc]on(?:f)?)\s+([Ii]gur(?:e|ed|ation|ations|ing)?)\b", re.IGNORECASE), r"\1f\2"),
    # workflow / workflows (dropped 'fl')
    (re.compile(r"\b([Ww]ork(?:f)?)\s+([Ll]ow(?:s)?)\b", re.IGNORECASE), r"\1f\2"),
]

# Replacement character glitches (\uFFFD)
REPLACEMENT_CHAR_GLITCHES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b([Ee])\uFFFD+ect(ive|ively|iveness|s)?\b", re.IGNORECASE), r"\1ffect\2"),
    (re.compile(r"\b([Ee])\uFFFD+icien(cy|t|tly|cies)\b", re.IGNORECASE), r"\1fficien\2"),
]


# ============================================================================
# 2. Primary ATS Functions
# ============================================================================

def sanitize_ligatures(text: Optional[str]) -> str:
    """
    Sanitizes font ligatures, PDF glyph corruptions, non-breaking spaces,
    and invisible Unicode artifacts from raw text.

    Pipeline Stages:
    1. Input validation & invisible character stripping (\\u200B, \\u00AD, etc.)
    2. Unicode presentation forms mapping (\\uFB00..\\uFB06, etc.)
    3. Forensic Ư / ư glyph restoration (eƯiciency -> efficiency)
    4. Space-split ligature repair (e\\s+ective -> effective)
    5. Replacement character repair (\\uFFFD)
    6. Non-breaking and typographic space normalization
    7. Typographic quotes and dashes standardization

    Args:
        text: Input string potentially containing broken ligatures or corrupted glyphs.

    Returns:
        Cleaned UTF-8 string with standard ASCII letter pairs and normalized spaces.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return ""

    # Stage 1: Strip invisible characters and soft hyphens
    result = INVISIBLE_CHARS_REGEX.sub("", text)

    # Stage 2: Direct Unicode presentation ligatures map
    # Strip whitespace/NBSP adjacent to presentation ligatures within words (e.g. "o\uFB00\u00A0ice" -> "o\uFB00ice")
    result = re.sub(r"(?<=[a-zA-Z])[\s\u00A0]*([\uFB00-\uFB06])[\s\u00A0]*(?=[a-zA-Z])", r"\1", result)
    result = re.sub(r"\b([\uFB00-\uFB06])[\s\u00A0]+(?=[a-zA-Z])", r"\1", result)
    result = re.sub(r"(?<=[a-zA-Z])[\s\u00A0]+([\uFB00-\uFB06])\b", r"\1", result)

    for glyph, ascii_replacement in UNICODE_LIGATURE_MAP.items():
        if glyph in result:
            result = result.replace(glyph, ascii_replacement)

    # Stage 3: Forensic PDF extraction horn glyph corruptions (Ư / ư -> ff)
    if "Ư" in result or "ư" in result:
        # Preserve specific title casing before generic pattern matches
        result = re.sub(r"\bEƯICIENCY\b", "EFFICIENCY", result)
        result = re.sub(r"\bEƯECTIVE\b", "EFFECTIVE", result)
        result = re.sub(r"\bEƯiciency\b", "Efficiency", result)
        result = re.sub(r"\bEƯective\b", "Effective", result)
        result = re.sub(r"\beƯiciency\b", "efficiency", result)
        result = re.sub(r"\beƯective\b", "effective", result)
        result = re.sub(r"\bEƯort\b", "Effort", result)
        result = re.sub(r"\beƯort\b", "effort", result)
        result = re.sub(r"(?<=[a-z]\s)EƯicien(cy|t|tly|cies)\b", r"efficien\1", result)
        for pattern, replacement in LIGATURE_HORN_GLITCHES:
            result = pattern.sub(replacement, result)

    # Stage 4: Broken whitespace repairs (e.g. "e  ective" -> "effective")
    # Handle all-uppercase cases first
    if "E  ICIENCY" in result or "E   ICIENCY" in result or re.search(r"\bE\s+ICIENCY\b", result):
        result = re.sub(r"\bE\s+ICIENCY\b", "EFFICIENCY", result)
    if "E  ECTIVE" in result or "E   ECTIVE" in result or re.search(r"\bE\s+ECTIVE\b", result):
        result = re.sub(r"\bE\s+ECTIVE\b", "EFFECTIVE", result)

    for pattern, replacement in BROKEN_SPACE_GLITCHES:
        def _case_preserving_sub(m: re.Match) -> str:
            prefix = m.group(1)
            suffix = m.group(2)
            clean_prefix = re.sub(r"[fF]+$", "", prefix)
            is_ff = "ff" in str(replacement)
            target_upper = "FF" if is_ff else "F"
            target_lower = "ff" if is_ff else "f"
            # If both prefix and suffix are uppercase, inject FF in uppercase
            if prefix.isupper() and suffix.isupper():
                return f"{clean_prefix}{target_upper}{suffix}"
            elif prefix.isupper() or clean_prefix.isupper():
                return f"{clean_prefix}{target_lower}{suffix}"
            return f"{clean_prefix}{target_lower}{suffix}"

        result = pattern.sub(_case_preserving_sub, result)

    # Stage 5: Replacement character glitches (\uFFFD)
    if "\uFFFD" in result:
        for pattern, replacement in REPLACEMENT_CHAR_GLITCHES:
            result = pattern.sub(replacement, result)
        # Purge any remaining orphan replacement characters
        result = result.replace("\uFFFD", "")

    # Stage 6: Non-breaking and typographic spaces normalization
    for space_char, ascii_space in SPACE_NORMALIZATION_MAP.items():
        if space_char in result:
            result = result.replace(space_char, ascii_space)

    # Stage 7: Standardize bullet points, typographic quotes, dashes, ellipses
    result = BULLET_REGEX.sub("- ", result)
    for typo_char, clean_char in TYPOGRAPHIC_MAP.items():
        if typo_char in result:
            result = result.replace(typo_char, clean_char)

    return result


def safe_filename(
    first: str,
    last: str,
    role: str,
    doc_type: str,
    ext: str = "pdf"
) -> str:
    """
    Generates a strict, ATS-friendly, underscore-delimited filename:
    `{First}_{Last}_{Role}_{DocType}.{ext}`

    Guarantees:
    - Zero spaces, hyphens, brackets, parentheses, colons, or shell-unsafe chars.
    - Consecutive underscores collapsed to a single underscore.
    - Compound first names (e.g. "John Victor") converted cleanly ("John_Victor").
    - Extension normalized (leading dot stripped, lowercased, default 'pdf').
    - Path traversal sequences stripped.
    - Windows MAX_PATH length constraint enforced (total filename <= 200 chars).

    Args:
        first: Candidate first or compound given name (e.g. "John", "John Victor").
        last: Candidate surname / family name (e.g. "Aniekwe").
        role: Target role title (e.g. "Cloud Solutions Architect", "Dev(Sec)Ops").
        doc_type: Document type descriptor (e.g. "CV", "Cover Letter", "Resume").
        ext: Target file extension (e.g. "pdf", ".PDF", "docx", "md"). Defaults to "pdf".

    Returns:
        A strictly sanitized filename string.
    """
    def _clean_token(token: Optional[str], fallback: str) -> str:
        if token is None:
            return fallback
        # Convert to string and replace any non-alphanumeric sequence with underscore
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(token)).strip("_")
        # Collapse multiple underscores
        cleaned = re.sub(r"_+", "_", cleaned)
        return cleaned if cleaned else fallback

    clean_first = _clean_token(first, "Candidate")
    clean_last = _clean_token(last, "Profile")
    clean_role = _clean_token(role, "General")
    clean_doc = _clean_token(doc_type, "Document")

    # Sanitize and normalize extension
    if ext is None:
        clean_ext = "pdf"
    else:
        ext_str = str(ext).lstrip(".").lower()
        clean_ext = re.sub(r"[^a-z0-9]", "", ext_str)
        if not clean_ext:
            clean_ext = "pdf"
        else:
            clean_ext = clean_ext[:10]

    # Assemble base filename
    base_name = f"{clean_first}_{clean_last}_{clean_role}_{clean_doc}"
    base_name = re.sub(r"_+", "_", base_name).strip("_")

    # Enforce maximum filename length for Windows compatibility (<= 200 chars)
    max_base_len = 200 - len(clean_ext) - 1
    if len(base_name) > max_base_len:
        # Calculate available room for the role
        fixed_len = len(clean_first) + len(clean_last) + len(clean_doc) + 3
        avail_role_len = max_base_len - fixed_len
        if avail_role_len > 10:
            truncated_role = clean_role[:avail_role_len].rstrip("_")
            base_name = f"{clean_first}_{clean_last}_{truncated_role}_{clean_doc}"
        else:
            base_name = base_name[:max_base_len].rstrip("_")

    result = f"{base_name}.{clean_ext}"
    if len(result) > 200:
        result = result[:200]
    return result


# ============================================================================
# 3. Auxiliary ATS Normalization Utilities
# ============================================================================

def normalize_whitespace(text: Optional[str]) -> str:
    """
    Normalizes runs of horizontal whitespace (spaces, tabs, non-breaking spaces)
    to a single standard space on each line while preserving newline structure.
    """
    if not text:
        return ""
    # First sanitize non-breaking spaces
    cleaned = sanitize_ligatures(text)
    # Replace horizontal tabs and multiple spaces on the same line with a single space
    lines = cleaned.splitlines()
    normalized_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
    return "\n".join(normalized_lines)


def clean_ats_text(text: Optional[str]) -> str:
    """
    Comprehensive ATS text hygiene pre-processor.
    Performs ligature repair, control character removal, typographic
    normalization, and line ending harmonization (\\r\\n -> \\n).
    """
    if not text:
        return ""
    # 1. Ligature and typographic clean-up
    cleaned = sanitize_ligatures(text)
    # 2. Normalize Windows/Mac line endings to standard Unix \n
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # 3. Strip non-printable ASCII control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    # 4. Collapse runs of horizontal spaces
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in cleaned.split("\n")]
    # 5. Collapse excessive blank lines (more than 2 consecutive newlines to 2)
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def strip_markdown(text: Optional[str]) -> str:
    """
    Removes common Markdown formatting syntax (headers, bold, italic,
    inline links, code blocks) to produce clean plain text for ATS engines.
    """
    if not text:
        return ""
    s = text
    # Remove code blocks
    s = re.sub(r"```[\s\S]*?```", "", s)
    # Remove inline code
    s = re.sub(r"`([^`]+)`", r"\1", s)
    # Remove images
    s = re.sub(r"!\[.*?\]\(.*?\)", "", s)
    # Convert links [anchor](url) -> anchor
    s = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", s)
    # Remove headers (# Header)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.MULTILINE)
    # Remove bold/italic (**text**, *text*, __text__, _text_)
    s = re.sub(r"(\*\*|__)(.*?)\1", r"\2", s)
    s = re.sub(r"(\*|_)(.*?)\1", r"\2", s)
    # Remove blockquotes
    s = re.sub(r"^\s*>\s+", "", s, flags=re.MULTILINE)
    # Remove horizontal rules
    s = re.sub(r"^[-*_]{3,}\s*$", "", s, flags=re.MULTILINE)
    return clean_ats_text(s)


def extract_clean_words(text: Optional[str]) -> List[str]:
    """
    Tokenizes text into a list of normalized, lowercase alphanumeric words.
    Useful for keyword matching, Jaccard similarity, and density scoring.
    """
    if not text:
        return []
    cleaned = clean_ats_text(text)
    words = re.findall(r"\b[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)*\b", cleaned.lower())
    return words
