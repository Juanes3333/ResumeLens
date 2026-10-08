"""Fixtures compartidas de pytest para ResumeLens.

Cargan en memoria los currículums sintéticos de ``data/input_resumes/`` usando
``read_resume_file`` (contrato de la etapa de ingesta).
"""

from pathlib import Path
from typing import Dict

import pytest

from resumelens.core.models import RawResumeData
from resumelens.core.reader import read_resume_file

RESUMES_DIR = Path(__file__).resolve().parent.parent / "data" / "input_resumes"

# Alias lógico -> nombre de archivo.
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
    """Directorio con los CVs sintéticos."""
    return RESUMES_DIR


@pytest.fixture(scope="session")
def resume_paths(resumes_dir) -> Dict[str, Path]:
    """Mapa alias -> ruta de cada CV sintético."""
    return {alias: resumes_dir / name for alias, name in RESUME_FILES.items()}


@pytest.fixture(scope="session")
def resume_texts(resume_paths) -> Dict[str, str]:
    """Mapa alias -> texto completo del CV, cargado en memoria."""
    return {alias: read_resume_file(path) for alias, path in resume_paths.items()}


@pytest.fixture(scope="session")
def valid_resume_texts(resume_texts) -> Dict[str, str]:
    """Solo los CVs bien formados (fullstack, ml, devops, data)."""
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
    """Construye un ``RawResumeData`` a partir del alias de un CV."""

    def _make(alias: str) -> RawResumeData:
        return RawResumeData(raw_text=resume_texts[alias])

    return _make
