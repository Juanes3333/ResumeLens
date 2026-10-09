"""Stage 1 — Extraction engine.

Orchestrates the compiled patterns of :mod:`resumelens.extraction.patterns` over the plain
text of a resume: segments it into sections, extracts the candidate's name, contact data,
education and experience lines, the raw (not normalized) skill tokens and the
technologies detected by the skill regex bank, and builds a ``RawResumeData``.
"""

from typing import Dict, List, Set

from resumelens.core.models import CandidateInfo, RawResumeData
from resumelens.extraction.patterns import (
    DATE_RANGE_PATTERN,
    DEGREE_PATTERN,
    EMAIL_PATTERN,
    EXPERIENCE_ENTRY_PATTERN,
    GITHUB_URL_PATTERN,
    INSTITUTION_PATTERN,
    LINKEDIN_URL_PATTERN,
    NAME_PATTERN,
    PHONE_PATTERN,
    SECTION_HEADER_PATTERN,
    SKILL_PATTERNS,
    SKILL_SEPARATOR_PATTERN,
    URL_PATTERN,
    YEARS_EXPERIENCE_PATTERN,
)

_SECTION_ALIASES: Dict[str, str] = {
    "skills": "technical skills",
    "work experience": "experience",
}


def split_sections(text: str) -> Dict[str, str]:
    """Split ``text`` into sections keyed by lowercase header title.

    Text before the first header is stored under the key ``""``. Aliases are unified
    (``Skills`` -> ``technical skills``, ``Work Experience`` -> ``experience``). If a
    header is repeated, the bodies are concatenated.
    """
    sections: Dict[str, str] = {}
    headers = list(SECTION_HEADER_PATTERN.finditer(text))
    preamble = text[: headers[0].start()] if headers else text
    sections[""] = preamble
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        title = match.group("title").lower()
        title = _SECTION_ALIASES.get(title, title)
        body = text[match.end():end]
        sections[title] = sections[title] + "\n" + body if title in sections else body
    return sections


def _nonempty_lines(block: str) -> List[str]:
    return [line.strip() for line in block.splitlines() if line.strip()]


def extract_name(text: str) -> str:
    """Return the first line if it is in the language of ``NAME_PATTERN``, else ``""``."""
    for line in _nonempty_lines(text):
        if SECTION_HEADER_PATTERN.match(line):
            break
        match = NAME_PATTERN.match(line)
        if match:
            return match.group("name")
        break
    return ""


def extract_contact(text: str) -> Dict[str, object]:
    """Return ``{"email", "phone", "links", "linkedin", "github"}`` (empty if absent).

    The ``Contact`` section is searched first for the email and the phone; if it has no
    match, the whole text is used. ``links`` holds every URL of the text without
    repetitions; ``linkedin`` and ``github`` hold the first profile URL of each kind.
    """
    scope = split_sections(text).get("contact", "")
    email = EMAIL_PATTERN.search(scope) or EMAIL_PATTERN.search(text)
    phone = PHONE_PATTERN.search(scope) or PHONE_PATTERN.search(text)
    links: List[str] = []
    for match in URL_PATTERN.finditer(text):
        url = match.group(0)
        if url not in links:
            links.append(url)
    linkedin = LINKEDIN_URL_PATTERN.search(text)
    github = GITHUB_URL_PATTERN.search(text)
    return {
        "email": email.group(0) if email else "",
        "phone": phone.group(0).strip() if phone else "",
        "links": links,
        "linkedin": linkedin.group(0) if linkedin else "",
        "github": github.group(0) if github else "",
    }


def extract_education(text: str) -> List[str]:
    """Return the lines of the ``Education`` section that describe a study.

    A line is kept if it contains an academic degree (``DEGREE_PATTERN``), an
    institution (``INSTITUTION_PATTERN``) or a period (``DATE_RANGE_PATTERN``).
    """
    patterns = (DEGREE_PATTERN, INSTITUTION_PATTERN, DATE_RANGE_PATTERN)
    lines = _nonempty_lines(split_sections(text).get("education", ""))
    return [line for line in lines if any(pattern.search(line) for pattern in patterns)]


def extract_experience(text: str) -> List[str]:
    """Return the declared years of experience and the job entries (role, company, dates)."""
    items: List[str] = []
    years = YEARS_EXPERIENCE_PATTERN.search(text)
    if years:
        items.append(years.group(0).strip())
    body = split_sections(text).get("experience", "")
    items.extend(m.group(0).strip() for m in EXPERIENCE_ENTRY_PATTERN.finditer(body))
    return items


def extract_skills(text: str) -> List[str]:
    """Return the raw skill tokens of the ``Technical Skills`` section.

    Tokens keep their original spelling and order of appearance; they are split with
    ``SKILL_SEPARATOR_PATTERN`` (commas, semicolons and line breaks) and a trailing
    period is dropped. Without the section the result is ``[]``.
    """
    body = split_sections(text).get("technical skills", "")
    tokens = (t.strip().rstrip(".").strip() for t in SKILL_SEPARATOR_PATTERN.split(body))
    return [t for t in tokens if t]


def extract_technologies(text: str) -> Dict[str, List[str]]:
    """Run the skill regex bank (``SKILL_PATTERNS``) over the whole resume.

    The ``Contact`` section is skipped and URLs are removed, so that the ``GitHub:`` label
    or ``github.com`` in a profile link are not reported as version-control skills. For
    every type with at least one match, the result lists the matched spellings in order
    of first appearance, without repetitions (ignoring case).
    """
    sections = split_sections(text)
    body = "\n".join(part for title, part in sections.items() if title != "contact")
    searchable = URL_PATTERN.sub(" ", body)
    found: Dict[str, List[str]] = {}
    for kind, pattern in SKILL_PATTERNS.items():
        seen: Set[str] = set()
        for match in pattern.finditer(searchable):
            skill = " ".join(match.group("skill").split())
            if skill.casefold() not in seen:
                seen.add(skill.casefold())
                found.setdefault(kind, []).append(skill)
    return found


def extract_resume(text: str) -> RawResumeData:
    """Run the whole Stage 1 over ``text`` and build a ``RawResumeData``."""
    contact = extract_contact(text)
    candidate = CandidateInfo(
        name=extract_name(text),
        email=str(contact["email"]),
        phone=str(contact["phone"]),
        links=list(contact["links"]),  # type: ignore[call-overload]
        education=extract_education(text),
        experience=extract_experience(text),
    )
    return RawResumeData(
        raw_text=text,
        candidate_info=candidate,
        raw_skills=extract_skills(text),
        detected_skills=extract_technologies(text),
    )
