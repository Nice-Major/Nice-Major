"""
Configuration settings and environment variable management for Career Automation.
Module: config.settings
Feature: F15 (Controlled Testing & Dry-Run Mode) & Milestone 1 Foundation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Union

# Root directory of the project
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_bool(val: Any, default: bool = False) -> bool:
    """
    Parses various representations of boolean values from strings, ints, or booleans.
    Handles 'true', '1', 'yes', 'y', 't', 'on' -> True
    Handles 'false', '0', 'no', 'n', 'f', 'off' -> False
    """
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y", "t", "on"):
        return True
    if s in ("false", "0", "no", "n", "f", "off", ""):
        return False
    return default


def parse_port(val: Any, default: int = 587) -> int:
    """
    Parses a port value to an integer, falling back safely to default on failure.
    """
    if val is None:
        return default
    try:
        port = int(val)
        if 1 <= port <= 65535:
            return port
        return default
    except (ValueError, TypeError):
        return default


def load_dotenv_file(filepath: Optional[Union[str, Path]] = None) -> Dict[str, str]:
    """
    Reads a simple key=value .env file without external dependencies.
    Returns parsed dictionary of environment variables.
    """
    env_vars: Dict[str, str] = {}
    if filepath is None:
        filepath = PROJECT_ROOT / ".env"
    else:
        filepath = Path(filepath)

    if not filepath.is_file():
        return env_vars

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    key, value = stripped.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Strip surrounding quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    env_vars[key] = value
    except (OSError, UnicodeDecodeError):
        pass

    return env_vars


@dataclass
class Settings:
    """
    Central application settings pre-filled with verified candidate data for
    John Victor Aniekwe (aniekwevictor9@gmail.com) and Stepcon Solutions (RC - 8284984).
    """
    # Operational flags (dry_run and offline_mode default to True for local safety)
    dry_run: bool = True
    offline_mode: bool = True

    # Profile path override
    career_profile_path: Optional[str] = None

    # Candidate Identity & Notification Dispatch (Pre-filled for John Victor Aniekwe)
    notification_email: str = "aniekwevictor9@gmail.com"
    candidate_name: str = "John Victor Aniekwe"
    candidate_phone: str = "+2348130004114"
    candidate_location: str = "Lagos, Nigeria (UTC+1 / CET Synchronous)"
    github_repo_url: str = "https://github.com/Nice-Major/Nice-Major.git"
    github_profile_url: str = "https://github.com/Nice-Major"
    portfolio_url: str = "https://nice-major.github.io/Nice-Major/"
    linkedin_url: str = "https://www.linkedin.com/in/victor-aniekwe/"

    # SMTP Configuration (Pre-filled for Gmail TLS; requires SMTP_PASSWORD in live mode)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "aniekwevictor9@gmail.com"
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_sender: str = "aniekwevictor9@gmail.com"

    # Business entity
    stepcon_entity_name: str = "Stepcon Solutions"
    stepcon_cac_number: str = "RC - 8284984"

    # Logging & Paths
    log_level: str = "INFO"
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")

    # API Keys (strictly optional; defaults to None for zero-cost operation)
    openai_api_key: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)

    @property
    def recipient_email(self) -> str:
        """Alias for notification_email."""
        return self.notification_email

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary format with both snake_case and UPPER_CASE keys."""
        base = asdict(self)
        base["DRY_RUN"] = self.dry_run
        base["OFFLINE_MODE"] = self.offline_mode
        base["CAREER_PROFILE_PATH"] = self.career_profile_path
        base["NOTIFICATION_EMAIL"] = self.notification_email
        base["RECIPIENT_EMAIL"] = self.notification_email
        base["CANDIDATE_NAME"] = self.candidate_name
        base["GITHUB_REPO_URL"] = self.github_repo_url
        base["PORTFOLIO_URL"] = self.portfolio_url
        base["LINKEDIN_URL"] = self.linkedin_url
        base["SMTP_HOST"] = self.smtp_host
        base["SMTP_PORT"] = self.smtp_port
        base["SMTP_USER"] = self.smtp_user
        base["SMTP_PASSWORD"] = self.smtp_password
        base["SMTP_USE_TLS"] = self.smtp_use_tls
        base["SMTP_SENDER"] = self.smtp_sender
        return base

    def __getitem__(self, item: str) -> Any:
        normalized = item.lower()
        if hasattr(self, normalized):
            return getattr(self, normalized)
        upper = item.upper()
        if upper in ("DRY_RUN", "OFFLINE_MODE", "CAREER_PROFILE_PATH", "NOTIFICATION_EMAIL"):
            return getattr(self, upper.lower())
        raise KeyError(f"Setting '{item}' not found in Settings.")

    def __contains__(self, item: str) -> bool:
        normalized = item.lower()
        return hasattr(self, normalized) or item.upper() in (
            "DRY_RUN",
            "OFFLINE_MODE",
            "CAREER_PROFILE_PATH",
            "NOTIFICATION_EMAIL",
            "SMTP_HOST",
            "SMTP_PORT",
        )

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def get_settings(
    env_file: Optional[Union[str, Path]] = None,
    **overrides: Any
) -> Settings:
    """
    Factory function to build Settings instance by resolving:
    1. Default values (pre-filled for John Victor Aniekwe)
    2. Optional .env file values
    3. os.environ values
    4. Explicit overrides keyword arguments
    """
    file_vars = load_dotenv_file(env_file)

    def _resolve(key: str, default: Any = None) -> Any:
        if key.lower() in overrides:
            return overrides[key.lower()]
        if key.upper() in overrides:
            return overrides[key.upper()]
        if key in os.environ:
            return os.environ[key]
        if key.upper() in os.environ:
            return os.environ[key.upper()]
        if key.lower() in os.environ:
            return os.environ[key.lower()]
        if key in file_vars:
            return file_vars[key]
        if key.upper() in file_vars:
            return file_vars[key.upper()]
        if key.lower() in file_vars:
            return file_vars[key.lower()]
        return default

    dry_run = parse_bool(_resolve("DRY_RUN", True), default=True)
    offline_mode = parse_bool(_resolve("OFFLINE_MODE", True), default=True)
    career_profile_path = _resolve("CAREER_PROFILE_PATH", _resolve("CANDIDATE_PROFILE_PATH", None))
    notification_email = _resolve("NOTIFICATION_EMAIL", "aniekwevictor9@gmail.com")
    candidate_name = _resolve("CANDIDATE_NAME", "John Victor Aniekwe")
    candidate_phone = _resolve("CANDIDATE_PHONE", "+2348130004114")
    candidate_location = _resolve("CANDIDATE_LOCATION", "Lagos, Nigeria (UTC+1 / CET Synchronous)")
    github_repo_url = _resolve("GITHUB_REPO_URL", "https://github.com/Nice-Major/Nice-Major.git")
    github_profile_url = _resolve("GITHUB_PROFILE_URL", "https://github.com/Nice-Major")
    portfolio_url = _resolve("PORTFOLIO_URL", "https://nice-major.github.io/Nice-Major/")
    linkedin_url = _resolve("LINKEDIN_URL", "https://www.linkedin.com/in/victor-aniekwe/")

    smtp_host = _resolve("SMTP_HOST", "smtp.gmail.com")
    smtp_port = parse_port(_resolve("SMTP_PORT", 587), default=587)
    smtp_user = _resolve("SMTP_USER", "aniekwevictor9@gmail.com")
    smtp_password = _resolve("SMTP_PASSWORD", "")
    smtp_use_tls = parse_bool(_resolve("SMTP_USE_TLS", True), default=True)
    smtp_sender = _resolve("SMTP_SENDER", "aniekwevictor9@gmail.com")

    log_level = _resolve("LOG_LEVEL", "INFO")

    out_dir = _resolve("OUTPUT_DIR", None)
    output_dir = Path(out_dir) if out_dir else PROJECT_ROOT / "output"

    dat_dir = _resolve("DATA_DIR", None)
    data_dir = Path(dat_dir) if dat_dir else PROJECT_ROOT / "data"

    openai_key = _resolve("OPENAI_API_KEY", None)

    return Settings(
        dry_run=dry_run,
        offline_mode=offline_mode,
        career_profile_path=str(career_profile_path) if career_profile_path else None,
        notification_email=notification_email,
        candidate_name=candidate_name,
        candidate_phone=candidate_phone,
        candidate_location=candidate_location,
        github_repo_url=github_repo_url,
        github_profile_url=github_profile_url,
        portfolio_url=portfolio_url,
        linkedin_url=linkedin_url,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_use_tls=smtp_use_tls,
        smtp_sender=smtp_sender,
        log_level=log_level,
        project_root=PROJECT_ROOT,
        output_dir=output_dir,
        data_dir=data_dir,
        openai_api_key=openai_key,
    )


# Module-level default instance
settings = get_settings()
