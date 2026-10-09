# ResumeLens: Formal Language-Based Resume Screening

Integrative project of **Computación y Estructuras Discretas III (2026-2)**, Universidad Icesi.
Professor: Andrés Aristizábal.

**Members:** Juan Restrepo, Samuel Granda, Daniel Varela.

## Formal pipeline in 4 stages

1. **Regex** — extraction of fields (contact, education, experience, skills) from the raw text of the resume.
2. **FST** (finite-state transducers, `pyformlang`) — normalization of the skills to their canonical form and canonical ordering by profile.
3. **Finite automata** (`pyformlang`) — recognition of the qualification pattern of each profile (ACCEPTED / REJECTED).
4. **textX DSL** — context-free grammar that represents and validates the candidate's resulting profile (data, skills and accepted profiles), and its HTML/Markdown visualization.

## Structure

```
resumelens/
  core/  extraction/  normalization/  classification/  grammar/  visualization/
docs/  tests/  data/input_resumes/  data/templates/
```

## Environment setup

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Linux/macOS:          source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Authorized dependencies: `pyformlang`, `textx`, `pytest`, `pydot`.
