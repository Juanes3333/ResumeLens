"""Stage 1 — Extraction engine.

Orchestrates the compiled patterns of :mod:`resumelens.extraction.patterns` over the plain
text of a resume: segments it into sections, extracts contact data, education and
experience lines and the raw (not normalized) skill tokens, and builds a ``RawResumeData``.
"""

import re
from typing import Dict, List

from resumelens.core.models import CandidateInfo, RawResumeData
from resumelens.extraction.patterns import (
    EMAIL_PATTERN,
    EXPERIENCE_ENTRY_PATTERN,
    PHONE_PATTERN,
    SECTION_HEADER_PATTERN,
    URL_PATTERN,
    YEARS_EXPERIENCE_PATTERN,
)

_SECTION_ALIASES: Dict[str, str] = {
    "skills": "technical skills",
    "work experience": "experience",
}

#: Name line: 2 to 4 words, each starting with an uppercase letter.
_NAME_PATTERN = re.compile(
    r"^[A-Z][A-Za-z'’.-]*(?:[ \t]+[A-Z][A-Za-z'’.-]*){1,3}$"
)
_SKILL_SEPARATOR = re.compile(r"[,;\n]")


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
    """Return the first line shaped like a person's name, or ``""`` if none."""
    for line in _nonempty_lines(text):
        if SECTION_HEADER_PATTERN.match(line):
            break
        if _NAME_PATTERN.match(line):
            return line
        break
    return ""


def extract_contact(text: str) -> Dict[str, object]:
    """Return ``{"email": str, "phone": str, "links": List[str]}`` (empty if absent).

    The ``Contact`` section is searched first; if it has no match, the whole text is used.
    """
    scope = split_sections(text).get("contact", "")
    email = EMAIL_PATTERN.search(scope) or EMAIL_PATTERN.search(text)
    phone = PHONE_PATTERN.search(scope) or PHONE_PATTERN.search(text)
    links: List[str] = []
    for match in URL_PATTERN.finditer(text):
        url = match.group(0)
        if url not in links:
            links.append(url)
    return {
        "email": email.group(0) if email else "",
        "phone": phone.group(0).strip() if phone else "",
        "links": links,
    }


def extract_education(text: str) -> List[str]:
    """Return the non-empty lines of the ``Education`` section."""
    return _nonempty_lines(split_sections(text).get("education", ""))


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

    Tokens keep their original spelling and order of appearance; they are split on commas,
    semicolons and line breaks, and a trailing period is dropped. Without the section the
    result is ``[]``.
    """
    body = split_sections(text).get("technical skills", "")
    tokens = (t.strip().rstrip(".").strip() for t in _SKILL_SEPARATOR.split(body))
    return [t for t in tokens if t]


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
    )
