"""
Interactive Command-Line Interface Package.
Module: cli
Feature: F13 (Interactive On-Demand Evaluation CLI)
Milestone: M5 (Interactive CLI & Stepcon Solutions Pipeline)
"""

from __future__ import annotations

from cli.main import (
    create_parser,
    evaluate_from_stdin,
    main,
    run_cli,
)

__all__ = [
    "create_parser",
    "run_cli",
    "evaluate_from_stdin",
    "main",
]
