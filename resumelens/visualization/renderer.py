"""Stage 4 — HTML5 report generated from a validated textX model.

The report follows the structure of the example in the assignment: a self-contained page
(embedded CSS, no scripts, no external resources) with the sections *Personal Information*,
*Education*, *Experience*, *Normalized Technical Skills* and *Qualification Evaluation*.
Every value is read from the model returned by ``parse_candidate_profile`` and escaped
before being inserted into ``data/templates/report_template.html``.
"""

from html import escape
from pathlib import Path
from string import Template
from typing import Any, Callable, Dict, List, Sequence

TEMPLATE_PATH: Path = (
    Path(__file__).resolve().parents[2] / "data" / "templates" / "report_template.html"
)

_PAD: str = " " * 8


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


def _line(markup: str, depth: int = 0) -> str:
    return f"{_PAD}{'    ' * depth}{markup}"


def _empty(message: str) -> str:
    return _line(f'<p class="empty">{_text(message)}</p>')


def _display_name(identifier: str) -> str:
    """Return a profile identifier as a title (``DEVOPS_ENGINEER`` -> ``DevOps Engineer``)."""
    special = {"DEVOPS": "DevOps"}
    words = identifier.split("_")
    return " ".join(special.get(word, word.capitalize()) for word in words)


def _field(label: str, value: str) -> str:
    return _line(f"<p><strong>{_text(label)}:</strong> {_text(value)}</p>")


def _render_personal(personal: Any) -> str:
    rows: List[str] = []
    if personal.email:
        rows.append(_field("Email", personal.email))
    if personal.phone:
        rows.append(_field("Phone", personal.phone))
    for link in personal.links:
        rows.append(
            _line(f'<p><strong>Link:</strong> <a href="{_text(link)}">{_text(link)}</a></p>')
        )
    return "\n".join(rows) if rows else _empty("No contact data provided.")


def _render_entries(entries: Sequence[Any], empty_message: str) -> str:
    if not entries:
        return _empty(empty_message)
    items = [_line(f"<li>{_text(entry.description)}</li>", 1) for entry in entries]
    return "\n".join([_line("<ul>"), *items, _line("</ul>")])


def _render_skills(skills: Sequence[Any]) -> str:
    chips = [
        _line(
            f'<span class="skill" title="written as: {_text(skill.raw)}">'
            f"{_text(skill.canonical)} <small>{_text(skill.category)}</small></span>",
            1,
        )
        for skill in skills
    ]
    return "\n".join([_line('<div class="skills">'), *chips, _line("</div>")])


def _render_result(result: Any) -> str:
    accepted = result.verdict == "ACCEPTED"
    css = "accepted" if accepted else "rejected"
    matched = ", ".join(result.matched) if result.matched else "none"
    lines = [
        _line('<div class="evaluation">'),
        _line(f"<h3>{_text(_display_name(result.name))}</h3>", 1),
        _line(
            f'<p><strong>Qualification pattern:</strong> '
            f'<span class="{css}">{_text(result.verdict)}</span></p>',
            1,
        ),
        _line(f"<p><strong>Matched skills:</strong> {_text(matched)}</p>", 1),
        _line(f"<p>{_text(result.details)}</p>", 1),
        _line("</div>"),
    ]
    return "\n".join(lines)


def _render_evaluation(results: Sequence[Any]) -> str:
    return "\n".join(_render_result(result) for result in results)


def render_html(model: Any) -> str:
    """Render a validated ``CandidateReport`` model as a self-contained HTML5 page.

    Args:
        model: The model returned by ``resumelens.grammar.parse_candidate_profile``.

    Returns:
        The HTML document, ending with a newline. Values are HTML-escaped.

    Raises:
        OSError: If the template file cannot be read.
    """
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    sections: Dict[str, Callable[[], str]] = {
        "personal": lambda: _render_personal(model.personal),
        "education": lambda: _render_entries(
            model.education.entries, "No education entries."
        ),
        "experience": lambda: _render_entries(
            model.experience.entries, "No experience entries."
        ),
        "skills": lambda: _render_skills(model.skills.skills),
        "evaluation": lambda: _render_evaluation(model.evaluation.results),
    }
    values = {key: build() for key, build in sections.items()}
    return template.substitute(name=_text(model.personal.name), **values)


def write_visualization(content: str, path: Path) -> Path:
    """Write ``content`` to ``path`` (UTF-8), creating missing parent directories.

    Returns:
        The path written.

    Raises:
        OSError: If the file cannot be written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target
