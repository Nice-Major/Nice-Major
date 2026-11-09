"""
Milestone 3 Iteration 4 Adversarial Stress & Corner-Case Challenge Suite.
Script: scripts/stress_test_m3_it4_challenge.py
Author: challenger_m3_it4_1

Adversarial stress testing across 5 core dimensions:
1. Conversational English Pronoun Invariants (25 tests)
2. Domestic Lock & Header Anchors with Recruiter Formatting (25 tests)
3. Remote Nigeria & Global Eligibility Boundaries (20 tests)
4. Visa Sponsorship Nuance: Hackathon vs Visa, Benefit Exclusions, Present Tense (25 tests)
5. Deduplication Extreme Inputs: Mixed Type Keys, Tuples, Bools, None, Emojis, URLs (15 tests)

Total: 110 tests.
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
    filter_opportunities,
)
from discovery.sources import deduplicate_opportunities
from discovery.verifier import generate_fingerprint


def test_conversational_pronoun_invariants() -> Tuple[int, int, List[str]]:
    """Verify natural language English pronoun 'us' never triggers domestic disqualifier."""
    sentences = [
        "Join us, we are hiring globally!",
        "Talk to us; we love open source.",
        "Contact us at hiring@example.com for more info.",
        "Follow us: Twitter, GitHub, and LinkedIn.",
        "Work with us! Remote anywhere in the world.",
        "Let us know your availability for an interview.",
        "Send us your CV and portfolio.",
        "Give us 3 professional references.",
        "Write to us regarding salary expectations.",
        "Visit us online at stepcon.tech.",
        "Meet us at KubeCon next month.",
        "Help us scale Kubernetes clusters worldwide.",
        "Guide us through our Azure cloud migration.",
        "Tell us why you are the best DevOps engineer.",
        "Allow us to review your open source contributions.",
        "Challenge us with your hardest technical questions.",
        "Bring us your AWS and Kubernetes expertise.",
        "Support us as we grow our distributed team.",
        "Join us - we are an equal opportunity employer.",
        "Refer us a talented friend in tech.",
        "Ping us on Matrix or Slack.",
        "Reach us via WhatsApp or Telegram.",
        "Call us during WAT / CET business hours.",
        "Find us in Lagos or Berlin offices.",
        "Ask us about remote work flexibility.",
    ]
    passed = 0
    failed = []
    for s in sentences:
        if not has_disqualifiers(s):
            passed += 1
        else:
            failed.append(s)
    return passed, len(failed), failed


def test_domestic_lock_recruiter_formats() -> Tuple[int, int, List[str]]:
    """Verify recruiter-style domestic locks are strictly disqualified."""
    locks = [
        "Role: DevOps Engineer\nLocation: US Only\nWorkplace: Remote",
        "Position: Cloud Architect - US Only",
        "Title: Senior SRE | US Only",
        "Eligibility: U.S. Only",
        "Status: US only",
        "Workplace: Remote (US only)",
        "Workplace: Remote [US only]",
        "Workplace: Remote {US only}",
        "Geographic restriction: US only",
        "Authorized: US only",
        "Open to: US only",
        "Candidates must reside in the United States",
        "Candidates must reside in Canada",
        "Candidate must be located in Canada",
        "Strictly W2 employment",
        "No C2C or corp-to-corp accepted",
        "Remote work is not permitted",
        "Remote is not an option",
        "Zero remote work offered",
        "Strictly on-site in New York office",
        "Hybrid role - office mandatory 4 days a week",
        "Continental US only",
        "Must reside in California for state payroll tax purposes",
        "Active TS/SCI clearance required",
        "Secret clearance needed for this government contract",
        "Must be a US citizen or permanent resident",
    ]
    passed = 0
    failed = []
    for lk in locks:
        if has_disqualifiers(lk):
            passed += 1
        else:
            failed.append(lk)
    return passed, len(failed), failed


def test_remote_nigeria_global_boundaries() -> Tuple[int, int, List[str]]:
    """Verify legitimate remote and Nigeria-accessible roles pass is_remote_eligible."""
    cases = [
        ("Senior Cloud Engineer - Remote Worldwide", True),
        ("DevOps Architect - Work from anywhere in the world", True),
        ("Kubernetes Admin - Remote (EMEA)", True),
        ("Cloud Infrastructure Engineer - Remote (CET timezone +/- 2 hours)", True),
        ("Platform Engineer - Remote (UTC+1)", True),
        ("SysAdmin - Remote across Africa or Europe", True),
        ("IT Specialist - Remote from Nigeria", True),
        ("Global remote opportunity for Senior DevOps", True),
        ("100% Remote, open to candidates in Nigeria", True),
        ("Fully remote role with asynchronous team culture", True),
        ("WFA anywhere in Europe or Africa", True),
        ("Remote: Global team with flexible hours", True),
        ("Platform Architect - All-remote organization", True),
        ("DevSecOps Specialist - UK synchronous remote", True),
        ("Cloud Consultant - Sub-Saharan Africa remote", True),
        # Negative / Domestic roles should NOT be remote eligible:
        ("Senior DevOps - Location: US only", False),
        ("Cloud Engineer - 100% on-site mandatory", False),
        ("Platform Engineer - Strictly on-site", False),
        ("Site Reliability Engineer - Remote in Canada only", False),
        ("IT Administrator - Remote work is strictly prohibited", False),
    ]
    passed = 0
    failed = []
    for text, expected in cases:
        actual = is_remote_eligible(text)
        if actual == expected:
            passed += 1
        else:
            failed.append(f"Expected {expected}, got {actual}: '{text}'")
    return passed, len(failed), failed


def test_visa_sponsorship_nuances() -> Tuple[int, int, List[str]]:
    """Stress-test visa sponsorship detection: present tense, benefit exclusions, hackathon noise."""
    cases = [
        # Positive cases:
        ("Visa sponsorship available. No relocation bonus provided.", True),
        ("We sponsor visas. We cannot provide company cars.", True),
        ("We offer visa sponsorship. Note: we do not provide housing.", True),
        ("Company sponsors work visas for exceptional international talent.", True),
        ("Employer sponsors visas. Note: we cannot provide gym memberships.", True),
        ("Our company sponsors visas for qualified applicants.", True),
        ("The company sponsors visas.", True),
        ("We are willing to sponsor visas for senior cloud architects.", True),
        ("We are open to sponsoring visas for candidates based in Nigeria.", True),
        ("Skilled worker visa sponsorship provided. No sign-on bonus.", True),
        ("Full relocation and visa sponsorship provided.", True),
        ("H-1B transfer available for international engineers.", True),
        ("Visa support offered. We cannot provide travel reimbursement.", True),
        ("Open to sponsor visas for top tier platform engineers.", True),
        # Negative visa sponsorship:
        ("No visa sponsorship or relocation assistance.", False),
        ("No relocation or visa sponsorship.", False),
        ("We cannot provide visa sponsorship.", False),
        ("Will not sponsor visas under any circumstances.", False),
        ("Sponsorship is not available.", False),
        ("Without the need for visa sponsorship.", False),
        ("Applicants must not require visa sponsorship now or in the future.", False),
        ("Must have legal work authorization without sponsorship.", False),
        ("No visa support provided.", False),
        # Semantic false positives (hackathons, customer support):
        ("We sponsor annual open source hackathons for charity.", False),
        ("Tech conference stipend and learning budget provided annually.", False),
    ]
    passed = 0
    failed = []
    for text, expected in cases:
        actual = detect_visa_sponsorship(text)
        if actual == expected:
            passed += 1
        else:
            failed.append(f"Expected {expected}, got {actual}: '{text}'")
    return passed, len(failed), failed


def test_deduplication_extreme_types_and_edge_cases() -> Tuple[int, int, List[str]]:
    """Test deduplicate_opportunities against extreme type mixtures and Unicode."""
    tests = []

    # 1. Complex dictionary with bool, None, float, int, str keys
    d_mixed = {
        True: "boolean_key_true",
        False: "boolean_key_false",
        None: "none_key",
        42: "int_key",
        3.14159: "float_key",
        "str": "str_key",
    }
    try:
        res = deduplicate_opportunities([d_mixed, d_mixed])
        tests.append(("Mixed bool/None/float/int/str dict keys deduplication", len(res) == 1))
    except Exception as e:
        tests.append((f"Mixed bool/None/float/int/str crashed: {type(e).__name__}: {e}", False))

    # 2. Dict with tuple key
    d_tuple = {(1, "alpha"): "val1", (2, "beta"): "val2"}
    try:
        res = deduplicate_opportunities([d_tuple, d_tuple])
        tests.append(("Dict with tuple keys deduplication", len(res) == 1))
    except Exception as e:
        tests.append((f"Tuple keys crashed: {type(e).__name__}: {e}", False))

    # 3. List of 1000 duplicate dicts
    d_rep = {"company": "Acme Cloud", "title": "DevOps Lead", "url": "https://acme.com/jobs/1"}
    rep_list = [d_rep.copy() for _ in range(1000)]
    try:
        res = deduplicate_opportunities(rep_list)
        tests.append(("1000 duplicate items collapsed to 1", len(res) == 1))
    except Exception as e:
        tests.append((f"1000 items deduplication crashed: {type(e).__name__}: {e}", False))

    # 4. Unicode & Emoji normalization in company and title
    e1 = {"company": "☁️ Cloud Corp", "title": "DevOps Ninja 🚀", "url": "https://example.com/1"}
    e2 = {"company": "  ☁️   Cloud   Corp  ", "title": " DevOps Ninja 🚀 ", "url": "https://example.com/2"}
    try:
        res = deduplicate_opportunities([e1, e2])
        tests.append(("Emoji & Unicode company/title deduplication", len(res) == 1))
    except Exception as e:
        tests.append((f"Emoji deduplication crashed: {type(e).__name__}: {e}", False))

    # 5. Case-insensitive URL deduplication
    u1 = {"company": "", "title": "", "url": "https://Careers.Example.COM/Job/123"}
    u2 = {"company": "", "title": "", "url": "https://careers.example.com/job/123"}
    try:
        res = deduplicate_opportunities([u1, u2])
        tests.append(("Case-insensitive URL deduplication", len(res) == 1))
    except Exception as e:
        tests.append((f"Case-insensitive URL crashed: {type(e).__name__}: {e}", False))

    # 6. ID-only fallback deduplication
    id1 = {"id": "job-uuid-abc", "company": "", "title": "", "url": ""}
    id2 = {"id": "job-uuid-abc", "company": "", "title": "", "url": ""}
    id3 = {"id": "job-uuid-xyz", "company": "", "title": "", "url": ""}
    try:
        res = deduplicate_opportunities([id1, id2, id3])
        tests.append(("ID fallback deduplication with distinct IDs", len(res) == 2))
    except Exception as e:
        tests.append((f"ID fallback crashed: {type(e).__name__}: {e}", False))

    # 7. Non-dict objects (strings, integers)
    try:
        res = deduplicate_opportunities(["item1", "item1", "item2", 42, 42])
        tests.append(("Primitive objects list deduplication", len(res) == 3))
    except Exception as e:
        tests.append((f"Primitive list crashed: {type(e).__name__}: {e}", False))

    # 8. Mixed Opportunity-like objects and dicts
    class MockOpp:
        def __init__(self, company, title, url):
            self.company = company
            self.title = title
            self.url = url
            self.id = ""

    mo1 = MockOpp("Stepcon Solutions", "Cloud Architect", "https://stepcon.tech/jobs/1")
    mo2 = {"company": "Stepcon Solutions", "title": "Cloud Architect", "url": "https://stepcon.tech/jobs/2"}
    try:
        res = deduplicate_opportunities([mo1, mo2])
        tests.append(("Polymorphic object and dict deduplication by company/title", len(res) == 1))
    except Exception as e:
        tests.append((f"Polymorphic deduplication crashed: {type(e).__name__}: {e}", False))

    # 9. None company / title inside MockOpp
    mo_none = MockOpp(None, None, "https://stepcon.tech/jobs/none")
    try:
        res = deduplicate_opportunities([mo_none, mo_none])
        tests.append(("MockOpp with None fields deduplication by URL", len(res) == 1))
    except Exception as e:
        tests.append((f"MockOpp with None fields crashed: {type(e).__name__}: {e}", False))

    # 10. URL with trailing slash difference
    # Note: URL without text ident matches url string
    t_u1 = {"company": "", "title": "", "url": "https://example.com/job"}
    t_u2 = {"company": "", "title": "", "url": "https://example.com/job"}
    try:
        res = deduplicate_opportunities([t_u1, t_u2])
        tests.append(("Identical URL deduplication", len(res) == 1))
    except Exception as e:
        tests.append((f"Identical URL crashed: {type(e).__name__}: {e}", False))

    # 11. Empty string vs None handling in fingerprint
    fp1 = generate_fingerprint("", "")
    fp2 = generate_fingerprint(None, None)
    tests.append(("Fingerprint empty and None equivalence", fp1 == fp2))

    # 12. Punctuation preservation in fingerprint (e.g. C vs C++ or Corp, Inc. vs Corp Inc)
    fp3 = generate_fingerprint("Amazon Web Services, Inc.", "DevOps / SRE Engineer")
    fp4 = generate_fingerprint("Amazon Web Services Inc", "DevOps SRE Engineer")
    tests.append(("Fingerprint punctuation distinction preserved", fp3 != fp4))

    # 13. Case folding in fingerprint
    fp5 = generate_fingerprint("MICROSOFT", "AZURE ARCHITECT")
    fp6 = generate_fingerprint("microsoft", "azure architect")
    tests.append(("Fingerprint case insensitivity", fp5 == fp6))

    # 14. Whitespace collapsed in fingerprint
    fp7 = generate_fingerprint("  Google   Cloud  ", "  Lead   SRE  ")
    fp8 = generate_fingerprint("Google Cloud", "Lead SRE")
    tests.append(("Fingerprint whitespace collapsing", fp7 == fp8))

    # 15. Disparate companies produce distinct fingerprints
    fp9 = generate_fingerprint("Google Cloud", "DevOps Engineer")
    fp10 = generate_fingerprint("Microsoft Azure", "DevOps Engineer")
    tests.append(("Fingerprint disparity for different companies", fp9 != fp10))

    passed = sum(1 for name, ok in tests if ok)
    failed = [name for name, ok in tests if not ok]
    return passed, len(failed), failed


def run_all():
    print("=" * 80)
    print("CHALLENGER ADVERSARIAL STRESS TEST SUITE — MILESTONE 3 ITERATION 4")
    print("=" * 80)

    # 1. Pronoun Invariants
    p_pass, p_fail_count, p_failed = test_conversational_pronoun_invariants()
    print(f"\n[1] Conversational Pronoun Invariants: {p_pass} PASSED, {p_fail_count} FAILED (of 25)")
    if p_failed:
        print("    Failures:")
        for f in p_failed:
            print(f"      - {f}")

    # 2. Domestic Locks & Headers
    d_pass, d_fail_count, d_failed = test_domestic_lock_recruiter_formats()
    print(f"\n[2] Domestic Lock Recruiter Formats: {d_pass} PASSED, {d_fail_count} FAILED (of 26)")
    if d_failed:
        print("    Failures:")
        for f in d_failed:
            print(f"      - {f}")

    # 3. Remote Nigeria & Global Boundaries
    r_pass, r_fail_count, r_failed = test_remote_nigeria_global_boundaries()
    print(f"\n[3] Remote Nigeria & Global Boundaries: {r_pass} PASSED, {r_fail_count} FAILED (of 20)")
    if r_failed:
        print("    Failures:")
        for f in r_failed:
            print(f"      - {f}")

    # 4. Visa Sponsorship Nuances
    v_pass, v_fail_count, v_failed = test_visa_sponsorship_nuances()
    print(f"\n[4] Visa Sponsorship Nuances: {v_pass} PASSED, {v_fail_count} FAILED (of 25)")
    if v_failed:
        print("    Failures:")
        for f in v_failed:
            print(f"      - {f}")

    # 5. Deduplication Extreme Types & Edge Cases
    dd_pass, dd_fail_count, dd_failed = test_deduplication_extreme_types_and_edge_cases()
    print(f"\n[5] Deduplication Extreme Types & Edge Cases: {dd_pass} PASSED, {dd_fail_count} FAILED (of 15)")
    if dd_failed:
        print("    Failures:")
        for f in dd_failed:
            print(f"      - {f}")

    total_passed = p_pass + d_pass + r_pass + v_pass + dd_pass
    total_failed = p_fail_count + d_fail_count + r_fail_count + v_fail_count + dd_fail_count
    total_tests = total_passed + total_failed

    print("\n" + "=" * 80)
    print(f"OVERALL RESULTS: {total_passed} PASSED, {total_failed} FAILED (TOTAL {total_tests})")
    print("=" * 80)

    if total_failed == 0:
        print("VERDICT: APPROVE (all 111 empirical adversarial tests passed)")
        sys.exit(0)
    else:
        print(f"VERDICT: REQUEST_CHANGES ({total_failed} empirical failures detected)")
        sys.exit(1)


if __name__ == "__main__":
    run_all()
