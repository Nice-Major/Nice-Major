"""
Empirical Adversarial & Stress Test Suite for Milestone 2 Matching Engine (F04, F07).
Target Modules:
- engine.competency (Feature F04)
- engine.scorer (Feature F07)

Authored by Milestone 2 Challenger 1 (challenger_m2_1).
Provides empirical verification for:
1. Invariants & arithmetic: DIMENSION_WEIGHTS sum to 1.000, score bounds [0.0, 100.0].
2. Contract dual interface: MatchResult attribute, subscript, to_dict(), and get().
3. Input polymorphism: CandidateProfile vs raw dictionary canonical_profile_data.
4. Malformed/Adversarial inputs: Null bytes, 50,000 words, nested HTML, XSS payloads.
5. Extreme domain jobs: Pastry chef, pure astronaut, junior with 30 years experience, TS/SCI US-only.
6. Empirical boundary behaviors: Polysemic English word exploitation ('support', 'container', 'windows', 'bash').
"""

import math
import time
import pytest
from typing import Any, Dict

import engine.competency as comp
import engine.scorer as scorer
from ingestion.models import CandidateProfile
from ingestion.parser import (
    load_profile_from_dict,
    get_embedded_default_profile,
    ProfileValidationError,
)


@pytest.fixture
def candidate_profile():
    return load_profile_from_dict(get_embedded_default_profile())


@pytest.fixture
def raw_candidate_dict():
    return get_embedded_default_profile()


# ============================================================================
# 1. Weights, Bounds, and Arithmetic Invariants
# ============================================================================

class TestArithmeticAndInvariants:
    def test_dimension_weights_sum_exact(self):
        """DIMENSION_WEIGHTS must contain the 5 canonical keys and sum to 1.000."""
        weights = scorer.DIMENSION_WEIGHTS
        expected_keys = {"skills", "title", "metrics", "mobility", "certs"}
        assert set(weights.keys()) == expected_keys
        for k, v in weights.items():
            assert isinstance(v, (int, float))
            assert v > 0.0, f"Weight for {k} must be positive"
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum {total} != 1.0"

    def test_score_bounded_on_random_and_adversarial_inputs(self, candidate_profile):
        """Across a barrage of adversarial inputs, overall_score and breakdown must stay in [0.0, 100.0]."""
        test_inputs = [
            "",
            "   \t\r\n   ",
            "\x00" * 500,
            "1234567890 !@#$%^&*()_+~`|}{[]:;?><,./",
            "A" * 10000,
            "Terraform " * 2000,
            "<div><p>" * 500,
            "Pastry Chef Baking Croissant Chocolatier",
            "Astronaut Spacewalk Mars Oxygen Rocket",
            "US Only Top Secret TS/SCI Polygraph Citizen Only W2",
            "Worldwide Remote AWS Azure Kubernetes Terraform Docker SLA 99.9% RCA KCNA B.Sc.",
            None,
        ]

        for idx, jd in enumerate(test_inputs):
            res = scorer.evaluate_job(candidate_profile, jd if jd is not None else "")
            assert isinstance(res.overall_score, float), f"Input {idx} score not float: {type(res.overall_score)}"
            assert not math.isnan(res.overall_score), f"Input {idx} score is NaN"
            assert not math.isinf(res.overall_score), f"Input {idx} score is Inf"
            assert 0.0 <= res.overall_score <= 100.0, f"Input {idx} score {res.overall_score} out of bounds [0, 100]"

            for dim, val in res.breakdown.items():
                assert isinstance(val, (int, float)), f"Input {idx} breakdown {dim} not numeric: {val}"
                assert not math.isnan(val), f"Input {idx} breakdown {dim} is NaN"
                assert 0.0 <= val <= 100.0, f"Input {idx} breakdown {dim} score {val} out of bounds [0, 100]"


# ============================================================================
# 2. Contract & Interface Verification (MatchResult & RoleTaxonomyEntry)
# ============================================================================

class TestContractDualInterface:
    def test_match_result_attribute_and_subscript_access(self, candidate_profile):
        """Verify MatchResult supports attribute access, dict subscripting, and to_dict()."""
        jd = "Senior DevOps Engineer with Kubernetes and Terraform experience. Remote worldwide."
        res = scorer.evaluate_job(candidate_profile, jd)

        # Attribute access
        assert isinstance(res.overall_score, float)
        assert isinstance(res.breakdown, dict)
        assert isinstance(res.matched_skills, list)
        assert isinstance(res.missing_skills, list)
        assert isinstance(res.target_role, str)
        assert isinstance(res.rationale, str)

        # Dict subscript access
        assert res["overall_score"] == res.overall_score
        assert res["breakdown"] == res.breakdown
        assert res["matched_skills"] == res.matched_skills
        assert res["missing_skills"] == res.missing_skills
        assert res["target_role"] == res.target_role
        assert res["rationale"] == res.rationale

        # dict .get() access
        assert res.get("overall_score") == res.overall_score
        assert res.get("non_existent_key", "default_val") == "default_val"

        # in operator
        assert "overall_score" in res
        assert "breakdown" in res
        assert "non_existent_key" not in res

        # Key error on invalid subscript
        with pytest.raises(KeyError):
            _ = res["invalid_key_xyz"]

        # .to_dict() test
        d = res.to_dict()
        assert isinstance(d, dict)
        assert set(d.keys()) == {"overall_score", "breakdown", "matched_skills", "missing_skills", "target_role", "rationale"}
        # Modifying to_dict copy does not mutate res
        d["overall_score"] = 999.9
        assert res.overall_score != 999.9

    def test_role_taxonomy_entry_dual_interface(self):
        """Verify RoleTaxonomyEntry supports attribute, subscript, and to_dict()."""
        taxonomy = comp.get_role_taxonomy()
        entry = taxonomy["Cloud Solutions Architect"]

        assert entry.title == "Cloud Solutions Architect"
        assert entry["title"] == "Cloud Solutions Architect"
        assert entry.get("title") == "Cloud Solutions Architect"
        assert entry.get("not_existing", 42) == 42
        assert "title" in entry
        assert "not_existing" not in entry

        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "Cloud Solutions Architect"
        assert "core_skills" in d
        assert "domain_weights" in d


# ============================================================================
# 3. Input Polymorphism: CandidateProfile vs raw dictionary vs malformed
# ============================================================================

class TestInputPolymorphism:
    def test_evaluate_job_with_raw_dict(self, raw_candidate_dict):
        """evaluate_job must accept raw candidate dict canonical_profile_data seamlessly."""
        jd = "DevOps Engineer with Kubernetes and Terraform experience. Remote worldwide."
        res = scorer.evaluate_job(raw_candidate_dict, jd)
        assert isinstance(res, scorer.MatchResult)
        assert res.overall_score > 60.0

    def test_evaluate_job_with_candidate_profile_instance(self, candidate_profile):
        """evaluate_job must accept CandidateProfile instance seamlessly."""
        jd = "DevOps Engineer with Kubernetes and Terraform experience. Remote worldwide."
        res = scorer.evaluate_job(candidate_profile, jd)
        assert isinstance(res, scorer.MatchResult)
        assert res.overall_score > 60.0

    def test_evaluate_job_with_empty_dict_behavior(self):
        """
        Document empirical behavior when candidate is empty dict {}:
        load_profile_from_dict raises ProfileValidationError because schema validation fails.
        """
        jd = "DevOps Engineer with Kubernetes and Terraform experience. Remote worldwide."
        with pytest.raises(ProfileValidationError):
            _ = scorer.evaluate_job({}, jd)

    def test_evaluate_job_with_none_or_invalid_type(self):
        """evaluate_job falls back to default CandidateProfile() if candidate is None."""
        jd = "DevOps Engineer with Kubernetes and Terraform experience."
        res = scorer.evaluate_job(None, jd)
        assert isinstance(res, scorer.MatchResult)
        assert 0.0 <= res.overall_score <= 100.0


# ============================================================================
# 4. Stress Tests: Massive, Binary, Repetitive, Nested HTML
# ============================================================================

class TestStressAndAdversarialInputs:
    def test_massive_50000_word_job_description(self, candidate_profile):
        """Verify performance and non-crash on massive 50,000 word JD."""
        base_text = (
            "Cloud Solutions Architect needed for multi-cloud deployment. "
            "Keywords: AWS, Azure, Terraform, Kubernetes, Docker, SLA 99.9%, RCA, remote worldwide. "
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt. "
        )
        # Repeat to reach ~50,000 words
        repetitions = 50000 // len(base_text.split())
        massive_jd = base_text * repetitions

        start_time = time.perf_counter()
        res = scorer.evaluate_job(candidate_profile, massive_jd)
        elapsed = time.perf_counter() - start_time

        assert elapsed < 5.0, f"Massive JD evaluation took {elapsed:.2f}s (exceeded 5.0s budget)"
        assert isinstance(res, scorer.MatchResult)
        assert 0.0 <= res.overall_score <= 100.0
        assert "Kubernetes" in res.matched_skills

    def test_binary_null_bytes_and_control_characters(self, candidate_profile):
        """Verify resilience to null bytes and binary payloads."""
        binary_jd = "Senior \x00DevOps\x00 Engineer \x01\x02\x03 Kubernetes \x00 Terraform \x7f\x80\xff remote worldwide"
        res = scorer.evaluate_job(candidate_profile, binary_jd)
        assert isinstance(res, scorer.MatchResult)
        assert 0.0 <= res.overall_score <= 100.0
        assert "Kubernetes" in res.matched_skills

    def test_nested_html_xss_and_script_injection(self, candidate_profile):
        """Verify HTML/script stripping and extraction safety."""
        html_jd = """
        <html>
            <head><script>alert('pwned');</script><style>body { display: none; }</style></head>
            <body>
                <div class="job-header">
                    <h1>Senior <!-- comment -->DevOps Engineer</h1>
                    <script src="https://evil.com/tracker.js"></script>
                </div>
                <div class="job-body">
                    <p>Requirements include: &lt;b&gt;Kubernetes&lt;/b&gt;, &amp; <b>Terraform</b>.</p>
                    <img src="x" onerror="stealCookies()" />
                    <p>Must have 99.9% SLA uptime experience.</p>
                    <span>Remote Worldwide / CET Synchronous</span>
                </div>
            </body>
        </html>
        """
        keywords = comp.extract_keywords(html_jd)
        assert "Kubernetes" in keywords
        assert "Terraform" in keywords
        assert not any(tag in [k.lower() for k in keywords] for tag in ["script", "style", "div", "span", "p", "img", "body"])

        res = scorer.evaluate_job(candidate_profile, html_jd)
        assert res.overall_score >= 70.0
        assert "Kubernetes" in res.matched_skills


# ============================================================================
# 5. Extreme Domain JDs & Boundary Scenarios
# ============================================================================

class TestExtremeDomainCases:
    def test_pure_pastry_chef_disqualification(self, candidate_profile):
        """Pastry chef must score 0.0 with 'Do Not Apply' recommendation."""
        pastry_jd = (
            "Head Pastry Chef & Chocolatier. Responsible for laminating croissant dough, "
            "baking artisan sourdough loaves, French macarons, and tempering chocolate. "
            "Culinary degree required."
        )
        res = scorer.evaluate_job(candidate_profile, pastry_jd)
        assert res.overall_score == 0.0
        assert "Do Not Apply" in res.rationale
        assert res.breakdown == {"skills": 0.0, "title": 0.0, "metrics": 0.0, "mobility": 0.0, "certs": 0.0}
        assert res.matched_skills == []

    def test_pure_astronaut_scores_do_not_apply(self, candidate_profile):
        """Pure astronaut role without polysemic IT words scores 38.75 with 'Do Not Apply'."""
        astronaut_jd = (
            "NASA Astronaut: Artemis Lunar Mission. "
            "Conduct extravehicular spacewalks, manage lunar life oxygen tanks, "
            "pilot spacecraft docking maneuvers, and sample extraterrestrial regolith."
        )
        res = scorer.evaluate_job(candidate_profile, astronaut_jd)
        assert res.overall_score < 50.0
        assert "Do Not Apply" in res.rationale
        assert res.matched_skills == []

    def test_empirical_finding_polysemic_word_vulnerability(self, candidate_profile):
        """
        EMPIRICAL VULNERABILITY REPORT:
        Demonstrates that common English words in CANONICAL_TECH_MAP ('support', 'container', 'windows', 'bash')
        inflate non-technical jobs into high-scoring IT matches:
        - Commercial Window Cleaner Specialist -> 85.0% ('Strong Apply')
        - Garbage Truck Driver (plastic containers) -> 74.5% ('Apply')
        - Party Planning Lead (company bash) -> 85.0% ('Strong Apply')
        - Astronaut with life support systems -> 73.75% ('Apply')
        """
        window_cleaner = "Commercial Window Cleaner Specialist: Washing glass exterior windows on commercial skyscrapers."
        res_win = scorer.evaluate_job(candidate_profile, window_cleaner)
        assert res_win.overall_score >= 80.0
        assert "Strong Apply" in res_win.rationale
        assert "Windows" in res_win.matched_skills

        garbage_driver = "Garbage Truck Driver: Empty curbside plastic trash containers into garbage compactor."
        res_garbage = scorer.evaluate_job(candidate_profile, garbage_driver)
        assert res_garbage.overall_score >= 70.0
        assert "Container" in res_garbage.matched_skills

        party_planner = "Party Planning Lead: Organize festive catering and venue decorations for our corporate bash."
        res_party = scorer.evaluate_job(candidate_profile, party_planner)
        assert res_party.overall_score >= 80.0
        assert "Bash" in res_party.matched_skills

    def test_junior_with_30_years_experience_absurdity(self, candidate_profile):
        """Absurd requirement must not break scoring logic or cause negative/overflow scores."""
        absurd_jd = (
            "Junior Cloud Intern: 30 years of Kubernetes experience required, "
            "35 years of AWS cloud architecture, 20 years of Azure OpenAI prompt engineering. "
            "Unpaid internship. Remote worldwide."
        )
        res = scorer.evaluate_job(candidate_profile, absurd_jd)
        assert 0.0 <= res.overall_score <= 100.0

    def test_security_clearance_us_only_hard_disqualification(self, candidate_profile):
        """TS/SCI US-only role must yield 0 for mobility and cap overall_score <= 65.0 (< 70.0)."""
        clearance_jd = (
            "DevOps Engineer. Required: Kubernetes, Terraform, AWS, Docker. "
            "Active Top Secret / SCI clearance required. US Citizen only. W2 only. "
            "Candidates outside the US rejected."
        )
        res = scorer.evaluate_job(candidate_profile, clearance_jd)
        assert res.breakdown["mobility"] == 0.0
        assert res.overall_score < 70.0
        assert res.overall_score <= 65.0, "Hard disqualifier must cap overall score at or below 65.0"


# ============================================================================
# 6. Keyword Anti-False-Positive Boundary Tests
# ============================================================================

class TestKeywordAntiFalsePositive:
    def test_no_false_positive_substrings(self):
        """Ensure substrings of keywords do not trigger false positive matches."""
        # e.g. "classic" shouldn't trigger "ci/cd", "awesome" shouldn't trigger "aws"
        tricky_text = "The awesome classic car had a flaw in its design manual."
        extracted = comp.extract_keywords(tricky_text)
        assert "AWS" not in extracted
        assert "CI/CD" not in extracted
        assert extracted == []

    def test_empirical_finding_regex_boundary_with_underscores(self):
        """
        EMPIRICAL FINDING:
        In competency.py:452, regex pattern r'(?<![a-zA-Z0-9])' considers '_' a boundary.
        Therefore, compound words with underscores like 'bicep_curls' match 'Bicep'.
        """
        extracted = comp.extract_keywords("Daily routine: 3 sets of bicep_curls.")
        assert "Bicep" in extracted  # Matches because _ is not in [a-zA-Z0-9]

    def test_canonical_mapping_preservation(self):
        """Terms like k8s, cicd, arm/bicep map to canonical representations."""
        text = "Experience with k8s, cicd, and arm/bicep."
        extracted = comp.extract_keywords(text)
        assert "Kubernetes" in extracted
        assert "CI/CD" in extracted
        assert ("ARM/Bicep" in extracted or "ARM" in extracted or "Bicep" in extracted)
