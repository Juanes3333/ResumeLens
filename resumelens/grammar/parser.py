"""Stage 4 — serialization of the pipeline data into the candidate DSL and its validation.

The DSL is defined by the textX grammar ``resume_grammar.tx``. This module:

* writes the output of the earlier stages (``CandidateInfo``, ``SkillRecord`` and
  ``EvaluationResult``) as a document of that language (``build_profile_source``);
* loads the metamodel with ``textx.metamodel_from_file`` (``load_metamodel``);
* instantiates and validates a document (``parse_candidate_profile``), which raises
  ``TextXSyntaxError`` on any lexical or syntactic violation (``is_valid_profile_source``
  is the boolean form of the same check).
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from textx import metamodel_from_file
from textx.exceptions import TextXSyntaxError

from resumelens.classification.classifier import ACCEPTED, REJECTED
from resumelens.core.models import CandidateInfo, EvaluationResult, SkillRecord

GRAMMAR_PATH: Path = Path(__file__).resolve().parent / "resume_grammar.tx"

_INDENT: str = "    "


def _quote(text: str) -> str:
    """Return ``text`` as a DSL string literal.

    textX only unescapes ``\\"``, so double quotes are escaped and backslashes are kept
    as they are (a text ending in a backslash yields a document rejected by the parser).
    """
    return '"' + text.replace('"', '\\"') + '"'


def _profile_identifier(profile_name: str) -> str:
    """Return the DSL identifier of a profile (``"Full Stack Developer"`` -> ``FULL_STACK_DEVELOPER``)."""
    return "_".join(profile_name.upper().split())


def _block(title: str, lines: Sequence[str]) -> str:
    body = "".join(f"{_INDENT * 2}{line}\n" for line in lines)
    return f"{_INDENT}{title} {{\n{body}{_INDENT}}}\n"


def build_profile_source(
    info: CandidateInfo,
    records: Sequence[SkillRecord],
    results: Sequence[EvaluationResult],
) -> str:
    """Serialize the pipeline data as a document of the candidate DSL.

    The text is not validated here: values that break the lexical rules of the grammar
    (an e-mail without ``@``, a skill with lower case letters, ...) or missing mandatory
    parts (no skills, not exactly the four profiles) are detected by
    ``parse_candidate_profile``.

    Args:
        info: Contact, education and experience data (Stage 1).
        records: Normalized skills (Stage 2).
        results: One evaluation per profile (Stage 3), in roadmap order.

    Returns:
        The source text, ending with a newline.
    """
    personal = [f"name: {_quote(info.name)}"]
    if info.email:
        personal.append(f"email: {info.email}")
    if info.phone:
        personal.append(f"phone: {info.phone}")
    personal.extend(f"link: {link}" for link in info.links)

    evaluation = []
    for result in results:
        verdict = ACCEPTED if result.is_accepted else REJECTED
        evaluation.append(f"profile {_profile_identifier(result.profile_name)}: {verdict}")
        evaluation.append(f"{_INDENT}matched [{', '.join(result.matched_sequence)}]")
        evaluation.append(f"{_INDENT}details {_quote(result.details)}")

    blocks = [
        _block("personal", personal),
        _block("education", [f"study {_quote(item)}" for item in info.education]),
        _block("experience", [f"job {_quote(item)}" for item in info.experience]),
        _block(
            "skills",
            [
                f"skill {r.canonical_name} category {r.category} raw {_quote(r.raw_name)}"
                for r in records
            ],
        ),
        _block("evaluation", evaluation),
    ]
    return "candidate {\n" + "".join(blocks) + "}\n"


@lru_cache(maxsize=1)
def load_metamodel() -> Any:
    """Load (once) the metamodel of ``resume_grammar.tx`` with ``metamodel_from_file``."""
    return metamodel_from_file(str(GRAMMAR_PATH))


def parse_candidate_profile(source: str) -> Any:
    """Instantiate the model of a DSL document, validating it against the grammar.

    Args:
        source: Text of the document (see ``build_profile_source``).

    Returns:
        The ``CandidateReport`` model: ``personal``, ``education``, ``experience``,
        ``skills`` and ``evaluation`` objects.

    Raises:
        TypeError: If ``source`` is not a string.
        TextXSyntaxError: If the text violates the lexical or syntactic rules of the grammar.
    """
    if not isinstance(source, str):
        raise TypeError("The DSL source must be a string.")
    return load_metamodel().model_from_str(source)


def is_valid_profile_source(source: str) -> bool:
    """Return whether ``source`` is a valid document of the language."""
    try:
        parse_candidate_profile(source)
    except TextXSyntaxError:
        return False
    return True
