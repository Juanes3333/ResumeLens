"""End-to-end integration tests of the whole ResumeLens pipeline.

Every test starts from the synthetic resumes stored in ``data/input_resumes/`` and goes
through the four stages (extraction, normalization, classification, candidate language)
down to the report written on disk, without any manual intervention. Both the in-process
API (``run_pipeline``, ``write_report``, ``main``) and the real entry point
(``python main.py``) are exercised.
"""

import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

from resumelens.cli import EXIT_ERROR, EXIT_OK, main, run_pipeline, run_pipeline_text, write_report
from resumelens.grammar import is_valid_profile_source

ROOT = Path(__file__).resolve().parent.parent

PROFILE_NAMES = (
    "Full Stack Developer",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Data Engineer",
)

#: alias -> (candidate name, raw skills, accepted profile, canonical sequence of that profile)
EXPECTED: Dict[str, Tuple[str, List[str], str, List[str]]] = {
    "fullstack": (
        "WEDNESDAY ADDAMS",
        ["JS", "React.js", "NodeJS", "Postgres", "Git"],
        "Full Stack Developer",
        ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"],
    ),
    "ml": (
        "Mary Jane Watson",
        ["Python", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "SQL", "Git"],
        "Machine Learning Engineer",
        ["PYTHON", "NUMPY", "PANDAS", "SCIKIT_LEARN", "TENSORFLOW", "SQL", "GIT"],
    ),
    "devops": (
        "Peter Parker",
        ["Python", "Docker", "Kubernetes", "Terraform", "Git"],
        "DevOps Engineer",
        ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT"],
    ),
    "data": (
        "Gwen Stacy",
        ["Python", "Apache Spark", "Airflow", "PostgreSQL", "Git"],
        "Data Engineer",
        ["PYTHON", "SPARK", "AIRFLOW", "POSTGRESQL", "GIT"],
    ),
}
VALID_ALIASES = tuple(EXPECTED)


class _TagChecker(HTMLParser):
    """Collect the tags of an HTML document and check that they are balanced."""

    VOID = {"meta", "link", "br", "hr", "img", "input"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []
        self.tags: List[str] = []
        self.classes: List[str] = []
        self.text: List[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.classes.extend(value for name, value in attrs if name == "class" and value)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> with open tags {self.stack}")
        else:
            self.stack.pop()

    def handle_data(self, data):
        self.text.append(data)


def _check_html(html: str) -> _TagChecker:
    checker = _TagChecker()
    checker.feed(html)
    checker.close()
    assert checker.errors == []
    assert checker.stack == []
    return checker


def _verdicts(run) -> Dict[str, bool]:
    return {result.profile_name: result.is_accepted for result in run.report.results}


# ---------------------------------------------------------------------------
# Stages 1 to 4 in process, from disk to the validated model
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", VALID_ALIASES)
class TestValidResumes:
    def test_stage_1_extracts_candidate_and_raw_skills(self, resume_paths, alias):
        name, raw_skills, _, _ = EXPECTED[alias]
        run = run_pipeline(resume_paths[alias])
        assert run.resume.candidate_info.name == name
        assert run.resume.raw_skills == raw_skills
        assert run.resume.candidate_info.email
        assert run.resume.candidate_info.education
        assert run.resume.candidate_info.experience

    def test_stage_2_normalizes_every_skill(self, resume_paths, alias):
        _, raw_skills, _, _ = EXPECTED[alias]
        run = run_pipeline(resume_paths[alias])
        assert [r.raw_name for r in run.normalization.records] == raw_skills
        assert run.normalization.unrecognized == []
        assert all(r.canonical_name and r.category for r in run.normalization.records)

    def test_stage_3_accepts_exactly_the_expected_profile(self, resume_paths, alias):
        _, _, accepted, sequence = EXPECTED[alias]
        run = run_pipeline(resume_paths[alias])
        verdicts = _verdicts(run)
        assert set(verdicts) == set(PROFILE_NAMES)
        assert [name for name, ok in verdicts.items() if ok] == [accepted]
        winner = next(r for r in run.report.results if r.is_accepted)
        assert winner.matched_sequence == sequence

    def test_stage_4_dsl_document_is_valid_and_matches_the_model(self, resume_paths, alias):
        name, _, accepted, sequence = EXPECTED[alias]
        run = run_pipeline(resume_paths[alias])
        assert run.dsl_error is None
        assert run.model is not None
        assert is_valid_profile_source(run.source)
        for token in [name, accepted, *sequence]:
            assert token in run.source


    def test_report_details_do_not_change_the_verdict(self, resume_texts, alias):
        """Location, current role, summary and bullets are shown, but they never decide."""
        text = resume_texts[alias]
        kept = [
            line
            for line in text.splitlines()
            if not line.startswith(("Location:", "Current role:", "- "))
        ]
        stripped = chr(10).join(kept)
        with_details = run_pipeline_text(text)
        without_details = run_pipeline_text(stripped)
        assert without_details.resume.candidate_info.location == ""
        assert without_details.resume.candidate_info.jobs[0].highlights == []
        assert with_details.report.verdicts() == without_details.report.verdicts()
        assert with_details.sequences == without_details.sequences


# ---------------------------------------------------------------------------
# Reports written on disk
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", VALID_ALIASES)
class TestReportFiles:
    def test_html_report(self, resume_paths, tmp_path, alias):
        name, _, accepted, sequence = EXPECTED[alias]
        output = tmp_path / f"{alias}.html"
        run = run_pipeline(resume_paths[alias])
        assert write_report(run.model, output) == output
        html = output.read_text(encoding="utf-8")

        checker = _check_html(html)
        assert html.lstrip().lower().startswith("<!doctype html")
        assert {"html", "head", "body", "h1", "h2", "ul"} <= set(checker.tags)
        assert "skill" in checker.classes
        assert "accepted" in checker.classes and "rejected" in checker.classes
        assert f"<h1>{name}</h1>" in html
        assert f"{accepted}" in html
        for canonical in sequence:
            assert canonical in html
        # Self-contained: no scripts and no external resources.
        assert "<script" not in html.lower()
        # (The candidate's own profile links are content, not page resources.)
        assert not re.search(r"<(?:link|img|iframe)\b", html, re.IGNORECASE)

    def test_html_report_marks_one_accepted_and_three_rejected_profiles(
        self, resume_paths, tmp_path, alias
    ):
        output = tmp_path / "report.html"
        write_report(run_pipeline(resume_paths[alias]).model, output)
        html = output.read_text(encoding="utf-8")
        assert len(re.findall(r'class="accepted"', html)) == 1
        assert len(re.findall(r'class="rejected"', html)) == 3

    def test_html_report_has_the_sections_of_the_example_page(self, resume_paths, tmp_path, alias):
        run = run_pipeline(resume_paths[alias])
        info = run.resume.candidate_info
        output = tmp_path / "report.html"
        write_report(run.model, output)
        html = output.read_text(encoding="utf-8")
        titles = re.findall(r"<h2>(.*?)</h2>", html)
        assert titles == [
            "Personal Information",
            "Profile Summary",
            "Education",
            "Experience",
            "Normalized Technical Skills",
            "Qualification Evaluation",
        ]
        assert f"<strong>Location:</strong> {info.location}" in html
        assert f"<strong>Current role:</strong> {info.current_role}" in html
        for paragraph in info.summary:
            assert f"<p>{paragraph}</p>" in html
        job = info.jobs[0]
        assert f"<h3>{job.role}</h3>" in html
        assert f'<p class="metadata">{job.company} &middot; {job.period}</p>' in html
        for highlight in job.highlights:
            assert f"<li>{highlight}</li>" in html

    def test_markdown_report(self, resume_paths, tmp_path, alias):
        name, _, accepted, sequence = EXPECTED[alias]
        output = tmp_path / f"{alias}.md"
        write_report(run_pipeline(resume_paths[alias]).model, output)
        markdown = output.read_text(encoding="utf-8")
        assert name in markdown
        assert "ACCEPTED" in markdown and "REJECTED" in markdown
        assert accepted in markdown
        for canonical in sequence:
            assert canonical in markdown
        assert "<html" not in markdown.lower()


# ---------------------------------------------------------------------------
# Corrupted resume
# ---------------------------------------------------------------------------
class TestInvalidResume:
    def test_stages_1_to_3_complete_and_reject_every_profile(self, resume_paths):
        run = run_pipeline(resume_paths["invalid"])
        assert run.resume.raw_skills == []
        assert run.normalization.records == []
        assert not any(_verdicts(run).values())

    def test_stage_4_reports_a_syntax_error_instead_of_raising(self, resume_paths):
        run = run_pipeline(resume_paths["invalid"])
        assert run.model is None
        assert run.dsl_error
        assert not is_valid_profile_source(run.source)

    def test_cli_fails_and_writes_no_report(self, resume_paths, tmp_path, capsys):
        output = tmp_path / "invalid.html"
        status = main(["--cv", str(resume_paths["invalid"]), "--output", str(output)])
        captured = capsys.readouterr()
        assert status == EXIT_ERROR
        assert not output.exists()
        assert "INVALID" in captured.out
        assert "not generated" in captured.out
        assert "error:" in captured.err


# ---------------------------------------------------------------------------
# Command line, in process and as a real subprocess
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_main_runs_the_whole_pipeline_and_writes_the_report(
    resume_paths, tmp_path, capsys, alias
):
    _, _, accepted, sequence = EXPECTED[alias]
    output = tmp_path / "nested" / "report.html"
    output.parent.mkdir()
    status = main(["--cv", str(resume_paths[alias]), "--output", str(output)])
    out = capsys.readouterr().out
    assert status == EXIT_OK
    assert output.is_file()
    for title in ("[Stage 1]", "[Stage 2]", "[Stage 3]", "[Stage 4]", "Final verdict"):
        assert title in out
    assert f"ACCEPTED : {accepted}" in out
    assert f"written to {output}" in out
    assert ", ".join(sequence) in out


@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_profile_option_narrows_the_console_report(resume_paths, capsys, alias):
    _, _, accepted, _ = EXPECTED[alias]
    status = main(["--cv", str(resume_paths[alias]), "--profile", accepted])
    out = capsys.readouterr().out
    assert status == EXIT_OK
    others = [p for p in PROFILE_NAMES if p != accepted]
    verdict = out.split("Final verdict", 1)[1]
    assert f"ACCEPTED : {accepted}" in verdict
    assert all(other not in verdict for other in others)


def test_pipeline_is_deterministic(resume_paths, tmp_path):
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    write_report(run_pipeline(resume_paths["ml"]).model, first)
    write_report(run_pipeline(resume_paths["ml"]).model, second)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_entry_point_subprocess(resume_paths, tmp_path, alias):
    _, _, accepted, _ = EXPECTED[alias]
    output = tmp_path / "cli.md"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--cv", str(resume_paths[alias]),
         "--output", str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        timeout=120,
    )
    assert completed.returncode == EXIT_OK, completed.stderr
    assert f"ACCEPTED : {accepted}" in completed.stdout
    assert output.is_file()


def test_entry_point_subprocess_with_missing_resume(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--cv", str(tmp_path / "missing_resume.txt")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert completed.returncode == EXIT_ERROR
    assert "not found" in completed.stderr
