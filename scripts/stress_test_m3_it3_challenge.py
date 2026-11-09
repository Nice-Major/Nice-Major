"""
Milestone 3 Iteration 3 Adversarial Challenge & Stress Test Harness.
Script: scripts/stress_test_m3_it3_challenge.py
Author: challenger_m3_it3_1

Empirically tests discovery/filters.py and discovery/sources.py against:
1. Pronoun torture tests ("us only" in various grammatical positions)
2. Anchored domestic locks ("Location: US only", "(US Only)", "Remote: US", etc.)
3. Visa sponsorship vs negative benefits statements
4. Empty/malformed opportunity dictionaries in deduplication
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from discovery.filters import (
    has_disqualifiers,
    is_remote_eligible,
    detect_visa_sponsorship,
    detect_contract_c2c,
)
from discovery.sources import deduplicate_opportunities


def test_pronoun_torture() -> Tuple[int, int, List[str]]:
    """Test English sentences containing 'us only' in various grammatical contexts."""
    cases = [
        "Contact us only via email for initial screening.",
        "Contact us only",
        "Join us only if you are passionate about cloud infrastructure and reliability engineering!",
        "Join us only if",
        "Tell us only about your cloud experience",
        "Tell us only your relevant certifications.",
        "Reach us only on Slack for emergency escalations.",
        "Write us only when available.",
        "Ask us only technical questions during the assessment.",
        "Trust us only for mission-critical Kubernetes deployments.",
        "Ping us only during working hours.",
        "Between us only, this is a top-priority initiative.",
        "Allow us only 24 hours to review your resume.",
        "Send us only PDF resumes with ATS formatting.",
        "Help us only with frontend infrastructure issues.",
        "Show us only recent projects within the last 3 years.",
        "Remind us only once before scheduling.",
        "Notify us only of critical alerts.",
        "Follow us only on our official GitHub page.",
        "Give us only your primary email address.",
        "Provide us only relevant references from previous engineering leads.",
        "Grant us only read-only access to your public repositories.",
        "Partner with us only if you adhere to DevOps best practices.",
        "Email us only at careers@example.com.",
        "Message us only through the secure candidate portal.",
    ]
    passed = 0
    failed = []
    for c in cases:
        if not has_disqualifiers(c):
            passed += 1
        else:
            failed.append(c)
    return passed, len(failed), failed


def test_anchored_domestic_locks() -> Tuple[int, int, List[str]]:
    """Test actual US-only and Canada-only domestic locks that MUST be disqualified."""
    cases = [
        "Location: US only",
        "Location: US Only",
        "location: u.s. only",
        "Location: USA only",
        "Location: United States only",
        "(US Only)",
        "(US only)",
        "[US Only]",
        "[US only]",
        "(U.S. Only)",
        "[U.S. Only]",
        "Remote: US",
        "Remote: US only",
        "Remote: USA",
        "Remote: United States",
        "Remote | US",
        "Remote | USA",
        "Remote | United States",
        "Remote: Canada",
        "Remote | Canada",
        "Remote in Canada",
        "Remote in the US",
        "Remote in the United States",
        "USA only",
        "U.S. only",
        "United States only",
        "Canada only",
        "Remote (US)",
        "Remote [US]",
        "Remote (Canada)",
        "Remote [Canada]",
        "Remote (US/Canada)",
        "Remote (US or Canada)",
        "Must reside in the US",
        "Must reside in Canada",
        "Must reside in North America",
        "100% On-site",
        "Active TS/SCI clearance",
        "Strictly W2",
        "No C2C",
        "This role is non-remote",
        "Remote work is not permitted",
        "Not a remote role",
        "Senior DevOps Engineer\nUS only\nApply here",
        "Title: Senior DevOps\nWorkplace: Remote\nEligibility: US only",
    ]
    passed = 0
    failed = []
    for c in cases:
        if has_disqualifiers(c):
            passed += 1
        else:
            failed.append(c)
    return passed, len(failed), failed


def test_visa_sponsorship_positive_and_negative() -> Tuple[int, int, List[Tuple[str, str, bool, bool]]]:
    """Test positive visa sponsorship with negative benefits statements and explicit negations."""
    positive_cases = [
        ("Visa sponsorship available. No relocation bonus.", True),
        ("We sponsor visas. We cannot provide housing.", True),
        ("Visa sponsorship offered. We do not provide equipment.", True),
        ("We provide visa sponsorship. We do not offer health insurance.", True),
        ("Skilled worker visa available. We cannot offer sign-on bonuses.", True),
        ("Full visa sponsorship provided. No company car provided.", True),
        ("We offer relocation assistance and visa sponsorship. Note that we do not offer stock options.", True),
        ("We sponsor work visas. We will not provide gym membership.", True),
        ("Visa support provided. Cannot provide travel reimbursement.", True),
        ("Will sponsor visas. Does not provide daycare.", True),
        ("We offer full UK Skilled Worker visa sponsorship. Note that we do not offer remote work.", True),
        ("We provide visa sponsorship for international hires. We cannot offer equity.", True),
        ("Full visa sponsorship provided! Note: we do not offer company cars.", True),
        ("We offer relocation assistance and visa support. We do not provide transit passes.", True),
        ("Visa sponsorship available for outstanding candidates. Note: our company does not offer dental insurance.", True),
        ("We offer visa sponsorship. No relocation assistance provided.", True),
        ("We sponsor visas for qualified international applicants.", True),
        ("Company sponsors visas for this opening.", True),
    ]

    negative_cases = [
        ("No visa sponsorship provided.", False),
        ("We cannot provide visa sponsorship.", False),
        ("Will not sponsor visas.", False),
        ("Visa sponsorship is not available.", False),
        ("Without the need for visa sponsorship.", False),
        ("Must have valid work authorization without sponsorship.", False),
        ("This position does not offer visa support.", False),
        ("Zero visa sponsorship.", False),
    ]

    all_cases = positive_cases + negative_cases
    passed = 0
    failed = []

    for text, expected in all_cases:
        actual = detect_visa_sponsorship(text)
        if actual == expected:
            passed += 1
        else:
            failed.append((text, "positive" if expected else "negative", expected, actual))

    return passed, len(failed), failed


def test_deduplication_malformed_and_edge_cases() -> Tuple[int, int, List[str]]:
    """Test deduplicate_opportunities with edge cases, malformed dicts, and mixed types."""
    tests = []

    # Test 1: Empty inputs
    t1_pass = (deduplicate_opportunities([]) == []) and (deduplicate_opportunities(None) == [])
    tests.append(("Empty and None list", t1_pass))

    # Test 2: List with None items
    t2 = deduplicate_opportunities([None, None])
    tests.append(("List of Nones", t2 == []))

    # Test 3: List of identical empty dicts
    t3 = deduplicate_opportunities([{}, {}])
    tests.append(("Duplicate empty dicts", len(t3) == 1))

    # Test 4: Dict with all None values
    d_none = {"id": None, "company": None, "title": None, "url": None}
    t4 = deduplicate_opportunities([d_none, d_none])
    tests.append(("Dict with all None values", len(t4) == 1))

    # Test 5: Distinct opportunities with empty company and title, distinct URLs
    o1 = {"id": "1", "company": "", "title": "", "url": "https://careers.example.com/job1"}
    o2 = {"id": "2", "company": "", "title": "", "url": "https://careers.example.com/job2"}
    t5 = deduplicate_opportunities([o1, o2])
    tests.append(("Distinct jobs with empty company/title and distinct URLs", len(t5) == 2))

    # Test 6: Same URL with empty company/title must merge
    o3 = {"id": "3", "company": "", "title": "", "url": "https://careers.example.com/job1"}
    t6 = deduplicate_opportunities([o1, o3])
    tests.append(("Same URL with empty company/title merges", len(t6) == 1))

    # Test 7: Distinct opportunities with empty company, title, URL, distinct IDs
    o_id1 = {"id": "uuid-1", "company": "", "title": "", "url": ""}
    o_id2 = {"id": "uuid-2", "company": "", "title": "", "url": ""}
    t7 = deduplicate_opportunities([o_id1, o_id2])
    tests.append(("Distinct IDs with empty company/title/url preserved", len(t7) == 2))

    # Test 8: Whitespace variations in company and title must merge
    w1 = {"id": "w1", "company": "  Google  Cloud  ", "title": "DevOps   Engineer  ", "url": "https://1"}
    w2 = {"id": "w2", "company": "Google Cloud", "title": "DevOps Engineer", "url": "https://2"}
    t8 = deduplicate_opportunities([w1, w2])
    tests.append(("Internal and trailing whitespace deduplication", len(t8) == 1))

    # Test 9: Malformed dict with mixed key types (int and str)
    try:
        mixed_dict = {1: "one", "two": 2}
        t9 = deduplicate_opportunities([mixed_dict])
        tests.append(("Malformed dict with mixed key types (no crash)", len(t9) == 1))
    except Exception as e:
        tests.append((f"Malformed dict with mixed key types crashed: {type(e).__name__}: {e}", False))

    passed = sum(1 for name, ok in tests if ok)
    failed = [name for name, ok in tests if not ok]
    return passed, len(failed), failed


def run_all():
    print("=" * 80)
    print("CHALLENGER ADVERSARIAL STRESS TEST SUITE — MILESTONE 3 ITERATION 3")
    print("=" * 80)

    # 1. Pronoun torture
    p_pass, p_fail_count, p_failed = test_pronoun_torture()
    print(f"\n[1] Pronoun Torture Tests: {p_pass} PASSED, {p_fail_count} FAILED")
    if p_failed:
        print("    Failures:")
        for f in p_failed:
            print(f"      - {f}")

    # 2. Anchored domestic locks
    d_pass, d_fail_count, d_failed = test_anchored_domestic_locks()
    print(f"\n[2] Anchored Domestic Lock Tests: {d_pass} PASSED, {d_fail_count} FAILED")
    if d_failed:
        print("    Failures:")
        for f in d_failed:
            print(f"      - {f}")

    # 3. Visa sponsorship
    v_pass, v_fail_count, v_failed = test_visa_sponsorship_positive_and_negative()
    print(f"\n[3] Visa Sponsorship & Benefits Negation Tests: {v_pass} PASSED, {v_fail_count} FAILED")
    if v_failed:
        print("    Failures:")
        for text, category, exp, act in v_failed:
            print(f"      - [{category}] Expected {exp}, got {act}: {text!r}")

    # 4. Deduplication
    m_pass, m_fail_count, m_failed = test_deduplication_malformed_and_edge_cases()
    print(f"\n[4] Deduplication Malformed & Edge Cases: {m_pass} PASSED, {m_fail_count} FAILED")
    if m_failed:
        print("    Failures:")
        for f in m_failed:
            print(f"      - {f}")

    total_pass = p_pass + d_pass + v_pass + m_pass
    total_fail = p_fail_count + d_fail_count + v_fail_count + m_fail_count
    print("\n" + "=" * 80)
    print(f"OVERALL RESULTS: {total_pass} PASSED, {total_fail} FAILED (TOTAL {total_pass + total_fail})")
    print("=" * 80)

    if total_fail > 0:
        print(f"VERDICT: REQUEST_CHANGES ({total_fail} empirical failures detected)")
        return 1
    else:
        print("VERDICT: APPROVE (all empirical adversarial tests passed)")
        return 0


if __name__ == "__main__":
    sys.exit(run_all())
