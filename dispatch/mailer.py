"""
SMTP Dispatcher & Dry-Run .eml Storage Exporter.
Module: dispatch.mailer
Feature: F11 (Daily 8:00 AM Notification Dispatch) & F15 (Controlled Testing & Dry-Run Mode)
Milestone: M4 (Daily 8:00 AM Dispatcher & Scheduling Architecture)

Complies with:
- Zero-cost offline dry-run serialization to .eml without network calls
- Environment variable configuration for SMTP host, port, credentials, and TLS
- Exception safety: raises ValueError/Exception when live mode is requested without credentials
- Attachment size limit verification guardrail (default 10 MB limit)
"""

from __future__ import annotations

import datetime
import os
import smtplib
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config.settings import settings, get_settings


# ============================================================================
# 1. Safety Guardrails & Verification
# ============================================================================

def check_attachment_size_limit(
    attachments: List[Tuple[str, Union[bytes, str]]],
    max_mb: float = 10.0,
) -> bool:
    """
    Guards against email transport rejections by verifying the cumulative size
    of all proposed attachments is within the allowable limit.

    Args:
        attachments: List of (filename, file_content_bytes_or_str).
        max_mb: Maximum allowable cumulative size in megabytes (default 10 MB).

    Returns:
        True if total size is within limit, False if oversized.
    """
    if not attachments:
        return True

    total_bytes = 0
    for item in attachments:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        content = item[1]
        if isinstance(content, bytes):
            total_bytes += len(content)
        elif isinstance(content, str):
            total_bytes += len(content.encode("utf-8"))

    limit_bytes = int(max_mb * 1024 * 1024)
    return total_bytes <= limit_bytes


def extract_attachments_from_message(
    msg: Union[MIMEMultipart, EmailMessage],
) -> List[Tuple[str, Union[bytes, str]]]:
    """
    Extracts all attachment payloads from a MIME message or EmailMessage.
    """
    extracted: List[Tuple[str, Union[bytes, str]]] = []
    if hasattr(msg, "walk"):
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = str(part.get("Content-Disposition", ""))
            ctype = str(part.get_content_type()).lower()
            if "attachment" in disp.lower() or ctype == "application/octet-stream" or isinstance(part, MIMEApplication):
                payload = part.get_payload(decode=True)
                filename = part.get_filename() or "attachment"
                if payload is not None:
                    extracted.append((filename, payload))
                else:
                    raw = part.get_payload()
                    if raw is not None:
                        extracted.append((filename, raw))
    elif hasattr(msg, "iter_attachments"):
        for part in msg.iter_attachments():
            payload = part.get_payload(decode=True)
            if payload is None and hasattr(part, "get_content"):
                payload = part.get_content()
            filename = part.get_filename() or "attachment"
            extracted.append((filename, payload or b""))
    return extracted


# ============================================================================
# 2. File Export Helpers
# ============================================================================

def export_eml(
    msg: Union[MIMEMultipart, EmailMessage],
    output_path: Union[str, Path],
) -> str:
    """
    Serializes a MIME email message directly to an RFC 5322 .eml file on disk.

    Args:
        msg: MIMEMultipart or EmailMessage instance.
        output_path: Destination file path.

    Returns:
        Absolute string path to the created .eml file.
    """
    p = Path(output_path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "wb") as f:
        f.write(msg.as_bytes())

    return str(p)


# ============================================================================
# 3. Main Dispatch API
# ============================================================================

def send_email(
    msg: Union[MIMEMultipart, EmailMessage],
    dry_run: Optional[bool] = None,
    output_dir: Optional[Union[str, Path]] = None,
    smtp_host: Optional[str] = None,
    smtp_port: Optional[int] = None,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    smtp_use_tls: Optional[bool] = None,
    smtp_sender: Optional[str] = None,
    attachments: Optional[List[Tuple[str, Union[bytes, str]]]] = None,
    max_attachment_mb: float = 10.0,
) -> str:
    """
    Dispatches an email message via SMTP or exports to disk in dry-run mode.

    Behavior:
    1. If dry_run is True (or unset and default settings.dry_run is True):
       - Exports message to an .eml file under output_dir without making any network calls.
       - Returns the .eml file path (guaranteed to exist on disk).
    2. If dry_run is False:
       - Validates presence of SMTP host, user, and password.
       - Raises ValueError if credentials are missing or empty.
       - Transmits email securely over TLS via smtplib.
       - Returns message tracking ID or confirmation path.

    Args:
        msg: Complete MIMEMultipart or EmailMessage instance.
        dry_run: Explicit dry-run override flag.
        output_dir: Directory where .eml digests are saved in dry-run mode.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port (default 587).
        smtp_user: SMTP authentication username.
        smtp_password: SMTP authentication password.
        smtp_use_tls: Flag to negotiate TLS encryption (default True).
        smtp_sender: Envelope sender address override.
        attachments: Optional list of explicit (filename, content) attachment tuples.
        max_attachment_mb: Cumulative attachment limit in megabytes (default 10 MB).

    Returns:
        File path to exported .eml (dry-run) or transmission confirmation string.
    """
    active_settings = get_settings()

    # Enforce cumulative attachment size limit guardrail (default 10 MB limit)
    target_attachments: List[Tuple[str, Union[bytes, str]]] = []
    if attachments is not None:
        target_attachments.extend(attachments)
    target_attachments.extend(extract_attachments_from_message(msg))

    if target_attachments and not check_attachment_size_limit(target_attachments, max_mb=max_attachment_mb):
        raise ValueError("Cumulative attachment size exceeds 10 MB limit.")

    # Resolve dry-run posture
    is_dry_run = dry_run if dry_run is not None else active_settings.dry_run

    # -------------------------------------------------------------------------
    # Mode A: Dry-Run / Offline Export (.eml)
    # -------------------------------------------------------------------------
    if is_dry_run:
        if output_dir:
            out_base = Path(output_dir)
            if out_base.suffix.lower() == ".eml":
                target_file = out_base
            else:
                out_base.mkdir(parents=True, exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
                target_file = out_base / f"daily_digest_{ts}.eml"
        else:
            digests_dir = active_settings.output_dir / "digests"
            digests_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            target_file = digests_dir / f"daily_digest_{ts}.eml"

        return export_eml(msg, target_file)

    # -------------------------------------------------------------------------
    # Mode B: Live SMTP Transmission
    # -------------------------------------------------------------------------
    host = smtp_host if smtp_host is not None else active_settings.smtp_host
    port = smtp_port if smtp_port is not None else active_settings.smtp_port
    user = smtp_user if smtp_user is not None else active_settings.smtp_user
    password = smtp_password if smtp_password is not None else active_settings.smtp_password
    use_tls = smtp_use_tls if smtp_use_tls is not None else active_settings.smtp_use_tls
    sender = smtp_sender if smtp_sender is not None else active_settings.smtp_sender

    # Credential Protection Gatekeeper
    if not host or not str(host).strip():
        raise ValueError("Live email transmission failed: SMTP_HOST is not configured.")
    if not user or not str(user).strip():
        raise ValueError("Live email transmission failed: SMTP_USER is not configured.")
    if not password or not str(password).strip():
        raise ValueError("Live email transmission failed: SMTP_PASSWORD is not configured.")

    # Execute SMTP delivery
    server = smtplib.SMTP(host=str(host).strip(), port=int(port), timeout=15)
    try:
        if use_tls:
            server.starttls()
        server.login(str(user).strip(), str(password).strip())

        from_addr = sender or msg.get("From") or str(user).strip()
        to_addrs = [r.strip() for r in str(msg.get("To", "")).split(",") if r.strip()]

        server.send_message(msg, from_addr=from_addr, to_addrs=to_addrs)
    finally:
        try:
            server.quit()
        except Exception:
            pass

    # Save audit record in output dir
    audit_dir = (Path(output_dir) if output_dir else active_settings.output_dir) / "sent"
    audit_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_file = audit_dir / f"sent_digest_{ts}.eml"
    export_eml(msg, audit_file)

    return str(audit_file)
