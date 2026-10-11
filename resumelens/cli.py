"""Command-line interface of ResumeLens: runs the four stages of the pipeline on one resume.

The stages follow the formal models of the project:

1. Extraction: the resume text is read (``core.reader``) and scanned with regular
   expressions (``extraction``).
2. Normalization: raw skills are translated to canonical names by finite-state
   transducers and put in the canonical order of every profile (``normalization``).
3. Classification: one deterministic finite automaton per profile accepts or rejects the
   canonical sequence (``classification``).
4. Language: the data is written in the candidate DSL, validated with the textX grammar
   (``grammar``) and, when requested, rendered as an HTML or Markdown report
   (``visualization``).

Usage::

    python main.py --cv data/input_resumes/resume_fullstack.txt
    python main.py --cv data/input_resumes/resume_ml.txt --output reports/ml.html
    python main.py --cv data/input_resumes/resume_data.txt --profile "Data Engineer" --output report.md

Exit status: ``0`` when the four stages finish and the requested report is written,
``1`` when the resume cannot be read, the DSL document is not valid (for instance, a
resume without recognized skills) or the report cannot be written, and ``2`` for invalid
command-line arguments.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from textx.exceptions import TextXSyntaxError

from resumelens.classification import ClassificationReport, classify_all
from resumelens.core.models import EvaluationResult, RawResumeData
from resumelens.core.reader import read_resume_file
from resumelens.extraction import extract_resume
from resumelens.grammar import build_profile_source, parse_candidate_profile
from resumelens.normalization import (
    PROFILES,
    NormalizationResult,
    UnknownProfileError,
    normalize_with_report,
    resolve_profile,
    sort_by_profile,
)
from resumelens.visualization import render_html, render_markdown_report, write_visualization

EXIT_OK: int = 0
EXIT_ERROR: int = 1

#: Report format of each supported output extension.
OUTPUT_RENDERERS: Dict[str, Callable[[Any], str]] = {
    ".html": render_html,
    ".htm": render_html,
    ".md": render_markdown_report,
    ".markdown": render_markdown_report,
}

_NOT_FOUND = "(not found)"
_INDENT = "  "


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
@dataclass
class PipelineRun:
    """Intermediate states and results of one run of the pipeline.

    Attributes:
        cv_path: Path of the resume that was processed.
        resume: Stage 1 output: contact data, sections and raw skills.
        normalization: Stage 2 output: normalized records and discarded tokens.
        sequences: Canonical sequence of each profile (identifier -> canonical names).
        report: Stage 3 output: the verdict of every profile.
        source: The resume written in the candidate DSL.
        model: The textX model of ``source``, or ``None`` if the DSL document is invalid.
        dsl_error: Description of the syntax error when ``model`` is ``None``.
    """

    cv_path: Path
    resume: RawResumeData
    normalization: NormalizationResult
    sequences: Dict[str, List[str]]
    report: ClassificationReport
    source: str
    model: Optional[Any] = None
    dsl_error: Optional[str] = None


def run_pipeline(cv_path: Path) -> PipelineRun:
    """Run the four stages on the resume stored in ``cv_path``.

    A resume whose DSL document violates the grammar (no recognized skills, for example)
    does not raise: the run keeps the results of stages 1 to 3 and reports the problem in
    ``dsl_error``.

    Raises:
        FileNotFoundError: If ``cv_path`` does not exist.
        OSError: If the file cannot be read.
        UnicodeDecodeError: If the file is not UTF-8 text.
    """
    path = Path(cv_path)
    return run_pipeline_text(read_resume_file(path), path)


def run_pipeline_text(text: str, source: Path = Path("<text>")) -> PipelineRun:
    """Run the four stages on the text of a resume (the same as :func:`run_pipeline`).

    It is the entry point for callers that do not have a file, such as the web interface.

    Args:
        text: Plain text of the resume.
        source: Label stored in ``PipelineRun.cv_path`` (the path or the name of the upload).
    """
    path = Path(source)
    resume = extract_resume(text)
    normalization = normalize_with_report(resume.raw_skills)
    sequences = {profile: sort_by_profile(normalization.records, profile) for profile in PROFILES}
    report = classify_all(normalization.records)
    source = build_profile_source(resume.candidate_info, normalization.records, report.results)
    run = PipelineRun(path, resume, normalization, sequences, report, source)
    try:
        run.model = parse_candidate_profile(source)
    except TextXSyntaxError as error:
        run.dsl_error = f"line {error.line}, column {error.col}: {error.message}"
    return run


def write_report(model: Any, output: Path) -> Path:
    """Render ``model`` in the format given by the extension of ``output`` and write it.

    Raises:
        ValueError: If the extension is not one of :data:`OUTPUT_RENDERERS`.
        OSError: If the file cannot be written.
    """
    path = Path(output)
    renderer = OUTPUT_RENDERERS.get(path.suffix.lower())
    if renderer is None:
        raise ValueError(_unsupported_extension_message(path))
    return write_visualization(renderer(model), path)


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------
def _or_missing(value: Any) -> str:
    return str(value) if value else _NOT_FOUND


def _join(items: Sequence[str]) -> str:
    return ", ".join(items) if items else "(none)"


def _reason(result: EvaluationResult) -> str:
    """Return the reason line of a rejection from the report of the automaton."""
    for line in result.details.splitlines():
        if line.startswith("Reason:"):
            return line[len("Reason:"):].strip()
    return "see details"


def _select(results: Sequence[EvaluationResult], profile: Optional[str]) -> List[EvaluationResult]:
    if profile is None:
        return list(results)
    return [r for r in results if resolve_profile(r.profile_name) == resolve_profile(profile)]


def _stage_1(run: PipelineRun) -> List[str]:
    info = run.resume.candidate_info
    return [
        "[Stage 1] Extraction (regular expressions)",
        f"{_INDENT}File        : {run.cv_path}",
        f"{_INDENT}Name        : {_or_missing(info.name)}",
        f"{_INDENT}Email       : {_or_missing(info.email)}",
        f"{_INDENT}Phone       : {_or_missing(info.phone)}",
        f"{_INDENT}Links       : {_join(info.links)}",
        f"{_INDENT}Education   : {len(info.education)} entries",
        f"{_INDENT}Experience  : {len(info.experience)} entries",
        f"{_INDENT}Raw skills  : {_join(run.resume.raw_skills)}",
    ]


def _stage_2(run: PipelineRun, profile: Optional[str]) -> List[str]:
    records = run.normalization.records
    width = max((len(r.raw_name) for r in records), default=0)
    name_width = max((len(r.canonical_name) for r in records), default=0)
    lines = ["[Stage 2] Normalization (finite-state transducers)"]
    for record in records:
        lines.append(
            f"{_INDENT}{record.raw_name.ljust(width)} -> {record.canonical_name.ljust(name_width)}"
            f"  ({record.category})"
        )
    if not records:
        lines.append(f"{_INDENT}(no recognized skills)")
    lines.append(f"{_INDENT}Unrecognized : {_join(run.normalization.unrecognized)}")
    lines.append(f"{_INDENT}Duplicates   : {_join(run.normalization.duplicates)}")
    lines.append(f"{_INDENT}Canonical order by profile:")
    selected = PROFILES if profile is None else (resolve_profile(profile),)
    for identifier in selected:
        lines.append(f"{_INDENT * 2}{identifier}: {_join(run.sequences[identifier])}")
    return lines


def _stage_3(run: PipelineRun, profile: Optional[str]) -> List[str]:
    results = _select(run.report.results, profile)
    width = max((len(r.profile_name) for r in results), default=0)
    lines = ["[Stage 3] Classification (finite automata)"]
    for result in results:
        verdict = "ACCEPTED" if result.is_accepted else "REJECTED"
        detail = (
            f"matched: {_join(result.matched_sequence)}"
            if result.is_accepted
            else f"reason: {_reason(result)}"
        )
        lines.append(f"{_INDENT}{result.profile_name.ljust(width)}  {verdict}  {detail}")
    if profile is not None:
        for result in results:
            lines.append(f"{_INDENT}Report of the automaton:")
            lines.extend(f"{_INDENT * 2}{line}" for line in result.details.splitlines())
    return lines


def _stage_4(run: PipelineRun, output: Optional[Path], write_error: Optional[str]) -> List[str]:
    lines = ["[Stage 4] Candidate language (textX) and report"]
    if run.model is None:
        lines.append(f"{_INDENT}DSL document : INVALID ({run.dsl_error})")
        lines.append(f"{_INDENT}Report       : not generated")
        return lines
    lines.append(f"{_INDENT}DSL document : valid ({len(run.source.splitlines())} lines)")
    if write_error is not None:
        lines.append(f"{_INDENT}Report       : not written ({write_error})")
    elif output is None:
        lines.append(f"{_INDENT}Report       : not requested (use --output)")
    else:
        lines.append(f"{_INDENT}Report       : written to {output}")
    return lines


def _final_verdict(run: PipelineRun, profile: Optional[str]) -> List[str]:
    results = _select(run.report.results, profile)
    accepted = [r.profile_name for r in results if r.is_accepted]
    rejected = [r.profile_name for r in results if not r.is_accepted]
    return [
        "Final verdict",
        f"{_INDENT}ACCEPTED : {_join(accepted)}",
        f"{_INDENT}REJECTED : {_join(rejected)}",
    ]


def format_console_report(
    run: PipelineRun,
    profile: Optional[str] = None,
    output: Optional[Path] = None,
    write_error: Optional[str] = None,
) -> str:
    """Format the intermediate states and the final verdicts of a run for the console.

    Args:
        run: The result of :func:`run_pipeline`.
        profile: If given, only this profile is detailed in stages 2 and 3 and in the
            final verdict (any name accepted by ``resolve_profile``).
        output: Path of the report that was written, if any.
        write_error: Why the requested report could not be written, if that happened.

    Returns:
        The text, ending with a newline.

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    if profile is not None:
        resolve_profile(profile)
    blocks = [
        ["ResumeLens - formal language-based resume screening"],
        _stage_1(run),
        _stage_2(run, profile),
        _stage_3(run, profile),
        _stage_4(run, output, write_error),
        _final_verdict(run, profile),
    ]
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"


# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
def _unsupported_extension_message(path: Path) -> str:
    supported = ", ".join(sorted(OUTPUT_RENDERERS))
    return f"unsupported report extension {path.suffix!r} in {str(path)!r}; use one of: {supported}"


def _output_argument(value: str) -> Path:
    path = Path(value)
    if path.suffix.lower() not in OUTPUT_RENDERERS:
        raise argparse.ArgumentTypeError(_unsupported_extension_message(path))
    return path


def _profile_argument(value: str) -> str:
    try:
        return resolve_profile(value)
    except UnknownProfileError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser of the command line."""
    parser = argparse.ArgumentParser(
        prog="resumelens",
        description=(
            "Formal language-based resume screening: regular expressions, finite-state "
            "transducers, finite automata and a textX domain-specific language."
        ),
    )
    parser.add_argument("--cv", required=True, type=Path, help="path of the plain-text resume")
    parser.add_argument(
        "--output",
        type=_output_argument,
        default=None,
        help="path of the report to write; .html and .htm give HTML, .md and .markdown give Markdown",
    )
    parser.add_argument(
        "--profile",
        type=_profile_argument,
        default=None,
        help=(
            "show only this profile in the console report "
            "(" + ", ".join(PROFILES) + "; 'Data Engineer' style names are accepted)"
        ),
    )
    return parser


def _configure_output_streams() -> None:
    """Make printing robust on consoles that cannot encode every character of a resume."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command line. Returns the exit status instead of exiting.

    Args:
        argv: Arguments without the program name; ``sys.argv[1:]`` when ``None``.

    Returns:
        :data:`EXIT_OK` or :data:`EXIT_ERROR` (invalid arguments make ``argparse`` exit
        with status 2).
    """
    args = build_parser().parse_args(argv)
    _configure_output_streams()

    try:
        run = run_pipeline(args.cv)
    except FileNotFoundError:
        print(f"error: resume file not found: {args.cv}", file=sys.stderr)
        return EXIT_ERROR
    except (OSError, UnicodeDecodeError) as error:
        print(f"error: cannot read {args.cv}: {error}", file=sys.stderr)
        return EXIT_ERROR

    written: Optional[Path] = None
    write_error: Optional[str] = None
    if run.model is not None and args.output is not None:
        try:
            written = write_report(run.model, args.output)
        except OSError as error:
            write_error = str(error)

    print(format_console_report(run, args.profile, written, write_error), end="")

    if run.model is None:
        print("error: the candidate DSL document is not valid; no report was generated.", file=sys.stderr)
        return EXIT_ERROR
    if write_error is not None:
        print(f"error: cannot write {args.output}: {write_error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK
