"""
Multi-Channel Job Description Ingestion & URL Fetcher.
Module: ingestion.job_fetcher

Supports 5 frictionless methods for bringing a new job opportunity into the pipeline:
1. Direct URL (--url): Workday (myworkdayjobs.com CXS JSON API), Greenhouse, Lever, Ashby,
   JSON-LD JobPosting schema, and generic HTML career pages.
2. Clipboard Paste (--paste / --clipboard): Reads copied JD text directly from OS clipboard.
3. Dropzone Inbox (data/paste_job_here.txt or data/job_inbox/*.txt): Paste text or URL into a file.
4. File Path (--file): Arbitrary local .txt / .md / .html job file.
5. Raw String (--text): Inline CLI string or GitHub Actions workflow_dispatch input.
"""

from __future__ import annotations

import html
import json
import logging
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class IngestedJob:
    """Normalized representation of an ingested job opportunity."""
    title: str
    company: str
    location: str
    description: str
    url: str = ""
    source_method: str = "text"

    @property
    def text(self) -> str:
        return self.description

    @property
    def source_type(self) -> str:
        return self.source_method

    @property
    def full_text(self) -> str:
        header = " | ".join(p for p in [self.title, self.company, self.location] if p)
        if header:
            return f"{header}\n\n{self.description}"
        return self.description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "url": self.url,
            "source_method": self.source_method,
        }


FetchedJobInput = IngestedJob


def _strip_html_tags(raw_html: str) -> str:
    """Converts HTML into clean readable plain text."""
    if not raw_html:
        return ""
    cleaned = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<(br|p|div|li|h[1-6]|tr)[^>]*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def _infer_metadata_from_text(text: str, url: str = "") -> IngestedJob:
    """Heuristically extracts job title, company, and location from raw job text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = ""
    company = ""
    location = ""

    if lines:
        title = lines[0][:120]

    # Check common patterns in early lines
    head_block = "\n".join(lines[:20])
    comp_match = re.search(r"(?:Company|Organization|Employer|Client)\s*:\s*([^\n|]+)", head_block, re.IGNORECASE)
    if comp_match:
        company = comp_match.group(1).strip()
    elif "gates foundation" in head_block.lower() or "gatesfoundation" in url.lower():
        company = "Gates Foundation"

    loc_match = re.search(r"(?:Location|Locations)\s*[:\n]\s*([^\n]+)", head_block, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()

    if not company and url:
        parsed = urllib.parse.urlparse(url)
        host_parts = parsed.netloc.lower().split(".")
        if "myworkdayjobs" in parsed.netloc.lower() and host_parts:
            company = host_parts[0].replace("-", " ").title()
        elif len(host_parts) >= 2:
            company = host_parts[-2].replace("-", " ").title()

    return IngestedJob(
        title=title or "Target Engineering Role",
        company=company or "Hiring Organization",
        location=location or "Remote / Global",
        description=text.strip(),
        url=url,
        source_method="url" if url else "text",
    )


def fetch_job_from_url(url: str, timeout: int = 15) -> IngestedJob:
    """
    Fetches a job posting from a public URL (Workday, Greenhouse, Lever, or generic HTML).
    """
    clean_url = url.strip()
    parsed = urllib.parse.urlparse(clean_url)

    # 1. Special Handler for Workday (*.myworkdayjobs.com) CXS JSON API
    if "myworkdayjobs.com" in parsed.netloc.lower():
        tenant = parsed.netloc.split(".")[0]
        # Path pattern: /en-US/<site>/job/<location>/<job_slug> or /<site>/job/<location>/<job_slug>
        path_parts = [p for p in parsed.path.split("/") if p]
        if "job" in path_parts:
            job_idx = path_parts.index("job")
            if job_idx >= 1:
                site = path_parts[job_idx - 1]
                job_subpath = "/".join(path_parts[job_idx:])
                cxs_url = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/{job_subpath}"
                try:
                    req = urllib.request.Request(
                        cxs_url,
                        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8", errors="replace"))
                        info = data.get("jobPostingInfo", {})
                        title = info.get("title", "")
                        loc = info.get("location", "")
                        additional_locs = info.get("additionalLocations", [])
                        if additional_locs:
                            loc = f"{loc} / {', '.join(additional_locs)}"
                        desc_html = info.get("jobDescription", "")
                        desc_text = _strip_html_tags(desc_html)
                        if desc_text:
                            return IngestedJob(
                                title=title or "Target Role",
                                company=tenant.replace("foundation", " Foundation").title(),
                                location=loc or "Global",
                                description=f"{title}\nLocations: {loc}\n\n{desc_text}",
                                url=clean_url,
                                source_method="workday_cxs_api",
                            )
                except Exception as exc:
                    logger.debug(f"Workday CXS JSON endpoint fallback triggered: {exc}")

    # 2. Generic HTTP fetch + JSON-LD JobPosting / Meta tag / Body extraction
    req = urllib.request.Request(
        clean_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_bytes = resp.read()
        raw_text = raw_bytes.decode("utf-8", errors="replace")

    # Check for JSON-LD JobPosting schema
    for ld_match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            ld_data = json.loads(ld_match.group(1).strip())
            items = ld_data if isinstance(ld_data, list) else [ld_data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    title = str(item.get("title", ""))
                    hiring_org = item.get("hiringOrganization", {})
                    company = hiring_org.get("name", "") if isinstance(hiring_org, dict) else ""
                    desc_html = str(item.get("description", ""))
                    desc_clean = _strip_html_tags(desc_html)
                    if desc_clean:
                        return IngestedJob(
                            title=title or "Target Role",
                            company=company or "Hiring Organization",
                            location="Remote / Global",
                            description=f"{title}\nCompany: {company}\n\n{desc_clean}",
                            url=clean_url,
                            source_method="json_ld",
                        )
        except Exception:
            continue

    plain_body = _strip_html_tags(raw_text)
    return _infer_metadata_from_text(plain_body, url=clean_url)


def read_clipboard_text() -> str:
    """Reads text from the system clipboard (Windows PowerShell Get-Clipboard fallback)."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def ingest_job_input(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    from_clipboard: bool = False,
    inbox_dir: Optional[Path] = None,
    dropzone_path: Optional[Path] = None,
    use_dropzone: bool = True,
) -> Optional[IngestedJob]:
    """
    Unified job ingestion resolver across URL, file, clipboard, raw text, or dropzone inbox.
    """
    # 1. Explicit URL
    if url and url.strip():
        return fetch_job_from_url(url.strip())

    # 2. Explicit File Path
    if file_path and Path(file_path).is_file():
        content = Path(file_path).read_text(encoding="utf-8").strip()
        if content.startswith("http://") or content.startswith("https://"):
            if len(content.splitlines()) == 1:
                return fetch_job_from_url(content)
        job = _infer_metadata_from_text(content)
        job.source_method = f"file:{file_path}"
        return job

    # 3. Direct Text (check if it is a single-line URL)
    if text and text.strip():
        stripped = text.strip()
        if (stripped.startswith("http://") or stripped.startswith("https://")) and len(stripped.splitlines()) == 1:
            return fetch_job_from_url(stripped)
        return _infer_metadata_from_text(stripped)

    # 4. System Clipboard
    if from_clipboard:
        clip = read_clipboard_text()
        if clip:
            if (clip.startswith("http://") or clip.startswith("https://")) and len(clip.splitlines()) == 1:
                return fetch_job_from_url(clip)
            job = _infer_metadata_from_text(clip)
            job.source_method = "clipboard"
            return job

    # 5. Dropzone Inbox (data/paste_job_here.txt or data/job_inbox/*.txt)
    if not use_dropzone and dropzone_path is None:
        return None

    root = Path(__file__).resolve().parent.parent
    paste_file = dropzone_path if dropzone_path is not None else (root / "data" / "paste_job_here.txt")
    if paste_file.is_file():
        content = paste_file.read_text(encoding="utf-8").strip()
        active_lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
        clean_content = "\n".join(active_lines).strip()
        if clean_content:
            if clean_content.startswith("http://") or clean_content.startswith("https://"):
                if len(clean_content.splitlines()) == 1:
                    return fetch_job_from_url(clean_content)
            job = _infer_metadata_from_text(clean_content)
            job.source_method = str(paste_file)
            return job

    target_inbox = inbox_dir or (root / "data" / "job_inbox")
    if target_inbox.is_dir():
        txt_files = sorted(target_inbox.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        for tf in txt_files:
            content = tf.read_text(encoding="utf-8").strip()
            if content:
                job = _infer_metadata_from_text(content)
                job.source_method = str(tf)
                return job

    return None


def resolve_job_input(
    text: Optional[str] = None,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    from_clipboard: bool = False,
    dropzone_path: Optional[Path] = None,
    inbox_dir: Optional[Path] = None,
) -> Optional[IngestedJob]:
    """Alias for ingest_job_input with explicit dropzone control."""
    return ingest_job_input(
        text=text,
        file_path=file_path,
        url=url,
        from_clipboard=from_clipboard,
        inbox_dir=inbox_dir,
        dropzone_path=dropzone_path,
        use_dropzone=(dropzone_path is not None),
    )
