"""Unit tests for Stage 1 (regex-based extraction).

Covers the extraction engine (``resumelens.extraction.extractor``) and the technical-skill
patterns (``resumelens.extraction.patterns``), using both direct synthetic strings and the
resume fixtures loaded by ``tests/conftest.py``.
"""

import pytest

from resumelens.core.models import CandidateInfo, RawResumeData
from resumelens.extraction import (
    extract_contact,
    extract_education,
    extract_experience,
    extract_name,
    extract_resume,
    extract_skills,
    split_sections,
)
from resumelens.extraction import patterns as p
from tests.conftest import VALID_ALIASES

SKILL_PATTERNS = {
    name: p.PATTERNS[name]
    for name in (
        "programming_language",
        "framework",
        "ml_library",
        "database",
        "version_control",
        "devops_cloud",
    )
}


def skills_found(pattern, text):
    """Return the ``skill`` group of every match of ``pattern`` in ``text``."""
    return [m["skill"] for m in pattern.finditer(text)]


def contact_block(*lines):
    """Build a resume fragment with a ``Contact:`` section."""
    return "Contact:\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Contact — emails
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "email",
    [
        "juan.perez-2026@sub.domain.edu.co",
        "mj.watson@dailybugle.com",
        "a.b+tag@mail.example.co.uk",
        "ana_95@icesi.edu.co",
        "x@y.io",
    ],
)
def test_contact_extracts_standard_and_complex_emails(email):
    result = extract_contact(contact_block(f"Email: {email}"))
    assert result["email"] == email


def test_contact_email_drops_trailing_sentence_period():
    assert extract_contact("Write me at ana@icesi.edu.co.")["email"] == "ana@icesi.edu.co"


@pytest.mark.parametrize("text", ["contact me: juan.perez at mail", "user@host", "no email"])
def test_contact_rejects_malformed_emails(text):
    assert extract_contact(text)["email"] == ""


def test_contact_section_has_priority_over_other_emails():
    text = "Summary:\nold@legacy.com wrote this.\n\nContact:\nEmail: new@current.com\n"
    assert extract_contact(text)["email"] == "new@current.com"


def test_contact_email_falls_back_to_whole_text():
    text = "Summary:\nReach me at ana@x.org any time.\n"
    assert extract_contact(text)["email"] == "ana@x.org"


# ---------------------------------------------------------------------------
# Contact — phones
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "phone",
    [
        "+57 300 123 4567",
        "(602) 888-9900",
        "+1-800-555-0199",
        "+1 (555) 123-4567",
        "555.123.4567",
        "3001234567",
    ],
)
def test_contact_extracts_international_and_varied_phones(phone):
    assert extract_contact(contact_block(f"Phone: {phone}"))["phone"] == phone


def test_contact_phone_ignores_year_ranges():
    text = "Education:\nB.S. in CS\nUniversidad Icesi (2019 - 2023)\n"
    assert extract_contact(text)["phone"] == ""


def test_contact_phone_falls_back_to_whole_text():
    assert extract_contact("Call +1 555 111 2222 anytime")["phone"] == "+1 555 111 2222"


# ---------------------------------------------------------------------------
# Contact — links
# ---------------------------------------------------------------------------
def test_contact_extracts_linkedin_github_and_portfolio_in_order():
    text = contact_block(
        "LinkedIn: https://www.linkedin.com/in/ana-gomez",
        "GitHub: https://github.com/ana-g/proj.git",
        "Portfolio: https://ana.dev/work/",
    )
    assert extract_contact(text)["links"] == [
        "https://www.linkedin.com/in/ana-gomez",
        "https://github.com/ana-g/proj.git",
        "https://ana.dev/work",
    ]


def test_contact_links_drop_trailing_punctuation_and_duplicates():
    text = (
        "See https://github.com/ana. Also https://github.com/ana, and "
        "https://github.com/ana\n"
    )
    assert extract_contact(text)["links"] == ["https://github.com/ana"]


def test_contact_without_data_returns_empty_values():
    assert extract_contact("nothing useful here") == {"email": "", "phone": "", "links": []}


# ---------------------------------------------------------------------------
# Name and sections
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Mary Jane Watson\n\nContact:\n", "Mary Jane Watson"),
        ("WEDNESDAY ADDAMS\nContact:\n", "WEDNESDAY ADDAMS"),
        ("juan perez\ncontact me", ""),
        ("Contact:\nAna Gomez", ""),
        ("Ana\nSummary:", ""),
        ("", ""),
    ],
)
def test_extract_name(text, expected):
    assert extract_name(text) == expected


@pytest.mark.xfail(
    reason=(
        "Known limitation: the name pattern only accepts the letters A-Za-z, so names "
        "with accents (common in Spanish) are not recognized."
    ),
    strict=False,
)
@pytest.mark.parametrize("name", ["Ana María Gómez", "José Núñez"])
def test_extract_name_accepts_accented_names(name):
    assert extract_name(f"{name}\n\nContact:\n") == name


def test_split_sections_segments_text_and_unifies_aliases():
    text = "Pre\nSkills:\nA\nWork Experience:\nB\nExperience:\nC\n"
    sections = split_sections(text)
    assert sections[""] == "Pre\n"
    assert sections["technical skills"].strip() == "A"
    assert sections["experience"].split() == ["B", "C"]  # repeated header is concatenated


def test_split_sections_headers_are_case_insensitive():
    sections = split_sections("EDUCATION:\nX\ntechnical skills:\nY\n")
    assert sections["education"].strip() == "X"
    assert sections["technical skills"].strip() == "Y"


def test_split_sections_without_headers_keeps_everything_in_preamble():
    assert split_sections("just text") == {"": "just text"}


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
def test_education_returns_section_lines_until_next_header():
    text = (
        "Education:\nB.S. in Computer Science\nNevermore University (2019 - 2023)\n\n"
        "Experience:\nDev, Acme (2023 - 2024)\n"
    )
    assert extract_education(text) == [
        "B.S. in Computer Science",
        "Nevermore University (2019 - 2023)",
    ]


def test_education_supports_multiple_records():
    text = (
        "Education:\nM.S. in Data Science\nEmpire State University (2022 - 2024)\n"
        "B.S. in Statistics\nBrooklyn Institute (2018 - 2022)\n"
    )
    assert len(extract_education(text)) == 4


def test_education_without_section_is_empty():
    assert extract_education("Summary:\nno studies listed") == []


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
def test_experience_returns_years_and_job_entries():
    text = (
        "Summary:\n2 years of experience in QA.\n\n"
        "Experience:\nQA Engineer, Acme (2020 - 2022)\n"
        "- Wrote test plans (2021 - 2022)\n"
        "Data Analyst at Beta (Jan 2022 - Present)\n"
    )
    assert extract_experience(text) == [
        "2 years of experience in QA",
        "QA Engineer, Acme (2020 - 2022)",
        "Data Analyst at Beta (Jan 2022 - Present)",
    ]


def test_experience_ignores_bullets_and_education_lines():
    text = (
        "Education:\nB.S. in CS\nUniversidad Icesi (2019 - 2023)\n\n"
        "Experience:\n- Built a dashboard (2023 - 2024)\n"
    )
    assert extract_experience(text) == []


def test_experience_accepts_plus_years_and_work_experience_alias():
    text = "5+ years of professional experience\nWork Experience:\nSRE | Rappi (2022 - 2024)\n"
    assert extract_experience(text) == [
        "5+ years of professional experience",
        "SRE | Rappi (2022 - 2024)",
    ]


def test_experience_without_data_is_empty():
    assert extract_experience("Summary:\nnothing") == []


# ---------------------------------------------------------------------------
# Raw skills — extract_skills (Technical Skills section)
# ---------------------------------------------------------------------------
def test_skills_keep_special_symbols_intact():
    text = "Technical Skills:\nC++, .NET, Node.js, React.js, C#\n"
    assert extract_skills(text) == ["C++", ".NET", "Node.js", "React.js", "C#"]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("JS, React.js, NodeJS, Postgres, Git.", ["JS", "React.js", "NodeJS", "Postgres", "Git"]),
        ("Python; SQL;Git", ["Python", "SQL", "Git"]),
        ("Python\nSQL\nGit.", ["Python", "SQL", "Git"]),
        ("Python, ,  , Git.", ["Python", "Git"]),
        ("  Docker  ,\tKubernetes  ", ["Docker", "Kubernetes"]),
        ("C++, .NET.", ["C++", ".NET"]),
    ],
)
def test_skills_tolerate_adjacent_punctuation(body, expected):
    assert extract_skills(f"Technical Skills:\n{body}\n") == expected


def test_skills_preserve_original_case_and_order():
    text = "Technical Skills:\njs, JavaScript, REACT, sklearn, Git\n"
    skills = extract_skills(text)
    assert skills == ["js", "JavaScript", "REACT", "sklearn", "Git"]
    assert "REACT" in skills and "React" not in skills


def test_skills_header_is_case_insensitive_and_accepts_skills_alias():
    assert extract_skills("TECHNICAL SKILLS:\nJS,REACT") == ["JS", "REACT"]
    assert extract_skills("Skills:\nPython, SQL") == ["Python", "SQL"]


def test_skills_stop_at_next_section():
    text = "Technical Skills:\nPython, Git\n\nExperience:\nDev, Acme (2020 - 2021)\n"
    assert extract_skills(text) == ["Python", "Git"]


def test_skills_never_leak_separators_or_trailing_periods():
    skills = extract_skills("Technical Skills:\nPython,\nSQL; Git.\n")
    assert all(not any(ch in token for ch in ",;\n") for token in skills)
    assert all(not token.endswith(".") for token in skills)


def test_skills_without_section_is_empty():
    assert extract_skills("Summary:\nI know Python and Git.") == []


# ---------------------------------------------------------------------------
# Skill patterns — token isolation in free text
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        ("I use C++ and C# daily.", ["C++", "C#"]),
        ("Java and JavaScript; Go. Golang! Rust", ["Java", "JavaScript", "Go", "Golang", "Rust"]),
        ("TS and ts, typescript, Ruby, PHP, Kotlin, Swift", ["TS", "ts", "typescript", "Ruby", "PHP", "Kotlin", "Swift"]),
        ("js, JS, Js", ["js", "JS", "Js"]),
        ("JavaScript", ["JavaScript"]),
    ],
)
def test_programming_language_pattern_isolates_symbol_tokens(text, expected):
    assert skills_found(p.PROGRAMMING_LANGUAGE_PATTERN, text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Node.js, React.js, Vue.js.", ["Node.js", "React.js", "Vue.js"]),
        ("REACT, react, ReactJS, NodeJS", ["REACT", "react", "ReactJS", "NodeJS"]),
        ("Spring Boot (Java), django; Express.js", ["Spring Boot", "django", "Express.js"]),
    ],
)
def test_framework_pattern_handles_dots_case_and_punctuation(text, expected):
    assert skills_found(p.FRAMEWORK_PATTERN, text) == expected


@pytest.mark.parametrize(
    "pattern_name, text, expected",
    [
        ("ml_library", "sklearn, Scikit-learn, scikit learn", ["sklearn", "Scikit-learn", "scikit learn"]),
        ("ml_library", "TensorFlow and Tensor Flow, PyTorch, Py Torch", ["TensorFlow", "Tensor Flow", "PyTorch", "Py Torch"]),
        ("ml_library", "numpy, NumPy, PANDAS", ["numpy", "NumPy", "PANDAS"]),
        ("database", "Postgres, PostgreSQL, SQL Server, mongo.", ["Postgres", "PostgreSQL", "SQL Server", "mongo"]),
        ("database", "MySQL / Oracle / redis", ["MySQL", "Oracle", "redis"]),
        ("version_control", "Git, GitHub, gitlab", ["Git", "GitHub", "gitlab"]),
        ("devops_cloud", "Docker, kubernetes, AWS, azure", ["Docker", "kubernetes", "AWS", "azure"]),
        ("devops_cloud", "Google Cloud Platform and Terraform", ["Google Cloud Platform", "Terraform"]),
    ],
)
def test_skill_patterns_are_case_and_variant_tolerant(pattern_name, text, expected):
    assert skills_found(SKILL_PATTERNS[pattern_name], text) == expected


@pytest.mark.parametrize("name", list(SKILL_PATTERNS))
@pytest.mark.parametrize(
    "text",
    [
        "I worked with the team and also with other people, but only on weekends.",
        "digital lab goal rustic cargo ago serviced",
        "Reactive programming and disorganized notes",
        "",
    ],
)
def test_skill_patterns_do_not_capture_functional_words_or_substrings(name, text):
    # Words such as "and", "with", "also", or skill names embedded inside longer
    # words (goal, cargo, Reactive, ...) must never be captured.
    assert skills_found(SKILL_PATTERNS[name], text) == []


def test_skill_patterns_isolate_only_the_skill_from_a_sentence():
    text = "I worked with Python and Git, but also with Docker or AWS."
    found = {
        name: skills_found(pattern, text)
        for name, pattern in SKILL_PATTERNS.items()
        if skills_found(pattern, text)
    }
    assert found == {
        "programming_language": ["Python"],
        "version_control": ["Git"],
        "devops_cloud": ["Docker", "AWS"],
    }


@pytest.mark.xfail(
    reason=(
        "Known limitation: PROGRAMMING_LANGUAGE_PATTERN uses (?<!\\w), so the 'js' inside "
        "'Node.js' / 'React.js' is also reported as a programming language."
    ),
    strict=False,
)
@pytest.mark.parametrize("text", ["Node.js", "React.js", "Vue.js"])
def test_language_pattern_does_not_split_dotted_framework_names(text):
    assert skills_found(p.PROGRAMMING_LANGUAGE_PATTERN, text) == []


# ---------------------------------------------------------------------------
# Resume fixtures (data/input_resumes/*.txt via tests/conftest.py)
# ---------------------------------------------------------------------------
EXPECTED_RESUMES = {
    "fullstack": {
        "name": "WEDNESDAY ADDAMS",
        "email": "wednesday.addams@nevermore.edu",
        "phone": "+1 555 666 7777",
        "links": [
            "https://www.linkedin.com/in/wednesday-addams",
            "https://github.com/wednesday-addams",
        ],
        "education": ["B.S. in Computer Science", "Nevermore University (2019 - 2023)"],
        "experience": [
            "3 years of experience developing web applications",
            "Full Stack Developer, Raven Labs (2023 - 2026)",
        ],
        "skills": ["JS", "React.js", "NodeJS", "Postgres", "Git"],
    },
    "ml": {
        "name": "Mary Jane Watson",
        "email": "mj.watson@dailybugle.com",
        "phone": "+1 555 123 4567",
        "links": [
            "https://www.linkedin.com/in/mary-jane-watson",
            "https://github.com/mjwatson",
        ],
        "education": ["M.S. in Data Science", "Empire State University (2022 - 2024)"],
        "experience": [
            "2 years of experience developing predictive models and data-processing pipelines",
            "Machine Learning Engineer, Oscorp Analytics (2024 - 2026)",
        ],
        "skills": ["Python", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "SQL", "Git"],
    },
    "devops": {
        "name": "Peter Parker",
        "email": "peter.parker@dailybugle.com",
        "phone": "+1 555 222 3344",
        "links": [
            "https://www.linkedin.com/in/peter-parker",
            "https://github.com/pparker",
        ],
        "education": ["B.S. in Systems Engineering", "Midtown Tech (2019 - 2023)"],
        "experience": [
            "3 years of experience automating infrastructure and deployment pipelines",
            "DevOps Engineer, Stark Cloud (2023 - 2026)",
        ],
        "skills": ["Python", "Docker", "Kubernetes", "Terraform", "Git"],
    },
    "data": {
        "name": "Gwen Stacy",
        "email": "gwen.stacy@oscorp.com",
        "phone": "+1 555 888 9900",
        "links": [
            "https://www.linkedin.com/in/gwen-stacy",
            "https://github.com/gstacy",
        ],
        "education": ["B.S. in Computer Engineering", "Brooklyn Institute (2019 - 2023)"],
        "experience": [
            "3 years of experience building scalable data architectures and analytical pipelines",
            "Data Engineer, Oscorp Data (2023 - 2026)",
        ],
        "skills": ["Python", "Apache Spark", "Airflow", "PostgreSQL", "Git"],
    },
}


@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_extract_resume_on_fixtures_matches_expected_data(resume_texts, alias):
    exp = EXPECTED_RESUMES[alias]
    result = extract_resume(resume_texts[alias])

    assert isinstance(result, RawResumeData)
    assert isinstance(result.candidate_info, CandidateInfo)
    assert result.raw_text == resume_texts[alias]

    info = result.candidate_info
    assert info.name == exp["name"]
    assert info.email == exp["email"]
    assert info.phone == exp["phone"]
    assert info.links == exp["links"]
    assert info.education == exp["education"]
    assert info.experience == exp["experience"]
    assert result.raw_skills == exp["skills"]


@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_individual_extractors_agree_with_extract_resume(resume_texts, alias):
    text = resume_texts[alias]
    result = extract_resume(text)
    assert result.raw_skills == extract_skills(text)
    assert result.candidate_info.education == extract_education(text)
    assert result.candidate_info.experience == extract_experience(text)
    assert result.candidate_info.name == extract_name(text)


@pytest.mark.parametrize("alias", ["fullstack", "devops"])
def test_fixture_skill_tokens_are_each_recognized_by_a_skill_pattern(resume_texts, alias):
    for token in extract_skills(resume_texts[alias]):
        assert any(pattern.fullmatch(token) for pattern in SKILL_PATTERNS.values()), token


def test_fixture_tokens_do_not_include_text_from_other_sections(resume_texts):
    for alias in VALID_ALIASES:
        for token in extract_skills(resume_texts[alias]):
            assert "(" not in token and ":" not in token and "\n" not in token


def test_extract_resume_on_invalid_fixture_returns_empty_fields(invalid_text):
    result = extract_resume(invalid_text)
    assert result.raw_text == invalid_text
    assert result.candidate_info == CandidateInfo()
    assert result.raw_skills == []


def test_extract_resume_is_deterministic(fullstack_text):
    assert extract_resume(fullstack_text) == extract_resume(fullstack_text)


# ---------------------------------------------------------------------------
# End-to-end Stage 1 over a synthetic resume
# ---------------------------------------------------------------------------
SYNTHETIC_RESUME = """Ana Maria Gomez

Contact:
Email: ana.gomez-2026@sub.domain.edu.co
Phone: +57 300 123 4567
LinkedIn: https://www.linkedin.com/in/ana-gomez
GitHub: https://github.com/anagomez

Summary:
5+ years of professional experience building APIs.

Technical Skills:
C++, .NET, Node.js, js, REACT, sklearn, Git.

Education:
B.S. in Software Engineering
Universidad Icesi (2016 - 2021)

Experience:
Backend Developer, Globant (Jan 2021 - Present)
- Built services with Node.js.
"""


def test_extract_resume_on_synthetic_text():
    result = extract_resume(SYNTHETIC_RESUME)
    info = result.candidate_info
    assert info.name == "Ana Maria Gomez"
    assert info.email == "ana.gomez-2026@sub.domain.edu.co"
    assert info.phone == "+57 300 123 4567"
    assert info.links == [
        "https://www.linkedin.com/in/ana-gomez",
        "https://github.com/anagomez",
    ]
    assert info.education == ["B.S. in Software Engineering", "Universidad Icesi (2016 - 2021)"]
    assert info.experience == [
        "5+ years of professional experience building APIs",
        "Backend Developer, Globant (Jan 2021 - Present)",
    ]
    assert result.raw_skills == ["C++", ".NET", "Node.js", "js", "REACT", "sklearn", "Git"]
