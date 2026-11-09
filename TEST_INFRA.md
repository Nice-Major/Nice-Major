# Test Infrastructure & 4-Tier E2E Testing Strategy

## 1. Executive Summary & Strategy

The Career Automation & Stepcon Solutions (RC - 8284984) test infrastructure provides a comprehensive, requirement-driven, opaque-box testing framework. Designed to validate the system across all 15 operational features (F01–F15) and acceptance criteria defined in `ORIGINAL_REQUEST.md` and `PROJECT.md`, it guarantees zero-cost operation, ATS compliance, strict typographical safety, and enterprise reliability.

The test infrastructure adopts a **4-Tier Testing Methodology**:
1. **Tier 1: Feature Coverage** — Isolated happy-path testing for all 15 features ($\ge 5$ test cases per feature = $\ge 75$ tests).
2. **Tier 2: Boundary & Corner Cases** — Extreme lengths, empty inputs, unicode ligatures, invalid schemas, and hostile edge conditions ($\ge 5$ test cases per feature = $\ge 75$ tests).
3. **Tier 3: Cross-Feature Combinations** — Pairwise interactions and integration chains (Ingestion $\to$ Scoring $\to$ Tailoring $\to$ Dispatch $\to$ Dry-Run).
4. **Tier 4: Real-World Workload Scenarios** — Complete realistic career pipelines (Worldwide remote role discovery, visa sponsorship matching, Stepcon tender evaluation, and daily digest dispatch).

---

## 2. Directory Layout & Architecture

The test suite is structured cleanly under `e2e_tests/` and coexists with standard unit tests under `tests/`:

```
career_automation/
├── TEST_INFRA.md             # Authoritative test infrastructure documentation
├── TEST_READY.md             # Test readiness report & test execution instructions
├── e2e_tests/                # Opaque-Box E2E Test Suite (Tiers 1-4)
│   ├── __init__.py           # Package marker
│   ├── conftest.py           # Shared fixtures, test harnesses & progressive wrappers
│   ├── test_tier1_features.py   # Tier 1: Feature Coverage (F01 - F15, >=5 each)
│   ├── test_tier2_boundaries.py # Tier 2: Boundary & Corner Cases (F01 - F15, >=5 each)
│   ├── test_tier3_combinations.py # Tier 3: Cross-Feature Pairwise & Pipeline Chains
│   ├── test_tier4_workloads.py  # Tier 4: Full Real-World Application Scenarios
│   └── runner.py             # Dual-mode standalone & pytest test runner
└── tests/                    # Unit & module integration tests
```

---

## 3. 4-Tier Test Suite Specification

### Tier 1: Feature Coverage Matrix (Isolated Happy Paths, $\ge 5$ tests per feature)
| Feature ID | Feature Name | Test File | Target Modules / Interfaces | Expected Tests |
| :--- | :--- | :--- | :--- | :--- |
| **F01** | Candidate Profile Data Ingestion | `test_tier1_features.py` | `ingestion.parser`, `ingestion.profile_loader` | 5+ |
| **F02** | Profile Representation & Schema Modeling | `test_tier1_features.py` | `ingestion.models`, `engine.schema` | 5+ |
| **F03** | ATS Text & Filename Utilities | `test_tier1_features.py` | `ingestion.text_utils`, `tailoring.formatter` | 5+ |
| **F04** | Role Competency & Keyword Extraction | `test_tier1_features.py` | `engine.competency`, `engine.keyword_extractor` | 5+ |
| **F05** | ATS-Friendly CV Tailoring Engine | `test_tier1_features.py` | `tailoring.cv_tailor` | 5+ |
| **F06** | Cover Letter Tailoring Engine | `test_tier1_features.py` | `tailoring.letter_tailor`, `tailoring.cover_letter` | 5+ |
| **F07** | Multi-Dimensional Match Scorer | `test_tier1_features.py` | `engine.scorer`, `engine.scoring` | 5+ |
| **F08** | Opportunity Discovery Engine | `test_tier1_features.py` | `discovery.sources`, `discovery.remote_apis` | 5+ |
| **F09** | Geo-Eligibility & Sponsorship Filter | `test_tier1_features.py` | `discovery.filters`, `engine.eligibility` | 5+ |
| **F10** | Opportunity Health & Verification | `test_tier1_features.py` | `discovery.verifier` | 5+ |
| **F11** | Daily 8:00 AM Notification Dispatch | `test_tier1_features.py` | `dispatch.digest`, `dispatch.mailer` | 5+ |
| **F12** | Scheduling Architectures & Documentation | `test_tier1_features.py` | `scheduler.daily_dispatch`, `.github/workflows` | 5+ |
| **F13** | Interactive On-Demand CLI | `test_tier1_features.py` | `cli.main` | 5+ |
| **F14** | Stepcon Solutions Consultancy Pipeline | `test_tier1_features.py` | `consultancy.tenders`, `consultancy.proposals` | 5+ |
| **F15** | Controlled Testing & Dry-Run Mode | `test_tier1_features.py` | `config.settings`, `dispatch.mailer` | 5+ |

### Tier 2: Boundary & Corner Cases ($\ge 5$ tests per feature)
- **F01**: Missing files, corrupted JSON syntax, truncated files, unexpected additional keys, extreme text payloads.
- **F02**: Invalid emails, wrong CAC registration format, empty lists, unicode names with diacritics, negative KPI values.
- **F03**: Typography ligatures (`\uFB01`, `\uFB02`, `\uFB00`), filesystem illegal characters (`/ \ : * ? " < > |`), excessive whitespace/hyphens, empty string tokens.
- **F04**: Empty job descriptions, HTML/DOM tagged strings, noise words, repetitive 50k-token texts, non-English text.
- **F05**: Unmatched roles falling back to default lens, master CV without JD, absence of external Credly URLs, layout integrity assertions, format case insensitivity.
- **F06**: Special characters in company names, absent contact numbers, zero buzzwords enforcement, platform mismatch handling.
- **F07**: Irrelevant job text (0% match), 100% saturation match, contradictory experience demands, zero text inputs, weight arithmetic integrity.
- **F08**: Offline network timeout handling, empty query roles, malformed API payloads, duplicate removal, invalid source fallback.
- **F09**: Hidden California/US tax restrictions, security clearance exclusions, unstated location neutral scoring, no-sponsorship declarations, European residence locks.
- **F10**: HTTP 404/410 status codes, redirect depth limits (>5 hops), unparseable dates, rate limiting handling, unicode fingerprinting.
- **F11**: Zero opportunity fallback digest, attachment size >10MB limits, missing SMTP credentials in dry-run, non-ASCII subject headers, HTML styling self-containment.
- **F12**: Crontab 5-field syntax validation, PowerShell parameter escaping, duplicate daily run prevention (idempotency), missing env fallbacks, WAT/UTC timezone offset verification.
- **F13**: Non-existent file arguments, empty stdin pipes, invalid subcommands, automatic directory creation, invalid role arguments.
- **F14**: Irrelevant civil construction tenders, missing client names, multi-currency proposals (USD, GBP, EUR, NGN), priority ordering under resource contention.
- **F15**: Missing `.env` file fallback, boolean flag string variants (`true`, `1`, `yes`), unset credentials handling, live mode guardrails, invalid port parsing.

### Tier 3: Cross-Feature Combinations (Pairwise & Pipeline Chains)
1. Ingestion $\to$ Scoring (`F01` + `F07`)
2. Ingestion $\to$ Tailoring (`F01` + `F05` + `F06`)
3. Tailoring $\to$ Text Utilities & Filenames (`F05` + `F03`)
4. Discovery $\to$ Geo-Eligibility Filtering (`F08` + `F09`)
5. Discovery $\to$ Active Health Verification (`F08` + `F10`)
6. Scoring $\to$ Tailoring Output Alignment (`F07` + `F05`)
7. Tailoring $\to$ Dispatch Digest Attachment (`F05` + `F06` + `F11`)
8. Dispatcher $\to$ Dry-Run Local Artifact Generation (`F11` + `F15`)
9. CLI Interface $\to$ Evaluation & Document Generation (`F13` + `F07` + `F05`)
10. Stepcon Profile $\to$ Tender Matching $\to$ Commercial Proposal (`F14` + `F02` + `F15`)
11. Career Workflow Priority vs Stepcon Execution Order (`F01` + `F11` + `F14`)
12. Full Pipeline Chain: Ingestion $\to$ Discovery $\to$ Filter $\to$ Score $\to$ Tailor $\to$ Dispatch (`F01`–`F15`)

### Tier 4: Real-World Workload Scenarios
1. **Scenario 1: Full Candidate Discovery & Dispatch Flow (Nigeria Remote Role)**
   - Ingest candidate profile $\to$ discover synthetic worldwide DevOps job $\to$ verify active status $\to$ score 85+ $\to$ generate ATS CV and STAR cover letter $\to$ format daily digest $\to$ export `.eml` artifact in dry-run.
2. **Scenario 2: High-Match Relocation & Visa Sponsorship Matching**
   - UK/EU Cloud Solutions Architect role with verified Skilled Worker / Blue Card sponsorship $\to$ score $\ge 80$ $\to$ tailor CV emphasizing AKS/multi-cloud SLA $\to$ tailor cover letter detailing relocation readiness $\to$ verify top-tier table placement.
3. **Scenario 3: Stepcon Solutions Enterprise B2B Tender Proposal Flow**
   - Corporate Cloud & Platform Engineering RFP $\to$ match against Stepcon CAC `RC - 8284984` capabilities $\to$ generate executive proposal with Statement of Work, 99.9% SLA, and C2C terms.
4. **Scenario 4: Disqualifying Filter & Clearance Gatekeeper**
   - US-only on-site position requiring Active Top Secret / SCI clearance $\to$ verify immediate exclusion with zero false positives.
5. **Scenario 5: Stale & Zombie Job Rejection**
   - Job posting closed >30 days ago or returning HTTP 410 Gone / "this position is filled" $\to$ verify rejection and clean omission from daily digest.

---

## 4. Progressive Testability Architecture

During active milestone development, the test suite executes without crashing even before downstream modules are completed.

### Mechanics:
1. `conftest.py` provides dynamic module loaders (`get_module_or_skip(module_name, feature_id, milestone)`).
2. If an implementation module is not yet present, the test is marked `SKIPPED` with a clear explanation (e.g. `[Milestone 2 Pending] Module 'tailoring.cv_tailor' not yet implemented`).
3. As each milestone is completed by implementation workers, the corresponding tests transition from `SKIPPED` to `PASSED` automatically without modifying test code.
4. The test runner (`e2e_tests/runner.py`) aggregates passed, skipped, and failed tests with a complete breakdown across all 4 tiers.

---

## 5. Test Execution Instructions

The test suite can be run using the built-in standalone runner or standard `pytest`:

```bash
# 1. Run via Custom Dual-Mode Runner (Zero external test runner dependencies):
python e2e_tests/runner.py

# 2. Run with detailed verbose output:
python e2e_tests/runner.py -v

# 3. Run specific tier only:
python e2e_tests/runner.py --tier 1
python e2e_tests/runner.py --tier 2
python e2e_tests/runner.py --tier 3
python e2e_tests/runner.py --tier 4

# 4. Run via Pytest:
pytest e2e_tests/ -v
```

---

## 6. Fixtures & Test Data Assets

All test fixtures are self-contained:
- Canonical profile data: `C:\Users\user\Downloads\Nice_Major_Portfolio_and_Automation_Suite\profile-data.json`
- Synthetic job postings: Stored in memory or generated via `conftest.py` synthetic fixtures.
- Synthetic tenders: Corporate and government RFPs covering cloud infrastructure, DevOps, and enterprise hardware.
- Temporary directories: Automatically provisioned and cleaned up using Python's `tempfile.TemporaryDirectory`.
