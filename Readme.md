# Career Automation & Stepcon Solutions (`RC - 8284984`) Workflow Suite

An end-to-end, zero-cost career development, ATS document tailoring, opportunity discovery, daily 8:00 AM email dispatch, and B2B IT consultancy pipeline built specifically for **John Victor Aniekwe** (`aniekwevictor9@gmail.com`) and **Stepcon Solutions** (`RC - 8284984`, registered with the Nigerian Corporate Affairs Commission).

---

## 1. Where the Single Source of Truth Lives

After reviewing and reconciling all three of your CV PDFs, your LinkedIn profile (`https://www.linkedin.com/in/victor-aniekwe`), and your GitHub repository (`https://github.com/Nice-Major/Nice-Major.git`), your **Single Source of Truth** is located at:

- **Primary File**: [`data/profile-data.json`](data/profile-data.json)
- **Schema & Validator**: [`ingestion/models.py`](ingestion/models.py) and [`ingestion/parser.py`](ingestion/parser.py)

### What Was Reconciled & Standardized in Your Single Source of Truth
1. **Unified Identity & Contact Metadata**:
   - Standardizes your name (`John Victor Aniekwe`), contact details (`aniekwevictor9@gmail.com`, `+234 816 484 1085`), location (`Lagos, Nigeria — UTC+1 / CET Synchronous`), LinkedIn, GitHub, and portfolio URLs.
2. **4 Role-Specific Persona Lenses (Covering All 8 Target Roles)**:
   - **`devops`**: *DevOps Engineer, DevSecOps Engineer, Azure/AWS DevOps Engineer, Platform Engineer, SRE*
   - **`architect`**: *Cloud Solutions Architect, Cloud Engineer, Multi-Cloud Platform Architect*
   - **`infra`**: *Cloud Infrastructure Engineer, System Administrator, Linux/Windows Systems Engineer*
   - **`support`**: *Technical Support Engineer (L3), IT Specialist / Administrator, Cloud Support Engineer*
3. **Verified Certifications & Zero-Tracker ATS Policy**:
   - Preserves **Kubernetes and Cloud Native Associate (KCNA)**, **AWS Certified Solutions Architect – Associate**, **AWS Certified Developer – Associate**, **AWS Certified Cloud Practitioner**, **Kubernetes and Cloud Native Essentials (KCNE)**, and **ITIL Foundation (Pursuing)**.
   - Enforces `no_external_tracker_links` so Credly/utm tracking links never trigger enterprise ATS spam filters.
4. **Empirical Production KPIs**:
   - `99.9%` Enterprise Cloud Uptime SLA (Azure & AWS)
   - `99%` First-Day L3 Issue Resolution via structured RCA (TeKnowledge)
   - `>60%` AI Prediction Engine Accuracy on Azure OpenAI / AKS pods (GVOC)
   - `<15 Min` Multi-Environment IaC Provisioning (down from hours via Terraform & ARM/Bicep)
5. **Complete Employment & Educational Timeline**:
   - **GVOC** (Dec 2025 – Present, Remote UK)
   - **TeKnowledge** (Oct 2021 – Nov 2025, Victoria Island, Lagos)
   - **Access Bank Plc** (Jan 2021 – Sep 2021, Lagos)
   - **State Ministry of Finance, Budget & National Planning** (Mar 2019 – Mar 2020, Uyo, Akwa Ibom)
   - **Nigerian Airspace Management Agency (NAMA)** (Jul 2016 – Dec 2016, Ikeja, Lagos)
   - **University of Nigeria, Nsukka** — B.Sc. in Computer Science (2014 – 2018)
6. **Typographic & Font Ligature Repair**:
   - Automatically repairs broken PDF ligatures found in your previous CVs (such as `eƯiciency` → `efficiency` and `eƯective` → `effective`) via `ingestion/text_utils.py`.
7. **Stepcon Solutions (`RC - 8284984`) Corporate Profile**:
   - Embeds your Nigerian CAC registration (`RC - 8284984`), B2B Corp-to-Corp (C2C) pitch, service offerings, and multi-currency commercial terms (`USD`, `GBP`, `EUR`, `NGN`).

> **How to update your profile in the future**: Whenever you gain a new certification, skill, or role, simply edit [`data/profile-data.json`](data/profile-data.json). Every CLI command, CV/cover letter generator, scorer, and daily email digest reads directly from [`data/profile-data.json`](data/profile-data.json).

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
Run the full discovery → Nigeria-remote/visa/B2B filtering → active link verification → CV/letter tailoring → email digest pipeline:

```powershell
# Dry-Run mode (generates RFC 5322 .eml email file + tailored attachments in output/)
python cli/main.py digest --dry-run --force --output-dir output/digests

# Live SMTP mode (sends directly to aniekwevictor9@gmail.com once .env is configured)
python cli/main.py digest --live --force
```

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
3. The workflow in [`.github/workflows/daily_dispatch.yml`](.github/workflows/daily_dispatch.yml) automatically executes every morning at `07:00 UTC` (`08:00 AM WAT`) and can also be triggered manually via the **Actions** tab.

---

## 4. Running the Verification & Test Suites

```powershell
# Run the 5-Tier Opaque-Box & Adversarial E2E Suite (193 tests)
python e2e_tests/runner.py --pytest -v

# Run the Full Unit & Regression Test Suite (809 tests)
python -m pytest tests/ -q
```
