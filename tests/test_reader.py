"""Pruebas de la ingesta (`read_resume_file`) y de los modelos de dominio."""

from dataclasses import is_dataclass

import pytest

from resumelens.core.models import (
    CandidateInfo,
    EvaluationResult,
    RawResumeData,
    SkillRecord,
)
from resumelens.core.reader import read_resume_file

from tests.conftest import RESUME_FILES, VALID_ALIASES


@pytest.mark.parametrize("alias", list(RESUME_FILES))
def test_read_resume_file_reads_each_synthetic_file(resume_paths, alias):
    """Cada CV sintético se lee sin lanzar errores y retorna texto limpio."""
    text = read_resume_file(resume_paths[alias])
    assert isinstance(text, str)
    assert text.strip()
    assert "\r" not in text and "\x00" not in text


def test_read_resume_file_reads_all_files_without_errors(resume_paths):
    texts = [read_resume_file(p) for p in resume_paths.values()]
    assert len(texts) == len(RESUME_FILES) == 5


def test_fixtures_load_all_resumes_in_memory(resume_texts, valid_resume_texts):
    assert set(resume_texts) == set(RESUME_FILES)
    assert set(valid_resume_texts) == set(VALID_ALIASES)
    assert all(isinstance(t, str) and t for t in resume_texts.values())


def test_read_accepts_str_path(resume_paths):
    text = read_resume_file(str(resume_paths["fullstack"]))
    assert "WEDNESDAY ADDAMS" in text


@pytest.mark.parametrize("alias", VALID_ALIASES)
def test_valid_resumes_have_expected_sections(valid_resume_texts, alias):
    for header in ("Technical Skills:", "Education:", "Experience:"):
        assert header in valid_resume_texts[alias]


def test_invalid_resume_has_no_technical_skills(invalid_text):
    assert "Technical Skills:" not in invalid_text


def test_official_examples_literal_content(fullstack_text, ml_text):
    assert "WEDNESDAY ADDAMS" in fullstack_text
    assert "3 years of experience developing web applications." in fullstack_text
    assert "JS, React.js, NodeJS, Postgres, Git." in fullstack_text
    assert "Mary Jane Watson" in ml_text
    assert (
        "2 years of experience developing predictive models "
        "and data-processing pipelines."
    ) in ml_text
    assert "Python, Pandas, NumPy, Scikit-learn, TensorFlow, SQL, Git." in ml_text


def test_raw_resume_factory_wraps_text(raw_resume_factory, fullstack_text):
    raw = raw_resume_factory("fullstack")
    assert isinstance(raw, RawResumeData)
    assert raw.raw_text == fullstack_text
    assert raw.raw_skills == []


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="no_existe"):
        read_resume_file(tmp_path / "no_existe.txt")


def test_normalizes_newlines_and_nulls(tmp_path):
    f = tmp_path / "cv.txt"
    f.write_bytes(b"a\r\nb\rc\x00d\n")
    assert read_resume_file(f) == "a\nb\ncd\n"


def test_models_instantiation():
    info = CandidateInfo(name="Ana", email="a@b.co", links=["https://x.y"])
    assert info.phone == "" and info.education == [] and info.experience == []

    raw = RawResumeData(raw_text="cv", candidate_info=info, raw_skills=["Git"])
    assert raw.candidate_info is info and raw.raw_skills == ["Git"]
    assert RawResumeData(raw_text="x").candidate_info == CandidateInfo()

    skill = SkillRecord(raw_name="NodeJS", canonical_name="NODE_JS", category="backend")
    assert skill.category == "backend"

    res = EvaluationResult(profile_name="fullstack", is_accepted=True, matched_sequence=["JS"])
    assert res.is_accepted is True and res.details == ""
    assert all(
        is_dataclass(c) for c in (CandidateInfo, RawResumeData, SkillRecord, EvaluationResult)
    )


def test_default_lists_not_shared():
    a, b = CandidateInfo(), CandidateInfo()
    a.links.append("x")
    assert b.links == []
