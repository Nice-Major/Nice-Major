# Career Automation & Stepcon Solutions (`RC - 8284984`) Workflow Suite

An end-to-end career development, ATS document tailoring, multi-source opportunity discovery, daily email dispatch, and B2B IT consultancy pipeline configured for **John Victor Aniekwe** and **Stepcon Solutions** (`RC - 8284984`).

---

## 1. Where the Single Source of Truth Lives

The profile currently used by the application is stored at:

- **Primary File**: [`data/profile-data.json`](data/profile-data.json)
- **Schema & Validator**: [`ingestion/models.py`](ingestion/models.py) and [`ingestion/parser.py`](ingestion/parser.py)

Treat this file as the current application context, not independent verification of every profile claim. Review generated documents against your latest CV before applying.

The GitHub Pages portfolio at `index.html` reads this same file directly. It does not keep an embedded profile or a second root-level JSON copy. Update only `data/profile-data.json` when you confirm a candidate fact; generated opportunity documents remain separate and editable. Certification issue and expiration dates are stored with each credential and carried into generated CVs.

Generated application documents are tailored from the profile and job description; the job description is not treated as evidence of candidate qualifications. The generators do not add fallback achievements, education, certifications, projects, contact details, or skills when those fields are absent. They preserve profile facts while prioritizing details relevant to each opportunity.

The repository profile is application input, not independent verification. The supplied CV could not be text-extracted during this implementation, so its contents have not been compared against the profile. Review `data/profile-data.json` against your current CV and update it only when you explicitly confirm a correction or addition. Generated opportunity documents can then be edited independently without modifying the profile.

---

## 2. How to Use the On-Demand Interactive Workflow (`cli/main.py`)

Open **PowerShell** in `C:\Users\user\Downloads\Career Development`:

```powershell
Set-Location "C:\Users\user\Downloads\Career Development"
```

### A. Evaluate Any Job Description On Demand (`eval`)
Whenever you find a job posting, save the text to a file (or pass it directly with `--text`) to get a **0–100% suitability rating** across 5 dimensions (Skills `35%`, Title `25%`, KPIs `15%`, Remote/Visa Mobility `15%`, Certifications `10%`), plus matched skills and gap analysis:

```powershell
# Evaluate from a file
python cli/main.py eval --file data/sample_job.txt

# Evaluate raw text directly
python cli/main.py eval --text "Looking for an AWS & Azure DevOps Engineer with Kubernetes (AKS/EKS), Terraform, and CI/CD experience. Remote from EMEA/Nigeria."

# Output machine-readable JSON
python cli/main.py eval --file data/sample_job.txt --json
```

### B. Generate Tailored ATS CV & STAR Cover Letter Packages (`tailor`)
Generate a single-column, ATS-compliant CV and a STAR-method Cover Letter tailored specifically to the job description and target role lens (`.md`, `.html`, or `.txt` for clean PDF printing):

```powershell
# Generate Markdown CV + Cover Letter
python cli/main.py tailor --file data/sample_job.txt --role "Cloud Solutions Architect" --company "Global FinTech Cloud Corp" --format md --output-dir output/tailored

# Generate print-ready HTML CV + Cover Letter (open in browser -> Print to PDF)
python cli/main.py tailor --file data/sample_job.txt --role "DevOps Engineer" --company "Global FinTech Cloud Corp" --format html --output-dir output/tailored
```

### C. Run the Stepcon Solutions (`RC - 8284984`) B2B Consultancy Pipeline (`stepcon`)
Discover B2B contracts/tenders, evaluate RFP alignment, and generate executive commercial proposals featuring your CAC registration (`RC - 8284984`), 99.9% SLA commitment, and multi-currency (`USD`, `GBP`, `EUR`, `NGN`) terms:

```powershell
# 1. Discover & score available IT consultancy tenders
python cli/main.py stepcon --discover

# 2. Evaluate a specific RFP / tender file
python cli/main.py stepcon --file data/sample_tender.txt

# 3. Generate a tailored B2B commercial proposal for a client
python cli/main.py stepcon --proposal data/sample_tender.txt --client "EuroFin Cloud Services Ltd" --output-dir output/proposals
```

### D. Trigger the Daily 8:00 AM Opportunity Digest (`digest`)
Run discovery → remote-eligibility or visa-sponsorship filtering → active link verification → CV/letter tailoring → email digest. B2B tenders are evaluated separately by the Stepcon pipeline:

```powershell
# Dry-Run mode (generates RFC 5322 .eml email file + tailored attachments in output/)
python cli/main.py digest --dry-run --force --output-dir output/digests

# Live SMTP mode (sends directly to aniekwevictor9@gmail.com once .env is configured)
python cli/main.py digest --live --force
```

The zero-cost live career adapters query Remote OK, We Work Remotely RSS, Jobicy, Remotive, and Arbeitnow. The curated company catalog at [`data/company-boards.json`](data/company-boards.json) also queries 9 validated Greenhouse boards and 8 validated Ashby boards on each run; postings are fetched fresh from the public ATS endpoints and balanced across configured employers before ranking. No provider API keys, paid plans, or repository variables are needed for this curated set. Lever remains available as an optional adapter, but no Lever board was seeded because the candidate-aligned boards checked during curation were inactive, unavailable, or had no suitable current roles. The collector gathers results across sources before eligibility checks and scoring; the email contains up to the 20 highest-ranked eligible, new postings, with tailored packages for the top matches. The run output reports per-source counts at discovery, eligibility, verification, scoring, and email selection. This is a broad multi-source search, not a crawler of the entire internet; each provider has different coverage and terms. Live discovery never substitutes synthetic examples when sources return no jobs. A listing must be remote-eligible for the candidate or explicitly offer visa/work-permit sponsorship; incidental mentions of remote activities or relocation benefits alone do not qualify. Region restrictions are checked even when a provider labels a role remote, and internship/co-op titles are excluded from the candidate's configured career targets. Eligibility is a pre-screen, not a guarantee of work authorization or role-specific sponsorship; confirm those details with the employer before applying. A B2B/fellowship label, timezone, or city alone does not establish eligibility.

No accounts or secrets are needed for the built-in public feeds/APIs:

- [Remote OK API](https://remoteok.com/api), [We Work Remotely RSS](https://weworkremotely.com/remote-jobs.rss), [Jobicy public API](https://jobicy.com/api/jobs), [Remotive public API](https://remotive.com/api/remote-jobs), and [Arbeitnow API](https://www.arbeitnow.com/api/job-board-api) are fetched without API credentials. Jobicy's optional direct-ATS API key is not used because it is paid. The daily scheduler makes one Remotive request per run (well below its published maximum of four requests per day). The email includes source attribution and direct listing links; Remotive results are used only in the candidate's private digest, not republished to another job board.
- Public employer-board endpoints are available for [Greenhouse](https://docs.greenhouse.io/job-board.html), [Lever](https://github.com/Lever/postings-api), and [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api). The curated Greenhouse/Ashby boards are ready to use without setup. To add more boards, open [repository Actions variables](https://github.com/Nice-Major/Nice-Major/settings/variables/actions) → **New repository variable** and add comma-separated public slugs to `GREENHOUSE_BOARD_TOKENS`, `LEVER_SITE_NAMES`, or `ASHBY_BOARD_NAMES`. For example, `boards.greenhouse.io/<slug>`, `jobs.lever.co/<slug>`, or `jobs.ashbyhq.com/<slug>` provide the slug; for EU Lever, use `eu:<slug>`. These are identifiers, not secrets; no account or API key is required. Extra identifiers are additive, capped at 20 boards per provider per run, checked against their public endpoint, and diversified with the curated catalog. The catalog is reviewed and expanded as suitable companies and boards are verified. No free universal index exposes every employer; public ATS endpoints cannot discover companies that have not published a known board identifier.
- Optional public RSS/Atom feeds can be added without an API key or employer slug. Set the Actions variable `RSS_JOB_FEED_URLS` to up to 20 comma- or newline-separated HTTP(S) feed URLs. The adapter parses RSS and Atom postings, filters titles against the configured role targets, then sends them through the same eligibility, verification, deduplication, and ranking pipeline. It does not assume an unspecified location is remote; listings still need evidence of Nigeria-eligible remote work or sponsorship. Only use feeds that publish job listings and permit automated fetching.

The workflow does not scrape Google Search or use Google Jobs, Adzuna, Jooble, SerpApi, or any other paid/metered search provider. Google's [JobPosting documentation](https://developers.google.com/search/docs/appearance/structured-data/job-posting) explains how employers publish structured job data for indexing; it is not a public search API. Lever's public postings API likewise requires an employer-specific site name and does not provide cross-company full-text search. Therefore a generic query such as `site:jobs.lever.co "DevOps" "Remote"` cannot be run as a reliable, supported, zero-cost automated search. For the supported public APIs, the workflow fetches listings from each known board, then applies candidate title, location, remote/sponsorship, eligibility, and fit checks locally. A manually supplied posting URL or description can instead be processed by the instant-tailoring workflow. The source set is broad but not an exhaustive crawler of the internet; each provider has its own coverage, terms, and rate limits. The curated company list is maintained as code, while currently published postings are refreshed on each daily search; a public job-board API does not provide a complete directory of other employers to automatically add.

The email includes the PDF CV and cover letter plus matching editable Word (`.docx`) documents. Names follow `First Last Company CV.pdf` and `First Last Company Cover Letter.pdf` (with matching `.docx` filenames). Edit the Word files or the Markdown sources in the downloaded package, then use `rebuild` to produce a new PDF from edited Markdown.

### E. Submit a Manually Found Opportunity
The GitHub Actions workflow **Instant Job Tailoring & PDF Application Generator** accepts a posting URL or pasted job description, plus optional company and role overrides. It reads the profile from `data/profile-data.json` by default, generates a dedicated application package, and can email it. Locally, use:

```powershell
python cli/main.py apply --url "https://jobs.example.com/posting"
python cli/main.py apply --file data/paste_job_here.txt --company "Example Corp"
python cli/main.py apply --text "Paste the complete job description here" --json
```

Each package includes editable Markdown sources and matching PDFs. Edit the `.md` files, then rebuild the PDFs with `python cli/main.py rebuild --opportunity <folder>`. The application email includes the PDF and Markdown files; the GitHub Actions artifact includes the generated source documents as well.

### F. Record Candidate Feedback
Use the **Career Search Feedback** GitHub Actions workflow or record it locally:

```powershell
python cli/main.py feedback --role "Cloud Engineer" --outcome interested
python cli/main.py feedback --role "Cloud Engineer" --outcome interview
```

Only aggregate role/outcome counts are persisted. Three or more explicit `interested` / `not_interested` votes for a role can adjust its ordering by at most five points; this does not change fit scores, eligibility, or candidate-profile facts. Application outcomes inform the self-review but do not automatically rewrite the CV/profile. Review `output/workflow_reviews/` before making profile changes.

---

## 3. Setting Up the Automated Daily 8:00 AM Email Workflow

Detailed architectural trade-offs (GitHub Actions vs. Windows Task Scheduler vs. Google Apps Script) are documented in [`scheduler/ARCHITECTURE.md`](scheduler/ARCHITECTURE.md).

### Option 1: Local Windows Task Scheduler (Zero Jitter, Runs at 8:00 AM Local WAT)
1. Copy `.env.example` to `.env` and fill in your Gmail App Password (`SMTP_USER=aniekwevictor9@gmail.com`, `SMTP_PASSWORD=...`, `DRY_RUN=False`, `OFFLINE_MODE=False`).
2. Register the scheduled task in PowerShell:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\schedule_task.ps1
   ```

### Option 2: GitHub Actions Free Tier (Cloud-Hosted 24/7, Runs at 07:00 UTC = 08:00 AM WAT)
1. Push this directory to your GitHub repository.
2. In your GitHub repo **Settings → Secrets and variables → Actions**, add:
   - `NOTIFICATION_EMAIL` (`aniekwevictor9@gmail.com`)
   - `SMTP_HOST` (`smtp.gmail.com`)
   - `SMTP_PORT` (`587`)
   - `SMTP_USER` (`aniekwevictor9@gmail.com`)
   - `SMTP_PASSWORD` (your 16-character Google App Password)
   - `SMTP_SENDER` (`aniekwevictor9@gmail.com`)
3. The workflow in [`.github/workflows/daily_dispatch.yml`](.github/workflows/daily_dispatch.yml) is scheduled for `07:00 UTC` (`08:00 AM WAT`) and can also be triggered manually via the **Actions** tab. GitHub scheduled runs are best-effort and may be delayed.
4. Opportunity history and aggregate feedback are restored/saved through the GitHub Actions cache. The history contains only hashes, not posting text, URLs, profile data, or generated documents. On the first upgraded run there is no prior cache, so previously emailed jobs may appear once while the history is initialized.

---

## 4. Running the Verification & Test Suites

```powershell
# Run the 5-Tier Opaque-Box & Adversarial E2E Suite (193 tests)
python e2e_tests/runner.py --pytest -v

# Run the Full Unit & Regression Test Suite (809 tests)
python -m pytest tests/ -q
```
