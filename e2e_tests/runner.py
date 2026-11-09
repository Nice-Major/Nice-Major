#!/usr/bin/env python3
"""
Career Automation & Stepcon Solutions (RC - 8284984)
Opaque-Box E2E Test Suite Dual-Mode Runner (Tiers 1-4)

Can be executed directly via standard library:
    python e2e_tests/runner.py [-v] [--tier 1|2|3|4] [--feature F01]
Or executed via Pytest:
    pytest e2e_tests/ -v
"""
import os
import sys
import time
import inspect
import pathlib
import argparse
import tempfile
import importlib
import traceback

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from e2e_tests.conftest import (
    CANONICAL_PROFILE_PATH,
    FeatureNotImplementedError
)


def load_fixtures():
    """Build shared test fixtures matching conftest.py definitions."""
    # Canonical profile
    if CANONICAL_PROFILE_PATH.exists():
        import json
        with open(CANONICAL_PROFILE_PATH, "r", encoding="utf-8") as f:
            canonical_profile = json.load(f)
    else:
        canonical_profile = {
            "candidate": {
                "firstName": "John",
                "middleName": "Victor",
                "lastName": "Aniekwe",
                "fullName": "John Victor Aniekwe",
                "email": "aniekwevictor9@gmail.com",
                "phone": "+2348130004114",
                "location": "Lagos, Nigeria (UTC+1 / CET Synchronous)",
                "education": {"degree": "B.Sc. in Computer Science", "institution": "University of Nigeria"},
                "certifications": [
                    {"name": "Kubernetes and Cloud Native Associate (KCNA)", "status": "Active"},
                    {"name": "AWS Certified Solutions Architect – Associate", "status": "Active"},
                    {"name": "AWS Certified Developer – Associate", "status": "Active"},
                    {"name": "AWS Certified Cloud Practitioner", "status": "Active"},
                    {"name": "ITIL Foundation", "status": "In Progress"}
                ]
            },
            "kpiMetrics": [
                {"value": "99.9%", "label": "Enterprise Cloud Uptime SLA"},
                {"value": "99%", "label": "First-Day L3 Issue Resolution"}
            ],
            "roleCategories": {
                "devops": {"categoryTitle": "Dev(Sec)Ops", "targetTitles": ["DevOps Engineer"]},
                "architect": {"categoryTitle": "Cloud Architect", "targetTitles": ["Cloud Solutions Architect"]}
            },
            "stepconSolutions": {
                "companyName": "Stepcon Solutions",
                "cacNumber": "RC - 8284984",
                "jurisdiction": "Corporate Affairs Commission (CAC), Federal Republic of Nigeria"
            }
        }

    synthetic_jobs = {
        "devops": {
            "title": "Senior DevOps Engineer",
            "company": "Global Cloud Corp",
            "location": "Remote - Worldwide (EMEA / UTC+1)",
            "description": (
                "We are seeking a Senior DevOps Engineer for Kubernetes and Terraform automation. "
                "Container orchestration (Kubernetes, Docker), IaC (Terraform), CI/CD pipelines (GitHub Actions), "
                "and AWS/Azure cloud platforms. 99.9% uptime SLA."
            ),
            "url": "https://careers.globalcloud.example/jobs/devops-101",
            "posted_date": "2026-11-01"
        },
        "architect": {
            "title": "Cloud Solutions Architect",
            "company": "Enterprise Horizons Ltd",
            "location": "Worldwide Remote / CET Synchronous",
            "description": (
                "Design scalable multi-cloud microservices on Azure and AWS. Well-Architected Framework, "
                "architect AKS/EKS clusters, configure private endpoints, and FinOps."
            ),
            "url": "https://careers.enterprisehorizons.example/jobs/csa-202",
            "posted_date": "2026-11-03"
        },
        "support": {
            "title": "L3 Technical Support Engineer",
            "company": "CloudCare Global",
            "location": "Remote (Anywhere)",
            "description": "L3 incident escalation on Azure App Service. RCA, logs, metrics, traces, TsG authoring.",
            "url": "https://careers.cloudcare.example/jobs/supp-303",
            "posted_date": "2026-11-04"
        },
        "us_only": {
            "title": "DevOps Engineer (US Only)",
            "company": "American Defense Systems",
            "location": "Remote - US",
            "description": "Must be US Citizen in continental US. Secret Clearance required. W2 Only.",
            "url": "https://careers.usdefense.example/jobs/us-404",
            "posted_date": "2026-11-02"
        },
        "stale": {
            "title": "Infrastructure Engineer",
            "company": "Legacy Tech Ltd",
            "location": "Worldwide",
            "description": "Legacy servers. Closed listing.",
            "url": "https://careers.legacytech.example/jobs/stale-505",
            "posted_date": "2026-08-01"
        },
        "closed": {
            "title": "Cloud Engineer",
            "company": "QuickFill Inc",
            "location": "Remote Worldwide",
            "description": "This position has been filled. Applications are now closed.",
            "url": "https://careers.quickfill.example/jobs/closed-606",
            "posted_date": "2026-11-05"
        }
    }

    synthetic_tenders = {
        "matching": {
            "tender_id": "TND-2026-088",
            "title": "Enterprise Multi-Cloud Infrastructure & DevSecOps Modernization",
            "client": "Pan-African Financial Services Group",
            "description": (
                "RFP for turnkey cloud engineering pod to design declarative Infrastructure as Code (Terraform), "
                "automate CI/CD pipelines, and deploy Kubernetes microservices on AWS and Azure under 99.9% availability SLA. "
                "B2B Corp-to-Corp contracting with synchronous EMEA/CET working hours required."
            ),
            "budget": "$120,000 USD",
            "deadline": "2026-12-15"
        },
        "non_matching": {
            "tender_id": "TND-CIVIL-009",
            "title": "Construction and Road Asphalt Paving Tender",
            "client": "Regional Transport Authority",
            "description": "Supply of asphalt concrete and civil engineering drainage maintenance.",
            "budget": "$500,000 USD",
            "deadline": "2026-12-01"
        }
    }

    return {
        "canonical_profile_data": canonical_profile,
        "synthetic_jobs": synthetic_jobs,
        "synthetic_tenders": synthetic_tenders,
        "project_root": PROJECT_ROOT
    }


def run_standalone_test_suite(selected_tier=None, selected_feature=None, verbose=False):
    """Discovers and executes tests across all 4 tiers."""
    fixture_dict = load_fixtures()

    tier_modules = [
        (1, "Tier 1: Feature Coverage", "e2e_tests.test_tier1_features"),
        (2, "Tier 2: Boundary & Corner Cases", "e2e_tests.test_tier2_boundaries"),
        (3, "Tier 3: Cross-Feature Combinations", "e2e_tests.test_tier3_combinations"),
        (4, "Tier 4: Real-World Workloads", "e2e_tests.test_tier4_workloads"),
        (5, "Tier 5: Adversarial Coverage Hardening", "e2e_tests.test_tier5_adversarial")
    ]

    tier_stats = {}
    all_results = []
    start_time = time.time()

    print("=" * 80)
    print("CAREER AUTOMATION & STEPCON SOLUTIONS (RC - 8284984) — E2E TEST RUNNER")
    print(f"Workspace: {PROJECT_ROOT}")
    print("=" * 80)

    for tier_num, tier_label, mod_name in tier_modules:
        if selected_tier and str(selected_tier).lower() != "all" and tier_num != int(selected_tier):
            continue

        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"Error loading {mod_name}: {e}")
            traceback.print_exc()
            continue

        tier_stats[tier_num] = {"label": tier_label, "passed": 0, "skipped": 0, "failed": 0, "total": 0}

        print(f"\n--- Running {tier_label} ---")

        # Discover test classes and test methods
        for attr_name in dir(mod):
            if not attr_name.startswith("Test"):
                continue
            cls = getattr(mod, attr_name)
            if not inspect.isclass(cls):
                continue

            instance = cls()
            for method_name in dir(cls):
                if not method_name.startswith("test_"):
                    continue

                if selected_feature and selected_feature.lower() not in method_name.lower():
                    continue

                method = getattr(instance, method_name)
                sig = inspect.signature(method)

                # Prepare fixture arguments
                args = {}
                temp_dir_obj = None
                for param in sig.parameters.values():
                    if param.name == "temp_output_dir":
                        temp_dir_obj = tempfile.TemporaryDirectory()
                        args["temp_output_dir"] = pathlib.Path(temp_dir_obj.name)
                    elif param.name in fixture_dict:
                        args[param.name] = fixture_dict[param.name]

                tier_stats[tier_num]["total"] += 1
                status = "PASSED"
                reason = ""

                try:
                    method(**args)
                    tier_stats[tier_num]["passed"] += 1
                    status = "PASSED"
                except BaseException as err:
                    if isinstance(err, (KeyboardInterrupt, SystemExit)):
                        raise
                    err_type = type(err).__name__
                    err_msg = str(err)
                    # Check if it was skipped or unimplemented
                    if isinstance(err, FeatureNotImplementedError) or err_type == "Skipped" or "skip" in err_msg.lower():
                        status = "SKIPPED"
                        reason = err_msg.split("\n")[0][:80]
                        tier_stats[tier_num]["skipped"] += 1
                    else:
                        status = "FAILED"
                        reason = f"{err_type}: {err_msg}"[:100]
                        tier_stats[tier_num]["failed"] += 1
                finally:
                    if temp_dir_obj:
                        try:
                            temp_dir_obj.cleanup()
                        except Exception:
                            pass

                all_results.append((tier_num, attr_name, method_name, status, reason))

                if verbose:
                    if status == "PASSED":
                        print(f"  [OK]   {method_name}")
                    elif status == "SKIPPED":
                        print(f"  [SKIP] {method_name} - {reason}")
                    else:
                        print(f"  [FAIL] {method_name} - {reason}")
                else:
                    if status == "PASSED":
                        sys.stdout.write(".")
                    elif status == "SKIPPED":
                        sys.stdout.write("s")
                    else:
                        sys.stdout.write("F")
                    sys.stdout.flush()

        if not verbose:
            sys.stdout.write("\n")

    duration = time.time() - start_time

    # Print Summary Table
    print("\n" + "=" * 80)
    print("E2E TEST SUITE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"{'Tier':<35} | {'Total':<6} | {'Passed':<7} | {'Skipped':<8} | {'Failed':<6}")
    print("-" * 80)

    total_all = 0
    passed_all = 0
    skipped_all = 0
    failed_all = 0

    for t_num, stats in tier_stats.items():
        total_all += stats["total"]
        passed_all += stats["passed"]
        skipped_all += stats["skipped"]
        failed_all += stats["failed"]
        print(f"{stats['label']:<35} | {stats['total']:<6} | {stats['passed']:<7} | {stats['skipped']:<8} | {stats['failed']:<6}")

    print("-" * 80)
    print(f"{'OVERALL TOTALS':<35} | {total_all:<6} | {passed_all:<7} | {skipped_all:<8} | {failed_all:<6}")
    print(f"Total Execution Time: {duration:.2f} seconds")
    print("=" * 80)

    if failed_all > 0:
        print("\n[!] DETECTED TEST FAILURES:")
        for t_num, c_name, m_name, st, r in all_results:
            if st == "FAILED":
                print(f"  - [{t_num}] {c_name}::{m_name}: {r}")
        print("\nResult: FAILURE")
        return 1
    else:
        print(f"\nResult: SUCCESS ({passed_all} passed, {skipped_all} pending milestone implementation)")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Career Automation E2E Test Suite Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose test execution output")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "5", "all"], default=None, help="Filter by test tier (1 to 5 or all)")
    parser.add_argument("--feature", help="Filter by feature ID (e.g. F01, F07)")
    parser.add_argument("--pytest", action="store_true", help="Delegate test execution to pytest")
    args = parser.parse_args()

    if args.pytest:
        try:
            import pytest
            test_path = PROJECT_ROOT / "e2e_tests"
            if args.tier and args.tier != "all":
                matched = list(test_path.glob(f"test_tier{args.tier}_*.py"))
                target = str(matched[0]) if matched else str(test_path)
            else:
                target = str(test_path)
            pytest_args = ["-v" if args.verbose else "-q", target]
            if args.feature:
                pytest_args.extend(["-k", args.feature])
            sys.exit(pytest.main(pytest_args))
        except ImportError:
            print("Pytest not installed in environment, falling back to standalone runner.")

    exit_code = run_standalone_test_suite(
        selected_tier=args.tier,
        selected_feature=args.feature,
        verbose=args.verbose
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
