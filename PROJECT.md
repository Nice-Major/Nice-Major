# Project: Career Automation & Stepcon Solutions Pipeline

## Architecture
A decoupled, pure Python 3.10+ modular suite with zero paid API dependencies, strict ATS compliance, dual scheduling (GitHub Actions primary, local secondary), interactive CLI, and B2B consultancy matching for Stepcon Solutions (RC - 8284984).

```
career_automation/
├── config/                  # Environment variables, constants, zero-cost settings
│   ├── __init__.py
│   └── settings.py
├── ingestion/               # Candidate data ingestion, schema validation, normalization
│   ├── __init__.py
│   ├── models.py            # Pydantic/dataclass schema for candidate & Stepcon
│   ├── parser.py            # JSON & document profile loader
│   └── text_utils.py        # Ligature repair (sanitize_ligatures) & safe_filename
├── engine/                  # Matching, scoring, competency extraction
│   ├── __init__.py
│   ├── competency.py        # 8-role skill & competency taxonomy
│   └── scorer.py            # 5-dimension 0-100 match scoring & gap analysis
├── tailoring/               # Document generation (CV & Cover Letter)
│   ├── __init__.py
│   ├── cv_tailor.py         # ATS single-column CV generator (MD/HTML/TXT)
│   └── letter_tailor.py     # STAR-method cover letter generator
├── discovery/               # Job search, geo-filtering, posting health verification
│   ├── __init__.py
│   ├── sources.py           # Free API adapters (Remotive, Arbeitnow, Jobicy, feeds)
│   ├── filters.py           # Remote Nigeria, EMEA, CET, visa-sponsorship filters
│   └── verifier.py          # HTTP status, redirect depth, closed-phrase & stale checks
├── dispatch/                # Daily digest & email delivery
│   ├── __init__.py
│   ├── digest.py            # HTML & plain text digest formatter
│   └── mailer.py            # SMTP dispatcher & dry-run .eml exporter
├── cli/                     # Interactive CLI interface
│   ├── __init__.py
│   └── main.py              # CLI entry point (eval, tailor, digest, stepcon)
├── consultancy/             # Stepcon Solutions (RC - 8284984) B2B pipeline
│   ├── __init__.py
│   ├── tenders.py           # Public/corporate tender discovery
│   └── proposals.py         # Tailored proposal & pitch deck generator
├── scheduler/               # Zero-cost automation & scheduling documentation
│   ├── daily_dispatch.py    # Daily cron entrypoint
│   └── ARCHITECTURE.md      # Detailed comparison: GitHub Actions vs Local vs Apps Script
├── .github/workflows/
│   └── daily_dispatch.yml   # Free tier GitHub Actions cron (0 7 * * * = 08:00 WAT)
├── scripts/
│   └── schedule_task.ps1    # Local Windows Task Scheduler setup script
├── tests/                   # Automated synthetic test suite
│   ├── conftest.py
│   ├── fixtures/            # Synthetic profile, jobs, tenders fixtures
│   ├── test_ingestion.py
│   ├── test_matching.py
│   ├── test_tailoring.py
│   ├── test_discovery.py
│   ├── test_dispatch.py
│   ├── test_cli.py
│   └── test_consultancy.py
└── e2e_tests/               # Opaque-box E2E test track suite (Tiers 1-4)
    ├── test_tier1_features.py
    ├── test_tier2_boundaries.py
    ├── test_tier3_combinations.py
    ├── test_tier4_workloads.py
    └── runner.py
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F01 | Candidate Profile Data Ingestion | Parse candidate qualifications, skills, and work history from profile-data.json, LinkedIn export, and CV files without omitting verified credentials. | M1 | R1, Survey |
| F02 | Profile Representation & Schema Modeling | Strict machine-readable data model (Pydantic/dataclass) representing contact, 4 role lenses, 6 skills domains, 4 active certs, 4 KPI metrics, and Stepcon corporate identity. | M1 | R1, Survey |
| F03 | ATS Text & Filename Utilities | Implement font ligature cleanup (preventing `eƯiciency` corruptions) and strict underscore naming convention `{First}_{Last}_{Role}_{DocType}.{ext}`. | M1 | R2, Survey |
| F04 | Role Competency & Keyword Extraction | Taxonomy and keyword matcher across all 8 target roles (Solutions Architect, Cloud Infra, Cloud Engineer, DevOps, SysAdmin, IT Specialist, Support, Azure/AWS DevOps). | M2 | R2, Survey |
| F05 | ATS-Friendly CV Tailoring Engine | Generate tailored, single-column, ATS-compliant CVs in Markdown, plain text, and clean print HTML reflecting actual background and job keywords with zero external tracker links. | M2 | R2, Survey |
| F06 | Cover Letter Tailoring Engine | Generate tailored cover letters using STAR methodology, empirical metrics (99.9% uptime, 99% RCA), and professional tone for specific job descriptions. | M2 | R2, Survey |
| F07 | Multi-Dimensional Match Scorer | 5-dimension 0-100 scoring algorithm (Skills 35%, Title 25%, Metrics 15%, Mobility 15%, Certs 10%) with transparent rationale and skill gap breakdown. | M2 | R5, Survey |
| F08 | Opportunity Discovery Engine | Connect to open, free recruitment feeds and APIs (Remotive, Arbeitnow, Jobicy, feeds) with synthetic fallback for offline operation. | M3 | R3, Survey |
| F09 | Geo-Eligibility & Sponsorship Filter | Filter for remote eligibility from Nigeria (Worldwide, EMEA, CET, UTC+1), visa/relocation sponsorship, and filter out US-only/W2/clearance-locked jobs. | M3 | R3, Survey |
| F10 | Opportunity Health & Active Verification | Verify postings via HTTP status (200 OK), redirect hops (<=5), DOM closed/expired phrase detection, stale date checking (<=30 days), and SHA-256 deduplication. | M3 | R3, Survey |
| F11 | Daily 8:00 AM Notification Dispatch | Build multipart HTML and plain text daily digest with opportunity links, fit scores, and generated application packages; send via SMTP or export to .eml in dry-run mode. | M4 | R4, Survey |
| F12 | Scheduling Architectures & Documentation | Comprehensive architectural comparison document (GitHub Actions vs Windows Task Scheduler vs Google Apps Script) + functional GitHub Actions workflow + PowerShell scheduler script. | M4 | R4, Survey |
| F13 | Interactive On-Demand Evaluation CLI | CLI interface accepting job descriptions via stdin or file path, returning numerical match score, gap analysis, and generating tailored materials. | M5 | R5, Survey |
| F14 | Stepcon Solutions Consultancy Pipeline | Automated discovery of IT contracts, government/public tenders, and corporate engagements matching Stepcon Solutions (RC - 8284984) cloud/hardware offerings, generating commercial proposals. | M5 | R6, Survey |
| F15 | Controlled Testing & Dry-Run Mode | Environment variable configuration (`DRY_RUN`, `OFFLINE_MODE`, SMTP creds) allowing 100% test execution without live emails or external paid APIs. | M5 | R7, Survey |
| F16 | Opaque-Box E2E Test Suite | 4-Tier test suite (Feature coverage, Boundary cases, Combinatorial pairs, Real-world workloads) verifying all system requirements independently of internal design. | M6 | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Data Ingestion, Modeling & ATS Text Utilities | F01, F02, F03: Candidate profile ingestion, Pydantic schemas, ligature sanitization, and safe filename generation. | None | DONE |
| M2 | Competency Matching & ATS Document Tailoring | F04, F05, F06, F07: 8-role competency taxonomy, ATS CV & cover letter generator, 0-100 scoring engine. | M1 | DONE |
| M3 | Opportunity Discovery, Geo-Filtering & Verification | F08, F09, F10: Job search adapters, Nigeria remote/visa filtering, HTTP/DOM status verification. | M1 | DONE |
| M4 | Daily 8:00 AM Dispatcher & Scheduling Architecture | F11, F12: Daily digest generator, SMTP/eml mailer, GitHub Actions workflow, scheduling trade-off report. | M2, M3 | DONE |
| M5 | Interactive CLI & Stepcon Solutions Pipeline | F13, F14, F15: CLI subcommands (`eval`, `tailor`, `digest`, `stepcon`), tender matcher, Stepcon proposal generator, dry-run mode. | M1, M2, M3, M4 | DONE |
| M6 | Final Milestone: E2E Verification & Adversarial Hardening | F16: Pass 100% of E2E test suite (Tiers 1-4) published via TEST_READY.md, followed by Tier 5 adversarial hardening. | M1, M2, M3, M4, M5 | IN_PROGRESS |

## Interface Contracts

### M1 (Ingestion) ↔ M2 (Tailoring) & M3 (Discovery)
- `CandidateProfile`: Data model exposing:
  - `candidate.full_name: str`, `candidate.email: str`, `candidate.phone: str`, `candidate.location: str`
  - `candidate.certifications: list[Certification]` (name, issuer, year, verified: bool)
  - `candidate.kpi_metrics: list[KpiMetric]` (metric, value, context)
  - `candidate.role_categories: dict[str, RoleCategory]`
  - `candidate.skills_matrix: dict[str, list[str]]`
  - `candidate.experience: list[WorkExperience]` (company, role, start_date, end_date, location, bullets, tags)
  - `stepcon_solutions: StepconProfile` (cac_number: str = "RC - 8284984", services, legal_status)
- `text_utils.sanitize_ligatures(text: str) -> str`
- `text_utils.safe_filename(first: str, last: str, role: str, doc_type: str, ext: str = "pdf") -> str`

### M2 (Tailoring & Scoring) ↔ M4 (Dispatch) & M5 (CLI)
- `scorer.evaluate_job(candidate: CandidateProfile, job_text: str) -> MatchResult`
  - `MatchResult`: `overall_score: float` (0-100), `breakdown: dict[str, float]`, `matched_skills: list[str]`, `missing_skills: list[str]`, `target_role: str`, `rationale: str`
- `cv_tailor.generate_cv(candidate: CandidateProfile, job_text: str, target_role: str, output_format: str = "md") -> str`
- `letter_tailor.generate_cover_letter(candidate: CandidateProfile, job_text: str, target_role: str, company_name: str = "") -> str`

### M3 (Discovery) ↔ M4 (Dispatch) & M5 (CLI)
- `discovery.fetch_opportunities(query_roles: list[str] = None, dry_run: bool = True) -> list[Opportunity]`
  - `Opportunity`: `id: str`, `title: str`, `company: str`, `url: str`, `location: str`, `remote_eligible_nigeria: bool`, `visa_sponsorship: bool`, `contract_b2b: bool`, `description: str`, `posted_date: str`, `verified_active: bool`

### M4 (Dispatch) & M5 (CLI) ↔ Consultancy (Stepcon)
- `consultancy.evaluate_tender(stepcon: StepconProfile, tender_text: str) -> TenderMatchResult`
- `consultancy.generate_proposal(stepcon: StepconProfile, tender: TenderOpportunity) -> str`

## Code Layout
All production code lives under `C:\Users\user\teamwork_projects\career_automation\`:
- `config/`
- `ingestion/`
- `engine/`
- `tailoring/`
- `discovery/`
- `dispatch/`
- `cli/`
- `consultancy/`
- `scheduler/`
- `.github/workflows/`
- `scripts/`
- `tests/`
- `e2e_tests/`
Agent metadata only lives under `.agents/teamwork/`.
