# ResumeLens — Module Design

Software design document (deliverable 2a: *Design of modules — functions, inputs-outputs*).
It describes the architecture, the data flow between the four formal stages and the
input/output contracts of each module. All the modules described here are marked
**[implemented]** and exist in the repository.

## 1. Scope and principles

- ResumeLens **does not rank candidates or make hiring decisions**: it only evaluates whether
  the qualifications *explicitly* identified in a resume satisfy the formal patterns of a profile.
- The four profiles (Full Stack Developer, Machine Learning Engineer, DevOps Engineer,
  Data Engineer) are processed by **the same general solution**; only the *data* changes
  (transducer tables, canonical order, automaton).
- Each stage relies on a formal model seen in the course:

| Stage | Formal model | Tool | Package |
|---|---|---|---|
| 1. Extraction | Regular expressions | `re` | `resumelens/extraction` |
| 2. Normalization | Finite-state transducers (7-tuple) | `pyformlang.fst.FST` | `resumelens/normalization` |
| 3. Classification | Finite automata (5-tuple) | `pyformlang.finite_automaton` | `resumelens/classification` |
| 4. DSL | Context-free grammar (EBNF) | `textX` | `resumelens/grammar`, `resumelens/visualization` |

## 2. Repository structure

```
ResumeLens/
├── data/input_resumes/        # synthetic resumes (fullstack, ml, devops, data, invalid)
├── docs/                      # design documents (Markdown)
├── resumelens/
│   ├── core/                  # domain models and ingestion           [implemented]
│   │   ├── models.py
│   │   └── reader.py
│   ├── extraction/            # Stage 1 (regex)                       [implemented]
│   │   ├── patterns.py
│   │   └── extractor.py
│   ├── normalization/         # Stage 2 (FST + canonical ordering)    [implemented]
│   │   ├── transducers.py
│   │   ├── normalizer.py
│   │   └── sorter.py
│   ├── classification/        # Stage 3 (automata)                    [implemented]
│   │   ├── automata.py
│   │   └── classifier.py
│   ├── grammar/               # Stage 4 (textX grammar, .tx)          [implemented]
│   │   ├── resume_grammar.tx
│   │   └── parser.py
│   ├── visualization/         # HTML/Markdown output                  [implemented]
│   │   └── renderer.py
│   └── cli.py                 # pipeline orchestration and CLI        [implemented]
├── data/templates/            # report_template.html (HTML5 report)
├── main.py                    # command-line entry point
├── app.py                     # Streamlit web interface               [implemented]
└── tests/                     # pytest (conftest.py with fixtures)
```

## 3. Data flow

```mermaid
flowchart LR
    A[.txt file] -->|read_resume_file| B[str text]
    B -->|Stage 1: extraction| C[RawResumeData]
    C -->|raw_skills: List str| D[Stage 2: FST normalization]
    D -->|List SkillRecord| E[canonical order by profile]
    E -->|List str canonical names| F[Stage 3: automata per profile]
    F -->|List EvaluationResult| G[Stage 4: textX DSL]
    C -->|CandidateInfo| G
    G -->|validated model| H[HTML / Markdown]
```

Summary by stage:

1. **Extraction** — from the raw text it obtains the name, contact data, education, experience,
   the *skill strings* of the *Technical Skills* section exactly as the candidate wrote them
   (`JS`, `React.js`, `Postgres`…) and the technologies that the regex bank detects in the whole
   resume, grouped by type. It does not decide equivalences or profiles.
2. **Normalization** — each raw string goes through the composition of two FSTs: one that lowers
   the token to lower case character by character, and one per technology family that translates
   the whole word to its canonical form (`JS → js → JAVASCRIPT`, `NodeJS → nodejs → NODE_JS`).
   The result is then sorted by the slots (categories) of the profile (e.g. Full Stack: Frontend →
   Backend → Database → Version control), so that it does not depend on the order in which the
   candidate wrote the resume.
3. **Classification** — for each profile, a finite automaton accepts or rejects the sorted
   canonical sequence. Output: one `EvaluationResult` per profile.
4. **DSL** — the structured information is serialized to the candidate specification language,
   validated with the textX grammar (rejecting lexical or syntactic violations) and the
   visualization is generated.

## 4. Domain models [implemented] — `resumelens/core/models.py`

| Class | Fields | Use |
|---|---|---|
| `JobEntry` | `description: str`, `role: str`, `company: str`, `period: str`, `highlights: List[str]` | A job of the *Experience* section with its bullets (Stage 1) |
| `CandidateInfo` | `name: str`, `email: str`, `phone: str`, `links: List[str]`, `education: List[str]`, `experience: List[str]`, `location: str`, `current_role: str`, `summary: List[str]`, `jobs: List[JobEntry]` | Extracted personal data (Stage 1). `location`, `current_role`, `summary` (paragraphs) and `jobs` are shown in the report and never take part in a verdict |
| `RawResumeData` | `raw_text: str`, `candidate_info: CandidateInfo`, `raw_skills: List[str]`, `detected_skills: Dict[str, List[str]]` | Output of Stage 1 |
| `SkillRecord` | `raw_name: str`, `canonical_name: str`, `category: str` | Output of Stage 2 |
| `EvaluationResult` | `profile_name: str`, `is_accepted: bool`, `matched_sequence: List[str]`, `details: str` | Output of Stage 3 |

Categories (`SkillRecord.category`, `CATEGORY_*` constants of `normalizer.py`). Each one
corresponds to a bullet of the qualification list of a profile in the assignment:

| Category | Canonical names | Assignment bullet / profile |
|---|---|---|
| `web_language` | `JAVASCRIPT`, `TYPESCRIPT` | "JavaScript or TypeScript" (Full Stack) |
| `frontend` | `REACT`, `ANGULAR`, `VUE` | "React, Angular, or Vue" (Full Stack) |
| `backend` | `NODE_JS`, `DJANGO`, `SPRING_BOOT` | "Node.js, Django, Spring Boot" (Full Stack) |
| `api` | `REST_API` | "REST APIs" (Full Stack) |
| `database` | `SQL`, `NOSQL`, `POSTGRESQL`, `MYSQL`, `MONGODB`, … | "SQL or NoSQL databases" (Full Stack), "SQL" (ML) |
| `vcs` | `GIT` | "Git" (all) |
| `language` | `PYTHON`, `JAVA`, `GO`, `C_PLUS_PLUS`, … | "Python" (ML) |
| `data_library` | `PANDAS`, `NUMPY`, `MATPLOTLIB` | "Pandas or NumPy" (ML) |
| `ml_framework` | `SCIKIT_LEARN`, `TENSORFLOW`, `PYTORCH`, `KERAS` | "Scikit-learn", "TensorFlow, or PyTorch" (ML) |
| `ml_practice` | `ML_MODEL_DEVELOPMENT` | "Machine-learning model development" (ML) |
| `container`, `orchestration`, `iac`, `ci_cd`, `cloud` | `DOCKER`; `KUBERNETES`; `TERRAFORM`, `ANSIBLE`; `JENKINS`; `AWS`, `AZURE`, `GCP` | DevOps Engineer (team profile) |
| `data_processing`, `workflow` | `SPARK`; `AIRFLOW` | Data Engineer (team profile) |

## 5. Function contracts by module

Conventions: functions are **pure** (no global state or side effects) except
`read_resume_file` and the writing of visualizations; errors are signaled with typed
exceptions, never with sentinel values.

### 5.1 Ingestion — `resumelens/core/reader.py` [implemented]

| Function | Input | Output | Errors |
|---|---|---|---|
| `read_resume_file(file_path)` | `str \| Path` | `str`: UTF‑8 text, without `\x00`, `\n` line breaks | `FileNotFoundError` if the file does not exist |

### 5.2 Stage 1 — `resumelens/extraction/` [implemented]

Patterns compiled with `re.compile` in `patterns.py` (registry `PATTERNS`, skill bank
`SKILL_PATTERNS`); use of `match`, `search`, `finditer`, `split` and `sub`, named groups
`(?P<name>...)`, `re.MULTILINE` and `re.IGNORECASE`. The formalization of each pattern is in
`docs/formalization.md`, Section 1.

| Function | Input | Output | Patterns used |
|---|---|---|---|
| `split_sections(text)` | `str` | `Dict[str, str]` (lower-case title → body; `""` = preamble) | `SECTION_HEADER_PATTERN` |
| `extract_name(text)` | `str` | `str` (empty if none) | `NAME_PATTERN` on the first line |
| `extract_contact(text)` | `str` | `Dict[str, object]` with `email`, `phone`, `links`, `linkedin`, `github` | `EMAIL_`, `PHONE_`, `URL_`, `LINKEDIN_URL_`, `GITHUB_URL_PATTERN` |
| `extract_education(text)` | `str` | `List[str]`: lines of *Education* with a degree, institution or period | `DEGREE_`, `INSTITUTION_`, `DATE_RANGE_PATTERN` |
| `extract_experience(text)` | `str` | `List[str]`: years of experience and job entries | `YEARS_EXPERIENCE_`, `EXPERIENCE_ENTRY_PATTERN` |
| `extract_location(text)`, `extract_current_role(text)` | `str` | `str`: the value of the `Location:` / `Current role:` line (empty if none; *Contact* first) | `LOCATION_`, `CURRENT_ROLE_PATTERN` |
| `extract_summary(text)` | `str` | `List[str]`: paragraphs of the *Summary* section | blank-line split |
| `extract_jobs(text)` | `str` | `List[JobEntry]`: each job of *Experience* with its role, company, period and bullets | `EXPERIENCE_ENTRY_`, `HIGHLIGHT_PATTERN` |
| `extract_skills(text)` | `str` | `List[str]`: raw strings of *Technical Skills* (also `Skills`, `Technologies`, `Tech Stack`; the list may start on the title line, and `-`, `*`, `+` markers are dropped), in order and not normalized | `SKILL_SEPARATOR_PATTERN`, `SKILL_BULLET_PATTERN` |
| `extract_technologies(text)` | `str` | `Dict[str, List[str]]`: type → detected spellings, without repetitions | `SKILL_PATTERNS` (whole resume except *Contact* and URLs) |
| `extract_resume(text)` | `str` | `RawResumeData` | Orchestrates the previous ones; `raw_text` keeps the original |

Contract: on a resume without a skills section (`resume_invalid.txt`) it returns
`raw_skills == []` without raising an exception.

### 5.3 Stage 2 — `resumelens/normalization/` [implemented]

Each transducer is defined as M = (Q, Σ, Γ, δ, ω, q₀, F) with `pyformlang.fst.FST`, built
with `add_transitions`, `add_start_state` and `add_final_state` and evaluated with `translate`,
as in class. The normalization of a token is the composition of two transducers:

1. **T_case** (`build_case_folding_transducer`): a single state `q0`, initial and accepting,
   with one loop `c:lower(c)` for each character of the alphabet `INPUT_ALPHABET`. It reads the
   token character by character and rejects characters outside the alphabet.
2. **T_family** (`build_transducer(variants)`): *whole-word* input symbols (like
   `translate(['llor', 'ar'])` in the slides). Q = {q0} ∪ {f_C}, one transition
   `variant:CANONICAL` from `q0` to `f_C` for each spelling. There are 7 families in
   `FAMILY_VARIANTS`: web, ai, database, devops, vcs, language and data.

**`transducers.py`**

| Function | Input | Output | Description |
|---|---|---|---|
| `build_case_folding_transducer(alphabet)` | `Iterable[str]` (default `INPUT_ALPHABET`) | `FST` | T_case |
| `fold_case(token)` | `str` | `str \| None` | Applies T_case; `None` if the token is empty or has characters outside Σ |
| `build_transducer(variants)` | `Mapping[str, Iterable[str]]` | `FST` | T_family; `ValueError` if a spelling maps to two canonical names |
| `apply_transducer(fst, token)` | `FST`, `str` | `str \| None` | T_case and then `fst.translate([lower_case_token])`; `ValueError` if ambiguous |
| `build_<family>_transducer()` / `get_<family>_transducer()` | — | `FST` | Builds / returns the cached FST of each family |
| `normalize_<family>_skill(token)` | `str` | `str \| None` | Translates with a single family |

**`normalizer.py`**

| Function | Input | Output | Description |
|---|---|---|---|
| `normalize_skill(raw)` | `str` | `str \| None` | Tries the families in order; collapses inner whitespace |
| `normalize_skills(raw_skills)` | `List[str]` | `List[SkillRecord]` | Normalizes, assigns a category and removes duplicate canonical names |
| `normalize_with_report(raw_skills)` | `List[str]` | `NormalizationResult` | Also reports `unrecognized` and `duplicates` |

**`sorter.py`**

| Function | Input | Output | Description |
|---|---|---|---|
| `resolve_profile(profile)` | `str` | `str` (`FULL_STACK_DEVELOPER`, …) | Accepts `"Full Stack Developer"`; `UnknownProfileError` if it does not exist |
| `profile_slots(profile)` | `str` | `Tuple[str, ...]` | Slots (categories) of the profile, in order (`PROFILE_SLOTS`) |
| `belongs_to_profile(record, profile)` | `SkillRecord`, `str` | `bool` | Whether the record goes to the profile part (a slot of the profile, restricted by `SLOT_RESTRICTIONS`) |
| `sort_records_by_profile(records, profile)` | `List[SkillRecord]`, `str` | `List[SkillRecord]` | Canonical permutation of the records |
| `sort_by_profile(records, profile)` | `List[SkillRecord]`, `str` | `List[str]` | Canonical names in canonical order |

Slots by profile (`PROFILE_SLOTS`):

| Profile | Slots |
|---|---|
| `FULL_STACK_DEVELOPER` | `web_language` → `frontend` → `backend` → `database` → `api` → `vcs` |
| `MACHINE_LEARNING_ENGINEER` | `language` → `data_library` → `ml_framework` → `ml_practice` → `database` → `vcs` |
| `DEVOPS_ENGINEER` | `language` → `container` → `orchestration` → `iac` → `ci_cd` → `cloud` → `vcs` |
| `DATA_ENGINEER` | `language` → `data_processing` → `workflow` → `database` → `cloud` → `vcs` |

Ordering rule (total; it depends only on the *set* of skills):

1. **Profile part:** the skills whose category is a slot of the profile (and that the slot
   admits, see `SLOT_RESTRICTIONS` below), slot by slot; inside a slot, in lexicographic order
   of the canonical name.
2. **Rest:** the skills of other categories, and the languages that the `language` slot of the
   profile does not admit (noise for that profile), in lexicographic order of
   `(category, canonical name)`.

Examples from the assignment:

- Full Stack: `["Git", "NodeJS", "JS", "Postgres", "React.js"]` →
  `["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]`.
- ML: `PYTHON, PANDAS, TENSORFLOW, POSTGRESQL, GIT` keeps that order.
- ML (Mary Jane Watson): `Python, Pandas, NumPy, Scikit-learn, TensorFlow, SQL, Git` →
  `PYTHON, NUMPY, PANDAS, SCIKIT_LEARN, TENSORFLOW, SQL, GIT`.

**Contract of the sorter output that Stage 3 must respect.** A slot may hold zero, one or
several skills (Mary Jane has `NUMPY` and `PANDAS` in `data_library`), and noise may follow the
profile part. The diagram of the assignment reads one symbol per slot
(`q0 –PYTHON→ q1 –PANDAS|NUMPY→ q2 …`). Therefore each automaton must accept **one or more**
skills per mandatory slot, allow optional slots to be missing and tolerate trailing noise.
Otherwise the reference ML resume would be rejected.

The profile part must also contain **only** skills that the automaton reads in a stage. A slot
may therefore be restricted (`SLOT_RESTRICTIONS` in `sorter.py`): the `language` slot of ML,
DevOps and Data Engineer admits only the languages of the stage, and any other language
(`JAVA` for ML, `RUST` for all three) is noise placed after the profile part.
`belongs_to_profile(record, profile)` tells which part a record goes to, and `classifier.py`
checks at import time that the sorter and the automata agree for the four profiles.

### 5.4 Stage 3 — `resumelens/classification/` [implemented]

Each automaton is a deterministic finite automaton M = (Q, Σ, δ, q₀, F) built with
`pyformlang.finite_automaton.DeterministicFiniteAutomaton`. Σ is the set of canonical names of
Stage 2 (`KNOWN_SKILLS`). A profile is a sequence of **stages** (`Stage(name, tokens, required)`):
the candidate satisfies the profile when its canonical sequence has at least one skill of every
required stage, in order, followed by any known skill that is not part of the profile (noise).
The four profiles are built by the same function, `build_automaton(ProfileSpec)`.

**`automata.py`**

| Function / constant | Input | Output | Description |
|---|---|---|---|
| `Stage`, `ProfileSpec` | name, tokens, `required` / name, stages | frozen dataclasses | Declarative description of a profile; `ProfileSpec.alphabet` lists its skills |
| `FULL_STACK_PROFILE`, `ML_PROFILE`, `DEVOPS_PROFILE`, `DATA_PROFILE`, `ALL_PROFILES` | — | `ProfileSpec` / tuple | The two official profiles and the two defined by the team |
| `KNOWN_SKILLS`, `DATABASE_TOKENS`, `CLOUD_TOKENS` | — | `FrozenSet[str]` / tuples | Alphabet of the automata, derived from the transducer tables |
| `build_automaton(profile)` | `ProfileSpec` | `DeterministicFiniteAutomaton` | DFA with `len(stages) + 2` states (`q0 … qn` and `q_noise`); `ValueError` if the profile is not valid (no stages, no required stage, empty stage, a name in two stages) |
| `build_<profile>_automaton()` / `get_<profile>_automaton()` | — | DFA | Builds / returns the cached DFA (`full_stack`, `ml`, `devops`, `data`) |
| `accepts(automaton, tokens)` | DFA, `Iterable[str]` | `bool` | `automaton.accepts(list(tokens))`; the empty sequence is never accepted |
| `accepts_<profile>(tokens)` | `Iterable[str]` | `bool` | The same with the cached automaton of each profile |

**`classifier.py`**

| Function | Input | Output | Errors |
|---|---|---|---|
| `classify_sequence(sequence, profile)` | `Iterable[str]` (canonical names in profile order), `str` | `EvaluationResult` | `UnknownProfileError`; `TypeError` if the sequence is a single string or has a non-string item |
| `classify_records(records, profile)` | `Sequence[SkillRecord]`, `str` | `EvaluationResult` | `UnknownProfileError` |
| `classify_all(records)` | `Sequence[SkillRecord]` | `ClassificationReport` (one result per profile, in the order of `PROFILES`) | — |
| `ClassificationReport` | — | `results`, `accepted_profiles`, `rejected_profiles`, `result_for(profile)`, `verdicts()` | `KeyError` / `UnknownProfileError` in `result_for` |
| `profile_spec(profile)`, `verdict_of(result)` | `str` / `EvaluationResult` | `ProfileSpec` / `"ACCEPTED"` or `"REJECTED"` | `UnknownProfileError` |

The verdict is always the one of `pyformlang`'s `accepts`. `EvaluationResult.details` starts with
`ACCEPTED - <profile>` or `REJECTED - <profile>` and then gives the sequence read and the stages
satisfied, or the `Reason:` of the rejection (computed by replaying the sequence over the stages
with the same rule as the DFA, only to explain). `matched_sequence` holds the skills of the
sequence that belong to a stage of the profile. When `classifier.py` is imported it checks that
the sorter and the automata agree on which skills belong to each profile (Section 5.3).

Profiles: `FULL_STACK_DEVELOPER`, `MACHINE_LEARNING_ENGINEER`, `DEVOPS_ENGINEER`, `DATA_ENGINEER`.
A resume may be accepted by 0, 1 or several profiles.

### 5.5 Stage 4 — `resumelens/grammar/` and `resumelens/visualization/` [implemented]

The grammar `resume_grammar.tx` (textX, context-free) describes one `CandidateReport`: personal
data (with an optional location and current role), an optional profile summary, education and
experience entries (zero or more; an experience entry may also give its role, company, period and
highlights), skills (one or more) and the verdict of each of the four profiles, always in that
order. It is documented in EBNF in
`docs/formalization.md`, Section 4.

**`grammar/parser.py`**

| Function | Input | Output | Errors |
|---|---|---|---|
| `build_profile_source(info, records, results)` | `CandidateInfo`, `Sequence[SkillRecord]`, `Sequence[EvaluationResult]` | `str` in the DSL (not validated) | — |
| `load_metamodel()` | — | metamodel (`metamodel_from_file`, cached) | — |
| `parse_candidate_profile(source)` | `str` | validated textX model | `TextXSyntaxError` on a lexical or syntactic violation; `TypeError` if `source` is not a `str` |
| `is_valid_profile_source(source)` | `str` | `bool` | — |

**`visualization/renderer.py`**

| Function | Input | Output | Errors |
|---|---|---|---|
| `render_html(model)` | validated model | `str`: self-contained HTML5 page built from `data/templates/report_template.html`, with the sections of the example page of the assignment (personal information, profile summary, education, experience with role, company, period and bullets, normalized skills and qualification evaluation); every value is escaped | `OSError` if the template cannot be read |
| `render_markdown_report(model)` | validated model | `str`: Markdown report with the same sections, escaped | — |
| `write_visualization(content, path)` | `str`, `Path` | `Path` written (creates missing folders) | `OSError` |

### 5.6 Orchestration and interfaces [implemented]

**`resumelens/cli.py`** runs the four stages and is the command-line interface
(`python main.py --cv FILE [--profile NAME] [--output FILE.html|.md]`).

| Function | Input | Output | Errors |
|---|---|---|---|
| `run_pipeline(cv_path)` | `str \| Path` | `PipelineRun` (`resume`, `normalization`, `sequences`, `report`, `source`, `model`, `dsl_error`) | `FileNotFoundError`, `OSError`, `UnicodeDecodeError` |
| `run_pipeline_text(text, source)` | `str`, `Path` (label) | `PipelineRun` | — |
| `write_report(model, output)` | validated model, `Path` | `Path` written; format chosen by the extension (`.html`, `.htm`, `.md`, `.markdown`) | `ValueError` (extension), `OSError` |
| `format_console_report(run, profile, output, write_error)` | `PipelineRun`, … | `str` with the four stages and the final verdict | `UnknownProfileError` |
| `build_parser()` / `main(argv)` | — / `Sequence[str]` | `ArgumentParser` / exit status | exit `1` if the file cannot be read or the DSL document is invalid; `2` for invalid arguments |

A resume whose DSL document is not valid (for instance, without recognized skills) does not
raise: the run keeps the results of Stages 1 to 3 and reports the problem in `dsl_error`.

**`app.py`** is the web interface (Streamlit). It contains no pipeline logic: it calls
`run_pipeline_text` and the renderers and shows the result of each stage in a tab (extraction,
normalization, classification, DSL and report), with the HTML and Markdown reports available for
download. It is started with `streamlit run app.py`.

## 6. Formalization (reference)

- **Stage 1:** for each data type, the regex and the language it recognizes are documented.
- **Stage 2:** M = (Q, Σ, Γ, δ, ω, q₀, F), with a transducer diagram.
- **Stage 3:** M = (Q, Σ, δ, q₀, F), stating whether it is a DFA, NFA or ε‑NFA, with a transition diagram.
- **Stage 4:** G = (V, Σ, S, P) in EBNF.

The details are in `docs/formalization.md`, one section per stage (Section 1, regular
expressions; Section 2, transducers; Section 3, profile automata; Section 4, grammar).

## 7. Test design

### 7.1 Fixtures (`tests/conftest.py`)

| Fixture | Scope | Content |
|---|---|---|
| `resumes_dir` | session | `Path` to `data/input_resumes/` |
| `resume_paths` | session | alias → `Path` (`fullstack`, `ml`, `devops`, `data`, `invalid`) |
| `resume_texts` | session | alias → text loaded in memory with `read_resume_file` |
| `valid_resume_texts` | session | only the 4 well-formed resumes |
| `fullstack_text`, `ml_text`, `devops_text`, `data_text`, `invalid_text` | function | text of each resume |
| `raw_resume_factory` | function | `alias → RawResumeData(raw_text=...)` |

### 7.2 Scenarios

| Scenario | Resume | Expected result |
|---|---|---|
| Valid Full Stack | `resume_fullstack` | Skills `JS, React.js, NodeJS, Postgres, Git`; Full Stack accepted |
| Valid ML | `resume_ml` | `Python, Pandas, NumPy, Scikit-learn, TensorFlow, SQL, Git`; ML accepted |
| Valid DevOps | `resume_devops` | DevOps accepted |
| Valid Data | `resume_data` | Data Engineer accepted |
| Invalid resume | `resume_invalid` | No skills section; no profile accepted; the DSL rejects incomplete representations |
| Writing order | any | The sorted sequence does not depend on the original order |
| Report details | the four valid resumes | Location, current role, a two-paragraph summary and a job with bullets appear in the DSL document and in both reports; they never change a verdict |
| Layout of the skills section | text | `Technical Skills:` on its own line, with the list on the same line, without colon, with `-` / bullet markers or separated by `\|` gives the same raw skills |
| Language outside the profile | `Java, Python, Pandas, …` | Machine Learning is still accepted: `Java` is noise for that profile |
| Invalid DSL document | resume without recognized skills | `TextXSyntaxError`; no report is generated |
| End to end | the five resumes | File → stages 1–4 → HTML / Markdown report (CLI) and the same result in the web interface |
| Missing file | — | `FileNotFoundError` |

### 7.3 Current tests

| File | What it verifies |
|---|---|
| `tests/test_reader.py` | `read_resume_file` reads the five resumes, normalizes `\r\n`/`\r` and NULs, accepts `str` or `Path` and raises `FileNotFoundError`; the models are instantiated with independent lists |
| `tests/test_patterns.py` | Each pattern of `patterns.py` with strings in and out of its language, over the resumes and the invalid resume |
| `tests/test_extraction.py` | Extractor functions, token isolation, `extract_technologies` and full extraction of the resumes |
| `tests/test_normalization.py` | 7-tuple of T_case and of the 7 families, translations, rejections, categories, duplicates and the pipeline with Stage 1 |
| `tests/test_sorter.py` | Canonical order of the four profiles, independence from the input order, remaining part and languages outside a profile |
| `tests/test_classification.py` | Automata of the four profiles (structure, acceptance and rejection paths), classifier reports and the full path from the resumes |
| `tests/test_grammar_definition.py`, `tests/test_grammar.py` | The textX grammar, the serializer, the parser and the rejection of malformed documents |
| `tests/test_visualization.py` | HTML and Markdown reports, escaping and file writing |
| `tests/test_cli.py`, `tests/test_e2e_pipeline.py` | Arguments, console report, exit statuses and the whole pipeline from file to report |
| `tests/test_app.py` | The web interface, run without a browser with Streamlit's `AppTest` |
| `tests/test_environment.py` | The packages of the project can be imported |

## 8. Constraints

Only `re`, `pyformlang` and `textX` are used by the pipeline, plus `streamlit` for the web
interface (`app.py`), which only displays the results of the pipeline. No NLP/ML libraries,
other parser generators, graph libraries, databases or external web services are used.
