"""Shared pytest fixtures for ResumeLens.

They load the synthetic resumes of ``data/input_resumes/`` into memory using
``read_resume_file`` (contract of the ingestion stage).
"""

from pathlib import Path
from typing import Dict

import pytest

from resumelens.core.models import RawResumeData
from resumelens.core.reader import read_resume_file

RESUMES_DIR = Path(__file__).resolve().parent.parent / "data" / "input_resumes"

# Logical alias -> file name.
RESUME_FILES: Dict[str, str] = {
    "fullstack": "resume_fullstack.txt",
    "ml": "resume_ml.txt",
    "devops": "resume_devops.txt",
    "data": "resume_data.txt",
    "invalid": "resume_invalid.txt",
}
VALID_ALIASES = ("fullstack", "ml", "devops", "data")


@pytest.fixture(scope="session")
def resumes_dir() -> Path:
    """Directory with the synthetic resumes."""
    return RESUMES_DIR


@pytest.fixture(scope="session")
def resume_paths(resumes_dir) -> Dict[str, Path]:
    """Map alias -> path of each synthetic resume."""
    return {alias: resumes_dir / name for alias, name in RESUME_FILES.items()}


@pytest.fixture(scope="session")
def resume_texts(resume_paths) -> Dict[str, str]:
    """Map alias -> full resume text, loaded in memory."""
    return {alias: read_resume_file(path) for alias, path in resume_paths.items()}


@pytest.fixture(scope="session")
def valid_resume_texts(resume_texts) -> Dict[str, str]:
    """Only the well-formed resumes (fullstack, ml, devops, data)."""
    return {alias: resume_texts[alias] for alias in VALID_ALIASES}


@pytest.fixture
def fullstack_text(resume_texts) -> str:
    return resume_texts["fullstack"]


@pytest.fixture
def ml_text(resume_texts) -> str:
    return resume_texts["ml"]


@pytest.fixture
def devops_text(resume_texts) -> str:
    return resume_texts["devops"]


@pytest.fixture
def data_text(resume_texts) -> str:
    return resume_texts["data"]


@pytest.fixture
def invalid_text(resume_texts) -> str:
    return resume_texts["invalid"]


@pytest.fixture
def raw_resume_factory(resume_texts):
    """Build a ``RawResumeData`` from the alias of a resume."""

    def _make(alias: str) -> RawResumeData:
        return RawResumeData(raw_text=resume_texts[alias])

    return _make
