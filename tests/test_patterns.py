"""Tests for the Stage 1 regex patterns (contact, education and career)."""

import re

import pytest

from resumelens.extraction import patterns as p

# Expected values per synthetic resume (aliases defined in tests/conftest.py).
EXPECTED = {
    "fullstack": {
        "email": ("wednesday.addams", "nevermore.edu"),
        "phone": ("+1", "555", "666", "7777"),
        "linkedin": "wednesday-addams",
        "github": "wednesday-addams",
        "level": "B.S.",
        "field": "Computer Science",
        "institution": "Nevermore University",
        "edu_range": ("2019", "2023"),
        "role": "Full Stack Developer",
        "company": "Raven Labs",
        "exp_range": ("2023", "2026"),
        "years": "3",
        "activity": "developing web applications",
    },
    "ml": {
        "email": ("mj.watson", "dailybugle.com"),
        "phone": ("+1", "555", "123", "4567"),
        "linkedin": "mary-jane-watson",
        "github": "mjwatson",
        "level": "M.S.",
        "field": "Data Science",
        "institution": "Empire State University",
        "edu_range": ("2022", "2024"),
        "role": "Machine Learning Engineer",
        "company": "Oscorp Analytics",
        "exp_range": ("2024", "2026"),
        "years": "2",
        "activity": "developing predictive models and data-processing pipelines",
    },
    "devops": {
        "email": ("peter.parker", "dailybugle.com"),
        "phone": ("+1", "555", "222", "3344"),
        "linkedin": "peter-parker",
        "github": "pparker",
        "level": "B.S.",
        "field": "Systems Engineering",
        "institution": "Midtown Tech",
        "edu_range": ("2019", "2023"),
        "role": "DevOps Engineer",
        "company": "Stark Cloud",
        "exp_range": ("2023", "2026"),
        "years": "3",
        "activity": "automating infrastructure and deployment pipelines",
    },
    "data": {
        "email": ("gwen.stacy", "oscorp.com"),
        "phone": ("+1", "555", "888", "9900"),
        "linkedin": "gwen-stacy",
        "github": "gstacy",
        "level": "B.S.",
        "field": "Computer Engineering",
        "institution": "Brooklyn Institute",
        "edu_range": ("2019", "2023"),
        "role": "Data Engineer",
        "company": "Oscorp Data",
        "exp_range": ("2023", "2026"),
        "years": "3",
        "activity": "building scalable data architectures and analytical pipelines",
    },
}
VALID = list(EXPECTED)


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------
def test_all_patterns_are_compiled():
    assert len(p.PATTERNS) == 12
    assert all(isinstance(pat, re.Pattern) for pat in p.PATTERNS.values())


# ---------------------------------------------------------------------------
# Contact — synthetic texts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, user, domain",
    [
        ("Email: mj.watson@dailybugle.com", "mj.watson", "dailybugle.com"),
        ("write to a.b+tag@mail.example.co.uk now", "a.b+tag", "mail.example.co.uk"),
        ("Contact: ana_95@icesi.edu.co.", "ana_95", "icesi.edu.co"),
    ],
)
def test_email_matches(text, user, domain):
    m = p.EMAIL_PATTERN.search(text)
    assert m is not None
    assert m.groupdict() == {"user": user, "domain": domain}


@pytest.mark.parametrize("text", ["juan.perez at mail", "user@host", "@domain.com", "no email here"])
def test_email_rejects(text):
    assert p.EMAIL_PATTERN.search(text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("+1 555 123 4567", ("+1", "555", "123", "4567")),
        ("+57 300 123 4567", ("+57", "300", "123", "4567")),
        ("(555) 123-4567", (None, "555", "123", "4567")),
        ("+1 (555) 123-4567", ("+1", "555", "123", "4567")),
        ("555-123-4567", (None, "555", "123", "4567")),
        ("555.123.4567", (None, "555", "123", "4567")),
        ("3001234567", (None, "300", "123", "4567")),
    ],
)
def test_phone_matches(text, expected):
    m = p.PHONE_PATTERN.search(text)
    assert m is not None
    assert (m["country"], m["area"], m["prefix"], m["line"]) == expected


@pytest.mark.parametrize("text", ["2019 - 2023", "12345", "30012345678", "call me maybe"])
def test_phone_rejects(text):
    assert p.PHONE_PATTERN.search(text) is None


def test_phone_span_covers_whole_number():
    text = "Phone: +1 555 123 4567"
    m = p.PHONE_PATTERN.search(text)
    assert text[m.start():m.end()] == "+1 555 123 4567"
    assert m.span() == (7, len(text))


def test_url_patterns_on_synthetic_text():
    text = "See https://www.linkedin.com/in/ana-gomez and https://github.com/ana/repo.name."
    urls = [m["host"] for m in p.URL_PATTERN.finditer(text)]
    assert urls == ["www.linkedin.com", "github.com"]
    assert p.LINKEDIN_URL_PATTERN.search(text).groupdict() == {
        "host": "www.linkedin.com", "kind": "in", "handle": "ana-gomez",
    }
    gh = p.GITHUB_URL_PATTERN.search(text)
    assert gh["user"] == "ana" and gh["repo"] == "repo.name"
    # The sentence-ending period is not part of the URL.
    assert [m["path"] for m in p.URL_PATTERN.finditer(text)][-1] == "/ana/repo.name"


def test_url_rejects_non_urls():
    assert p.URL_PATTERN.search("linkedin.com/in/ana without scheme") is None
    assert p.LINKEDIN_URL_PATTERN.search("https://github.com/ana") is None
    assert p.GITHUB_URL_PATTERN.search("https://www.linkedin.com/in/ana") is None


# ---------------------------------------------------------------------------
# Contact — fixtures
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", VALID)
def test_contact_on_fixtures(resume_texts, alias):
    text, exp = resume_texts[alias], EXPECTED[alias]
    assert p.EMAIL_PATTERN.findall(text) == [exp["email"]]
    phones = [m.groups() for m in p.PHONE_PATTERN.finditer(text)]
    assert phones == [exp["phone"]]
    assert p.LINKEDIN_URL_PATTERN.search(text)["handle"] == exp["linkedin"]
    assert p.GITHUB_URL_PATTERN.search(text)["user"] == exp["github"]
    assert len(p.URL_PATTERN.findall(text)) == 2


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", VALID)
def test_section_headers_on_fixtures(resume_texts, alias):
    titles = [m["title"] for m in p.SECTION_HEADER_PATTERN.finditer(resume_texts[alias])]
    assert titles == ["Contact", "Summary", "Technical Skills", "Education", "Experience"]


def test_section_header_ignores_inline_colons():
    assert p.SECTION_HEADER_PATTERN.search("Email: a@b.co") is None
    assert p.SECTION_HEADER_PATTERN.search("skills:\nPython")["title"] == "skills"


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, start, end",
    [
        ("2019 - 2023", "2019", "2023"),
        ("2019-2023", "2019", "2023"),
        ("2019 \u2013 2023", "2019", "2023"),
        ("Jan 2020 to Present", "Jan 2020", "Present"),
        ("March 2018 - Dec. 2021", "March 2018", "Dec. 2021"),
    ],
)
def test_date_range_matches(text, start, end):
    m = p.DATE_RANGE_PATTERN.search(text)
    assert m is not None and (m["start"], m["end"]) == (start, end)


@pytest.mark.parametrize("text", ["2023", "year 3000 - 4000", "abc - def"])
def test_date_range_rejects(text):
    assert p.DATE_RANGE_PATTERN.search(text) is None


@pytest.mark.parametrize(
    "text, level, field",
    [
        ("B.S. in Computer Science", "B.S.", "Computer Science"),
        ("M.S. in Data Science", "M.S.", "Data Science"),
        ("Bachelor of Science in Software Engineering", "Bachelor", "Software Engineering"),
        ("MBA in Finance", "MBA", "Finance"),
        ("Ph.D. in Mathematics, 2020", "Ph.D.", "Mathematics"),
        ("BSc in Physics", "BSc", "Physics"),
    ],
)
def test_degree_matches(text, level, field):
    m = p.DEGREE_PATTERN.search(text)
    assert m is not None
    assert (m["level"], m["field"]) == (level, field)


@pytest.mark.parametrize("text", ["looking for any job opportunity", "i like computers", "in Computer Science"])
def test_degree_rejects(text):
    assert p.DEGREE_PATTERN.search(text) is None


@pytest.mark.parametrize(
    "text, institution",
    [
        ("Nevermore University (2019 - 2023)", "Nevermore University"),
        ("Studied at Brooklyn Institute", "Brooklyn Institute"),
        ("University of Texas", "University of Texas"),
        ("Universidad Icesi", "Universidad Icesi"),
        ("Midtown Tech", "Midtown Tech"),
    ],
)
def test_institution_matches(text, institution):
    assert p.INSTITUTION_PATTERN.search(text)["institution"] == institution


def test_education_entry_with_graduation_year():
    text = "B.S. in Computer Science\nUniversidad Icesi (2022)"
    m = p.EDUCATION_ENTRY_PATTERN.search(text)
    assert m is not None
    assert m["institution"] == "Universidad Icesi"
    assert m["graduation"] == "2022" and m["start"] is None


@pytest.mark.parametrize("alias", VALID)
def test_education_on_fixtures(resume_texts, alias):
    exp = EXPECTED[alias]
    matches = list(p.EDUCATION_ENTRY_PATTERN.finditer(resume_texts[alias]))
    assert len(matches) == 1
    d = matches[0].groupdict()
    assert (d["level"], d["field"], d["institution"]) == (exp["level"], exp["field"], exp["institution"])
    assert (d["start"], d["end"]) == exp["edu_range"]
    assert d["degree"] == f"{exp['level']} in {exp['field']}"
    # The simple patterns agree with the full record.
    assert p.DEGREE_PATTERN.search(resume_texts[alias])["degree"] == d["degree"]
    assert p.INSTITUTION_PATTERN.search(resume_texts[alias])["institution"] == exp["institution"]


# ---------------------------------------------------------------------------
# Career / experience
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, years, plus, activity",
    [
        ("3 years of experience developing web applications.", "3", None, "developing web applications"),
        ("5+ years of professional experience", "5", "+", None),
        ("1 year of experience in QA.", "1", None, "in QA"),
    ],
)
def test_years_experience_matches(text, years, plus, activity):
    m = p.YEARS_EXPERIENCE_PATTERN.search(text)
    assert m is not None
    assert (m["years"], m["plus"], m["activity"]) == (years, plus, activity)


def test_years_experience_rejects():
    assert p.YEARS_EXPERIENCE_PATTERN.search("worked at a local store for a while") is None
    assert p.YEARS_EXPERIENCE_PATTERN.search("years of experience") is None


@pytest.mark.parametrize(
    "text, role, company, start, end",
    [
        ("Data Analyst, Acme Corp (2020 - 2022)", "Data Analyst", "Acme Corp", "2020", "2022"),
        ("Backend Developer at Globant (Jan 2021 - Present)", "Backend Developer", "Globant", "Jan 2021", "Present"),
        ("QA Engineer @ Rappi (2019 to 2021)", "QA Engineer", "Rappi", "2019", "2021"),
        ("SRE | Mercado Libre (2022 \u2013 2024)", "SRE", "Mercado Libre", "2022", "2024"),
    ],
)
def test_experience_entry_matches(text, role, company, start, end):
    m = p.EXPERIENCE_ENTRY_PATTERN.search(text)
    assert m is not None
    assert (m["role"], m["company"], m["start"], m["end"]) == (role, company, start, end)


@pytest.mark.parametrize(
    "text",
    [
        "- Built a dashboard (2023 - 2024)",
        "Nevermore University (2019 - 2023)",
        "Full Stack Developer, Raven Labs",
    ],
)
def test_experience_entry_rejects(text):
    assert p.EXPERIENCE_ENTRY_PATTERN.search(text) is None


@pytest.mark.parametrize("alias", VALID)
def test_experience_on_fixtures(resume_texts, alias):
    exp = EXPECTED[alias]
    matches = list(p.EXPERIENCE_ENTRY_PATTERN.finditer(resume_texts[alias]))
    assert len(matches) == 1
    d = matches[0].groupdict()
    assert (d["role"], d["company"]) == (exp["role"], exp["company"])
    assert (d["start"], d["end"]) == exp["exp_range"]
    y = p.YEARS_EXPERIENCE_PATTERN.search(resume_texts[alias])
    assert (y["years"], y["activity"]) == (exp["years"], exp["activity"])


# ---------------------------------------------------------------------------
# Invalid resume: no pattern should produce matches
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(p.PATTERNS))
def test_invalid_resume_yields_no_matches(invalid_text, name):
    assert p.PATTERNS[name].search(invalid_text) is None
