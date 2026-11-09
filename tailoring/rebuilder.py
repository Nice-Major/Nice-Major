"""
Opportunity Document Rebuilder & Markdown-to-PDF Live Compiler.
Module: tailoring.rebuilder

Provides frictionless two-way editing between Markdown (.md), HTML (.html),
and ATS-compliant PDFs (.pdf):
1. Rebuilds PDFs directly from edited Markdown (.md) or HTML (.html) files.
2. Supports automated find-and-replace patching across opportunity files.
3. Provides live watch mode (--watch) that automatically recompiles PDFs on save.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Standard ATS Print CSS template
CV_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{doc_title}</title>
  <style>
    * {{
      box-sizing: border-box;
      font-variant-ligatures: none;
      -webkit-font-variant-ligatures: none;
    }}
    body {{
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1E293B;
      background: #FFFFFF;
      line-height: 1.48;
      font-size: 13.2px;
    }}
    .cv-container {{
      max-width: 820px;
      margin: 0 auto;
      background: #FFFFFF;
      padding: 32px 42px;
    }}
    header {{
      border-bottom: 2px solid #0F52BA;
      padding-bottom: 12px;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0 0 4px 0;
      font-size: 25px;
      font-weight: 800;
      color: #0F172A;
      letter-spacing: -0.3px;
    }}
    .role-headline {{
      font-size: 14.5px;
      font-weight: 700;
      color: #0F52BA;
      margin-bottom: 6px;
    }}
    .contact-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12px;
      color: #475569;
    }}
    .contact-strip a {{
      color: #0F52BA;
      text-decoration: none;
      font-weight: 500;
    }}
    .mobility-note {{
      margin-top: 8px;
      font-size: 11.5px;
      color: #1D4ED8;
      background: #EFF6FF;
      padding: 6px 10px;
      border-left: 3px solid #0F52BA;
    }}
    section {{
      margin-bottom: 15px;
    }}
    h2 {{
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #0F172A;
      border-bottom: 1.5px solid #E2E8F0;
      padding-bottom: 4px;
      margin: 14px 0 8px 0;
    }}
    p {{
      margin: 0 0 6px 0;
      text-align: justify;
    }}
    ul {{
      margin: 3px 0 6px 0;
      padding-left: 18px;
    }}
    li {{
      margin-bottom: 3.5px;
    }}
    .exp-item {{
      margin-bottom: 12px;
      page-break-inside: avoid;
    }}
    .exp-header {{
      font-size: 13px;
      margin-bottom: 3px;
    }}
    .exp-role {{
      font-weight: 700;
      color: #0F172A;
    }}
    .exp-company {{
      font-weight: 700;
      color: #0F52BA;
    }}
    .exp-dates {{
      font-size: 12px;
      color: #64748B;
      float: right;
    }}
    @media print {{
      @page {{
        size: A4;
        margin: 14mm 14mm 14mm 14mm;
      }}
      body {{
        background: #FFFFFF;
        font-size: 12.8px;
      }}
      .cv-container {{
        padding: 0;
        max-width: 100%;
        border: none;
        box-shadow: none;
      }}
      .exp-item {{
        page-break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <div class="cv-container">
    {body_content}
  </div>
</body>
</html>
"""

COVER_LETTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{doc_title}</title>
  <style>
    * {{
      box-sizing: border-box;
      font-variant-ligatures: none;
      -webkit-font-variant-ligatures: none;
    }}
    body {{
      margin: 0;
      padding: 0;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1E293B;
      background: #FFFFFF;
      line-height: 1.55;
      font-size: 13.5px;
    }}
    .letter-container {{
      max-width: 820px;
      margin: 0 auto;
      background: #FFFFFF;
      padding: 36px 44px;
    }}
    header {{
      border-bottom: 2px solid #0F52BA;
      padding-bottom: 12px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 4px 0;
      font-size: 24px;
      font-weight: 800;
      color: #0F172A;
    }}
    .role-headline {{
      font-size: 14px;
      font-weight: 700;
      color: #0F52BA;
      margin-bottom: 6px;
    }}
    .contact-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12px;
      color: #475569;
    }}
    .contact-strip a {{
      color: #0F52BA;
      text-decoration: none;
      font-weight: 500;
    }}
    .meta-block {{
      margin: 14px 0 16px 0;
      font-size: 13px;
      color: #334155;
      line-height: 1.5;
    }}
    .salutation {{
      font-weight: 700;
      margin-bottom: 12px;
      color: #0F172A;
    }}
    p {{
      margin: 0 0 11px 0;
      text-align: justify;
    }}
    .sign-off {{
      margin-top: 18px;
      line-height: 1.4;
    }}
    .sign-off .name {{
      font-weight: 700;
      color: #0F172A;
    }}
    @media print {{
      @page {{
        size: A4;
        margin: 16mm 16mm 16mm 16mm;
      }}
      body {{
        background: #FFFFFF;
        font-size: 13px;
      }}
      .letter-container {{
        padding: 0;
        max-width: 100%;
        border: none;
      }}
    }}
  </style>
</head>
<body>
  <div class="letter-container">
    {body_content}
  </div>
</body>
</html>
"""


def _inline_markdown_to_html(text: str) -> str:
    """Converts bold, italic, and links in markdown text to HTML."""
    # Convert links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Convert bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Convert italic: *text* or _text_
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def markdown_to_cv_html(md_text: str, doc_title: str = "Curriculum Vitae") -> str:
    """
    Parses a customized Markdown CV into ATS-compliant semantic HTML.
    Supports user edits to text, bullet points, headers, and contact lines.
    """
    lines = md_text.splitlines()
    html_parts: List[str] = []

    in_header = False
    in_list = False
    in_exp_item = False
    name = "John Victor Aniekwe"
    headline = "Senior Cloud & Platform Engineer"
    headline_set = False
    contacts: List[str] = []
    mobility_banner = ""

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Empty line
        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            i += 1
            continue

        # Header detection: # Name
        if line.startswith("# ") and i < 5:
            name = line[2:].strip()
            in_header = True
            i += 1
            continue

        # Headline detection: **Headline**
        if line.startswith("**") and line.endswith("**") and in_header and not headline_set:
            headline = line[2:-2].strip()
            headline_set = True
            i += 1
            continue

        # Contact strip line (e.g. Location | Phone | Email | LinkedIn...)
        if in_header and ("|" in line or "@" in line):
            raw_contacts = [c.strip() for c in line.split("|") if c.strip()]
            contacts = [_inline_markdown_to_html(c) for c in raw_contacts]
            i += 1
            continue

        # Global engagement track / mobility block
        if in_header and (line.startswith("> ") or "Global Engagement" in line):
            clean_mob = line.lstrip("> ").strip()
            mobility_banner = f'<div class="mobility-note">{_inline_markdown_to_html(clean_mob)}</div>'
            i += 1
            continue

        # End of header divider (---)
        if line == "---" and in_header:
            in_header = False
            # Render complete header HTML
            contact_spans = "".join([f"<span>{c}</span>" for c in contacts])
            header_html = f"""<header>
      <h1>{html.escape(name)}</h1>
      <div class="role-headline">{html.escape(headline)}</div>
      <div class="contact-strip">{contact_spans}</div>
      {mobility_banner}
    </header>"""
            html_parts.append(header_html)
            i += 1
            continue

        # Section Heading: ## SECTION TITLE
        if line.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_exp_item:
                html_parts.append("</article>")
                in_exp_item = False
            sec_title = line[3:].strip()
            html_parts.append(f"<section>\n      <h2>{html.escape(sec_title)}</h2>")
            i += 1
            continue

        # Experience Subheading: ### Role — Company
        if line.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_exp_item:
                html_parts.append("</article>")
                in_exp_item = False

            raw_title = line[4:].strip()
            role_part, comp_part = raw_title, ""
            if "—" in raw_title:
                role_part, comp_part = [p.strip() for p in raw_title.split("—", 1)]
            elif " - " in raw_title:
                role_part, comp_part = [p.strip() for p in raw_title.split(" - ", 1)]

            # Look ahead for dates line (e.g. Remote, UK | Dec 2025 - Present)
            date_line = ""
            if i + 1 < len(lines) and not lines[i + 1].startswith("-") and not lines[i + 1].startswith("#"):
                date_line = lines[i + 1].strip()
                i += 1

            html_parts.append(f"""<article class="exp-item">
        <div class="exp-header">
          <span class="exp-role">{html.escape(role_part)}</span>{f' — <span class="exp-company">{html.escape(comp_part)}</span>' if comp_part else ''}
          {f'<span class="exp-dates">{html.escape(date_line)}</span>' if date_line else ''}
        </div>""")
            in_exp_item = True
            i += 1
            continue

        # Bullet list item: - Item
        if line.startswith("- ") or line.startswith("* "):
            bullet_text = line[2:].strip()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"  <li>{_inline_markdown_to_html(bullet_text)}</li>")
            i += 1
            continue

        # Paragraph
        if in_list:
            html_parts.append("</ul>")
            in_list = False

        html_parts.append(f"<p>{_inline_markdown_to_html(line)}</p>")
        i += 1

    if in_list:
        html_parts.append("</ul>")
    if in_exp_item:
        html_parts.append("</article>")

    body_html = "\n    ".join(html_parts)
    return CV_HTML_TEMPLATE.format(doc_title=html.escape(doc_title), body_content=body_html)


def markdown_to_cover_letter_html(md_text: str, doc_title: str = "Cover Letter") -> str:
    """Parses a customized Cover Letter Markdown file into ATS-compliant HTML."""
    lines = md_text.splitlines()
    html_parts: List[str] = []

    name = "John Victor Aniekwe"
    headline = "Senior Cloud & Platform Engineer"
    contacts: List[str] = []
    in_header = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.startswith("# ") and i < 5:
            name = line[2:].strip()
            in_header = True
            i += 1
            continue

        if line.startswith("**") and line.endswith("**") and in_header:
            headline = line[2:-2].strip()
            i += 1
            continue

        if in_header and ("|" in line or "@" in line):
            raw_contacts = [c.strip() for c in line.split("|") if c.strip()]
            contacts = [_inline_markdown_to_html(c) for c in raw_contacts]
            i += 1
            continue

        if line == "---" and in_header:
            in_header = False
            contact_spans = "".join([f"<span>{c}</span>" for c in contacts])
            header_html = f"""<header>
      <h1>{html.escape(name)}</h1>
      <div class="role-headline">{html.escape(headline)}</div>
      <div class="contact-strip">{contact_spans}</div>
    </header>"""
            html_parts.append(header_html)
            i += 1
            continue

        # Salutation (e.g. Dear Hiring Team,)
        if line.startswith("Dear ") or line.startswith("To the "):
            html_parts.append(f'<div class="salutation">{html.escape(line)}</div>')
            i += 1
            continue

        # Subheading / STAR section
        if line.startswith("### "):
            sec = line[4:].strip()
            html_parts.append(f'<p><strong>{html.escape(sec)}:</strong></p>')
            i += 1
            continue

        # Sign-off (Sincerely, / Best regards,)
        if line.lower() in ("sincerely,", "best regards,", "warm regards,"):
            val_name = lines[i + 1].strip() if i + 1 < len(lines) else name
            html_parts.append(f"""<div class="sign-off">
      <p>{html.escape(line)}</p>
      <p class="name">{html.escape(val_name)}</p>
    </div>""")
            i += 2
            continue

        # Standard paragraph
        html_parts.append(f"<p>{_inline_markdown_to_html(line)}</p>")
        i += 1

    body_html = "\n    ".join(html_parts)
    return COVER_LETTER_HTML_TEMPLATE.format(doc_title=html.escape(doc_title), body_content=body_html)


def get_pdf_page_count(pdf_path: Path) -> int:
    """Returns the total number of pages in a generated PDF."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception:
        # Fallback inspection of /Count in PDF binary
        try:
            raw = pdf_path.read_bytes()
            m = re.findall(rb"/Count\s+(\d+)", raw)
            if m:
                return int(m[-1])
        except Exception:
            pass
    return 1


def rebuild_opportunity_package(
    opportunity_dir: Union[str, Path],
    from_format: str = "md",
) -> Dict[str, Any]:
    """
    Rebuilds all application documents in an opportunity directory.
    Converts edited Markdown (.md) or HTML (.html) into verified ATS PDFs.
    """
    from tailoring.pdf_renderer import render_html_to_pdf_bytes

    target_dir = Path(opportunity_dir).resolve()
    if not target_dir.is_dir():
        # Search inside default output/applications/
        default_base = Path("output/applications").resolve()
        candidates = list(default_base.glob(f"*{target_dir.name}*"))
        if candidates:
            target_dir = candidates[0]
        else:
            raise FileNotFoundError(f"Opportunity directory not found: {opportunity_dir}")

    results: List[Dict[str, Any]] = []

    # 1. Discover CV files
    cv_md_files = list(target_dir.glob("*_CV.md"))
    cv_html_files = list(target_dir.glob("*_CV.html"))

    if cv_md_files and from_format in ("md", "all"):
        for md_file in cv_md_files:
            md_content = md_file.read_text(encoding="utf-8")
            html_content = markdown_to_cv_html(md_content, doc_title=md_file.stem)
            html_path = md_file.with_suffix(".html")
            pdf_path = md_file.with_suffix(".pdf")
            txt_path = md_file.with_suffix(".txt")

            html_path.write_text(html_content, encoding="utf-8")
            pdf_bytes = render_html_to_pdf_bytes(html_content, fallback_text=md_content, output_pdf_path=pdf_path)
            # Plaintext companion
            clean_txt = re.sub(r"<[^>]+>", " ", html_content)
            txt_path.write_text(clean_txt, encoding="utf-8")

            pages = get_pdf_page_count(pdf_path)
            results.append({
                "type": "CV",
                "source": str(md_file.name),
                "pdf": str(pdf_path.name),
                "pages": pages,
                "status": "success",
            })
    elif cv_html_files and from_format == "html":
        for html_file in cv_html_files:
            html_content = html_file.read_text(encoding="utf-8")
            pdf_path = html_file.with_suffix(".pdf")
            pdf_bytes = render_html_to_pdf_bytes(html_content, output_pdf_path=pdf_path)
            pages = get_pdf_page_count(pdf_path)
            results.append({
                "type": "CV",
                "source": str(html_file.name),
                "pdf": str(pdf_path.name),
                "pages": pages,
                "status": "success",
            })

    # 2. Discover Cover Letter files
    letter_md_files = list(target_dir.glob("*_Cover_Letter.md"))
    letter_html_files = list(target_dir.glob("*_Cover_Letter.html"))

    if letter_md_files and from_format in ("md", "all"):
        for md_file in letter_md_files:
            md_content = md_file.read_text(encoding="utf-8")
            html_content = markdown_to_cover_letter_html(md_content, doc_title=md_file.stem)
            html_path = md_file.with_suffix(".html")
            pdf_path = md_file.with_suffix(".pdf")
            txt_path = md_file.with_suffix(".txt")

            html_path.write_text(html_content, encoding="utf-8")
            pdf_bytes = render_html_to_pdf_bytes(html_content, fallback_text=md_content, output_pdf_path=pdf_path)
            clean_txt = re.sub(r"<[^>]+>", " ", html_content)
            txt_path.write_text(clean_txt, encoding="utf-8")

            pages = get_pdf_page_count(pdf_path)
            results.append({
                "type": "Cover_Letter",
                "source": str(md_file.name),
                "pdf": str(pdf_path.name),
                "pages": pages,
                "status": "success",
            })

    return {
        "opportunity_directory": str(target_dir),
        "folder_name": target_dir.name,
        "rebuilt_documents": results,
    }


def patch_opportunity_text(
    opportunity_dir: Union[str, Path],
    find_str: str,
    replace_str: str,
) -> Dict[str, Any]:
    """
    Performs a safe, comprehensive find-and-replace across all text/markdown/html files
    in an opportunity folder and immediately recompiles the corresponding PDFs.
    """
    target_dir = Path(opportunity_dir).resolve()
    if not target_dir.is_dir():
        default_base = Path("output/applications").resolve()
        candidates = list(default_base.glob(f"*{target_dir.name}*"))
        if candidates:
            target_dir = candidates[0]
        else:
            raise FileNotFoundError(f"Opportunity directory not found: {opportunity_dir}")

    modified_files: List[str] = []
    # Files to patch
    for ext in ("*.md", "*.html", "*.txt", "*.json"):
        for f in target_dir.glob(ext):
            try:
                content = f.read_text(encoding="utf-8")
                if find_str in content:
                    updated = content.replace(find_str, replace_str)
                    f.write_text(updated, encoding="utf-8")
                    modified_files.append(f.name)
            except Exception as e:
                logger.warning(f"Error patching {f.name}: {e}")

    # Rebuild PDFs to reflect changes
    rebuild_res = rebuild_opportunity_package(target_dir, from_format="md")

    return {
        "status": "success",
        "folder": str(target_dir),
        "find_string": find_str,
        "replacement": replace_str,
        "modified_files": modified_files,
        "rebuilt": rebuild_res["rebuilt_documents"],
    }
