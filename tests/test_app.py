"""Tests of the Streamlit web interface (``app.py``).

The page is run without a browser with Streamlit's ``AppTest``: the tests choose a résumé in
the sidebar and check the verdicts, the tabs and the report of Stage 4. The helper functions
of the module are tested directly.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app
from resumelens.classification.automata import ML_PROFILE, build_automaton
from resumelens.normalization import PROFILES

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

# Example résumé -> profile that accepts it (and only it).
ACCEPTED_BY = {
    "resume_fullstack": "Full Stack Developer",
    "resume_ml": "Machine Learning Engineer",
    "resume_devops": "DevOps Engineer",
    "resume_data": "Data Engineer",
    "resume_invalid": None,
}


def run_app() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=60).run()


def verdicts(at: AppTest) -> dict:
    return {metric.label: metric.value for metric in at.metric}


class TestPage:
    def test_first_run_has_no_exception(self):
        at = run_app()
        assert not at.exception
        assert at.title[0].value == "ResumeLens"

    def test_the_four_stage_tabs_are_there(self):
        labels = [tab.label for tab in run_app().tabs]
        assert len(labels) >= 4
        assert [label.split(" ")[0] for label in labels[:4]] == ["1", "2", "3", "4"]

    @pytest.mark.parametrize("name, accepted", list(ACCEPTED_BY.items()))
    def test_example_resumes_give_the_expected_verdicts(self, name, accepted):
        at = run_app()
        at.sidebar.selectbox(key="example").select(name).run()
        assert not at.exception
        result = verdicts(at)
        assert len(result) == 4
        assert [profile for profile, verdict in result.items() if verdict == "ACCEPTED"] == (
            [accepted] if accepted else []
        )

    def test_valid_resume_shows_a_valid_document_and_downloads(self):
        at = run_app()
        at.sidebar.selectbox(key="example").select("resume_fullstack").run()
        assert any("valid" in success.value for success in at.success)
        assert not at.error
        assert len(at.get("download_button")) == 2

    def test_invalid_resume_shows_the_syntax_error_and_no_report(self):
        at = run_app()
        at.sidebar.selectbox(key="example").select("resume_invalid").run()
        assert not at.exception
        assert any("not valid" in error.value for error in at.error)
        assert len(at.get("download_button")) == 0

    @pytest.mark.parametrize("profile", PROFILES)
    def test_every_profile_can_be_detailed(self, profile):
        at = run_app()
        at.sidebar.selectbox(key="profile").select(profile).run()
        assert not at.exception


class TestPastedText:
    def test_inline_skills_header_is_read(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_PASTE).run()
        at.sidebar.text_area(key="pasted").set_value(
            "Mary Jane Watson\nTechnical Skills: Java, Python, Pandas, sklearn, SQL, Git.\n"
        ).run()
        assert not at.exception
        assert verdicts(at)["Machine Learning Engineer"] == "ACCEPTED"

    def test_default_sample_is_the_resume_of_the_assignment(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_PASTE).run()
        assert verdicts(at)["Full Stack Developer"] == "ACCEPTED"

    def test_empty_text_asks_for_a_resume(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_PASTE).run()
        at.sidebar.text_area(key="pasted").set_value("   ").run()
        assert not at.exception
        assert not at.metric
        assert at.info

    def test_text_without_skills_is_reported_not_raised(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_PASTE).run()
        at.sidebar.text_area(key="pasted").set_value("Jane Doe\nNothing to see here.\n").run()
        assert not at.exception
        assert set(verdicts(at).values()) == {"REJECTED"}
        assert any("not valid" in error.value for error in at.error)

    def test_upload_without_a_file_asks_for_a_resume(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_UPLOAD).run()
        assert not at.exception
        assert not at.metric
        assert at.info


class TestHelpers:
    def test_example_resumes_are_the_five_synthetic_files(self):
        assert sorted(app.example_resumes()) == sorted(ACCEPTED_BY)
        assert all(path.is_file() for path in app.example_resumes().values())

    def test_profile_labels_are_official_names(self):
        assert [app.profile_label(profile) for profile in PROFILES] == [
            "Full Stack Developer",
            "Machine Learning Engineer",
            "DevOps Engineer",
            "Data Engineer",
        ]

    def test_transition_rows_describe_the_whole_function_delta(self):
        automaton = build_automaton(ML_PROFILE)
        rows = app.transition_rows(automaton)
        assert {"From": "q0", "To": "q1", "On": "PYTHON"} in rows
        symbols = {symbol for row in rows for symbol in row["On"].split(", ")}
        assert symbols == {str(symbol) for symbol in automaton.symbols}
        assert {row["From"] for row in rows} <= {str(state) for state in automaton.states}

    def test_selected_profile_is_detected_by_name(self):
        assert app.resolve_selected("DevOps Engineer", "DEVOPS_ENGINEER")
        assert not app.resolve_selected("Data Engineer", "DEVOPS_ENGINEER")


class TestReportDetails:
    def test_extraction_tab_shows_location_summary_and_jobs(self):
        at = run_app()
        at.sidebar.selectbox(key="example").select("resume_fullstack").run()
        assert not at.exception
        tables = [table.value.to_dict("records") for table in at.table]
        fields = {row["Field"]: row["Value"] for row in tables[0]}
        assert fields["Location"] == "Nevermore Academy, Jericho"
        assert fields["Current role"] == "Student and independent investigator"
        jobs = next(t for t in tables if t and "Role" in t[0])
        assert jobs[0]["Role"] == "Full Stack Developer" and jobs[0]["Company"] == "Raven Labs"

    def test_pasted_text_without_details_shows_placeholders(self):
        at = run_app()
        at.sidebar.radio(key="source").set_value(app.SOURCE_PASTE).run()
        assert not at.exception
        fields = {row["Field"]: row["Value"] for row in at.table[0].value.to_dict("records")}
        assert fields["Location"] == "(not found)"


class TestMarkdownList:
    def test_items_become_bullets(self):
        assert app.markdown_list(["One", "Two"]) == "- One\n- Two"

    def test_empty_list_shows_none(self):
        assert app.markdown_list([]) == "- (none)"

    def test_special_characters_are_shown_literally(self):
        bs = chr(92)
        assert app.markdown_list(["a_b $5 *x* [y]"]) == "- a" + bs + "_b " + bs + "$5 " + bs + "*x" + bs + "* " + bs + "[y" + bs + "]"
