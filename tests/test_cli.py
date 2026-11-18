"""
Comprehensive Unit Test Suite for Milestone 5 Interactive CLI.
Module: tests.test_cli
Feature: F13 (Interactive On-Demand Evaluation CLI)
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from email import policy
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cli.main import (
    create_parser,
    evaluate_from_stdin,
    handle_digest,
    handle_eval,
    handle_tailor,
    run_cli,
)


@pytest.fixture
def sample_jd_text() -> str:
    return (
        "Seeking Senior DevOps Engineer to lead Kubernetes, Terraform, and AWS/Azure cloud estates. "
        "Must maintain 99.9% uptime SLA, automate CI/CD with GitHub Actions, and hold KCNA or AWS certifications."
    )


class TestCliArgumentParser:
    """Verifies CLI argument parsing and subcommand configuration."""

    def test_parser_creation(self):
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "career-automation"

    def test_help_menu_returns_exit_code_zero(self):
        exit_code = run_cli(["--help"])
        assert exit_code == 0

    def test_no_arguments_prints_help_and_returns_zero(self):
        exit_code = run_cli([])
        assert exit_code == 0

    def test_unrecognized_subcommand_returns_nonzero(self):
        exit_code = run_cli(["invalid_subcmd_999"])
        assert exit_code != 0

    def test_digest_live_mode_passes_supported_dispatch_arguments(self, monkeypatch, capsys):
        import scheduler.daily_dispatch as daily_dispatch
        captured = {}

        def fake_run_daily_job(**kwargs):
            captured.update(kwargs)
            return {"status": "success"}

        monkeypatch.setattr(daily_dispatch, "run_daily_job", fake_run_daily_job)
        args = Namespace(
            live=True,
            date="2026-11-18",
            output_dir="output/live_test",
            force=True,
            per_opportunity=True,
        )

        assert handle_digest(args) == 0
        assert captured == {
            "dry_run": False,
            "date_str": "2026-11-18",
            "output_dir": "output/live_test",
            "force": True,
            "per_opportunity_email": True,
        }
        assert json.loads(capsys.readouterr().out) == {"status": "success"}


class TestCliEvalSubcommand:
    """Verifies the 'eval' subcommand with text, files, and boundary conditions."""

    def test_eval_with_text(self, sample_jd_text):
        exit_code = run_cli(["eval", "--text", sample_jd_text])
        assert exit_code == 0

    def test_eval_with_file(self, sample_jd_text, tmp_path):
        jd_file = tmp_path / "test_jd.txt"
        jd_file.write_text(sample_jd_text, encoding="utf-8")
        exit_code = run_cli(["eval", "--file", str(jd_file)])
        assert exit_code == 0

    def test_eval_with_nonexistent_file_returns_nonzero(self):
        exit_code = run_cli(["eval", "--file", "C:/non_existent_path_xyz_9876.txt"])
        assert exit_code != 0

    def test_eval_with_json_output(self, sample_jd_text, capsys):
        exit_code = run_cli(["eval", "--text", sample_jd_text, "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "overall_score" in data
        assert "breakdown" in data
        assert data["overall_score"] >= 70.0

    def test_eval_with_role_override(self, sample_jd_text):
        exit_code = run_cli(["eval", "--text", sample_jd_text, "--role", "Cloud Solutions Architect"])
        assert exit_code == 0

    def test_eval_with_invalid_role_override_handled_safely(self, sample_jd_text):
        exit_code = run_cli(["eval", "--text", sample_jd_text, "--role", "nonexistent_role_xyz"])
        assert exit_code in [0, 1, 2]


class TestCliTailorSubcommand:
    """Verifies the 'tailor' subcommand document generation."""

    def test_tailor_generates_cv_and_letter(self, sample_jd_text, tmp_path):
        jd_file = tmp_path / "target_jd.txt"
        jd_file.write_text(sample_jd_text, encoding="utf-8")
        out_dir = tmp_path / "tailored_output"

        exit_code = run_cli([
            "tailor",
            "--jd", str(jd_file),
            "--role", "devops",
            "--output-dir", str(out_dir),
            "--company", "Enterprise Cloud Inc",
        ])
        assert exit_code == 0
        assert out_dir.exists()
        files = list(out_dir.glob("*.*"))
        assert len(files) >= 2

    def test_tailor_auto_creates_deeply_nested_output_dir(self, sample_jd_text, tmp_path):
        jd_file = tmp_path / "jd.txt"
        jd_file.write_text(sample_jd_text, encoding="utf-8")
        nested_dir = tmp_path / "deeply" / "nested" / "path" / "artifacts"

        exit_code = run_cli([
            "tailor",
            "--jd", str(jd_file),
            "--role", "devops",
            "--output-dir", str(nested_dir),
        ])
        assert exit_code == 0
        assert nested_dir.exists()

    def test_tailor_with_html_format(self, sample_jd_text, tmp_path):
        jd_file = tmp_path / "jd.txt"
        jd_file.write_text(sample_jd_text, encoding="utf-8")
        out_dir = tmp_path / "html_out"

        exit_code = run_cli([
            "tailor",
            "--jd", str(jd_file),
            "--format", "html",
            "--output-dir", str(out_dir),
        ])
        assert exit_code == 0
        html_files = list(out_dir.glob("*.html"))
        assert len(html_files) >= 1


class TestCliStdinEvaluation:
    """Verifies stdin evaluation."""

    def test_evaluate_from_stdin_valid_text(self, sample_jd_text):
        exit_code = evaluate_from_stdin(sample_jd_text)
        assert exit_code == 0

    def test_evaluate_from_stdin_empty_input_returns_nonzero(self):
        exit_code = evaluate_from_stdin("")
        assert exit_code != 0

    def test_evaluate_from_stdin_whitespace_returns_nonzero(self):
        exit_code = evaluate_from_stdin("    \n\t  ")
        assert exit_code != 0


class TestCliStepconSubcommand:
    """Verifies the 'stepcon' subcommand."""

    def test_stepcon_discover_subcommand(self, capsys):
        exit_code = run_cli(["stepcon", "--discover"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "STEPCON SOLUTIONS" in captured.out

    def test_stepcon_discover_json(self, capsys):
        exit_code = run_cli(["stepcon", "--discover", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) >= 1

    def test_stepcon_with_nonexistent_file_returns_nonzero(self):
        exit_code = run_cli(["stepcon", "--file", "C:/non_existent_tender_xyz_9876.txt"])
        assert exit_code == 1

    def test_stepcon_eval_with_text(self, capsys):
        exit_code = run_cli([
            "stepcon",
            "--text",
            "Enterprise RFP for AWS and Azure cloud migration with Kubernetes and 99.9% uptime SLA.",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "STEPCON SOLUTIONS (RC - 8284984): TENDER EVALUATION" in captured.out
        assert "Overall Fit Score:" in captured.out

    def test_stepcon_eval_with_file(self, tmp_path, capsys):
        tender_file = tmp_path / "tender.txt"
        tender_file.write_text(
            "Turnkey cloud architecture on AWS/Azure, Terraform IaC, and Kubernetes orchestration.",
            encoding="utf-8",
        )
        exit_code = run_cli(["stepcon", "--file", str(tender_file)])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "STEPCON SOLUTIONS (RC - 8284984): TENDER EVALUATION" in captured.out

    def test_stepcon_proposal_generation_to_file(self, tmp_path):
        out_dir = tmp_path / "proposals"
        exit_code = run_cli([
            "stepcon",
            "--proposal",
            "Enterprise cloud migration RFP for Kubernetes and Terraform infrastructure.",
            "--client", "Alpha Corp",
            "--output-dir", str(out_dir),
        ])
        assert exit_code == 0
        assert out_dir.exists()
        files = list(out_dir.glob("Proposal_Stepcon_*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "RC - 8284984" in content
        assert "{cac_reg}" not in content



class TestCliApplyAuditAndPdfGeneration:
    """Verifies PDF generation, one-step apply subcommand, audit subcommand, and Cisco CyberOps integration."""

    def test_tailor_pdf_format_creates_valid_pdfs(self, sample_jd_text, tmp_path):
        out_dir = tmp_path / "pdf_out"
        exit_code = run_cli([
            "tailor",
            "--text", sample_jd_text,
            "--format", "pdf",
            "--company", "Gates Foundation",
            "--role", "AI Fellow",
            "--output-dir", str(out_dir),
        ])
        assert exit_code == 0
        pdf_files = list(out_dir.glob("*.pdf"))
        assert len(pdf_files) == 2
        for pf in pdf_files:
            raw = pf.read_bytes()
            assert raw.startswith(b"%PDF-1.")
            assert len(raw) > 500

    def test_apply_subcommand_generates_tied_pdf_package(self, sample_jd_text, tmp_path, capsys):
        out_dir = tmp_path / "apply_out"
        exit_code = run_cli([
            "apply",
            "--text", sample_jd_text,
            "--company", "Gates Foundation",
            "--role", "AI Fellow - Africa Regional Offices",
            "--output-dir", str(out_dir),
            "--email",
            "--json",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["company_name"] == "Gates Foundation"
        assert data["cv_pdf_path"].endswith(".pdf")
        assert data["letter_pdf_path"].endswith(".pdf")
        assert Path(data["cv_pdf_path"]).is_file()
        assert Path(data["letter_pdf_path"]).is_file()
        assert Path(data["cv_md_path"]).is_file()
        assert Path(data["letter_md_path"]).is_file()
        assert Path(data["cv_docx_path"]).is_file()
        assert Path(data["letter_docx_path"]).is_file()
        assert Path(data["cv_pdf_path"]).name == "John Aniekwe Gates Foundation CV.pdf"
        with ZipFile(data["cv_docx_path"]) as document:
            assert "John Victor Aniekwe" in document.read("word/document.xml").decode("utf-8")
        assert data["email_dispatched"] is True
        email_files = list(out_dir.glob("*.eml"))
        assert len(email_files) == 1
        message = BytesParser(policy=policy.default).parsebytes(email_files[0].read_bytes())
        attachment_names = {part.get_filename() for part in message.iter_attachments()}
        assert Path(data["cv_pdf_path"]).with_suffix(".docx").name in attachment_names
        assert Path(data["letter_pdf_path"]).with_suffix(".docx").name in attachment_names

    def test_feedback_cli_records_aggregate_preference(self, tmp_path, capsys):
        state_file = tmp_path / "feedback.json"
        exit_code = run_cli([
            "feedback",
            "--role", "Cloud Engineer",
            "--outcome", "interested",
            "--state-file", str(state_file),
        ])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["recorded_counts"] == {"interested": 1}
        assert json.loads(state_file.read_text(encoding="utf-8"))["roles"]["Cloud Engineer"]["interested"] == 1

    def test_audit_subcommand_json_and_markdown(self, tmp_path, capsys):
        exit_code = run_cli(["audit", "--output-dir", str(tmp_path), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_opportunities_evaluated"] >= 1
        assert "optimization_recommendations" in data

    def test_cisco_cyberops_in_single_source_of_truth(self):
        from ingestion.parser import load_profile
        profile = load_profile(allow_fallback=False)
        cert_names = [c.name for c in profile.certifications]
        assert any("Cisco Certified CyberOps Associate" in n for n in cert_names)
        assert not any("ITIL" in n for n in cert_names)

    def test_rebuild_subcommand_from_markdown(self, capsys):
        exit_code = run_cli(["rebuild", "--opportunity", "Gates_Foundation", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "Gates_Foundation" in data["folder_name"]
        assert len(data["rebuilt_documents"]) >= 2
        for doc in data["rebuilt_documents"]:
            assert doc["status"] == "success"
            assert doc["pages"] in (1, 2, 3)

    def test_correct_subcommand_find_and_replace(self, capsys):
        exit_code = run_cli([
            "correct",
            "--opportunity", "Gates_Foundation",
            "--find", "tcpdump",
            "--replace", "tcpdump",
            "--json",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "success"
        assert len(data["rebuilt"]) >= 2
