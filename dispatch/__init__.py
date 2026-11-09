"""
Dispatch module for Career Automation & Stepcon Pipeline.
Features: F11 (Daily 8:00 AM Notification Dispatch)
"""

from dispatch.digest import (
    build_digest_email,
    format_digest_html,
    format_digest_text,
)
from dispatch.mailer import (
    check_attachment_size_limit,
    export_eml,
    send_email,
)

__all__ = [
    "build_digest_email",
    "format_digest_html",
    "format_digest_text",
    "send_email",
    "check_attachment_size_limit",
    "export_eml",
]
