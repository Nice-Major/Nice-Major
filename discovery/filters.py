"""
Geographic & Mobility Eligibility Filter for Career Automation & Stepcon Pipeline.
Module: discovery.filters
Feature: F09 (Geo-Eligibility & Sponsorship Filter)
Milestone: M3 (Opportunity Discovery, Geo-Filtering & Verification)

Filters opportunities for remote eligibility from Nigeria (Worldwide, EMEA, CET, UTC+1),
visa/relocation sponsorship, and contract/consultancy types, while enforcing strict hard
rejection of US-only, W2-only, security clearance, and payroll-tax locked roles.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Import candidate models with resilient fallback
try:
    from ingestion.models import CandidateProfile
    from ingestion.parser import get_embedded_default_profile
except ImportError:
    CandidateProfile = Any
    get_embedded_default_profile = lambda: {}


# ============================================================================
# 1. Authoritative Regex Taxonomies
# ============================================================================

HARD_DISQUALIFIERS: List[str] = [
    # US Citizenship & Legal Status Locks
    r"\bus citizen(?:s)? only\b",
    r"\bmust be (?:a )?u\.?s\.? citizen\b",
    r"\bmust be a us citizen\b",
    r"\brequires? u\.?s\.? citizenship\b",
    r"\bu\.s\. citizenship required\b",
    r"\bus citizenship required\b",
    r"\bu\.?s\.? citizen(?:s)? (?:required|or green card)\b",
    r"\bus persons? only\b",
    r"\bpermanent residents? or us citizens?\b",
    r"\bcandidates outside the (?:us|united states) (?:will not be considered|rejected)\b",
    r"\bonly open to candidates (?:in|within) the (?:us|united states)\b",
    r"\bcandidates must reside in the (?:us|united states)\b",

    # Domestic Geographic & Residence Locks
    r"\b(?:u\.s\.|usa|united states)\s+only\b",
    r"[-–—,/:|]\s*u\.?s\.?\s+only\b",
    r"\b(?:location|eligibility|residency|status|authorized|open\s+to|role|title|workplace|position)\s*[-–—:/|]?\s*u\.?s\.?\s+only\b",
    r"\b(?:is|are|must\s+be|open\s+(?:to|for)|restricted\s+to|available\s+(?:to|for))\s+u\.?s\.?\s+only\b",
    r"\b(?:location\s*:\s*|in\s+the\s+)u\.?s\.?\s+only\b",
    r"\bu\.?s\.?\s+only\s+(?:candidates?|applicants?|roles?|positions?|residents?|citizens?|workers?|hires?|employees?)\b",
    r"[\(\[{]\s*u\.?s\.?\s+only\b",
    r"(?m)^\s*u\.?s\.?\s+only\s*$",
    r"\bu\.s\. only\b",
    r"\busa only\b",
    r"\bunited states only\b",
    r"\bremote\s*[-–—,/:\s|]\s*(?:u\.?s\.?(?:a\.)?|usa|united states)(?:\s+only)?\b",
    r"\bremote\s*[-–—,/:\s|]?\s*[\(\[]\s*(?:u\.?s\.?(?:a\.)?|usa|united states)(?:\s*[-/]?\s*(?:only|based|residents?))?\s*[\)\]]",
    r"\bremote\s*[-–—,/:\s|]?\s*[\(\[]\s*(?:u\.?s\.?(?:a\.)?|usa|united states)\s*(?:/|or|and|,)\s*canada\s*[\)\]]",
    r"\b(?:u\.?s\.?(?:a\.)?|usa|united states)\s+remote(?:\s+only)?\b",
    r"\bremote\s+(?:in\s+the\s+)?(?:u\.?s\.?(?:a\.)?|usa|united states)(?:\s+only)?\b",
    r"\bremote\s+in\s+(?:the\s+)?(?:u\.?s\.?(?:a\.)?|usa|united states|canada)\b",
    r"\bcontinental us only\b",
    r"\bmust reside in the continental us\b",
    r"\bmust reside in the continental united states\b",
    r"\bmust reside in the (?:us|united states)\b",
    r"\bmust reside in (?:us|canada)\b",
    r"\bmust reside in us/canada\b",
    r"\bmust reside in north america\b",
    r"\bcandidate must be located in canada\b",
    r"\bcanada only\b",
    r"\bremote\s*[-–—,/:\s|]\s*canada(?:\s+only)?\b",
    r"\bremote\s*[-–—,/:\s|]?\s*[\(\[]\s*canada(?:\s*[-/]?\s*(?:only|based|residents?))?\s*[\)\]]",
    r"\bcanada\s+remote(?:\s+only)?\b",
    r"\bremote\s+canada(?:\s+only)?\b",

    # State-Specific Payroll Tax Restrictions
    r"\b(state )?payroll tax purposes\b",
    r"\bmust reside in california\b",
    r"\bcalifornia for (state )?payroll tax purposes\b",
    r"\bmust reside in [a-z\s]+ for (state )?(payroll )?tax purposes\b",

    # Security Clearance Locks
    r"\bactive ts/sci\b",
    r"\bts/sci\b",
    r"\btop secret\s*/\s*sci\b",
    r"\btop secret/sci\b",
    r"\btop secret\b",
    r"\bsecret clearance\b",
    r"\bactive secret clearance\b",
    r"\bsecurity clearance required\b",
    r"\bsecurity clearance\b",
    r"\bpolygraph\b",
    r"\bactive clearance\b",

    # Domestic Employment / Contract Locks
    r"\bw2 only\b",
    r"\bw-2 only\b",
    r"\bstrictly w2\b",
    r"\bno c2c\b",
    r"\bno corp-to-corp\b",
    r"\bnot open to c2c\b",
    r"\bno 1099\b",
    r"\bno third part(y|ies)\b",

    # Mandatory On-Site Locks & Negative Remote Patterns
    r"\b100%\s*on-?site\b",
    r"\bmust\s+work\s+on-?site\b",
    r"\bmandatory\s+on-?site\b",
    r"\bstrictly\s+on-?site\b",
    r"\bin-person\s+mandatory\b",
    r"\bno\s+remote\b",
    r"\bzero\s+remote\b",
    r"\b(?:no|not|non)[\s-]remote\b",
    r"\bnot\s+open\s+to\s+remote(?:\s+(?:work|workers?|candidates?|applicants?|employment))?\b",
    r"\b(?:do\s+not|don\'?t|does\s+not|doesn\'?t|cannot|can\'?t|can\s+not|will\s+not|won\'?t|unable\s+to)\s+(?:offer|support|allow|permit|accept|consider)\s+remote(?:\s+work|\s+employment|\s+candidates?|\s+applicants?)?\b",
    r"\bremote(?:\s+work|\s+option|\s+employment)?\s+is\s+(?:strictly\s+)?(?:not\s+(?:permitted|allowed|available|offered|supported|possible|an\s+option|considered)|prohibited|forbidden|disallowed)\b",
    r"\bremote(?:\s+(?:work|candidates?|applicants?|applications?|options?|employment))?\s+(?:(?:will\s+not|cannot)\s+be|(?:is\s+not|are\s+not)(?:\s+be)?)\s+(?:considered|accepted|supported|permitted|offered|allowed)\b",
    r"\bremote(?:\s+work)?\s+is\s+(?:strictly\s+)?prohibited\b",
    r"\b(?:this\s+)?(?:role|position|job)\s+is\s+not\s+remote\b",
    r"\bnot\s+a\s+remote\s+(?:role|position|job|opportunity|opening)\b",
    r"\bhybrid\s+role.*office\s+mandatory\b",
    r"\bon-?site\s+in\s+[a-z\s]+\s+office\s+mandatory\b",
]

REMOTE_WORLDWIDE_PATTERNS: List[str] = [
    r"\bworldwide\b",
    r"\bwork from anywhere\b",
    r"\banywhere\b",
    r"\bglobal remote\b",
    r"\bglobal\b",
    r"\bwfa\b",
    r"\b100%\s*remote\b",
    r"\bfully remote\b",
    r"\ball-remote\b",
    r"\bremote worldwide\b",
]

REMOTE_REGIONAL_PATTERNS: List[str] = [
    # Explicit EMEA Remote
    r"\bremote\s*[-–—,/]?\s*emea\b",
    r"\bemea\s*[-–—,/]?\s*remote\b",
    r"\bremote\s*[\(\[]\s*emea\b",
    r"\bemea\s*[\(\[]\s*remote\b",
    r"\bemea\s*\([^)]*remote[^)]*\)",
    r"\bremote\s*\([^)]*emea[^)]*\)",
    r"\b(?:within|across|in)\s+emea\s+(?:remote|remotely)\b",
    r"\bremote\s+(?:within|across|in)?\s*emea\b",

    # Explicit Europe Remote
    r"\bremote\s*[-–—,/]?\s*europe\b",
    r"\beurope\s*[-–—,/]?\s*remote\b",
    r"\bremote\s*[\(\[]\s*europe\b",
    r"\beurope\s*[\(\[]\s*remote\b",
    r"\beurope\s*\([^)]*remote[^)]*\)",
    r"\bremote\s*\([^)]*europe[^)]*\)",
    r"\b(?:within|across|in)\s+europe\s+(?:remote|remotely)\b",
    r"\bremote\s+(?:within|across|in)?\s*europe\b",

    # Explicit Africa Remote
    r"\bremote\s*[-–—,/]?\s*africa\b",
    r"\bafrica\s*[-–—,/]?\s*remote\b",
    r"\bremote\s*[\(\[]\s*africa\b",
    r"\bafrica\s*[\(\[]\s*remote\b",
    r"\bafrica\s*\([^)]*remote[^)]*\)",
    r"\bremote\s*\([^)]*africa[^)]*\)",
    r"\b(?:within|across|in)\s+africa\s+(?:remote|remotely)\b",
    r"\bremote\s+(?:within|across|in)?\s*africa\b",

    # Local Candidate Market (Nigeria / Lagos)
    r"\bnigeria\b",
    r"\blagos\b",
]

REMOTE_TIMEZONE_PATTERNS: List[str] = [
    r"\bremote\s*[-–—,/]?\s*cet\b",
    r"\bcet\s*[-–—,/]?\s*remote\b",
    r"\bcet\s+synchronous\b",
    r"\b(?:synchronous|aligned|overlap)\s+(?:with\s+)?cet\b",
    r"\bcet\s+timezone\b",
    r"\bcet\s+(?:business\s+)?hours\b",
    r"\bcet\s*\(?remote\)?\b",
    r"\b(?:remote\s*[-–—,/]?\s*)?utc\s*[\+\-]\s*1\b",
    r"\b(?:remote\s*[-–—,/]?\s*)?utc\s*[\+\-]\s*0\b",
    r"\b(?:remote\s*[-–—,/]?\s*)?gmt\s*[\+\-]\s*1\b",
    r"\b(?:remote\s*[-–—,/]?\s*)?gmt\s*[\+\-]\s*0\b",
    r"\baligned\s+with\s+utc\s*[\+\-]\s*1\b",
    r"\baligned\s+with\s+utc\s*[\+\-]\s*0\s*/\s*gmt\b",
    r"\buk\s+synchronous\b",
    r"\buk\s+timezone\b",
]

REMOTE_WORK_STYLE_PATTERNS: List[str] = [
    r"\basynchronous remote\b",
    r"\basynchronous\b",
    r"\basync remote\b",
    r"\basync\b",
]

GENERIC_REMOTE_PATTERNS: List[str] = [
    r"\bremote\b",
]

NO_SPONSORSHIP_PATTERNS: List[str] = [
    # 1. Direct explicit negation declarations
    r"\bno\s+(?:visa\s+|work\s+visa\s+|work\s+)?sponsorship\b",
    r"\bno\s+sponsorship\b",
    r"\bzero\s+(?:visa\s+)?sponsorship\b",
    r"\bno\s+(?:work\s+)?visa\s+(?:or|and)\s+relocation(?:\s+assistance)?\b",
    r"\bno\s+(?:relocation\s+or\s+visa\s+sponsorship|visa\s+sponsorship\s+or\s+relocation)\b",
    r"\bno\s+(?:visa|immigration)\s+support\b",

    # 2. Employer refusal / inability verbs (sponsor, provide, offer, extend, grant, consider)
    r"\b(?:will\s+not|won'?t|cannot|can'?t|can\s+not|unable\s+to|not\s+able\s+to|do\s+not|don'?t|does\s+not|doesn'?t)\s+sponsor(?:\s+(?:visas?|work\s+visas?|applicants?|candidates?|foreign\s+workers?))?\b",
    r"\b(?:will\s+not|won'?t|cannot|can'?t|can\s+not|unable\s+to|not\s+able\s+to|do\s+not|don'?t|does\s+not|doesn'?t|not\s+offering|not\s+providing)\s+(?:provide|offer|support|extend|grant|consider)\s+(?:any\s+)?(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:not\s+providing|not\s+offering)\s+(?:any\s+)?(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:will\s+not|won'?t|cannot|can'?t|can\s+not|unable\s+to|not\s+able\s+to|do\s+not|don'?t|does\s+not|doesn'?t|not\s+offering|not\s+providing)\s+(?:provide|offer|extend|grant)\s+(?:any\s+)?(?:visa|work\s+permit|immigration)\s+(?:support|assistance)\b",

    # 3. Passive voice & availability constructs (is not provided, is unavailable, cannot be provided)
    r"\b(?:(?:relocation\s+(?:and|or)\s+)?(?:visa\s+|work\s+)?sponsorship|(?:visa\s+|work\s+)?visa\s+support)\s+(?:is\s+|will\s+be\s+|can\s+be\s+)?(?:not\s+(?:available|provided|offered|supported)|unavailable)\b",
    r"\b(?:(?:relocation\s+(?:and|or)\s+)?(?:visa\s+|work\s+)?sponsorship|(?:visa\s+|work\s+)?visa\s+support)\s+not\s+(?:available|provided|offered|supported)\b",
    r"\b(?:(?:relocation\s+(?:and|or)\s+)?(?:visa\s+|work\s+)?sponsorship|(?:visa\s+|work\s+)?visa\s+support)\s+(?:cannot|will\s+not)\s+be\s+(?:provided|offered|supported|extended)\b",
    r"\bsponsorship\s+(?:is\s+)?(?:not\s+available|unavailable|not\s+provided)\b",

    # 4. Candidate requirement & authorization independence (without sponsorship, must not require)
    r"\bwithout\s+(?:the\s+need\s+for\s+|any\s+need\s+for\s+|need\s+for\s+)?(?:visa\s+|work\s+)?sponsorship\b",
    r"\bwithout\s+requiring\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:must\s+not|does\s+not|do\s+not|cannot|will\s+not|not)\s+require\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\bnot\s+requiring\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:no|without)\s+requirement\s+for\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\b(?:no|with\s+no)\s+need\s+for\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\bno\s+future\s+sponsorship\b",
    r"\b(?:not\s+eligible|ineligible)\s+for\s+(?:visa\s+|work\s+)?sponsorship\b",
    r"\bmust\s+have\s+(?:existing|current|valid|legal)\s+work\s+authorization\b",
    r"\bexisting\s+work\s+authorization\s+required\b",
    r"\bwithout\s+sponsorship\b",
]

VISA_SPONSORSHIP_PATTERNS: List[str] = [
    # 1. Direct visa sponsorship noun phrases
    r"\bvisa sponsorship\b",
    r"\bskilled worker visa\b",
    r"\bwork visa sponsorship\b",
    r"\bwork permit sponsorship\b",
    r"\bh-?1b transfer\b",
    r"\bvisa support\b",

    # 2. Relocation perks & packages
    r"\brelocation assistance\b",
    r"\brelocation package\b",
    r"\brelocation support\b",
    r"\bfull relocation\b",
    r"\brelocation provided\b",

    # 3. Availability declarations
    r"\bsponsorship available\b",
    r"\bsponsorship provided\b",

    # 4. Verb phrases: future, present, and active declarations
    r"\bwill sponsor\b",
    r"\b(?:we\s+|company\s+|employer\s+|client\s+|our\s+company\s+|the\s+company\s+)?sponsors?\s+(?:work\s+|employment\s+)?visas?\b",
    r"\b(?:we\s+|company\s+|employer\s+|client\s+)?sponsors?\s+(?:international\s+|foreign\s+)?(?:candidates?|applicants?)(?:\s+for\s+(?:employment\s+|work\s+)?visas?)?\b",
    r"\b(?:open\s+to\s+|willing\s+to\s+|able\s+to\s+|happy\s+to\s+)?sponsor(?:s|ing)?\s+(?:visas?|work\s+visas?|international\s+candidates?|foreign\s+workers?)\b",
    r"\bsponsors?\s+visas?\b",
    r"\bsponsoring\s+visas?\b",
]

NO_CONTRACT_C2C_PATTERNS: List[str] = [
    # 1. W2 & Direct Hire Exclusivity Locks
    r"\bw-?2\s+only\b",
    r"\bstrictly\s+w-?2\b",
    r"\bw-?2\s+(?:employment|candidates?|applicants?|roles?)\s+only\b",
    r"\bw-?2\s+candidates\s+only\b",
    r"\bdirect[\s-]hire\s+only\b",
    r"\bdirect[\s-]placement\s+only\b",
    r"\bfull[\s-]time\s+direct[\s-]hire\b",
    r"\bpermanent\s+direct[\s-]hire\b",

    # 2. Negative 1099 Exclusions
    r"\bno\s+1099(?:'s|s)?\b",
    r"\bnot\s+open\s+to\s+1099(?:'s|s)?\b",
    r"\b(?:cannot|unable\s+to|will\s+not|do\s+not|does\s+not)\s+(?:accept|support|work\s+with|offer)\s+1099\b",
    r"\b1099\s+(?:is\s+)?not\s+(?:permitted|allowed|accepted|offered|available|supported|an\s+option)\b",

    # 3. Negative C2C / Corp-to-Corp Exclusions
    r"\bno\s+c2c\b",
    r"\bno\s+c[\s-]to[\s-]c\b",
    r"\bno\s+corp[\s-]to[\s-]corp\b",
    r"\bnot\s+open\s+to\s+c2c\b",
    r"\bnot\s+open\s+to\s+c[\s-]to[\s-]c\b",
    r"\bnot\s+open\s+to\s+corp[\s-]to[\s-]corp\b",
    r"\b(?:cannot|unable\s+to|will\s+not|do\s+not|does\s+not)\s+(?:accept|support|work\s+with|offer)\s+(?:c2c|c[\s-]to[\s-]c|corp[\s-]to[\s-]corp)\b",
    r"\b(?:c2c|c[\s-]to[\s-]c|corp[\s-]to[\s-]corp)\s+(?:is\s+)?not\s+(?:permitted|allowed|accepted|offered|available|supported|an\s+option)\b",

    # 4. Negative B2B Exclusions
    r"\bno\s+b2b\b",
    r"\bno\s+business[\s-]to[\s-]business\b",
    r"\bnot\s+open\s+to\s+b2b\b",
    r"\bnot\s+open\s+to\s+business[\s-]to[\s-]business\b",

    # 5. Negative Contractor, Freelance, Subcontractor & Third-Party Exclusions
    r"\bno\s+contractors?\b",
    r"\bnot\s+open\s+to\s+contractors?\b",
    r"\b(?:cannot|unable\s+to|will\s+not)\s+accept\s+contractors?\b",
    r"\bno\s+subcontract(?:ing|ors?)\b",
    r"\bnot\s+open\s+to\s+subcontract(?:ing|ors?)\b",
    r"\bno\s+(?:3rd|third)[\s-]part(?:y|ies)\b",
    r"\bno\s+agenc(?:y|ies)\b",
    r"\bno\s+freelanc(?:e|ers?|ing)\b",
    r"\bnot\s+open\s+to\s+freelanc(?:e|ers?)\b",
    r"\bno\s+consulting\s+firms?\b",
    r"\bno\s+consultanc(?:y|ies)\b",
    r"\bcannot\s+support\s+(?:c2c|corp-to-corp|1099|b2b)\b",
]

CONTRACT_C2C_PATTERNS: List[str] = [
    r"\bcorp-to-corp\b",
    r"\bc2c\b",
    r"\bb2b\b",
    r"\bbusiness-to-business\b",
    r"\b1099\b",
    r"\bindependent contractor\b",
    r"\bcontractor\b",
    r"\bfixed-term contract\b",
    r"\bconsultancy\b",
    r"\bconsultant\b",
    r"\bconsulting engagement\b",
    r"\bfreelance\b",
    r"\bfreelancer\b",
    r"\bstatement of work\b",
    r"\bsow\b",
    r"\bmonthly retainer\b",
]

RESEARCH_FELLOWSHIP_PATTERNS: List[str] = [
    r"\bfellowship\b",
    r"\bresearch fellow\b",
    r"\bresidency program\b",
    r"\bresearch residency\b",
    r"\bai residency\b",
    r"\bpostdoctoral\b",
    r"\bpostdoc\b",
    r"\bvisiting researcher\b",
    r"\bvisiting scholar\b",
    r"\bacademic program\b",
    r"\bresearch grant\b",
]


# ============================================================================
# 2. Output Data Model
# ============================================================================

@dataclass
class EligibilityResult:
    """
    Detailed evaluation outcome for an opportunity's geographic, mobility,
    sponsorship, and contracting eligibility.
    Provides dual attribute and dict subscript access.
    """
    is_eligible: bool
    remote_eligible_nigeria: bool
    visa_sponsorship: bool
    contract_b2b: bool
    research_fellowship: bool
    disqualified: bool
    disqualification_reasons: List[str] = field(default_factory=list)
    positive_indicators: List[str] = field(default_factory=list)
    mobility_score: float = 0.0
    status: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_eligible": self.is_eligible,
            "remote_eligible_nigeria": self.remote_eligible_nigeria,
            "nigeria_eligible": self.remote_eligible_nigeria,
            "visa_sponsorship": self.visa_sponsorship,
            "visa_sponsored": self.visa_sponsorship,
            "contract_b2b": self.contract_b2b,
            "research_fellowship": self.research_fellowship,
            "disqualified": self.disqualified,
            "disqualification_reasons": list(self.disqualification_reasons),
            "positive_indicators": list(self.positive_indicators),
            "mobility_score": self.mobility_score,
            "status": self.status,
        }

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in ("nigeria_eligible", "remote_eligible_nigeria"):
            return self.remote_eligible_nigeria
        if item in ("visa_sponsored", "visa_sponsorship"):
            return self.visa_sponsorship
        raise KeyError(item)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in ("nigeria_eligible", "remote_eligible_nigeria"):
            self.remote_eligible_nigeria = bool(value)
        elif key in ("visa_sponsored", "visa_sponsorship"):
            self.visa_sponsorship = bool(value)
        elif hasattr(self, key):
            setattr(self, key, value)
        else:
            raise KeyError(key)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in ("nigeria_eligible", "visa_sponsored")

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


# ============================================================================
# 3. Core Predicate & Evaluation Functions
# ============================================================================

def has_disqualifiers(text: Any) -> bool:
    """
    Evaluates whether the given text contains any hard disqualifiers
    (US-only, W2-only, security clearance, state payroll tax lock, etc.).
    """
    if text is None:
        return False
    norm_text = str(text).lower()
    if not norm_text.strip():
        return False

    for pattern in HARD_DISQUALIFIERS:
        if re.search(pattern, norm_text):
            return True
    return False


def is_remote_eligible(location_or_text: Any) -> bool:
    """
    Determines if a location string or job description is eligible for a candidate
    working remotely from Lagos, Nigeria (UTC+1 / CET synchronous).

    Strict Rules:
    1. Checks hard disqualifiers FIRST. If any match -> False immediately.
    2. Empty or pure whitespace -> False.
    3. Checks positive signals (Worldwide, EMEA, CET, UTC+1, Africa, generic Remote).
    """
    if location_or_text is None:
        return False
    norm_text = str(location_or_text).lower()
    if not norm_text.strip():
        return False

    # 1. Hard Disqualifiers Check FIRST!
    if has_disqualifiers(norm_text):
        return False

    # 2. Check Positive Signals
    indicator_groups = [
        REMOTE_WORLDWIDE_PATTERNS,
        REMOTE_REGIONAL_PATTERNS,
        REMOTE_TIMEZONE_PATTERNS,
        REMOTE_WORK_STYLE_PATTERNS,
        GENERIC_REMOTE_PATTERNS,
    ]
    for group in indicator_groups:
        for pattern in group:
            if re.search(pattern, norm_text):
                return True

    return False


def detect_visa_sponsorship(text: Any) -> bool:
    """
    Detects whether the text offers visa sponsorship or relocation assistance.

    Strict Rules:
    1. Checks explicit negation patterns FIRST ("no visa sponsorship will be provided").
       If negation found -> False immediately.
    2. Checks positive sponsorship/relocation patterns.
    """
    if text is None:
        return False
    norm_text = str(text).lower()
    if not norm_text.strip():
        return False

    # 1. Explicit Negation Check FIRST!
    for neg_pattern in NO_SPONSORSHIP_PATTERNS:
        if re.search(neg_pattern, norm_text):
            return False

    # 2. Positive Sponsorship Check
    for pos_pattern in VISA_SPONSORSHIP_PATTERNS:
        if re.search(pos_pattern, norm_text):
            return True

    return False


def detect_contract_c2c(text: Any) -> bool:
    """
    Detects whether the opportunity supports Corp-to-Corp (C2C), B2B, 1099,
    or independent consultancy contracting.
    """
    if text is None:
        return False
    norm_text = str(text).lower()
    if not norm_text.strip():
        return False

    # 1. Check negative restrictions FIRST!
    for neg_pattern in NO_CONTRACT_C2C_PATTERNS:
        if re.search(neg_pattern, norm_text):
            return False

    for pattern in CONTRACT_C2C_PATTERNS:
        if re.search(pattern, norm_text):
            return True

    return False


# Contract alias for test suite compatibility
detect_contract_consultancy = detect_contract_c2c


def detect_research_fellowship(text: Any) -> bool:
    """
    Detects whether the opportunity represents an academic, research, or fellowship program.
    """
    if text is None:
        return False
    norm_text = str(text).lower()
    if not norm_text.strip():
        return False

    for pattern in RESEARCH_FELLOWSHIP_PATTERNS:
        if re.search(pattern, norm_text):
            return True

    return False


# Contract alias for test suite compatibility
detect_fellowship_research = detect_research_fellowship


def evaluate_location_mobility(text: Any) -> Tuple[float, str]:
    """
    Evaluates text for location mobility score and classification status.
    Returns: (score: float, status: str)

    Contracts:
    - Empty string -> (60.0, "neutral") (Satisfies assert status in ["unspecified", "neutral", "review"])
    - Hard disqualifier -> (0.0, "disqualified")
    - Remote eligible (Worldwide/EMEA/CET/Nigeria) -> (100.0, "eligible")
    - Visa sponsorship -> (95.0, "visa_sponsorship")
    - Contract C2C -> (90.0, "contract_b2b")
    - Research/Fellowship -> (90.0, "fellowship")
    - Remote -> (85.0, "remote")
    - Otherwise -> (60.0, "neutral")
    """
    if text is None:
        return 60.0, "neutral"
    norm_text = str(text).lower().strip()
    if not norm_text:
        return 60.0, "neutral"

    if has_disqualifiers(norm_text):
        return 0.0, "disqualified"

    if is_remote_eligible(norm_text):
        return 100.0, "eligible"

    if detect_visa_sponsorship(norm_text):
        return 95.0, "visa_sponsorship"

    if detect_contract_c2c(norm_text):
        return 90.0, "contract_b2b"

    if detect_research_fellowship(norm_text):
        return 90.0, "fellowship"

    if "remote" in norm_text:
        return 85.0, "remote"

    return 60.0, "neutral"


def evaluate_opportunity_eligibility(
    job: Any,
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
) -> EligibilityResult:
    """
    Comprehensive multi-factor eligibility evaluation of an opportunity against candidate mobility criteria.
    """
    if job is None:
        return EligibilityResult(
            is_eligible=False,
            remote_eligible_nigeria=False,
            visa_sponsorship=False,
            contract_b2b=False,
            research_fellowship=False,
            disqualified=True,
            disqualification_reasons=["Null job opportunity provided"],
            status="disqualified",
        )

    # Extract fields with polymorphism (JobOpportunity, dict, or object)
    if isinstance(job, dict):
        title = str(job.get("title", ""))
        location = str(job.get("location", ""))
        description = str(job.get("description", ""))
    else:
        title = str(getattr(job, "title", ""))
        location = str(getattr(job, "location", ""))
        description = str(getattr(job, "description", ""))

    combined_text = f"{title} {location} {description}"

    # 1. Hard Disqualifiers Check
    disqualified = False
    disqualification_reasons: List[str] = []
    if has_disqualifiers(combined_text):
        disqualified = True
        disqualification_reasons.append("Matched hard disqualifier pattern in location or description")

    # 2. Positive Pathways Check
    remote_ok = is_remote_eligible(location) or is_remote_eligible(combined_text)
    visa_ok = detect_visa_sponsorship(description) or detect_visa_sponsorship(location)
    contract_ok = detect_contract_c2c(combined_text)
    fellowship_ok = detect_research_fellowship(combined_text)

    # Candidate has mobility preferences:
    # 1. Remote from Nigeria (Worldwide/EMEA/CET)
    # 2. Visa-Sponsored Relocation (e.g. UK Skilled Worker)
    # 3. B2B / C2C consultancy
    # 4. Research / Fellowship
    is_eligible = not disqualified and (remote_ok or visa_ok or contract_ok or fellowship_ok)

    score, status = evaluate_location_mobility(combined_text if not remote_ok else location)
    if disqualified:
        status = "disqualified"
        score = 0.0

    return EligibilityResult(
        is_eligible=is_eligible,
        remote_eligible_nigeria=remote_ok and not disqualified,
        visa_sponsorship=visa_ok and not disqualified,
        contract_b2b=contract_ok and not disqualified,
        research_fellowship=fellowship_ok and not disqualified,
        disqualified=disqualified,
        disqualification_reasons=disqualification_reasons,
        mobility_score=score,
        status=status,
    )


def categorize_opportunity(
    job: Any,
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Helper returning a summary dictionary of eligibility categorization."""
    res = evaluate_opportunity_eligibility(job, candidate)
    return res.to_dict()


def filter_opportunities(
    jobs: List[Any],
    candidate: Optional[Union[CandidateProfile, Dict[str, Any]]] = None,
) -> List[Any]:
    """
    Filters a list of jobs, admitting only those meeting candidate mobility eligibility criteria.
    Enforces polymorphic candidate handling and tags admitted jobs with eligibility flags.
    """
    if not jobs or not isinstance(jobs, (list, tuple)):
        return []

    filtered: List[Any] = []
    for job in jobs:
        if job is None:
            continue

        result = evaluate_opportunity_eligibility(job, candidate=candidate)
        if result.is_eligible:
            # Tag the job
            if isinstance(job, dict):
                job["remote_eligible_nigeria"] = result.remote_eligible_nigeria
                job["nigeria_eligible"] = result.remote_eligible_nigeria
                job["visa_sponsorship"] = result.visa_sponsorship
                job["visa_sponsored"] = result.visa_sponsorship
                job["contract_b2b"] = result.contract_b2b
                job["is_remote"] = result.remote_eligible_nigeria
                job["eligibility_status"] = result.status
            else:
                if hasattr(job, "remote_eligible_nigeria"):
                    job.remote_eligible_nigeria = result.remote_eligible_nigeria
                if hasattr(job, "nigeria_eligible"):
                    job.nigeria_eligible = result.remote_eligible_nigeria
                if hasattr(job, "visa_sponsorship"):
                    job.visa_sponsorship = result.visa_sponsorship
                if hasattr(job, "visa_sponsored"):
                    job.visa_sponsored = result.visa_sponsorship
                if hasattr(job, "contract_b2b"):
                    job.contract_b2b = result.contract_b2b
                if hasattr(job, "is_remote"):
                    job.is_remote = result.remote_eligible_nigeria
                if hasattr(job, "eligibility_status"):
                    setattr(job, "eligibility_status", result.status)

            filtered.append(job)

    return filtered
