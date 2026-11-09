"""
Empirical Adversarial Stress Test Suite for Milestone 5 Deliverables.
Author: challenger_m5_2 (Teamwork Empirical Challenger Subagent)
Module: tests.test_adversarial_m5_2
Features Tested: F13 (Interactive CLI), F14 (Stepcon Solutions Pipeline), F15 (Dry-Run & Env Controls)

Stress Testing Dimensions:
1. CLI execution under varied environment configurations:
   - DRY_RUN=true vs DRY_RUN=false
   - OFFLINE_MODE=1
   - Clean stdout/stderr separation without corrupting redirect pipes.
2. Stepcon tender discovery & proposal generation edge cases:
   - Category filtering (query_categories=["cloud"] vs ["hardware"] vs unknown).
   - Empirical investigation of category keyword argument in fetch_tenders.
   - Multi-currency detection and rendering (USD, GBP, EUR, NGN).
   - Filename safety in get_proposal_filename() against path traversal and Windows invalid chars.
3. Concurrency, thread safety, and workflow integration:
   - Multi-threaded on-demand evaluation & document generation.
   - Non-IT civil works rejection (< 35%).
   - Corporate identity preservation (RC - 8284984, John Victor Aniekwe, KCNA, AWS, C2C, 99.9% SLA).
   - Zero literal 'None' string pollution.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cli.main import (
    create_parser,
    evaluate_from_stdin,
    handle_eval,
    handle_stepcon,
    handle_tailor,
    run_cli,
)
from config.settings import get_settings, parse_bool, settings
from consultancy.proposals import generate_proposal, get_proposal_filename
from consultancy.tenders import (
    evaluate_tender,
    fetch_tenders,
    TenderMatchResult,
    TenderOpportunity,
)
from ingestion.models import CandidateProfile, StepconProfile


# ============================================================================
# 1. CLI Execution & Environment Isolation Tests
# ============================================================================

class TestCliEnvironmentIsolation:
    """Verifies CLI behavior across environment configurations and stdout/stderr hygiene."""

    def test_cli_env_dry_run_isolation_in_subprocess(self):
        """Tests that DRY_RUN environment variable is correctly resolved in independent subprocesses."""
        env_true = os.environ.copy()
        env_true["DRY_RUN"] = "true"
        p_true = subprocess.run(
            ["python", "-c", "from config.settings import get_settings; print(get_settings().dry_run)"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env_true,
        )
        assert p_true.returncode == 0
        assert p_true.stdout.strip() == "True"

        env_false = os.environ.copy()
        env_false["DRY_RUN"] = "false"
        p_false = subprocess.run(
            ["python", "-c", "from config.settings import get_settings; print(get_settings().dry_run)"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env_false,
        )
        assert p_false.returncode == 0
        assert p_false.stdout.strip() == "False"

    def test_cli_env_offline_mode_isolation_in_subprocess(self):
        """Tests that OFFLINE_MODE=1 forces offline setting across process boundaries."""
        env_offline = os.environ.copy()
        env_offline["OFFLINE_MODE"] = "1"
        p_off = subprocess.run(
            ["python", "-c", "from config.settings import get_settings; print(get_settings().offline_mode)"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env_offline,
        )
        assert p_off.returncode == 0
        assert p_off.stdout.strip() == "True"

        env_online = os.environ.copy()
        env_online["OFFLINE_MODE"] = "0"
        p_on = subprocess.run(
            ["python", "-c", "from config.settings import get_settings; print(get_settings().offline_mode)"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            env=env_online,
        )
        assert p_on.returncode == 0
        assert p_on.stdout.strip() == "False"

    def test_cli_stdout_clean_json_redirection(self):
        """Verifies that eval --json produces pure, uncorrupted JSON on STDOUT suitable for pipe redirection."""
        jd_text = (
            "Seeking Senior DevOps Engineer with deep Kubernetes, Terraform, and AWS experience. "
            "Must maintain 99.9% uptime SLA and automate CI/CD with GitHub Actions."
        )
        proc = subprocess.run(
            ["python", "cli/main.py", "eval", "--text", jd_text, "--json"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip(), "STDOUT must not be empty"

        # Crucial check: STDOUT must be strictly parseable as JSON without regex cleaning
        data = json.loads(proc.stdout)
        assert isinstance(data, dict)
        assert "overall_score" in data
        assert "breakdown" in data
        assert "matched_skills" in data
        assert data["overall_score"] >= 70.0

    def test_cli_stderr_error_separation_nonexistent_file(self):
        """Verifies that operational errors are written strictly to STDERR and exit code is non-zero."""
        nonexistent = "C:/path_that_does_not_exist_xyz_12345.txt"
        proc = subprocess.run(
            ["python", "cli/main.py", "eval", "--file", nonexistent],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert proc.stdout.strip() == "", "STDOUT must be completely empty on file error"
        assert "Error: Job description file does not exist" in proc.stderr

    def test_cli_stderr_error_separation_empty_input(self):
        """Verifies that empty input errors are routed to STDERR without contaminating STDOUT."""
        proc = subprocess.run(
            ["python", "cli/main.py", "eval", "--text", ""],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 1
        assert proc.stdout.strip() == ""
        assert "Error: No job description provided" in proc.stderr

    def test_cli_unrecognized_subcommand_exit_code_and_stderr(self):
        """Verifies that unrecognized subcommands exit with code 2 and usage information."""
        proc = subprocess.run(
            ["python", "cli/main.py", "invalid_subcmd_9999"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2

    def test_cli_verbose_logging_directed_to_stderr(self):
        """Verifies that --verbose debug logging goes to STDERR, leaving JSON on STDOUT uncorrupted."""
        jd_text = "AWS and Azure Cloud Solutions Architect with Kubernetes and Terraform"
        proc = subprocess.run(
            ["python", "cli/main.py", "--verbose", "eval", "--text", jd_text, "--role", "architect", "--json"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        # STDOUT must parse cleanly as JSON even with verbose logging active
        data = json.loads(proc.stdout)
        assert data["overall_score"] > 0
        # Debug logs must appear in STDERR
        assert "DEBUG: Role override requested: architect" in proc.stderr


# ============================================================================
# 2. CLI Stdin & Boundary Stress Tests
# ============================================================================

class TestCliStdinStress:
    """Stress tests on stdin evaluation and extreme input boundary conditions."""

    def test_evaluate_from_stdin_empty_or_whitespace(self):
        """Verifies evaluate_from_stdin rejects None, empty strings, and pure whitespace with code 1."""
        assert evaluate_from_stdin("") == 1
        assert evaluate_from_stdin(None) == 1
        assert evaluate_from_stdin("   \t\n  \r\n ") == 1

    def test_evaluate_from_stdin_unicode_and_emojis(self):
        """Verifies evaluate_from_stdin handles high-Unicode and emoji characters gracefully."""
        unicode_jd = (
            "🚀 Senior DevOps Engineer role at Global Tech! 🌍 "
            "Must master Kubernetes ☸️, Terraform 🏗️, and AWS ☁️. "
            "Uptime SLA 99.9% ⏱️. Lagos / Remote EMEA."
        )
        exit_code = evaluate_from_stdin(unicode_jd)
        assert exit_code == 0

    def test_evaluate_from_stdin_massive_text_payload(self):
        """Stress-tests evaluate_from_stdin with a massive 15,000-word repetitive input."""
        massive_text = "DevOps Engineer Kubernetes Terraform AWS CI/CD Python Linux Azure " * 1500
        exit_code = evaluate_from_stdin(massive_text)
        assert exit_code == 0


# ============================================================================
# 3. Stepcon Tender Discovery & Category Filtering Stress Tests
# ============================================================================

class TestStepconTenderDiscoveryStress:
    """Empirically tests tender discovery, category filtering, and parameter edge cases."""

    def test_fetch_tenders_category_filtering_cloud_vs_hardware(self):
        """Verifies category filtering with valid categories ('cloud' vs 'hardware')."""
        cloud_tenders = fetch_tenders(dry_run=True, query_categories=["cloud"])
        assert len(cloud_tenders) >= 1
        for t in cloud_tenders:
            assert t.category.lower() == "cloud"

        hw_tenders = fetch_tenders(dry_run=True, query_categories=["hardware"])
        assert len(hw_tenders) >= 1
        for t in hw_tenders:
            assert t.category.lower() == "hardware"

    def test_fetch_tenders_category_kwarg_empirical_finding(self):
        """
        Empirically probes whether fetch_tenders accepts category='cloud' as a keyword argument.
        Finding: In consultancy.tenders.fetch_tenders, the parameter is named 'query_categories'
        (expecting a List[str]). Calling fetch_tenders(category='cloud') raises TypeError.
        """
        try:
            fetch_tenders(category="cloud")  # type: ignore
            # If the signature is ever broadened to support category kwarg:
            category_kwarg_supported = True
        except TypeError as e:
            category_kwarg_supported = False
            assert "got an unexpected keyword argument 'category'" in str(e)

        # Documented empirical result:
        assert category_kwarg_supported is False

    def test_fetch_tenders_unknown_category_fallback_behavior(self):
        """
        Empirically verifies discovery behavior when querying an unknown / non-existent category.
        Finding: fetch_tenders uses `return (filtered or synth)[:limit]`.
        When filtered is empty, it returns the entire synthetic catalog rather than an empty list.
        """
        unknown_tenders = fetch_tenders(dry_run=True, query_categories=["nonexistent_category_999"])
        # Because (filtered or synth) evaluates to synth when filtered == []:
        assert len(unknown_tenders) == 4
        categories = {t.category for t in unknown_tenders}
        assert "cloud" in categories
        assert "civil" in categories

    def test_tender_opportunity_dual_subscript_attribute_access(self):
        """Verifies TenderOpportunity behaves interchangeably as dataclass and dictionary."""
        tender = TenderOpportunity(
            id="TND-TEST-01",
            title="Cloud Architecture Retainer",
            client="Global FinTech",
            description="Terraform and AWS infrastructure",
            budget="$50,000 USD",
            category="cloud",
        )
        # Attribute access
        assert tender.id == "TND-TEST-01"
        assert tender.title == "Cloud Architecture Retainer"
        assert tender.category == "cloud"

        # Dict subscript access
        assert tender["id"] == "TND-TEST-01"
        assert tender["tender_id"] == "TND-TEST-01"
        assert tender["title"] == "Cloud Architecture Retainer"
        assert tender.get("client") == "Global FinTech"
        assert tender.get("nonexistent_key", "default_val") == "default_val"
        assert "budget" in tender


# ============================================================================
# 4. Stepcon Proposal Multi-Currency & Corporate Identity Tests
# ============================================================================

class TestStepconProposalStress:
    """Verifies proposal generation across all currencies, identity rules, and edge cases."""

    @pytest.fixture
    def stepcon_profile(self) -> StepconProfile:
        return StepconProfile(
            company_name="Stepcon Solutions",
            cac_number="RC - 8284984",
        )

    def test_proposal_multi_currency_rendering_usd(self, stepcon_profile):
        """Verifies USD budget detection and multi-currency options block."""
        tender_usd = {
            "title": "Cloud Modernization RFP",
            "budget": "$120,000 USD",
            "description": "Multi-cloud AWS & Azure migration under 99.9% uptime SLA.",
        }
        prop = generate_proposal(stepcon_profile, tender_usd)
        assert "$120,000 USD" in prop
        assert "United States Dollars (USD - $)" in prop
        assert "SWIFT" in prop

    def test_proposal_multi_currency_rendering_gbp(self, stepcon_profile):
        """Verifies GBP budget detection and multi-currency options block."""
        tender_gbp = {
            "title": "UK FinTech Infrastructure Modernization",
            "budget": "£95,000 GBP",
            "description": "Kubernetes platform engineering in synchronous CET/EMEA hours.",
        }
        prop = generate_proposal(stepcon_profile, tender_gbp)
        assert "£95,000 GBP" in prop
        assert "British Pounds Sterling (GBP - £)" in prop
        assert "Faster Payments" in prop

    def test_proposal_multi_currency_rendering_eur(self, stepcon_profile):
        """Verifies EUR budget detection and multi-currency options block."""
        tender_eur = {
            "title": "European Cloud Estate Automation",
            "budget": "€110,000 EUR",
            "description": "DevSecOps pipelines and Terraform IaC governance.",
        }
        prop = generate_proposal(stepcon_profile, tender_eur)
        assert "€110,000 EUR" in prop
        assert "European Union Euros (EUR - €)" in prop
        assert "SEPA" in prop

    def test_proposal_multi_currency_rendering_ngn(self, stepcon_profile):
        """Verifies NGN budget detection and Nigerian banking rails."""
        tender_ngn = {
            "title": "Federal Data Center Cloud Migration",
            "budget": "₦85,000,000 NGN",
            "description": "Cloud migration and AKS orchestration for federal health records.",
        }
        prop = generate_proposal(stepcon_profile, tender_ngn)
        assert "₦85,000,000 NGN" in prop
        assert "Nigerian Naira (NGN - ₦)" in prop
        assert "NIBSS" in prop or "NIP" in prop

    def test_proposal_mandatory_corporate_identity_and_credentials(self, stepcon_profile):
        """Verifies strict presence of all mandatory statutory and credential entities."""
        tender = {
            "title": "Multi-Cloud RFP",
            "description": "DevOps, Kubernetes, and Cloud Architecture.",
        }
        prop = generate_proposal(stepcon_profile, tender)
        # Corporate legal status
        assert "Stepcon Solutions" in prop
        assert "RC - 8284984" in prop
        assert "Corporate Affairs Commission" in prop
        # Lead Architect
        assert "John Victor Aniekwe" in prop
        assert "KCNA" in prop or "Kubernetes and Cloud Native Associate" in prop
        assert "AWS Certified" in prop
        assert "Computer Science" in prop
        # Contracting & SLA
        assert "Corp-to-Corp" in prop or "C2C" in prop
        assert "99.9%" in prop
        assert "99%" in prop  # RCA resolution rate

    def test_proposal_zero_literal_none_pollution(self, stepcon_profile):
        """Verifies that completely empty or None fields never leak literal 'None' into output."""
        empty_tender = {
            "title": None,
            "client": None,
            "description": None,
            "budget": None,
            "deadline": None,
        }
        prop = generate_proposal(stepcon_profile, empty_tender)
        assert "None" not in prop
        assert "Enterprise Procurement Committee" in prop or "Stepcon Solutions" in prop


# ============================================================================
# 5. Output Filename Safety & Edge Cases (get_proposal_filename)
# ============================================================================

class TestProposalFilenameSafety:
    """Stress tests get_proposal_filename against path traversal and OS edge cases."""

    def test_proposal_filename_path_traversal_sanitized(self):
        """Verifies directory traversal sequences (../ and ..\\) in tender_id are sanitized."""
        tender_linux_traversal = {"tender_id": "../../etc/passwd"}
        fn_linux = get_proposal_filename(tender_linux_traversal)
        assert "/" not in fn_linux
        assert ".." not in fn_linux
        assert fn_linux.startswith("Proposal_Stepcon_etc_passwd_")

        tender_win_traversal = {"tender_id": r"..\..\Windows\System32\calc.exe"}
        fn_win = get_proposal_filename(tender_win_traversal)
        assert "\\" not in fn_win
        assert ".." not in fn_win
        assert fn_win.startswith("Proposal_Stepcon_Windows_System32_calc_exe_")

    def test_proposal_filename_windows_reserved_characters_replaced(self):
        """Verifies Windows reserved characters (: * ? \" < > |) are replaced with underscores."""
        tender_reserved = {"tender_id": "RFP:2026*Q4?Draft<Alpha>Beta|Final"}
        fn = get_proposal_filename(tender_reserved)
        for char in [":", "*", "?", '"', "<", ">", "|"]:
            assert char not in fn

    def test_proposal_filename_date_str_traversal_empirical_finding(self):
        """
        Empirically tests get_proposal_filename when caller passes unsanitized date_str.
        Finding: In consultancy.proposals.get_proposal_filename, active_date is computed via
        `(date_str or ...).replace('-', '')`. If date_str contains '../../', it leaks into the
        return value. Callers must sanitize date_str or use standard YYYY-MM-DD.
        """
        tender = {"tender_id": "TND-01"}
        fn_clean = get_proposal_filename(tender, date_str="2026-11-07")
        assert fn_clean == "Proposal_Stepcon_TND-01_20261107.md"

        fn_traversal = get_proposal_filename(tender, date_str="../../2026-11-07")
        # Empirical proof of finding:
        assert "../" in fn_traversal

    def test_proposal_filename_length_boundary_empirical_finding(self):
        """
        Empirically tests behavior with a 300-character tender_id.
        Finding: get_proposal_filename does not truncate length, producing a 325-character filename.
        On Windows NTFS without long paths enabled, saving this file triggers FileNotFoundError/OSError.
        """
        tender_long = {"tender_id": "X" * 300}
        fn = get_proposal_filename(tender_long)
        assert len(fn) > 300
        # On standard Windows paths, writing a >260 char path causes an error:
        with tempfile.TemporaryDirectory() as td:
            long_path = Path(td) / fn
            with pytest.raises(OSError):
                long_path.write_text("test", encoding="utf-8")


# ============================================================================
# 6. Concurrency, Stress & Multi-Threading Verification
# ============================================================================

class TestMilestone5ConcurrencyStress:
    """Stress tests concurrent CLI evaluation and document tailoring."""

    def test_concurrent_cli_evaluations_thread_safety(self):
        """Tests 16 simultaneous job evaluations across threads for zero cross-talk."""
        roles = [
            "Senior DevOps Engineer with AWS and Kubernetes",
            "Cloud Solutions Architect with Azure and Terraform",
            "Platform Engineer with Docker, Helm, and CI/CD",
            "Linux Systems Administrator with Bash and Networking",
        ]

        def run_eval(idx: int) -> float:
            jd = roles[idx % len(roles)] + f" (batch run {idx})"
            res_code = evaluate_from_stdin(jd)
            assert res_code == 0
            # Direct scorer check
            profile = CandidateProfile()
            from engine.scorer import evaluate_job
            result = evaluate_job(profile, jd)
            return result.overall_score

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            scores = list(executor.map(run_eval, range(16)))

        assert len(scores) == 16
        for score in scores:
            assert 0.0 <= score <= 100.0

    def test_concurrent_tailoring_distinct_directories(self):
        """Tests concurrent tailoring operations writing to separate destination folders."""
        with tempfile.TemporaryDirectory() as base_tmp:
            base_path = Path(base_tmp)
            jd_file = base_path / "sample_jd.txt"
            jd_file.write_text(
                "Seeking DevOps Architect with AWS, Kubernetes, Terraform under 99.9% uptime SLA.",
                encoding="utf-8",
            )

            def tailor_task(worker_id: int) -> int:
                out_dir = base_path / f"worker_{worker_id}"
                return run_cli([
                    "tailor",
                    "--jd", str(jd_file),
                    "--role", "devops",
                    "--output-dir", str(out_dir),
                    "--company", f"Enterprise Corp {worker_id}",
                ])

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                exit_codes = list(executor.map(tailor_task, range(12)))

            assert set(exit_codes) == {0}
            for i in range(12):
                worker_dir = base_path / f"worker_{i}"
                assert worker_dir.is_dir()
                files = list(worker_dir.glob("*.md"))
                assert len(files) == 2, f"Worker {i} must create exactly 2 files (CV & Letter)"

    def test_tender_evaluation_civil_rejection_boundary(self):
        """Verifies civil road/paving tenders strictly score < 35%."""
        civil_rfp = (
            "Regional Ministry tender for road asphalt resurfacing, gravel drainage grading, "
            "and culvert concrete reinforcement."
        )
        res = evaluate_tender(StepconProfile(), civil_rfp)
        assert res.overall_score < 35.0
        assert "Do Not Bid" in res.rationale or "Civil" in res.rationale
