"""Lectura de currículums desde disco."""

from pathlib import Path
from typing import Union


def read_resume_file(file_path: Union[str, Path]) -> str:
    """Lee un CV en UTF-8 y retorna el texto sin nulos y con saltos '\n'."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de currículum: {path}")
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    text = text.replace("\x00", "")
    return text.replace("\r\n", "\n").replace("\r", "\n")
