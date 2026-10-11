"""Unit tests for the command-line interface (``resumelens.cli`` and ``main.py``).

They cover the argument parser, the console report, the exit statuses and the report files
written by ``--output``. The end-to-end suite of the whole pipeline is a separate file.
"""

import io
import subprocess
import sys
from pathlib import Path

import pytest

from resumelens import cli
from resumelens.cli import (
    EXIT_ERROR,
    EXIT_OK,
    OUTPUT_RENDERERS,
    PipelineRun,
    build_parser,
    format_console_report,
    main,
    run_pipeline,
    run_pipeline_text,
    write_report,
)
from resumelens.normalization import PROFILES

ROOT = Path(__file__).resolve().parent.parent

PROFILE_NAMES = {
    "FULL_STACK_DEVELOPER": "Full Stack Developer",
    "MACHINE_LEARNING_ENGINEER": "Machine Learning Engineer",
    "DEVOPS_ENGINEER": "DevOps Engineer",
    "DATA_ENGINEER": "Data Engineer",
}
ACCEPTED_BY = {
    "fullstack": "Full Stack Developer",
    "ml": "Machine Learning Engineer",
    "devops": "DevOps Engineer",
    "data": "Data Engineer",
}
STAGE_TITLES = [
    "[Stage 1] Extraction (regular expressions)",
    "[Stage 2] Normalization (finite-state transducers)",
    "[Stage 3] Classification (finite automata)",
    "[Stage 4] Candidate language (textX) and report",
    "Final verdict",
]


def _run(capsys, *argv):
    status = main(list(argv))
    captured = capsys.readouterr()
    return status, captured.out, captured.err


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
class TestArguments:
    def test_cv_is_required(self, capsys):
        with pytest.raises(SystemExit) as error:
            build_parser().parse_args([])
        assert error.value.code == 2
        assert "--cv" in capsys.readouterr().err

    def test_defaults(self):
        args = build_parser().parse_args(["--cv", "resume.txt"])
        assert args.cv == Path("resume.txt")
        assert args.output is None
        assert args.profile is None

    def test_all_arguments(self):
        args = build_parser().parse_args(["--cv", "a.txt", "--output", "out/report.html", "--profile", "Data Engineer"])
        assert args.cv == Path("a.txt")
        assert args.output == Path("out/report.html")
        assert args.profile == "DATA_ENGINEER"

    @pytest.mark.parametrize("extension", [".html", ".htm", ".md", ".markdown", ".HTML", ".Md"])
    def test_supported_output_extensions(self, extension):
        args = build_parser().parse_args(["--cv", "a.txt", "--output", f"report{extension}"])
        assert args.output == Path(f"report{extension}")

    @pytest.mark.parametrize("name", ["report.pdf", "report.txt", "report", "report.html.bak", "report."])
    def test_unsupported_output_extension_is_an_argument_error(self, name, capsys):
        with pytest.raises(SystemExit) as error:
            build_parser().parse_args(["--cv", "a.txt", "--output", name])
        assert error.value.code == 2
        assert "unsupported report extension" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "value, identifier",
        [
            ("Full Stack Developer", "FULL_STACK_DEVELOPER"),
            ("full-stack developer", "FULL_STACK_DEVELOPER"),
            ("MACHINE_LEARNING_ENGINEER", "MACHINE_LEARNING_ENGINEER"),
            ("devops engineer", "DEVOPS_ENGINEER"),
            ("Data  Engineer", "DATA_ENGINEER"),
        ],
    )
    def test_profile_names_are_resolved(self, value, identifier):
        assert build_parser().parse_args(["--cv", "a.txt", "--profile", value]).profile == identifier

    def test_unknown_profile_is_an_argument_error(self, capsys):
        with pytest.raises(SystemExit) as error:
            build_parser().parse_args(["--cv", "a.txt", "--profile", "Backend Developer"])
        assert error.value.code == 2
        assert "Unknown profile" in capsys.readouterr().err

    def test_unknown_option_is_an_argument_error(self):
        with pytest.raises(SystemExit) as error:
            build_parser().parse_args(["--cv", "a.txt", "--verbose"])
        assert error.value.code == 2

    def test_help_mentions_every_option(self, capsys):
        with pytest.raises(SystemExit) as error:
            build_parser().parse_args(["--help"])
        assert error.value.code == 0
        text = capsys.readouterr().out
        for option in ("--cv", "--output", "--profile"):
            assert option in text

    def test_output_renderers_cover_html_and_markdown(self):
        assert set(OUTPUT_RENDERERS) == {".html", ".htm", ".md", ".markdown"}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
class TestRunPipeline:
    @pytest.mark.parametrize("alias, accepted", list(ACCEPTED_BY.items()))
    def test_valid_resumes(self, resume_paths, alias, accepted):
        run = run_pipeline(resume_paths[alias])
        assert isinstance(run, PipelineRun)
        assert run.cv_path == resume_paths[alias]
        assert run.model is not None
        assert run.dsl_error is None
        assert run.report.accepted_profiles == [accepted]
        assert tuple(run.sequences) == PROFILES

    def test_stage_outputs_are_chained(self, resume_paths):
        run = run_pipeline(resume_paths["fullstack"])
        assert run.resume.raw_skills == ["JS", "React.js", "NodeJS", "Postgres", "Git"]
        assert run.normalization.canonical_names == ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]
        assert run.sequences["FULL_STACK_DEVELOPER"] == ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]
        assert run.source.startswith("candidate {")
        assert [r.canonical for r in run.model.skills.skills] == run.normalization.canonical_names
        assert run.model.personal.name == run.resume.candidate_info.name

    def test_model_holds_the_four_verdicts(self, resume_paths):
        run = run_pipeline(resume_paths["ml"])
        verdicts = {r.name: r.verdict for r in run.model.evaluation.results}
        assert verdicts == {
            "FULL_STACK_DEVELOPER": "REJECTED",
            "MACHINE_LEARNING_ENGINEER": "ACCEPTED",
            "DEVOPS_ENGINEER": "REJECTED",
            "DATA_ENGINEER": "REJECTED",
        }

    def test_resume_without_skills_keeps_stages_1_to_3_and_reports_the_dsl_error(self, resume_paths):
        run = run_pipeline(resume_paths["invalid"])
        assert run.model is None
        assert "Expected 'skill'" in run.dsl_error
        assert run.normalization.records == []
        assert run.report.accepted_profiles == []
        assert len(run.report.rejected_profiles) == 4

    @pytest.mark.parametrize("alias", sorted(ACCEPTED_BY))
    def test_text_gives_the_same_run_as_the_file(self, resume_paths, alias):
        from_file = run_pipeline(resume_paths[alias])
        from_text = run_pipeline_text(resume_paths[alias].read_text(encoding="utf-8"), resume_paths[alias])
        assert from_text.source == from_file.source
        assert from_text.cv_path == from_file.cv_path
        assert from_text.report.verdicts() == from_file.report.verdicts()

    def test_text_uses_a_default_label_and_accepts_inline_skills(self):
        run = run_pipeline_text("Mary Jane Watson\nTechnical Skills: Python, Pandas, sklearn, SQL, Git.\n")
        assert run.cv_path == Path("<text>")
        assert run.resume.raw_skills == ["Python", "Pandas", "sklearn", "SQL", "Git"]
        assert run.report.accepted_profiles == ["Machine Learning Engineer"]

    def test_accepts_a_string_path(self, resume_paths):
        assert run_pipeline(str(resume_paths["data"])).report.accepted_profiles == ["Data Engineer"]

    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_pipeline(tmp_path / "missing.txt")

    def test_directory_is_not_a_resume(self, tmp_path):
        with pytest.raises(OSError):
            run_pipeline(tmp_path)

    def test_resume_with_only_unrecognized_skills(self, tmp_path):
        path = tmp_path / "cv.txt"
        path.write_text("Jane Doe\n\nTechnical Skills:\nCobol, Fortran.\n", encoding="utf-8")
        run = run_pipeline(path)
        assert run.model is None
        assert run.normalization.unrecognized == ["Cobol", "Fortran"]


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------
class TestConsoleReport:
    def test_stages_appear_in_order(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["fullstack"]))
        positions = [text.index(title) for title in STAGE_TITLES]
        assert positions == sorted(positions)
        assert text.startswith("ResumeLens - formal language-based resume screening")
        assert text.endswith("\n")

    def test_stage_1_shows_the_extracted_data(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["fullstack"]))
        assert "Name        : WEDNESDAY ADDAMS" in text
        assert "Email       : wednesday.addams@nevermore.edu" in text
        assert "Phone       : +1 555 666 7777" in text
        assert "Raw skills  : JS, React.js, NodeJS, Postgres, Git" in text
        assert "Education   : 2 entries" in text

    def test_stage_2_shows_each_translation_and_the_canonical_orders(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["fullstack"]))
        assert "JS       -> JAVASCRIPT  (web_language)" in text
        assert "Postgres -> POSTGRESQL  (database)" in text
        assert "FULL_STACK_DEVELOPER: JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT" in text
        for identifier in PROFILES:
            assert f"{identifier}:" in text

    def test_stage_2_shows_discarded_tokens(self, tmp_path):
        path = tmp_path / "cv.txt"
        path.write_text("Jane Doe\n\nTechnical Skills:\nJS, JavaScript, Cobol, Git.\n", encoding="utf-8")
        text = format_console_report(run_pipeline(path))
        assert "Unrecognized : Cobol" in text
        assert "Duplicates   : JavaScript" in text

    @pytest.mark.parametrize("alias, accepted", list(ACCEPTED_BY.items()))
    def test_stage_3_and_final_verdict(self, resume_paths, alias, accepted):
        text = format_console_report(run_pipeline(resume_paths[alias]))
        for name in PROFILE_NAMES.values():
            assert name in text
        assert text.count("ACCEPTED  matched:") == 1
        assert text.count("REJECTED  reason:") == 3
        assert f"ACCEPTED : {accepted}" in text
        others = ", ".join(n for n in PROFILE_NAMES.values() if n != accepted)
        assert f"REJECTED : {others}" in text

    def test_rejections_show_the_reason_of_the_automaton(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["ml"]))
        assert "belongs to stage 'database' but the required stage(s)" in text

    def test_invalid_resume(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["invalid"]))
        assert "DSL document : INVALID (line" in text
        assert "Report       : not generated" in text
        assert "(no recognized skills)" in text
        assert "ACCEPTED : (none)" in text
        assert "the sequence is empty" in text
        assert "Name        : (not found)" in text

    def test_report_line_of_stage_4(self, resume_paths):
        run = run_pipeline(resume_paths["ml"])
        assert "Report       : not requested (use --output)" in format_console_report(run)
        assert "Report       : written to out.html" in format_console_report(run, output=Path("out.html"))
        failed = format_console_report(run, output=None, write_error="disk full")
        assert "Report       : not written (disk full)" in failed
        assert "DSL document : valid" in failed

    def test_profile_filter_restricts_stages_2_and_3_and_the_verdict(self, resume_paths):
        run = run_pipeline(resume_paths["data"])
        text = format_console_report(run, profile="DATA_ENGINEER")
        assert "DATA_ENGINEER: PYTHON, SPARK, AIRFLOW, POSTGRESQL, GIT" in text
        assert "FULL_STACK_DEVELOPER:" not in text
        assert "Full Stack Developer" not in text
        assert "Report of the automaton:" in text
        assert "Stages satisfied: language (PYTHON)" in text
        assert "ACCEPTED : Data Engineer" in text
        assert "REJECTED : (none)" in text

    def test_profile_filter_of_a_rejecting_profile(self, resume_paths):
        text = format_console_report(run_pipeline(resume_paths["data"]), profile="Full Stack Developer")
        assert "ACCEPTED : (none)" in text
        assert "REJECTED : Full Stack Developer" in text
        assert "Reason:" in text

    def test_unknown_profile_filter(self, resume_paths):
        with pytest.raises(cli.UnknownProfileError):
            format_console_report(run_pipeline(resume_paths["data"]), profile="Nope")

    @pytest.mark.parametrize("alias", ["fullstack", "ml", "devops", "data", "invalid"])
    def test_output_is_plain_ascii(self, resume_paths, alias):
        text = format_console_report(run_pipeline(resume_paths[alias]))
        assert text.isascii()


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def model(resume_paths):
    """Validated textX model of the full stack resume."""
    return run_pipeline(resume_paths["fullstack"]).model


class TestWriteReport:
    @pytest.mark.parametrize("name", ["r.html", "r.htm", "R.HTML"])
    def test_html(self, model, tmp_path, name):
        path = write_report(model, tmp_path / name)
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().lower().startswith("<!doctype html")
        assert "WEDNESDAY ADDAMS" in text

    @pytest.mark.parametrize("name", ["r.md", "r.markdown", "R.MD"])
    def test_markdown(self, model, tmp_path, name):
        path = write_report(model, tmp_path / name)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# WEDNESDAY ADDAMS")
        assert "## Qualification Evaluation" in text

    def test_missing_directories_are_created(self, model, tmp_path):
        target = tmp_path / "a" / "b" / "report.html"
        assert write_report(model, target) == target
        assert target.is_file()

    def test_existing_report_is_overwritten(self, model, tmp_path):
        target = tmp_path / "report.md"
        target.write_text("old", encoding="utf-8")
        write_report(model, target)
        assert target.read_text(encoding="utf-8") != "old"

    def test_unsupported_extension(self, model, tmp_path):
        with pytest.raises(ValueError, match="unsupported report extension"):
            write_report(model, tmp_path / "report.pdf")
        assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# main(): exit statuses, streams and files
# ---------------------------------------------------------------------------
class TestMain:
    @pytest.mark.parametrize("alias, accepted", list(ACCEPTED_BY.items()))
    def test_valid_resume_exits_with_success(self, capsys, resume_paths, alias, accepted):
        status, out, err = _run(capsys, "--cv", str(resume_paths[alias]))
        assert status == EXIT_OK == 0
        assert err == ""
        assert f"ACCEPTED : {accepted}" in out
        for title in STAGE_TITLES:
            assert title in out

    def test_html_report_is_written(self, capsys, resume_paths, tmp_path):
        target = tmp_path / "reports" / "fullstack.html"
        status, out, err = _run(capsys, "--cv", str(resume_paths["fullstack"]), "--output", str(target))
        assert status == EXIT_OK
        assert f"Report       : written to {target}" in out
        assert "WEDNESDAY ADDAMS" in target.read_text(encoding="utf-8")

    def test_markdown_report_is_written(self, capsys, resume_paths, tmp_path):
        target = tmp_path / "ml.md"
        status, out, _ = _run(capsys, "--cv", str(resume_paths["ml"]), "--output", str(target))
        assert status == EXIT_OK
        assert target.read_text(encoding="utf-8").startswith("# Mary Jane Watson")

    def test_no_file_is_written_without_output(self, capsys, resume_paths, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        status, _, _ = _run(capsys, "--cv", str(resume_paths["ml"]))
        assert status == EXIT_OK
        assert list(tmp_path.iterdir()) == []

    def test_profile_option(self, capsys, resume_paths):
        status, out, _ = _run(capsys, "--cv", str(resume_paths["devops"]), "--profile", "devops engineer")
        assert status == EXIT_OK
        assert "ACCEPTED : DevOps Engineer" in out
        assert "Full Stack Developer" not in out

    def test_resume_without_skills_fails_and_writes_nothing(self, capsys, resume_paths, tmp_path):
        target = tmp_path / "invalid.html"
        status, out, err = _run(capsys, "--cv", str(resume_paths["invalid"]), "--output", str(target))
        assert status == EXIT_ERROR == 1
        assert "DSL document : INVALID" in out
        assert "Final verdict" in out
        assert "no report was generated" in err
        assert not target.exists()

    def test_missing_resume_file(self, capsys, tmp_path):
        status, out, err = _run(capsys, "--cv", str(tmp_path / "missing.txt"))
        assert status == EXIT_ERROR
        assert out == ""
        assert "resume file not found" in err

    def test_directory_instead_of_a_file(self, capsys, tmp_path):
        status, out, err = _run(capsys, "--cv", str(tmp_path))
        assert status == EXIT_ERROR
        assert out == ""
        assert "error:" in err

    def test_unwritable_output_is_reported(self, capsys, resume_paths, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        status, out, err = _run(capsys, "--cv", str(resume_paths["ml"]), "--output", str(blocker / "r.html"))
        assert status == EXIT_ERROR
        assert "Report       : not written" in out
        assert "cannot write" in err
        assert "ACCEPTED : Machine Learning Engineer" in out

    @pytest.mark.parametrize(
        "argv",
        [
            [],
            ["--cv"],
            ["--cv", "a.txt", "--output", "r.pdf"],
            ["--cv", "a.txt", "--profile", "Nope"],
            ["--unknown"],
        ],
    )
    def test_invalid_arguments_exit_with_status_2(self, argv):
        with pytest.raises(SystemExit) as error:
            main(argv)
        assert error.value.code == 2

    def test_invalid_arguments_run_nothing(self, tmp_path):
        target = tmp_path / "r.html"
        with pytest.raises(SystemExit):
            main(["--cv", str(tmp_path / "missing.txt"), "--output", str(target), "--profile", "Nope"])
        assert not target.exists()

    def test_main_reads_sys_argv_by_default(self, capsys, resume_paths, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["resumelens", "--cv", str(resume_paths["data"])])
        assert main() == EXIT_OK
        assert "ACCEPTED : Data Engineer" in capsys.readouterr().out

    def test_two_runs_give_the_same_report(self, capsys, resume_paths):
        first = _run(capsys, "--cv", str(resume_paths["fullstack"]))
        second = _run(capsys, "--cv", str(resume_paths["fullstack"]))
        assert first == second

    def test_characters_the_console_cannot_encode_do_not_crash(self, resume_paths, monkeypatch, tmp_path):
        path = tmp_path / "cv.txt"
        text = resume_paths["ml"].read_text(encoding="utf-8").replace("Python,", "Python, \u00d1and\u00fa, \u65e5\u672c,", 1)
        path.write_text(text, encoding="utf-8")
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="ascii", errors="strict", write_through=True)
        monkeypatch.setattr(sys, "stdout", stream)
        assert main(["--cv", str(path)]) == EXIT_OK
        stream.flush()
        assert b"Unrecognized" in buffer.getvalue()


# ---------------------------------------------------------------------------
# Entry point script
# ---------------------------------------------------------------------------
class TestEntryPoint:
    def test_main_py_runs_the_pipeline(self, resume_paths):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--cv", str(resume_paths["fullstack"])],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert completed.returncode == 0, completed.stderr
        assert "ACCEPTED : Full Stack Developer" in completed.stdout

    def test_main_py_propagates_the_exit_status(self, resume_paths):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--cv", str(resume_paths["invalid"])],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert completed.returncode == 1
        assert "no report was generated" in completed.stderr

    def test_main_py_argument_errors_exit_with_status_2(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "main.py")], capture_output=True, text=True, cwd=ROOT
        )
        assert completed.returncode == 2
        assert "--cv" in completed.stderr

    def test_main_py_is_a_thin_wrapper(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        assert "from resumelens.cli import main" in source
        assert len(source.splitlines()) < 15
