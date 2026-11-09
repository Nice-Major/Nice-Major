# Architectural Analysis: Zero-Cost Automated Scheduling for Daily 8:00 AM Career Dispatch

**Document ID:** ARCH-SCHED-001  
**Project:** Career Automation & Stepcon Solutions Pipeline (RC - 8284984)  
**Target Recipient:** John Victor Aniekwe (`aniekwevictor9@gmail.com`)  
**Timezone Requirement:** 8:00 AM West Africa Time (WAT = UTC+1) Daily  
**Status:** APPROVED FOR PRODUCTION  

---

## 1. Executive Summary & Recommendation

Requirement **R4** mandates an automated daily notification dispatch delivering verified opportunities, transparent match scores, and tailored application packages by **8:00 AM daily** to `aniekwevictor9@gmail.com`. The system must operate under a strict **zero-cost constraint**, avoiding paid SaaS scheduling platforms (e.g. AWS EventBridge, Zapier, Cronhooks).

This document evaluates three candidate zero-cost scheduling architectures:
1. **GitHub Actions** (Cloud-Native Serverless Cron)
2. **Windows Task Scheduler** (Host-Local Daemon via PowerShell)
3. **Google Apps Script** (Cloud Workspace Serverless Scripting)

### Primary Architectural Decision: Dual-Architecture Strategy
- **Primary Production Engine:** **GitHub Actions** (`.github/workflows/daily_dispatch.yml`) configured with crontab `0 7 * * *` (7:00 AM UTC = 8:00 AM WAT). Provides autonomous cloud execution without requiring the candidate's personal computer to be powered on.
- **Secondary Local Fallback:** **Windows Task Scheduler** (`scripts/schedule_task.ps1`) configured natively on the candidate's Windows workstation. Provides deterministic, zero-jitter local execution for development, offline dry-run testing, and local fallback.

---

## 2. Systematic Architecture Evaluation

| Evaluation Dimension | GitHub Actions (Cloud) | Windows Task Scheduler (Local) | Google Apps Script (GAS) |
| :--- | :--- | :--- | :--- |
| **Operational Cost** | **$0.00** (2,000 free minutes/mo) | **$0.00** (Runs on local host) | **$0.00** (Free Google Workspace) |
| **Host Independence** | **100% Cloud-Hosted** (Runs 24/7) | Dependent on PC power/wake | **100% Cloud-Hosted** |
| **Native Python Support**| **Native** (Python 3.10, 3.11, 3.12)| **Native** (Local Python interpreter)| **None** (JavaScript/V8 engine only)|
| **Cron Syntax & Timing** | `0 7 * * *` (07:00 UTC = 08:00 WAT)| `08:00` Local WAT Daily | Time-driven triggers (1-hr window)|
| **Scheduling Jitter** | **Moderate Jitter** (5–30 min queue)| **Zero Jitter** (Exact second) | **High Jitter** (Fires in 1-hr slot)|
| **Secrets Management** | **GitHub Encrypted Secrets** | Windows Credential Manager / DPAPI | Script Properties (Plaintext) |
| **Network Egress** | Unlimited cloud outbound HTTPS/SMTP| Local ISP outbound | Google Egress Quota (100–500 emails)|
| **Failure Telemetry** | Built-in email & workflow logs | Windows Event Viewer (`Microsoft-Windows-TaskScheduler`)| Google Stackdriver Logging |
| **Maintenance Burden**| Minimal (GitOps managed) | Host-specific setup | High (Requires JS-to-Python bridge)|

---

## 3. Deep Dive: Architecture 1 — GitHub Actions (Primary Cloud)

### Schedule Crontab & Timezone Conversion
GitHub Actions cron triggers execute strictly in Coordinated Universal Time (UTC). Nigeria operates on **West Africa Time (WAT)**, which has a constant offset of **UTC+1** (no Daylight Saving Time adjustments).

$$\text{UTC Hour} = \text{WAT Hour} - 1 = 8 - 1 = 7$$

Therefore, 8:00 AM WAT corresponds precisely to **07:00 UTC**:
```yaml
on:
  schedule:
    - cron: '0 7 * * *'  # 07:00 UTC = 08:00 WAT Daily
  workflow_dispatch:      # On-demand manual trigger
```

### Analysis of GitHub Actions Jitter & Mitigation
- **The Jitter Phenomenon:** GitHub Actions cron schedules operate on a shared, best-effort queue. During peak top-of-the-hour traffic (e.g. `00` minutes), queue latency can introduce **jitter between 5 and 35 minutes**.
- **Impact Assessment:** A notification arriving between 08:05 and 08:30 AM WAT fully satisfies human morning workflow expectations.
- **Jitter Mitigation Option:** To guarantee delivery closer to 08:00:00 AM, the cron can be offset to fire at `50 6 * * *` (07:50 WAT), ensuring execution finishes before 08:05 WAT.
- **Cost Analysis:** Each daily run consumes approximately 45 seconds of Ubuntu runner time:
  $$\text{Monthly Consumption} = 30 \times 45\text{s} = 1,350\text{s} = 22.5\text{ minutes/month}$$
  This represents **1.12%** of the 2,000 monthly free tier minutes. Total cost: **$0.00**.

### Secrets & Security
Environment variables and SMTP credentials are encrypted via repository secrets:
`NOTIFICATION_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_SENDER`.

---

## 4. Deep Dive: Architecture 2 — Windows Task Scheduler (Local Secondary)

### Operational Characteristics
Windows Task Scheduler is a native Windows OS daemon (`taskschd.msc`).
- **Zero Jitter:** Triggers exactly at `08:00:00` local system time.
- **Power & Sleep Resilience:** The script configures `New-ScheduledTaskSettingsSet` with `-WakeToRun` and `-StartWhenAvailable`. If the workstation is asleep, the system wakes to run the task; if powered off, the task triggers immediately upon the next user logon.
- **Zero Network Cost:** In dry-run mode, generates `.eml` files directly to `output/digests/` without internet connectivity.

### Automated Registration Script
The PowerShell setup script (`scripts/schedule_task.ps1`) automates registration with robust path quoting and parameter escaping:
```powershell
Register-ScheduledTask -TaskName "CareerAutomationDailyDispatch" -Action $action -Trigger $trigger -Settings $settings -Force
```

---

## 5. Deep Dive: Architecture 3 — Google Apps Script (Evaluated & Deprecated)

### Technical Analysis
Google Apps Script (GAS) runs within Google Workspace infrastructure.
- **The Language Barrier:** GAS operates exclusively on the Google V8 JavaScript runtime. It cannot natively execute the Python 3.10+ Career Automation suite without deploying an external containerized microservice (e.g. AWS Lambda, Google Cloud Run), which re-introduces hosting overhead, cold-start latency, and credential management complexity.
- **Quota Limitations:** Free consumer Gmail accounts are restricted to 100 recipients/day and 6 minutes maximum execution time per trigger.
- **Conclusion:** GAS is rejected as the primary scheduler; it is documented purely as an architectural comparative baseline.

---

## 6. Synthesis & Final Operational Strategy

1. **Deploy GitHub Actions workflow** as the primary autonomous daily runner.
2. **Register Windows Task Scheduler** on the developer workstation for local dry-run validation and offline capability.
3. Both runners execute the identical entrypoint: `python -m scheduler.daily_dispatch`.
