"""Reading of resumes from disk."""

from pathlib import Path
from typing import Union


def read_resume_file(file_path: Union[str, Path]) -> str:
    """Read a resume as UTF-8 and return the text without NUL characters and with '\n' line breaks."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Resume file not found: {path}")
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    text = text.replace("\x00", "")
    return text.replace("\r\n", "\n").replace("\r", "\n")
