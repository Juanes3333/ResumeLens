from dataclasses import is_dataclass
from pathlib import Path

import pytest

from resumelens.core.models import (
    CandidateInfo,
    EvaluationResult,
    RawResumeData,
    SkillRecord,
)
from resumelens.core.reader import read_resume_file

RESUMES_DIR = Path(__file__).resolve().parent.parent / "data" / "input_resumes"
RESUME_NAMES = [
    "resume_fullstack.txt",
    "resume_ml.txt",
    "resume_devops.txt",
    "resume_data.txt",
    "resume_invalid.txt",
]
VALID_NAMES = RESUME_NAMES[:4]


@pytest.mark.parametrize("name", RESUME_NAMES)
def test_read_each_resume(name):
    text = read_resume_file(RESUMES_DIR / name)
    assert isinstance(text, str)
    assert text.strip()
    assert "\r" not in text and "\x00" not in text


def test_read_accepts_str_path():
    assert "WEDNESDAY ADDAMS" in read_resume_file(str(RESUMES_DIR / "resume_fullstack.txt"))


@pytest.mark.parametrize("name", VALID_NAMES)
def test_valid_resumes_have_technical_skills_header(name):
    text = read_resume_file(RESUMES_DIR / name)
    for header in ("Technical Skills:", "Education:", "Experience:"):
        assert header in text


def test_invalid_resume_has_no_technical_skills():
    assert "Technical Skills:" not in read_resume_file(RESUMES_DIR / "resume_invalid.txt")


def test_official_examples_literal_content():
    full = read_resume_file(RESUMES_DIR / "resume_fullstack.txt")
    assert "WEDNESDAY ADDAMS" in full
    assert "3 years of experience developing web applications." in full
    assert "JS, React.js, NodeJS, Postgres, Git." in full
    ml = read_resume_file(RESUMES_DIR / "resume_ml.txt")
    assert "Mary Jane Watson" in ml
    assert "2 years of experience developing predictive models and data-processing pipelines." in ml
    assert "Python, Pandas, NumPy, Scikit-learn, TensorFlow, SQL, Git." in ml


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

    skill = SkillRecord(raw_name="NodeJS", canonical_name="Node.js", category="backend")
    assert skill.category == "backend"

    res = EvaluationResult(profile_name="fullstack", is_accepted=True, matched_sequence=["JS"])
    assert res.is_accepted is True and res.details == ""
    assert all(is_dataclass(c) for c in (CandidateInfo, RawResumeData, SkillRecord, EvaluationResult))


def test_default_lists_not_shared():
    a, b = CandidateInfo(), CandidateInfo()
    a.links.append("x")
    assert b.links == []
