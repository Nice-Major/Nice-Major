"""
Opportunity-Specific File Organization & Deduplication Storage Engine.
Module: tailoring.opportunity_storage

Organizes application materials (Job Description, CV, Cover Letter, Evaluation Summary)
into dedicated subdirectories per opportunity:
    output/applications/<Company>_<Role_Title>/
        ├── job_description.txt
        ├── John_Aniekwe_<Company>_<Role>_CV.pdf
        ├── John_Aniekwe_<Company>_<Role>_CV.html
        ├── John_Aniekwe_<Company>_<Role>_CV.md
        ├── John_Aniekwe_<Company>_<Role>_Cover_Letter.pdf
        ├── John_Aniekwe_<Company>_<Role>_Cover_Letter.html
        ├── John_Aniekwe_<Company>_<Role>_Cover_Letter.md
        └── evaluation_summary.json

Deduplication:
When an ingested opportunity matches an existing application (exact or >=80% title/text similarity),
it links to the existing application package, notes the match in alias_opportunities.json,
and prevents duplicate generation.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def clean_slug_part(val: str) -> str:
    """Sanitizes strings for safe, readable folder directory names."""
    if not val:
        return "Opportunity"
    cleaned = re.sub(r"[^\w\s-]", "", val)
    cleaned = re.sub(r"[\s_]+", "_", cleaned.strip())
    return cleaned[:60] or "Opportunity"


def get_opportunity_dir_name(company: str, role_title: str) -> str:
    """Builds a canonical, collision-free folder name for an opportunity."""
    c = clean_slug_part(company or "General")
    r = clean_slug_part(role_title or "Position")
    return f"{c}_{r}"


def _tokenize(text: str) -> Set[str]:
    """Tokenizes alphanumeric words for fast set similarity."""
    if not text:
        return set()
    return set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower()))


def compute_text_similarity(text1: str, text2: str) -> float:
    """Calculates Jaccard word token similarity (0.0 to 1.0) between two texts."""
    t1 = _tokenize(text1)
    t2 = _tokenize(text2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    return float(intersection) / float(union) if union > 0 else 0.0


def find_matching_opportunity(
    base_dir: Path,
    company: str,
    role_title: str,
    jd_text: str = "",
    title_threshold: float = 0.80,
    jd_threshold: float = 0.75,
) -> Optional[Dict[str, Any]]:
    """
    Scans base_dir for an existing opportunity folder that matches the incoming opportunity.

    Returns dict with matched folder info if found, or None.
    """
    if not base_dir.is_dir():
        return None

    target_c = (company or "").lower().strip()
    target_r = (role_title or "").lower().strip()
    target_dir_name = get_opportunity_dir_name(company, role_title).lower()

    for child in base_dir.iterdir():
        if not child.is_dir():
            continue

        folder_name = child.name
        folder_lower = folder_name.lower()

        # 1. Exact folder slug match
        if folder_lower == target_dir_name:
            return {
                "folder_path": child,
                "folder_name": folder_name,
                "match_reason": "exact_slug",
                "similarity": 1.0,
            }

        # 2. Inspect metadata if evaluation_summary.json exists
        summary_path = child / "evaluation_summary.json"
        existing_c = ""
        existing_r = ""
        existing_jd = ""

        if summary_path.is_file():
            try:
                meta = json.loads(summary_path.read_text(encoding="utf-8"))
                existing_c = meta.get("company_name", "").lower().strip()
                existing_r = meta.get("role_title", "").lower().strip()
            except Exception:
                pass

        jd_file = child / "job_description.txt"
        if jd_file.is_file():
            try:
                existing_jd = jd_file.read_text(encoding="utf-8")
            except Exception:
                pass

        # Check company match + title similarity
        if target_c and existing_c:
            companies_match = (target_c in existing_c) or (existing_c in target_c)
        else:
            companies_match = True

        if companies_match and target_r and existing_r:
            sim = compute_text_similarity(target_r, existing_r)
            if sim >= title_threshold:
                return {
                    "folder_path": child,
                    "folder_name": folder_name,
                    "match_reason": f"title_similarity_{sim:.2f}",
                    "similarity": sim,
                }

        # Check JD text similarity if text is provided
        if jd_text and existing_jd:
            jd_sim = compute_text_similarity(jd_text, existing_jd)
            if jd_sim >= jd_threshold:
                return {
                    "folder_path": child,
                    "folder_name": folder_name,
                    "match_reason": f"jd_text_similarity_{jd_sim:.2f}",
                    "similarity": jd_sim,
                }

    return None


def store_opportunity_package(
    base_dir: Path,
    company: str,
    role_title: str,
    jd_text: str,
    cv_pdf_bytes: bytes,
    letter_pdf_bytes: bytes,
    cv_md_text: str,
    letter_md_text: str,
    cv_html_text: str = "",
    letter_html_text: str = "",
    cv_pdf_filename: str = "",
    letter_pdf_filename: str = "",
    eval_summary: Optional[Dict[str, Any]] = None,
    source_url: str = "",
    location: str = "",
    check_deduplication: bool = True,
) -> Dict[str, Any]:
    """
    Saves or links all application materials inside a dedicated opportunity directory.

    If an opportunity closely matches an existing one and check_deduplication=True:
    Reuses the existing package, records an alias note, and returns the existing paths.
    """
    base_dir.mkdir(parents=True, exist_ok=True)

    if check_deduplication:
        match = find_matching_opportunity(
            base_dir=base_dir,
            company=company,
            role_title=role_title,
            jd_text=jd_text,
        )
        if match:
            matched_folder: Path = match["folder_path"]
            logger.info(f"Opportunity matches existing package '{matched_folder.name}'. Reusing files.")

            # Record alias mapping inside the matched folder
            aliases_file = matched_folder / "alias_opportunities.json"
            aliases: List[Dict[str, Any]] = []
            if aliases_file.is_file():
                try:
                    aliases = json.loads(aliases_file.read_text(encoding="utf-8"))
                except Exception:
                    aliases = []

            aliases.append({
                "incoming_role": role_title,
                "incoming_company": company,
                "source_url": source_url,
                "timestamp": datetime.now().isoformat(),
                "similarity": match.get("similarity", 1.0),
                "match_reason": match.get("match_reason", "matched"),
            })
            aliases_file.write_text(json.dumps(aliases, indent=2), encoding="utf-8")

            # Discover existing CV and Letter PDF files
            pdf_cvs = list(matched_folder.glob("*_CV.pdf"))
            pdf_letters = list(matched_folder.glob("*_Cover_Letter.pdf"))
            cv_path = pdf_cvs[0] if pdf_cvs else None
            letter_path = pdf_letters[0] if pdf_letters else None

            return {
                "folder_path": matched_folder,
                "folder_name": matched_folder.name,
                "reused": True,
                "match_reason": match.get("match_reason", "matched"),
                "cv_pdf_path": cv_path,
                "letter_pdf_path": letter_path,
                "all_files": list(matched_folder.glob("*.*")),
            }

    # Brand new opportunity directory
    dir_name = get_opportunity_dir_name(company, role_title)
    opp_dir = base_dir / dir_name
    opp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Job Description File
    jd_file = opp_dir / "job_description.txt"
    jd_header = [
        "=" * 78,
        f"JOB REQUISITION: {role_title}",
        f"ORGANIZATION:    {company}",
        f"LOCATION:        {location or 'Not Specified'}",
        f"SOURCE URL:      {source_url or 'N/A'}",
        f"INGESTION DATE:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 78,
        "",
        jd_text.strip(),
        "",
    ]
    jd_file.write_text("\n".join(jd_header), encoding="utf-8")

    # 2. PDF Documents
    c_pdf_name = cv_pdf_filename or f"John_Aniekwe_{clean_slug_part(company)}_{clean_slug_part(role_title)}_CV.pdf"
    l_pdf_name = letter_pdf_filename or f"John_Aniekwe_{clean_slug_part(company)}_{clean_slug_part(role_title)}_Cover_Letter.pdf"

    cv_pdf_path = opp_dir / c_pdf_name
    letter_pdf_path = opp_dir / l_pdf_name

    cv_pdf_path.write_bytes(cv_pdf_bytes)
    letter_pdf_path.write_bytes(letter_pdf_bytes)

    # 3. Markdown Documents
    cv_md_path = opp_dir / c_pdf_name.replace(".pdf", ".md")
    letter_md_path = opp_dir / l_pdf_name.replace(".pdf", ".md")
    cv_md_path.write_text(cv_md_text, encoding="utf-8")
    letter_md_path.write_text(letter_md_text, encoding="utf-8")

    # 4. HTML Documents (if provided)
    if cv_html_text:
        (opp_dir / c_pdf_name.replace(".pdf", ".html")).write_text(cv_html_text, encoding="utf-8")
    if letter_html_text:
        (opp_dir / l_pdf_name.replace(".pdf", ".html")).write_text(letter_html_text, encoding="utf-8")

    # 5. Evaluation Summary
    summary_path = opp_dir / "evaluation_summary.json"
    summary_data = eval_summary or {}
    summary_data.update({
        "role_title": role_title,
        "company_name": company,
        "location": location,
        "source_url": source_url,
        "created_at": datetime.now().isoformat(),
        "cv_pdf_path": str(cv_pdf_path.resolve()),
        "letter_pdf_path": str(letter_pdf_path.resolve()),
    })
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")

    return {
        "folder_path": opp_dir,
        "folder_name": dir_name,
        "reused": False,
        "cv_pdf_path": cv_pdf_path,
        "letter_pdf_path": letter_pdf_path,
        "cv_md_path": cv_md_path,
        "letter_md_path": letter_md_path,
        "jd_path": jd_file,
        "summary_path": summary_path,
        "all_files": list(opp_dir.glob("*.*")),
    }
