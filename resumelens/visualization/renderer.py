"""Stage 4 — HTML5 and Markdown reports generated from a validated textX model.

``render_html`` fills ``data/templates/report_template.html``; ``render_markdown_report`` is the
alternative export for when no HTML output is needed (it does not depend on the template).

The HTML report follows the structure of the example in the assignment: a self-contained page
(embedded CSS, no scripts, no external resources) with the sections *Personal Information*,
*Education*, *Experience*, *Normalized Technical Skills* and *Qualification Evaluation*.
Every value is read from the model returned by ``parse_candidate_profile`` and escaped
before being inserted into ``data/templates/report_template.html``.
"""

import re
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


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------
_MD_SPECIALS: str = "\\`*[]<>|&"


def _md_line(value: Any) -> str:
    """Return ``value`` as one line of Markdown text that is displayed literally.

    Underscores inside a word (``NODE_JS``) are left as they are, because Markdown does not
    treat them as emphasis; a leading ``#``, ``+`` or ``-`` that would open a heading or a
    list is escaped.
    """
    text = " ".join(str(value).split())
    text = "".join("\\" + char if char in _MD_SPECIALS else char for char in text)
    text = re.sub(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])", r"\\_", text)
    return re.sub(r"^([#+\-])(?=[ #+\-]|$)", r"\\\1", text)


def _md_code(value: Any) -> str:
    """Return ``value`` as an inline code span that is safe inside a table cell."""
    text = " ".join(str(value).split()).replace("`", "'").replace("|", "\\|")
    return f"`{text}`"


def _md_link(url: Any) -> str:
    """Return ``url`` as an autolink, or as escaped text when it is not a plain http(s) URL."""
    text = str(url)
    plain = not any(char.isspace() or char in "<>" for char in text)
    if plain and text.lower().startswith(("http://", "https://")):
        return f"<{text}>"
    return _md_line(text)


def _md_quote(text: Any) -> str:
    """Return ``text`` as a block quote, one quoted line per line of the text."""
    lines = str(text).splitlines()
    return "\n".join(f"> {_md_line(line)}" if line.strip() else ">" for line in lines)


def _md_bullets(items: Sequence[str], empty_message: str) -> List[str]:
    return items if items else [f"_{empty_message}_"]


def render_markdown_report(model: Any) -> str:
    """Render a validated ``CandidateReport`` model as a Markdown report.

    It has the same sections as the HTML report (personal information, education,
    experience, normalized skills and qualification evaluation) and does not use the HTML
    template, so it works as the alternative export when HTML output is not needed. Values
    are escaped so that Markdown shows them literally.

    Args:
        model: The model returned by ``resumelens.grammar.parse_candidate_profile``.

    Returns:
        The Markdown document, ending with a newline.
    """
    personal = model.personal
    contact: List[str] = []
    if personal.email:
        contact.append(f"- **Email:** {_md_line(personal.email)}")
    if personal.phone:
        contact.append(f"- **Phone:** {_md_line(personal.phone)}")
    contact.extend(f"- **Link:** {_md_link(link)}" for link in (personal.links or []))

    education = [f"- {_md_line(e.description)}" for e in (model.education.entries or [])]
    experience = [f"- {_md_line(e.description)}" for e in (model.experience.entries or [])]

    skills = list(model.skills.skills or [])
    skill_lines = (
        [
            "| Skill | Category | Written as |",
            "| --- | --- | --- |",
            *(
                f"| {_md_code(s.canonical)} | {_md_code(s.category)} | {_md_line(s.raw)} |"
                for s in skills
            ),
        ]
        if skills
        else ["_No skills recognized._"]
    )

    evaluation: List[str] = []
    for result in model.evaluation.results or []:
        matched = ", ".join(_md_code(name) for name in (result.matched or [])) or "none"
        evaluation += [
            f"### {_md_line(_display_name(result.name))}",
            "",
            f"- **Qualification pattern:** {_md_line(result.verdict)}",
            f"- **Matched skills:** {matched}",
        ]
        if result.details and result.details.strip():
            evaluation += ["", _md_quote(result.details)]
        evaluation.append("")
    if not evaluation:
        evaluation = ["_No evaluation results._"]

    blocks = [
        f"# {_md_line(personal.name) or 'Unnamed candidate'}",
        "_Candidate profile generated by ResumeLens_",
        "## Personal Information\n\n"
        + "\n".join(_md_bullets(contact, "No contact data provided.")),
        "## Education\n\n" + "\n".join(_md_bullets(education, "No education entries.")),
        "## Experience\n\n" + "\n".join(_md_bullets(experience, "No experience entries.")),
        "## Normalized Technical Skills\n\n" + "\n".join(skill_lines),
        "## Qualification Evaluation\n\n" + "\n".join(evaluation).rstrip("\n"),
    ]
    return "\n\n".join(blocks) + "\n"


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
