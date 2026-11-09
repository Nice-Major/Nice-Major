# Original User Request

## Initial Request — 2026-11-07T01:05:26Z

Build an automated career development, technical recruitment, and consultancy opportunity matching workflow for candidate John Victor Aniekwe and IT consultancy Stepcon Solutions (RC - 8284984). The system must ingest candidate data, discover and verify relevant opportunities, tailor CVs and application materials against global standards, support interactive on-demand job evaluation, and deliver daily opportunity digests.

Working directory: ~/teamwork_projects/career_automation
Integrity mode: development

Reference material:
- Candidate LinkedIn: https://www.linkedin.com/in/victor-aniekwe/
- Candidate GitHub: https://github.com/Nice-Major/Nice-Major.git
- Candidate Email: aniekwevictor9@gmail.com
- Candidate CVs: Provided PDF profiles (DevOps/Platform Architect & Cloud Infrastructure Engineer, 5+ years experience, AWS & KCNA certified)
- Business Entity: Stepcon Solutions (RC - 8284984, registered with Nigerian CAC)

## Requirements

### R1. Candidate Profile Data Ingestion and Representation
The system must parse, structure, and model candidate qualifications, skills, and work history from the candidate's CVs, LinkedIn profile, and GitHub repository. It must capture core competencies across Azure, AWS, Kubernetes, CI/CD, Infrastructure as Code, Linux/Windows administration, and DevSecOps, including verified certifications.

### R2. Global Standards CV and Cover Letter Tailoring Engine
The system must analyze target job descriptions (specifically Cloud Solutions Architect, Cloud Infrastructure Engineer, Cloud Engineer, Dev(Sec)Ops Engineer, System Administrator, IT Specialist/Administrator, Technical Support Engineer, Azure/AWS DevOps Engineer) and produce tailored, ATS-friendly CVs and cover letters. Generated materials must adjust formatting, tone, and grammar according to global technical recruitment standards and research-backed practices, aligning the candidate's actual experience with role requirements.

### R3. Opportunity Search and Verification Engine
The system must identify recently posted and verified opportunities from online recruitment platforms, public job boards, and company career pages. Opportunities must be filtered for eligibility to work remotely from Nigeria, visa/relocation sponsorship offers, research/fellowship programs, and contract or consultancy opportunities.

### R4. Automated Daily 8:00 AM Notification Dispatch
The system must implement a cost-effective, automated daily mailing workflow that sends verified high-match opportunities to aniekwevictor9@gmail.com by 8:00 AM daily. Each email must include opportunity summaries, fit analysis, and the corresponding tailored CV and application documents. The implementation must evaluate and document trade-offs across zero-cost scheduling approaches (including local schedulers, GitHub Actions free tiers, and Google Apps Script).

### R5. On-Demand Interactive Evaluation and Tailoring CLI
The system must provide a command-line interface or file-based input allowing the candidate to supply a job description on demand. The system must evaluate and score candidate suitability against the opportunity, provide transparent rating feedback, and generate tailored application materials if the role aligns.

### R6. Stepcon Solutions IT Consultancy Business Pipeline
The system must provide an automated workflow for Stepcon Solutions (RC - 8284984) to discover global IT service contracts, government/public tenders, and corporate consultancy engagements matching the firm's cloud, platform engineering, and infrastructure offerings, generating tailored business proposals and pitch documentation. If execution constraints require prioritizing between workflows, the candidate career workflow takes primary operational precedence.

### R7. Controlled Testing and Environment Configuration
The system must read email and API credentials from environment variables and must include a dry-run or mock mode that validates data ingestion, opportunity search, tailoring, and email formatting without sending live emails or calling external paid APIs.

## Acceptance Criteria

### Profile Ingestion & Modeling
- [ ] Parser extracts candidate experience, certifications, and technical proficiencies from provided CV data and profile sources without omitting verified credentials.
- [ ] Candidate profile data is structured into a machine-readable schema for evaluation and tailoring.

### Document Generation
- [ ] Tailoring engine produces CVs and cover letters customized to specific job descriptions across all specified role types (Cloud Architect, DevOps, SysAdmin, Support).
- [ ] Generated documents strictly reflect the candidate's actual background while incorporating relevant job description keywords and professional phrasing.
- [ ] Output documents are generated in standard formats (plain text, markdown, or PDF-ready formats).

### Opportunity Discovery & Filtering
- [ ] Search engine retrieves and validates job listings, rejecting expired, closed, or non-matching postings.
- [ ] Filters correctly categorize opportunities by remote eligibility (working from Nigeria), visa/relocation sponsorship, and contract/consultancy type.

### Automated Scheduling & Mailing
- [ ] Daily schedule is configured for 8:00 AM execution.
- [ ] Email notification builder formats a daily digest containing opportunity links, role details, match ratings, and generated application packages.
- [ ] System documentation compares implementation architectures (GitHub Actions, Google Apps Script, local cron/task scheduler) detailing cost, limitations, and operational trade-offs.

### Interactive Evaluation CLI
- [ ] CLI accepts arbitrary job description text or file input and outputs a numerical match score with rationale.
- [ ] CLI produces tailored application documents for matched inputs upon user command.

### Stepcon Solutions Consultancy Pipeline
- [ ] Pipeline identifies business IT consultancy leads and generates tailored pitch/proposal drafts referencing Stepcon Solutions (RC - 8284984) capabilities.

### Verification & Test Suite
- [ ] Automated test suite verifies profile parsing, match scoring, document generation, and email formatting against synthetic test job postings.
- [ ] Dry-run execution runs end-to-end without requiring live external SMTP or paid API credentials.

---
Operational Parameters:
Working directory: C:\Users\user\teamwork_projects\career_automation\.agents\teamwork\orchestrator\
Project Workspace: C:\Users\user\teamwork_projects\career_automation
Original request: C:\Users\user\teamwork_projects\career_automation\.agents\teamwork\ORIGINAL_REQUEST.md
Identity: teamwork_orchestrator
Sentinel: 93994e10-6cac-4bca-bd47-8f679f09cc03
Existing files & candidate documents located at: C:\Users\user\Downloads\Nice_Major_Portfolio_and_Automation_Suite
