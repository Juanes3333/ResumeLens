"""Modelos de dominio de ResumeLens."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CandidateInfo:
    name: str = ""
    email: str = ""
    phone: str = ""
    links: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)
    experience: List[str] = field(default_factory=list)


@dataclass
class RawResumeData:
    raw_text: str
    candidate_info: CandidateInfo = field(default_factory=CandidateInfo)
    raw_skills: List[str] = field(default_factory=list)


@dataclass
class SkillRecord:
    raw_name: str
    canonical_name: str
    category: str  # p. ej. 'frontend', 'backend', 'database', 'vcs', 'ml', 'cloud'


@dataclass
class EvaluationResult:
    profile_name: str
    is_accepted: bool
    matched_sequence: List[str] = field(default_factory=list)
    details: str = ""
