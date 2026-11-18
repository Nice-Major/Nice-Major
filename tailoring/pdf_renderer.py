"""
Native ATS-Compliant PDF Renderer (Headless Chromium/Edge + Pure-Python PDF 1.4 Fallback).
Module: tailoring.pdf_renderer

Renders tailored HTML or plain-text CVs, Cover Letters, and B2B Proposals into
true binary PDF (.pdf) documents with selectable text, zero external headers/footers,
and strict ATS single-column linear layout.
"""

from __future__ import annotations

import html
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Union


def _find_browser_binary() -> Optional[str]:
    """Locates an installed Chromium, Google Chrome, or Microsoft Edge binary."""
    env_browser = os.environ.get("PDF_BROWSER_PATH", "").strip()
    if env_browser and os.path.isfile(env_browser):
        return env_browser

    for cmd in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge"):
        found = shutil.which(cmd)
        if found:
            return found

    windows_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in windows_candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


def _escape_pdf_text(text: str) -> str:
    """Escapes parentheses and backslashes for PDF literal strings and normalizes to Latin-1."""
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2022": "*",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_line(line: str, max_chars: int = 92) -> List[str]:
    """Word-wraps a single line to fit within standard A4 width."""
    if not line or len(line) <= max_chars:
        return [line]
    words = line.split(" ")
    wrapped: List[str] = []
    current = ""
    for w in words:
        if not current:
            current = w
        elif len(current) + 1 + len(w) <= max_chars:
            current += " " + w
        else:
            wrapped.append(current)
            current = w
    if current:
        wrapped.append(current)
    return wrapped


def render_text_to_pdf_bytes(text: str, title: str = "Application Document") -> bytes:
    """
    Pure-Python zero-dependency PDF 1.4 generator using standard Type1 Helvetica/Helvetica-Bold.
    Produces multi-page A4 selectable-text PDFs.
    """
    raw_lines = text.splitlines()
    visual_lines: List[tuple[str, bool, float]] = []  # (text, is_bold, font_size)

    for idx, raw in enumerate(raw_lines):
        stripped = raw.strip()
        if not stripped:
            visual_lines.append(("", False, 9.5))
            continue
        if stripped.startswith("=" * 10) or stripped.startswith("-" * 10):
            continue
        if stripped.startswith("# "):
            visual_lines.append((stripped[2:].strip(), True, 15.0))
        elif stripped.startswith("## "):
            visual_lines.append(("", False, 6.0))
            visual_lines.append((stripped[3:].strip().upper(), True, 11.0))
        elif stripped.startswith("### "):
            visual_lines.append((stripped[4:].strip(), True, 10.0))
        elif idx == 0 and stripped.isupper():
            visual_lines.append((stripped, True, 14.0))
        elif stripped.isupper() and len(stripped) < 60:
            visual_lines.append(("", False, 5.0))
            visual_lines.append((stripped, True, 10.5))
        else:
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
            clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
            clean = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", clean)
            is_bold = stripped.startswith("**") and stripped.endswith("**")
            for w_line in _wrap_line(clean, max_chars=94):
                visual_lines.append((w_line, is_bold, 9.5))

    # Paginate into A4 pages (595 x 842 pt, top margin 792, bottom margin 48)
    pages_streams: List[bytes] = []
    y_cursor = 792.0
    current_ops: List[str] = ["BT"]

    for line_text, is_bold, fsize in visual_lines:
        line_height = fsize * 1.38
        if y_cursor - line_height < 48.0:
            current_ops.append("ET")
            pages_streams.append("\n".join(current_ops).encode("latin-1"))
            current_ops = ["BT"]
            y_cursor = 792.0

        if line_text:
            font_ref = "/F2" if is_bold else "/F1"
            esc = _escape_pdf_text(line_text)
            current_ops.append(f"{font_ref} {fsize:.1f} Tf")
            current_ops.append(f"1 0 0 1 45 {y_cursor:.2f} Tm")
            current_ops.append(f"({esc}) Tj")
        y_cursor -= line_height

    current_ops.append("ET")
    pages_streams.append("\n".join(current_ops).encode("latin-1"))

    # Construct PDF 1.4 objects
    # Object 1: Catalog, Object 2: Pages, Object 3: Font F1 (Helvetica), Object 4: Font F2 (Helvetica-Bold)
    objects: List[bytes] = []
    num_pages = len(pages_streams)
    first_page_obj_id = 5

    page_kids = " ".join(f"{first_page_obj_id + i * 2} 0 R" for i in range(num_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{page_kids}] /Count {num_pages} >>".encode("latin-1"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    for i, stream_bytes in enumerate(pages_streams):
        page_obj_id = first_page_obj_id + i * 2
        content_obj_id = page_obj_id + 1
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {content_obj_id} 0 R >>"
        ).encode("latin-1")
        content_dict = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1")
            + stream_bytes
            + b"\nendstream"
        )
        objects.append(page_dict)
        objects.append(content_dict)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: List[int] = [0]
    for obj_idx, obj_body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{obj_idx} 0 obj\n".encode("latin-1"))
        out.extend(obj_body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    esc_title = _escape_pdf_text(title)
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)


def render_markdown_to_docx_bytes(markdown_text: str) -> bytes:
    """Creates an editable, single-column Word document from generated Markdown."""
    document_paragraphs: List[str] = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---":
            document_paragraphs.append("<w:p/>")
            continue

        style = "Normal"
        text = stripped
        if stripped.startswith("# "):
            style, text = "Title", stripped[2:].strip()
        elif stripped.startswith("## "):
            style, text = "Heading1", stripped[3:].strip()
        elif stripped.startswith("### "):
            style, text = "Heading2", stripped[4:].strip()
        elif stripped.startswith(("- ", "* ")):
            style, text = "ListParagraph", "\u2022 " + stripped[2:].strip()

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
        document_paragraphs.append(
            f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{html.escape(text)}</w:t></w:r></w:p>'
        )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        + "".join(document_paragraphs)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="850" w:right="850" w:bottom="850" w:left="850"/>'
        "</w:sectPr></w:body></w:document>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>'
        '<w:sz w:val="20"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
        '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
        "</w:style></w:styles>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    relationships_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_relationships_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types_xml)
        docx.writestr("_rels/.rels", relationships_xml)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
        docx.writestr("word/_rels/document.xml.rels", document_relationships_xml)
    return output.getvalue()


def render_html_to_pdf_bytes(
    html_content: str,
    fallback_text: str = "",
    output_pdf_path: Optional[Union[str, Path]] = None,
) -> bytes:
    """
    Renders semantic ATS HTML into a high-resolution, selectable-text PDF via Headless Chrome/Edge,
    falling back to the pure-Python PDF 1.4 engine if no browser binary is available.
    """
    browser = _find_browser_binary()
    if browser:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_html = Path(tmpdir) / "document.html"
            tmp_pdf = Path(output_pdf_path) if output_pdf_path else (Path(tmpdir) / "document.pdf")
            tmp_pdf.parent.mkdir(parents=True, exist_ok=True)
            tmp_html.write_text(html_content, encoding="utf-8")

            cmd = [
                browser,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-software-rasterizer",
                "--no-pdf-header-footer",
                f"--print-to-pdf={str(tmp_pdf.resolve())}",
                str(tmp_html.resolve()),
            ]
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=25,
                    check=False,
                )
                if tmp_pdf.is_file() and tmp_pdf.stat().st_size > 500:
                    pdf_bytes = tmp_pdf.read_bytes()
                    if pdf_bytes.startswith(b"%PDF"):
                        return pdf_bytes
            except Exception:
                pass

    # Pure-Python fallback (ensure all HTML entities like &amp; are unescaped)
    text_source = fallback_text or html.unescape(re.sub(r"<[^>]+>", " ", html_content))
    pdf_bytes = render_text_to_pdf_bytes(text_source)
    if output_pdf_path:
        p = Path(output_pdf_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pdf_bytes)
    return pdf_bytes
