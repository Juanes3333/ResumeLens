"""Web interface of ResumeLens (Streamlit): ``streamlit run app.py``.

The page contains no pipeline logic. It reads a résumé (an example, an uploaded ``.txt`` file or
pasted text), runs the four stages with :func:`resumelens.cli.run_pipeline_text` and shows the
result of each stage in its own tab: extraction (regular expressions), normalization
(finite-state transducers), classification (finite automata) and the candidate language
(textX) with the HTML and Markdown reports.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
from pyformlang.finite_automaton import DeterministicFiniteAutomaton

from resumelens.classification import PROFILE_SPECS, profile_spec
from resumelens.classification.automata import build_automaton
from resumelens.cli import PipelineRun, run_pipeline_text
from resumelens.core.reader import decode_resume
from resumelens.normalization import PROFILES
from resumelens.visualization import render_html, render_markdown_report

ROOT: Path = Path(__file__).resolve().parent
EXAMPLES_DIR: Path = ROOT / "data" / "input_resumes"

SOURCE_EXAMPLE: str = "Example résumé"
SOURCE_UPLOAD: str = "Upload a .txt file"
SOURCE_PASTE: str = "Paste text"

#: Text offered in the "Paste text" box: the fragment of the assignment.
SAMPLE_TEXT: str = (
    "Wednesday Addams\n"
    "3 years of experience developing web applications.\n"
    "Technical Skills:\n"
    "JS, React.js, NodeJS, Postgres, Git.\n"
)


def example_resumes() -> Dict[str, Path]:
    """Return the synthetic résumés of ``data/input_resumes`` by name, sorted."""
    return {path.stem: path for path in sorted(EXAMPLES_DIR.glob("*.txt"))}


@st.cache_resource
def automaton_of(identifier: str) -> DeterministicFiniteAutomaton:
    """Return the (shared) automaton of a profile identifier. It must not be modified."""
    return build_automaton(profile_spec(identifier))


def profile_label(identifier: str) -> str:
    """Return the official name of a profile identifier (``DEVOPS_ENGINEER`` -> ``DevOps Engineer``)."""
    return PROFILE_SPECS[identifier].name


def read_input() -> Optional[Tuple[str, str]]:
    """Show the input widgets of the sidebar and return ``(label, text)``, or ``None``."""
    source = st.sidebar.radio(
        "Résumé source", [SOURCE_EXAMPLE, SOURCE_UPLOAD, SOURCE_PASTE], key="source"
    )
    if source == SOURCE_EXAMPLE:
        examples = example_resumes()
        if not examples:
            st.sidebar.warning("No example résumés were found.")
            return None
        name = st.sidebar.selectbox("Example", list(examples), key="example")
        return name, decode_resume(examples[name].read_bytes())
    if source == SOURCE_UPLOAD:
        uploaded = st.sidebar.file_uploader("Plain-text résumé", type=["txt"], key="upload")
        if uploaded is None:
            return None
        return uploaded.name, decode_resume(uploaded.getvalue())
    text = st.sidebar.text_area("Résumé text", value=SAMPLE_TEXT, height=260, key="pasted")
    return ("pasted text", text) if text.strip() else None


def show_verdicts(run: PipelineRun) -> None:
    """Show one verdict per profile, side by side."""
    columns = st.columns(len(run.report.results))
    for column, result in zip(columns, run.report.results):
        column.metric(result.profile_name, "ACCEPTED" if result.is_accepted else "REJECTED")


def markdown_list(items: List[str]) -> str:
    """Return ``items`` as a Markdown bullet list with the special characters escaped.

    An empty list gives ``- (none)``. The text of a résumé is shown literally: ``$`` would
    otherwise open a formula and ``_`` or ``*`` would format the text.
    """
    special = "\\`*_[]<>$~#|"

    def escape(text: str) -> str:
        return "".join("\\" + char if char in special else char for char in text)

    return "\n".join(f"- {escape(item)}" for item in items) if items else "- (none)"


def show_extraction(run: PipelineRun) -> None:
    """Stage 1: what the regular expressions found."""
    info = run.resume.candidate_info
    st.subheader("Stage 1 · Extraction with regular expressions")
    st.table(
        [
            {"Field": "Name", "Value": info.name or "(not found)"},
            {"Field": "Email", "Value": info.email or "(not found)"},
            {"Field": "Phone", "Value": info.phone or "(not found)"},
            {"Field": "Location", "Value": info.location or "(not found)"},
            {"Field": "Current role", "Value": info.current_role or "(not found)"},
            {"Field": "Links", "Value": ", ".join(info.links) or "(none)"},
        ]
    )
    st.markdown("**Profile summary** (shown in the report; it does not take part in the verdict)")
    st.markdown(markdown_list(info.summary))
    left, right = st.columns(2)
    left.markdown("**Education**")
    left.markdown(markdown_list(info.education))
    right.markdown("**Experience**")
    right.markdown(markdown_list(info.experience))
    if info.jobs:
        st.markdown("**Jobs** (role, company, period and bullets)")
        st.table(
            [
                {
                    "Role": job.role,
                    "Company": job.company,
                    "Period": job.period,
                    "Highlights": " | ".join(job.highlights) or "(none)",
                }
                for job in info.jobs
            ]
        )
    st.markdown("**Raw skills** (input of Stage 2, exactly as written)")
    st.code(", ".join(run.resume.raw_skills) or "(none)", language="text")
    if run.resume.detected_skills:
        st.markdown("**Technologies detected in the whole résumé** (informational)")
        st.table(
            [
                {"Type": kind, "Spellings": ", ".join(spellings)}
                for kind, spellings in run.resume.detected_skills.items()
            ]
        )


def show_normalization(run: PipelineRun, profile: str) -> None:
    """Stage 2: transducers and canonical order."""
    st.subheader("Stage 2 · Normalization with finite-state transducers")
    records = run.normalization.records
    if records:
        st.table(
            [
                {"Written as": r.raw_name, "Canonical name": r.canonical_name, "Category": r.category}
                for r in records
            ]
        )
    else:
        st.warning("No skill was recognized.")
    if run.normalization.unrecognized:
        st.markdown("**Unrecognized** (reported, never guessed): " + ", ".join(run.normalization.unrecognized))
    if run.normalization.duplicates:
        st.markdown("**Duplicates** (same canonical name as an earlier skill): " + ", ".join(run.normalization.duplicates))
    st.markdown(f"**Canonical order for {profile_label(profile)}**")
    st.code(", ".join(run.sequences[profile]) or "(empty)", language="text")


def transition_rows(automaton: DeterministicFiniteAutomaton) -> List[Dict[str, str]]:
    """Return the transition function grouped by (state, next state), one row per pair."""
    grouped: Dict[Tuple[str, str], List[str]] = {}
    for state, moves in automaton.to_dict().items():
        for symbol, target in moves.items():
            grouped.setdefault((str(state), str(target)), []).append(str(symbol))
    return [
        {"From": source, "To": target, "On": ", ".join(sorted(symbols))}
        for (source, target), symbols in sorted(grouped.items())
    ]


def show_classification(run: PipelineRun, profile: str) -> None:
    """Stage 3: verdict of each automaton and the formal definition of the selected one."""
    st.subheader("Stage 3 · Classification with finite automata")
    for result in run.report.results:
        label = f"{'ACCEPTED' if result.is_accepted else 'REJECTED'} · {result.profile_name}"
        with st.expander(label, expanded=resolve_selected(result.profile_name, profile)):
            st.code(result.details, language="text")
    spec = PROFILE_SPECS[profile]
    automaton = automaton_of(profile)
    st.markdown(f"**Automaton of {spec.name}**: M = (Q, Σ, δ, q0, F), deterministic (DFA)")
    st.table(
        [
            {"Stage": stage.name, "Required": "yes" if stage.required else "no", "Skills": ", ".join(stage.tokens)}
            for stage in spec.stages
        ]
    )
    st.markdown(
        f"|Q| = {len(automaton.states)} · |Σ| = {len(automaton.symbols)} · "
        f"q0 = {automaton.start_state} · F = {{{', '.join(sorted(str(s) for s in automaton.final_states))}}}"
    )
    with st.expander("Transition function δ"):
        st.table(transition_rows(automaton))


def resolve_selected(profile_name: str, profile: str) -> bool:
    """Return whether ``profile_name`` is the profile selected in the sidebar."""
    return PROFILE_SPECS[profile].name == profile_name


def show_language(run: PipelineRun) -> None:
    """Stage 4: the candidate DSL, its validation and the reports."""
    st.subheader("Stage 4 · Candidate language (textX) and report")
    if run.model is None:
        st.error(f"The DSL document is not valid: {run.dsl_error}")
        st.info("No report is generated for a document that violates the grammar.")
        st.code(run.source, language="text")
        return
    st.success(f"The DSL document is valid ({len(run.source.splitlines())} lines).")
    html = render_html(run.model)
    markdown = render_markdown_report(run.model)
    dsl_tab, html_tab, markdown_tab = st.tabs(["DSL document", "HTML report", "Markdown report"])
    with dsl_tab:
        st.code(run.source, language="text")
    with html_tab:
        # The page is generated by ``render_html``, which escapes every value and has no scripts.
        st.iframe(html, height=900)
        st.download_button("Download HTML", html, file_name="resumelens_report.html", mime="text/html")
    with markdown_tab:
        st.code(markdown, language="markdown")
        st.download_button("Download Markdown", markdown, file_name="resumelens_report.md", mime="text/markdown")


def main() -> None:
    """Draw the page."""
    st.set_page_config(page_title="ResumeLens", page_icon=":mag:", layout="wide")
    st.title("ResumeLens")
    st.caption(
        "Formal language-based résumé screening: regular expressions, finite-state transducers, "
        "finite automata and a context-free grammar. It checks qualification patterns; it does not rank candidates."
    )
    profile = st.sidebar.selectbox("Profile to detail", PROFILES, format_func=profile_label, key="profile")
    given = read_input()
    if given is None:
        st.info("Choose a résumé in the sidebar to run the pipeline.")
        return
    label, text = given
    run = run_pipeline_text(text, Path(label))
    st.markdown(f"**Résumé:** {label}")
    show_verdicts(run)
    extraction, normalization, classification, language = st.tabs(
        ["1 · Extraction", "2 · Normalization", "3 · Classification", "4 · DSL and report"]
    )
    with extraction:
        show_extraction(run)
    with normalization:
        show_normalization(run, profile)
    with classification:
        show_classification(run, profile)
    with language:
        show_language(run)


if __name__ == "__main__":  # Streamlit runs the script as __main__; tests can import the helpers.
    main()
