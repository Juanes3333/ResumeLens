"""Unit tests for the Stage 4 reports (``resumelens.visualization``).

* ``render_html``: structure of the HTML5 page, injection of the candidate data, escaping,
  null/empty values and behaviour when the template is missing.
* ``render_markdown_report``: the Markdown export (an alternative that does not need the
  HTML template).
* ``write_visualization``: writing a report to disk.

The models come from the real pipeline (resume fixtures -> Stages 1-3 -> DSL -> textX model)
or, for edge cases that the grammar would reject, from small stand-in objects with the same
attributes as the textX model.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest

import resumelens.visualization as visualization
from resumelens.classification import classify_all
from resumelens.extraction.extractor import extract_resume
from resumelens.grammar import build_profile_source, parse_candidate_profile
from resumelens.normalization import normalize_with_report
from resumelens.visualization import (
    TEMPLATE_PATH,
    render_html,
    render_markdown_report,
    write_visualization,
)
from resumelens.visualization import renderer

ACCEPTED_PROFILE_BY_ALIAS = {
    "fullstack": "Full Stack Developer",
    "ml": "Machine Learning Engineer",
    "devops": "DevOps Engineer",
    "data": "Data Engineer",
}
PROFILE_TITLES = list(ACCEPTED_PROFILE_BY_ALIAS.values())
SECTIONS = [
    "Personal Information",
    "Education",
    "Experience",
    "Normalized Technical Skills",
    "Qualification Evaluation",
]
VOID_TAGS = {"meta", "br", "hr", "img", "link", "input"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def model_from_text(text):
    """Resume text -> Stages 1-3 -> DSL document -> validated textX model."""
    raw = extract_resume(text)
    records = normalize_with_report(raw.raw_skills).records
    results = classify_all(records).results
    return parse_candidate_profile(build_profile_source(raw.candidate_info, records, results))


def fake_model(
    name="Ana Gomez",
    email="ana@icesi.edu.co",
    phone="+57 300 123 4567",
    links=(),
    education=(),
    experience=(),
    skills=(("JAVASCRIPT", "web_language", "JS"),),
    results=(("FULL_STACK_DEVELOPER", "ACCEPTED", ("JAVASCRIPT",), "report"),),
):
    """Build a stand-in with the attributes of a ``CandidateReport`` model."""
    return SimpleNamespace(
        personal=SimpleNamespace(name=name, email=email, phone=phone, links=list(links)),
        education=SimpleNamespace(entries=[SimpleNamespace(description=d) for d in education]),
        experience=SimpleNamespace(entries=[SimpleNamespace(description=d) for d in experience]),
        skills=SimpleNamespace(
            skills=[SimpleNamespace(canonical=c, category=k, raw=r) for c, k, r in skills]
        ),
        evaluation=SimpleNamespace(
            results=[
                SimpleNamespace(name=n, verdict=v, matched=list(m), details=d)
                for n, v, m, d in results
            ]
        ),
    )


class TagChecker(HTMLParser):
    """Records the tags of a document and checks that they are balanced."""

    def __init__(self):
        super().__init__()
        self.stack, self.seen, self.errors = [], [], []

    def handle_starttag(self, tag, attrs):
        self.seen.append(tag)
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack})")
        else:
            self.stack.pop()


def check_tags(html):
    checker = TagChecker()
    checker.feed(html)
    checker.close()
    return checker


def table_cells(row):
    """Split a Markdown table row on unescaped pipes."""
    return re.split(r"(?<!\\)\|", row)


@pytest.fixture(scope="module")
def models(resume_texts):
    return {alias: model_from_text(resume_texts[alias]) for alias in ACCEPTED_PROFILE_BY_ALIAS}


@pytest.fixture
def missing_template(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer, "TEMPLATE_PATH", tmp_path / "no_such_template.html")


# ---------------------------------------------------------------------------
# Package and template
# ---------------------------------------------------------------------------
def test_package_exports_the_public_api():
    assert set(visualization.__all__) == {
        "TEMPLATE_PATH",
        "render_html",
        "render_markdown_report",
        "write_visualization",
    }


def test_template_exists_and_has_all_placeholders():
    assert isinstance(TEMPLATE_PATH, Path) and TEMPLATE_PATH.is_file()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder in ("$name", "$personal", "$education", "$experience", "$skills", "$evaluation"):
        assert placeholder in template


# ---------------------------------------------------------------------------
# HTML — structure
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_html_is_a_complete_html5_document(models, alias):
    html = render_html(models[alias])
    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in html
    assert "<head>" in html and "</head>" in html
    assert '<meta charset="UTF-8">' in html
    assert "<title>" in html and "</title>" in html
    assert "<body>" in html and "</body>" in html
    assert html.rstrip().endswith("</html>") and html.endswith("\n")


@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_html_tags_are_balanced(models, alias):
    checker = check_tags(render_html(models[alias]))
    assert checker.errors == []
    assert checker.stack == []
    for tag in ("html", "head", "body", "h1", "h2", "h3", "ul", "li", "span", "a"):
        assert tag in checker.seen


@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_html_has_the_sections_in_order(models, alias):
    html = render_html(models[alias])
    headings = re.findall(r"<h2>(.*?)</h2>", html)
    assert headings == SECTIONS


def test_html_has_no_unfilled_placeholders(models):
    html = render_html(models["fullstack"])
    assert not re.search(r"\$(name|personal|education|experience|skills|evaluation)\b", html)


def test_html_is_self_contained(models):
    html = render_html(models["ml"])
    assert "<style>" in html
    for external in ("<script", "<link ", "src=", "@import", "url("):
        assert external not in html


def test_html_is_deterministic(models):
    assert render_html(models["devops"]) == render_html(models["devops"])


# ---------------------------------------------------------------------------
# HTML — data injection
# ---------------------------------------------------------------------------
def test_html_injects_candidate_data(models):
    html = render_html(models["fullstack"])
    assert "<title>ResumeLens - Candidate Profile - WEDNESDAY ADDAMS</title>" in html
    assert "<h1>WEDNESDAY ADDAMS</h1>" in html
    assert "<strong>Email:</strong> wednesday.addams@nevermore.edu" in html
    assert "<strong>Phone:</strong> +1 555 666 7777" in html
    assert (
        '<a href="https://github.com/wednesday-addams">https://github.com/wednesday-addams</a>'
        in html
    )
    assert "<li>B.S. in Computer Science</li>" in html
    assert "<li>Nevermore University (2019 - 2023)</li>" in html
    assert "<li>Full Stack Developer, Raven Labs (2023 - 2026)</li>" in html


def test_html_injects_the_normalized_skills(models):
    html = render_html(models["fullstack"])
    assert re.findall(r'<span class="skill" title="written as: ([^"]*)">', html) == [
        "JS",
        "React.js",
        "NodeJS",
        "Postgres",
        "Git",
    ]
    for canonical, category in [
        ("JAVASCRIPT", "web_language"),
        ("REACT", "frontend"),
        ("NODE_JS", "backend"),
        ("POSTGRESQL", "database"),
        ("GIT", "vcs"),
    ]:
        assert f"{canonical} <small>{category}</small>" in html


@pytest.mark.parametrize("alias, accepted", list(ACCEPTED_PROFILE_BY_ALIAS.items()))
def test_html_shows_the_verdict_of_each_profile(models, alias, accepted):
    html = render_html(models[alias])
    assert re.findall(r"<h3>(.*?)</h3>", html) == PROFILE_TITLES
    assert html.count('<span class="accepted">ACCEPTED</span>') == 1
    assert html.count('<span class="rejected">REJECTED</span>') == 3
    block = re.search(rf"<h3>{accepted}</h3>(.*?)</div>", html, re.S).group(1)
    assert 'class="accepted"' in block


def test_html_shows_matched_skills_and_automaton_report(models):
    html = render_html(models["fullstack"])
    assert "<strong>Matched skills:</strong> JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT" in html
    assert "<strong>Matched skills:</strong> none" in html
    assert "ACCEPTED - Full Stack Developer" in html
    assert "REJECTED - Machine Learning Engineer" in html


# ---------------------------------------------------------------------------
# HTML — escaping, null values and missing template
# ---------------------------------------------------------------------------
def test_html_escapes_values_to_avoid_markup_injection():
    model = fake_model(
        name='<script>alert("x")</script> & Co',
        links=['https://a.com/?q="x"&y=<b>'],
        education=["<b>bold</b>"],
        skills=(("JAVASCRIPT", "web_language", "<i>JS</i>"),),
        results=(("FULL_STACK_DEVELOPER", "ACCEPTED", (), "<img src=x onerror=1>"),),
    )
    html = render_html(model)
    assert "<script" not in html and "<b>" not in html and "<img" not in html
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Co" in html
    assert 'href="https://a.com/?q=&quot;x&quot;&amp;y=&lt;b&gt;"' in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert check_tags(html).errors == []


def test_html_handles_null_contact_data():
    html = render_html(fake_model(email=None, phone=None, links=[]))
    assert '<p class="empty">No contact data provided.</p>' in html
    assert "<strong>Email:</strong>" not in html and "<strong>Phone:</strong>" not in html


def test_html_shows_only_the_contact_data_that_exists():
    html = render_html(fake_model(email="a@b.co", phone=None, links=[]))
    assert "<strong>Email:</strong> a@b.co" in html
    assert "<strong>Phone:</strong>" not in html and "No contact data provided." not in html


def test_html_handles_empty_education_and_experience():
    html = render_html(fake_model(education=[], experience=[]))
    assert '<p class="empty">No education entries.</p>' in html
    assert '<p class="empty">No experience entries.</p>' in html
    assert "<ul>" not in html
    assert check_tags(html).errors == []


def test_html_handles_empty_skills_and_results_without_breaking():
    html = render_html(fake_model(skills=(), results=()))
    assert '<div class="skills">' in html
    assert "<h3>" not in html
    checker = check_tags(html)
    assert checker.errors == [] and checker.stack == []


def test_html_handles_empty_matched_and_details():
    html = render_html(fake_model(results=(("DEVOPS_ENGINEER", "REJECTED", (), ""),)))
    assert "<h3>DevOps Engineer</h3>" in html
    assert "<strong>Matched skills:</strong> none" in html


def test_html_renders_non_ascii_text():
    html = render_html(fake_model(name="María Núñez", education=["Ingeniería de Sistemas"]))
    assert "<h1>María Núñez</h1>" in html and "<li>Ingeniería de Sistemas</li>" in html


def test_html_with_missing_template_raises_a_clear_os_error(missing_template):
    with pytest.raises(FileNotFoundError, match="no_such_template"):
        render_html(fake_model())


# ---------------------------------------------------------------------------
# Markdown — structure and data
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_markdown_has_title_and_sections_in_order(models, alias):
    md = render_markdown_report(models[alias])
    lines = md.splitlines()
    assert lines[0].startswith("# ") and md.endswith("\n") and not md.endswith("\n\n")
    assert [line[3:] for line in lines if line.startswith("## ")] == SECTIONS
    assert [line[4:] for line in lines if line.startswith("### ")] == PROFILE_TITLES


def test_markdown_is_plain_markdown_without_html_page_markup(models):
    md = render_markdown_report(models["fullstack"])
    for markup in ("<!DOCTYPE", "<html", "<body", "<table", "<style", "<script"):
        assert markup not in md


def test_markdown_injects_candidate_data(models):
    md = render_markdown_report(models["fullstack"])
    assert md.splitlines()[0] == "# WEDNESDAY ADDAMS"
    assert "- **Email:** wednesday.addams@nevermore.edu" in md
    assert "- **Phone:** +1 555 666 7777" in md
    assert "- **Link:** <https://www.linkedin.com/in/wednesday-addams>" in md
    assert "- **Link:** <https://github.com/wednesday-addams>" in md
    assert "- B.S. in Computer Science" in md
    assert "- Nevermore University (2019 - 2023)" in md
    assert "- Full Stack Developer, Raven Labs (2023 - 2026)" in md


def test_markdown_lists_the_normalized_skills_in_a_table(models):
    lines = render_markdown_report(models["fullstack"]).splitlines()
    start = lines.index("| Skill | Category | Written as |")
    assert lines[start + 1] == "| --- | --- | --- |"
    assert lines[start + 2 : start + 7] == [
        "| `JAVASCRIPT` | `web_language` | JS |",
        "| `REACT` | `frontend` | React.js |",
        "| `NODE_JS` | `backend` | NodeJS |",
        "| `POSTGRESQL` | `database` | Postgres |",
        "| `GIT` | `vcs` | Git |",
    ]


@pytest.mark.parametrize("alias, accepted", list(ACCEPTED_PROFILE_BY_ALIAS.items()))
def test_markdown_shows_the_verdict_of_each_profile(models, alias, accepted):
    md = render_markdown_report(models[alias])
    assert md.count("- **Qualification pattern:** ACCEPTED") == 1
    assert md.count("- **Qualification pattern:** REJECTED") == 3
    section = md.split(f"### {accepted}\n", 1)[1].split("###", 1)[0]
    assert "- **Qualification pattern:** ACCEPTED" in section


def test_markdown_shows_matched_skills_and_automaton_report(models):
    md = render_markdown_report(models["fullstack"])
    assert "- **Matched skills:** `JAVASCRIPT`, `REACT`, `NODE_JS`, `POSTGRESQL`, `GIT`" in md
    assert "- **Matched skills:** none" in md
    assert "> ACCEPTED - Full Stack Developer" in md
    assert "> REJECTED - Machine Learning Engineer" in md


def test_markdown_quotes_every_line_of_a_multiline_report():
    results = (("DATA_ENGINEER", "REJECTED", (), "first line\n\nthird line"),)
    md = render_markdown_report(fake_model(results=results))
    assert "> first line\n>\n> third line" in md


@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_markdown_and_html_report_the_same_content(models, alias):
    model = models[alias]
    html, md = render_html(model), render_markdown_report(model)
    for skill in model.skills.skills:
        assert skill.canonical in html and skill.canonical in md
    accepted = [r.name for r in model.evaluation.results if r.verdict == "ACCEPTED"]
    assert len(accepted) == 1
    assert md.count("ACCEPTED") >= 1 and html.count('class="accepted"') == 1
    assert model.personal.name in html and model.personal.name in md


def test_markdown_is_deterministic(models):
    assert render_markdown_report(models["data"]) == render_markdown_report(models["data"])


# ---------------------------------------------------------------------------
# Markdown — escaping, null values and independence from the template
# ---------------------------------------------------------------------------
def test_markdown_escapes_special_characters():
    model = fake_model(
        name="Ana *The Dev* [x]",
        education=["# not a heading", "- not a list", "<b>raw</b> & more"],
        skills=(("JAVASCRIPT", "web_language", "a|b"),),
    )
    md = render_markdown_report(model)
    assert "# Ana \\*The Dev\\* \\[x\\]" in md
    assert "- \\# not a heading" in md and "- \\- not a list" in md
    assert "- \\<b\\>raw\\</b\\> \\& more" in md
    assert "<b>" not in md


def test_markdown_keeps_table_rows_aligned_when_values_contain_pipes():
    model = fake_model(skills=(("A_B", "web_language", "x|y|z"), ("C", "vcs", "a\nb")))
    rows = [line for line in render_markdown_report(model).splitlines() if line.startswith("| ")]
    assert len(rows) == 4  # header, separator and two skills
    assert {len(table_cells(row)) for row in rows} == {5}  # 3 cells + 2 outer pipes
    assert "x\\|y\\|z" in rows[2] and "a b" in rows[3]


def test_markdown_does_not_turn_unsafe_urls_into_autolinks():
    md = render_markdown_report(fake_model(links=["javascript:alert(1)", "https://ok.dev/x"]))
    assert "<javascript" not in md
    assert "- **Link:** javascript:alert(1)" in md
    assert "- **Link:** <https://ok.dev/x>" in md


def test_markdown_handles_null_contact_data():
    md = render_markdown_report(fake_model(email=None, phone=None, links=[]))
    assert "## Personal Information\n\n_No contact data provided._" in md
    assert "**Email:**" not in md and "**Phone:**" not in md


def test_markdown_handles_links_set_to_none():
    model = fake_model(email=None, phone=None)
    model.personal.links = None
    assert "_No contact data provided._" in render_markdown_report(model)


def test_markdown_handles_empty_education_experience_skills_and_results():
    md = render_markdown_report(fake_model(education=[], experience=[], skills=(), results=()))
    assert "## Education\n\n_No education entries._" in md
    assert "## Experience\n\n_No experience entries._" in md
    assert "## Normalized Technical Skills\n\n_No skills recognized._" in md
    assert "## Qualification Evaluation\n\n_No evaluation results._" in md
    assert "| Skill |" not in md


def test_markdown_handles_empty_matched_and_details():
    md = render_markdown_report(fake_model(results=(("DEVOPS_ENGINEER", "REJECTED", (), ""),)))
    assert "### DevOps Engineer" in md
    assert "- **Matched skills:** none" in md
    assert ">" not in md.split("### DevOps Engineer", 1)[1]


def test_markdown_handles_an_empty_name():
    assert render_markdown_report(fake_model(name="")).startswith("# Unnamed candidate\n")


def test_markdown_renders_non_ascii_text():
    md = render_markdown_report(fake_model(name="María Núñez", education=["Ingeniería"]))
    assert md.startswith("# María Núñez\n") and "- Ingeniería" in md


def test_markdown_export_works_when_the_html_template_is_missing(models, missing_template):
    # The Markdown report is the fallback: it does not read the HTML template.
    md = render_markdown_report(models["fullstack"])
    assert md.startswith("# WEDNESDAY ADDAMS")
    with pytest.raises(FileNotFoundError):
        render_html(models["fullstack"])


# ---------------------------------------------------------------------------
# Writing the reports
# ---------------------------------------------------------------------------
def test_write_visualization_writes_html_and_markdown_files(models, tmp_path):
    html_path = write_visualization(render_html(models["ml"]), tmp_path / "report.html")
    md_path = write_visualization(render_markdown_report(models["ml"]), tmp_path / "report.md")
    assert html_path == tmp_path / "report.html" and md_path == tmp_path / "report.md"
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert md_path.read_text(encoding="utf-8").startswith("# Mary Jane Watson")


def test_write_visualization_creates_missing_directories_and_accepts_str(tmp_path):
    target = write_visualization("# hi\n", str(tmp_path / "out" / "nested" / "r.md"))
    assert isinstance(target, Path) and target.read_text(encoding="utf-8") == "# hi\n"


def test_write_visualization_overwrites_and_keeps_utf8(tmp_path):
    path = tmp_path / "r.md"
    write_visualization("old", path)
    write_visualization("María Núñez\n", path)
    assert path.read_text(encoding="utf-8") == "María Núñez\n"


def test_write_visualization_to_a_directory_raises_os_error(tmp_path):
    with pytest.raises(OSError):
        write_visualization("x", tmp_path)
