"""Domain models of ResumeLens."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class JobEntry:
    """A job of the *Experience* section: ``Role, Company (start - end)`` and its bullets."""

    description: str = ""  # the entry as written, e.g. "Full Stack Developer, Raven Labs (2023 - 2026)"
    role: str = ""
    company: str = ""
    period: str = ""  # "2023 - 2026"
    highlights: List[str] = field(default_factory=list)


@dataclass
class CandidateInfo:
    name: str = ""
    email: str = ""
    phone: str = ""
    links: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)
    experience: List[str] = field(default_factory=list)
    # Information shown in the report that does not take part in the verdict.
    location: str = ""
    current_role: str = ""
    summary: List[str] = field(default_factory=list)  # paragraphs of the *Summary* section
    jobs: List[JobEntry] = field(default_factory=list)  # structure of the entries of ``experience``


@dataclass
class RawResumeData:
    raw_text: str
    candidate_info: CandidateInfo = field(default_factory=CandidateInfo)
    # Raw tokens of the "Technical Skills" section (input of Stage 2).
    raw_skills: List[str] = field(default_factory=list)
    # Technologies found by the regex bank over the whole resume, grouped by type
    # (programming_language, framework, database, ...). This is extracted information kept
    # in the data structure; Stage 2 only normalizes ``raw_skills``.
    detected_skills: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class SkillRecord:
    raw_name: str
    canonical_name: str
    category: str  # e.g. 'web_language', 'frontend', 'backend', 'database', 'vcs'


@dataclass
class EvaluationResult:
    profile_name: str
    is_accepted: bool
    matched_sequence: List[str] = field(default_factory=list)
    details: str = ""
