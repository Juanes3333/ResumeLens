# ResumeLens - Test Cases and Traceability Matrix

Test plan of the four stages of the pipeline (1 regular expressions, 2 finite-state transducers and canonical order, 3 finite automata, 4 candidate language with textX and visualization), of the ingestion that feeds them, of the command-line interface, of the end-to-end runs and of the web interface. Every test case (`TC-xx`) is tied to the functional requirement it verifies (`RF-xx`), to the `pytest` functions that implement it and to an acceptance criterion.

## 1. Introduction and scope

### 1.1 Validation strategy

The validation is **formal**: each stage is tested against the model that defines it in `docs/formalization.md`, not only against examples.

| Layer | What is checked | Stage |
|---|---|---|
| Language membership | Every regular expression, every spelling of a transducer, every sequence of an automaton and every document of the candidate language is tested with strings **inside** the language (positive cases) and **outside** it (negative cases, which must raise `TextXSyntaxError` in Stage 4). | 1, 2, 3, 4 |
| Boundaries | Empty input, one-character tokens, case, whitespace, punctuation, prefixes of valid words, symbols outside the alphabet, missing sections. | 1, 2, 3 |
| Formal structure | The 7-tuple M = (Q, Σ, Γ, δ, ω, q₀, F) of every transducer and the 5-tuple M = (Q, Σ, δ, q₀, F) of every automaton are read from the `pyformlang` object and compared with the definition: states, alphabets, transitions, initial and final states, determinism. | 2, 3 |
| Oracles | The automata are compared, over every short word, with independent oracles: a Python `re` regular expression and a `pyformlang` `Regex`. | 3 |
| Properties | Idempotence, determinism, independence from the order in which the skills were written, permutation of the sorter output, no mutation of the input. | 2, 3 |
| Round trip | The pipeline data written in the DSL and parsed back give the same data; the generated reports contain the values of the validated model, escaped. | 4 |
| Integration | The five synthetic resumes (`data/input_resumes/`) go through the four stages: each valid resume is accepted by its own profile only, produces a valid DSL document and a report, and the invalid resume is rejected by all the profiles and cannot be represented in the language. The same runs are made through the command line (as a function and as a subprocess) and through the web interface (Streamlit `AppTest`, without a browser). | 1-4, CLI, UI |

The system **does not rank candidates**: no test compares candidates; each test checks the verdict *accepted / rejected* of a profile or an intermediate result of a stage.

### 1.2 Test inventory

Tests are `pytest` functions. A function with `@pytest.mark.parametrize` runs once per parameter set, so the number of executed cases is larger than the number of functions.

| File | Functions | Subject |
|---|---|---|
| `tests/test_reader.py` | 14 | Ingestion (`read_resume_file`, `decode_resume`) and domain models |
| `tests/test_patterns.py` | 50 | Compiled regular expressions of `extraction/patterns.py` |
| `tests/test_extraction.py` | 66 | Extractor functions of `extraction/extractor.py` |
| `tests/test_normalization.py` | 119 | Transducers (`transducers.py`) and `SkillNormalizer` (`normalizer.py`) |
| `tests/test_sorter.py` | 81 | Canonical order (`sorter.py`) |
| `tests/test_classification.py` | 149 | Automata (`automata.py`) and classifier (`classifier.py`) |
| `tests/test_grammar_definition.py` | 34 | The textX grammar `resume_grammar.tx`: valid and invalid documents |
| `tests/test_grammar.py` | 54 | Parser, model, validation and serializer (`grammar/parser.py`) |
| `tests/test_visualization.py` | 52 | HTML and Markdown reports and their files (`visualization/renderer.py`) |
| `tests/test_cli.py` | 55 | Command line (`cli.py`, `main.py`) |
| `tests/test_e2e_pipeline.py` | 17 | The whole pipeline, from the files on disk to the report |
| `tests/test_app.py` | 20 | Web interface (`app.py`) |
| `tests/test_environment.py` | 1 | Every package of `resumelens` can be imported |
| **Total** | **712** | |

Shared fixtures are in `tests/conftest.py`: `resume_texts`, `valid_resume_texts`, `fullstack_text`, `ml_text`, `devops_text`, `data_text`, `invalid_text` and `raw_resume_factory`.

### 1.3 Notation

- **Type:** **P** positive (valid input, accepted or translated), **N** negative (invalid input, rejected or error), **E** edge case (boundary or special situation).
- **Tests:** `file::function` or `file::Class::function`, where `file` is the name of the test file without the `test_` prefix and the `.py` extension (`patterns`, `extraction`, `reader`, `normalization`, `sorter`, `classification`, `grammar_definition`, `grammar`, `visualization`, `cli`, `e2e_pipeline`, `app`, `environment`). A class alone, such as `normalization::TestWebTranslations`, stands for **all** the tests of that class.
- **Acceptance criterion:** a test case passes when all its tests pass.

### 1.4 How to run

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q                            # whole suite
python3 -m pytest tests/test_sorter.py -q       # one file
python3 -m pytest -k "TestWebTranslations" -q   # one class
```

The suite must finish with **0 failures and 0 errors**. `tests/test_app.py` needs `streamlit`, which is in `requirements.txt`; it does not open a browser.

## 2. Functional requirements

The requirements are derived from the function contracts of `docs/module_design.md` (Section 5) and from the statement of the project.

| RF | Requirement | Stage |
|---|---|---|
| RF-01 | The system reads a resume file as UTF-8 text, with `\n` line breaks and without NUL characters, and signals a missing file with `FileNotFoundError`. | Ingestion |
| RF-02 | The domain models (`CandidateInfo`, `RawResumeData`, `SkillRecord`, `EvaluationResult`) can be created without sharing default lists, and every package of `resumelens` can be imported. | Ingestion |
| RF-03 | Extract the contact data: email, phone (national and international formats) and links (LinkedIn, GitHub, others). | 1 |
| RF-04 | Extract the candidate name and split the resume into sections. | 1 |
| RF-05 | Extract the education entries (degree, institution, period). | 1 |
| RF-06 | Extract the experience (years of experience and job entries). | 1 |
| RF-07 | Isolate the raw skills of the *Technical Skills* section, in order, without normalizing them. | 1 |
| RF-08 | Detect technologies with the skill regex bank, isolating each token without capturing substrings or functional words; extract the whole resume in one call. | 1 |
| RF-09 | Translate the lexical variants of a skill to its canonical name with finite-state transducers (7-tuple), ignoring case and surrounding whitespace. | 2 |
| RF-10 | Reject the tokens that are not in the language of any transducer, including tokens with symbols outside the input alphabet, and reject invalid transducer tables. | 2 |
| RF-11 | Coordinate the transducers: one record per distinct canonical skill, in order of appearance, with category, original spelling and a report of the unrecognized tokens. | 2 |
| RF-12 | Sort the normalized skills in the canonical order of the selected profile, independently of the order in the resume. | 2 |
| RF-13 | Recognize each of the four profiles with a finite automaton (5-tuple): accept the complete sequences and reject the incomplete, out-of-order or foreign ones. | 3 |
| RF-14 | Tolerate alternatives inside a stage, optional stages and trailing skills outside the profile. | 3 |
| RF-15 | Produce a formal verdict (`ACCEPTED` / `REJECTED`) with a report, for one profile or for the four profiles, and expose it through the public interface of the package. | 3 |
| RF-16 | The result is deterministic and does not depend on the order, the case or the spelling variant with which the skills were written. | 1-3 |
| RF-17 | The candidate-profile language is a context-free grammar written in textX; a valid document (personal data, repeated education and experience entries, one or more skills, one verdict per profile) is instantiated as a model. | 4 |
| RF-18 | A document that violates a lexical or syntactic rule is rejected with `TextXSyntaxError` and a position; a source that is not a string raises `TypeError`. | 4 |
| RF-19 | The data of the pipeline are serialized as a document of the language that parses back to the same data. | 4 |
| RF-20 | A self-contained HTML5 report with every section of the candidate is generated from the validated model, with every value escaped. | 4 |
| RF-21 | The same report can be exported as Markdown, and the reports are written to disk (creating missing folders, in UTF-8). | 4 |
| RF-22 | The command line runs the four stages (`--cv`, `--profile`, `--output`), shows the intermediate states and signals errors with exit statuses (`0`, `1`, `2`). | CLI |
| RF-23 | The real resumes go from disk to the final report without manual steps, with a deterministic result; the invalid resume ends with an error and no report. | End to end |
| RF-24 | The web interface runs the pipeline on an example, an uploaded or a pasted resume and shows the result of each stage, the DSL document and the downloadable reports. | UI |
| RF-25 | Extract the details that the report shows and that never decide a verdict: location, current role, the paragraphs of the summary and, for each job, its role, company, period and bullets. | 1 |
| RF-26 | The candidate language carries those details as optional parts (a summary block, location, current role and a structured job) and rejects them when they are malformed or out of order. | 4 |
| RF-27 | The HTML and Markdown reports show those details in the structure of the example page of the assignment: personal information, profile summary, experience with role, company, period and bullets. | 4 |

## 3. Traceability matrix

Each requirement is traced to its test cases, to the files where they are implemented and to its acceptance criterion. *Functions* is the number of `pytest` functions that implement the requirement.

| RF | Test cases | Test files | Functions | Acceptance criterion |
|---|---|---|---|---|
| RF-01 | TC-01, TC-02, TC-03, TC-04, TC-05, TC-64 | `test_reader.py` | 12 | The five synthetic files are read with `str` and `Path`; a missing file raises `FileNotFoundError`; `\r\n`, `\r` and `\x00` are normalized, also when the text comes from bytes. |
| RF-02 | TC-06 | `test_reader.py`, `test_environment.py` | 3 | Models are created with independent default lists; the seven packages import without errors. |
| RF-03 | TC-07, TC-08, TC-09, TC-10, TC-11, TC-12 | `test_patterns.py`, `test_extraction.py` | 21 | Valid emails, phones and links are extracted exactly; malformed or look-alike strings give an empty value; the Contact section has priority. |
| RF-04 | TC-13, TC-14, TC-62, TC-63 | `test_patterns.py`, `test_extraction.py` | 19 | Names, including accented ones, and section headers (with the list on the same line, without colon, or with an alias) are recognized; a title inside a sentence is not a header; text without headers stays in the preamble. |
| RF-05 | TC-15, TC-16 | `test_patterns.py`, `test_extraction.py` | 12 | Degree, institution and period are recognized; lines that have none of them are dropped. |
| RF-06 | TC-17, TC-18 | `test_patterns.py`, `test_extraction.py` | 9 | Years of experience and job entries are recognized; bullets and education lines are not. |
| RF-07 | TC-05, TC-19, TC-20, TC-62, TC-63 | `test_reader.py`, `test_patterns.py`, `test_extraction.py` | 23 | `raw_skills` keeps order, case and symbols; separators and list markers never leak; the section may use other layouts; a resume without the section gives `[]`. |
| RF-08 | TC-21, TC-22, TC-23 | `test_patterns.py`, `test_extraction.py` | 29 | Every skill pattern matches its spellings and only them; `extract_resume` returns the expected data for the five resumes. |
| RF-09 | TC-24, TC-25, TC-27, TC-28, TC-34 | `test_normalization.py` | 62 | Every listed variant is translated to its canonical name; the transducers have the documented 7-tuple structure. |
| RF-10 | TC-26, TC-29 | `test_normalization.py` | 11 | Tokens outside the language or the alphabet have no translation; invalid tables raise `ValueError`. |
| RF-11 | TC-30, TC-31, TC-32, TC-33, TC-34 | `test_normalization.py` | 54 | Records are unique, ordered and categorized; unrecognized tokens are reported and never become records. |
| RF-12 | TC-35, TC-36, TC-37, TC-38, TC-39, TC-40, TC-41, TC-42, TC-57, TC-65, TC-68 | `test_sorter.py`, `test_classification.py` | 99 | The output is the canonical order of the profile for every permutation of the input; a language that the profile does not read is noise and goes after the profile part. |
| RF-13 | TC-43, TC-46, TC-47, TC-48, TC-50, TC-51, TC-52, TC-56, TC-59, TC-67, TC-68 | `test_classification.py` | 83 | Complete sequences are accepted, every rejection path is rejected and the automata match the formal definition and the independent oracles. |
| RF-14 | TC-44, TC-45, TC-49, TC-60, TC-65, TC-66 | `test_sorter.py`, `test_classification.py` | 21 | Optional stages may be missing, the alternatives of a stage are interchangeable and trailing noise, including languages outside the profile, is accepted. |
| RF-15 | TC-53, TC-54, TC-55, TC-56, TC-57, TC-58, TC-59 | `test_classification.py` | 52 | The verdict is the automaton's; the report states the satisfied stages or the reason for the rejection; errors are typed. |
| RF-16 | TC-23, TC-39, TC-42, TC-59, TC-60, TC-61, TC-96 | `test_extraction.py`, `test_sorter.py`, `test_classification.py`, `test_e2e_pipeline.py` | 28 | Shuffled, re-cased or re-spelled skills give the same verdicts; each resume is accepted by its own profile only; the report details never change a verdict. |
| RF-17 | TC-69, TC-72 | `test_grammar_definition.py`, `test_grammar.py` | 49 | The grammar loads; valid documents, with repeated elements and comments, are instantiated as a model; the real resumes are valid documents. |
| RF-18 | TC-70, TC-72, TC-93 | `test_grammar_definition.py`, `test_grammar.py` | 28 | Every lexical or syntactic violation raises `TextXSyntaxError` with its position; a resume without skills cannot be represented; malformed or misplaced details are rejected. |
| RF-19 | TC-71, TC-72 | `test_grammar.py`, `test_grammar_definition.py` | 19 | The serializer writes the documented layout and its output parses back to the same data. |
| RF-20 | TC-73, TC-74 | `test_visualization.py` | 20 | The HTML is a complete, balanced, self-contained HTML5 page with every section and value, escaped, also with missing data. |
| RF-21 | TC-75, TC-76, TC-77 | `test_visualization.py` | 23 | The Markdown report has the same content and escapes special characters; files are written in UTF-8, creating folders. |
| RF-22 | TC-78, TC-79, TC-80, TC-81, TC-82, TC-83 | `test_cli.py` | 55 | Arguments are validated; the console report shows each stage; exit statuses are `0`, `1` and `2`; `main.py` is a thin wrapper. |
| RF-23 | TC-84, TC-85, TC-86 | `test_e2e_pipeline.py` | 17 | Each resume goes from disk to the report with the expected verdicts and a deterministic result; the report has the sections of the example page; the invalid resume fails without a report. |
| RF-24 | TC-87, TC-88, TC-89, TC-97 | `test_app.py` | 20 | Every example gives the expected verdicts; pasted text with other layouts works; the invalid resume shows the error and no download; the helpers behave as documented; the extraction tab shows the report details. |
| RF-25 | TC-90, TC-91, TC-96 | `test_patterns.py`, `test_extraction.py`, `test_e2e_pipeline.py` | 16 | Location, current role, summary paragraphs and job bullets are extracted exactly; look-alike lines and resumes without them give empty values; they never change a verdict. |
| RF-26 | TC-92, TC-93 | `test_grammar.py` | 9 | The serializer writes the optional parts only when they exist; the model maps them; they round-trip; malformed or misplaced parts are rejected. |
| RF-27 | TC-94, TC-95, TC-96 | `test_visualization.py`, `test_e2e_pipeline.py` | 11 | Both reports show the details in the order of the example page, with every value escaped and a plain layout when a part is missing. |

The same matrix read the other way round (test case -> requirement):

| TC | Type | RF | Functions |
|---|---|---|---|
| TC-01 | P | RF-01 | 4 |
| TC-02 | P | RF-01 | 3 |
| TC-03 | N | RF-01 | 1 |
| TC-04 | E | RF-01 | 1 |
| TC-05 | E | RF-01, RF-07 | 1 |
| TC-06 | P | RF-02 | 3 |
| TC-07 | P | RF-03 | 5 |
| TC-08 | N | RF-03 | 2 |
| TC-09 | P | RF-03 | 4 |
| TC-10 | N | RF-03 | 2 |
| TC-11 | P | RF-03 | 4 |
| TC-12 | N | RF-03 | 4 |
| TC-13 | P | RF-04 | 6 |
| TC-14 | N | RF-04 | 3 |
| TC-15 | P | RF-05 | 7 |
| TC-16 | N | RF-05 | 5 |
| TC-17 | P | RF-06 | 5 |
| TC-18 | N | RF-06 | 4 |
| TC-19 | P | RF-07 | 7 |
| TC-20 | N | RF-07 | 5 |
| TC-21 | P | RF-08 | 15 |
| TC-22 | N | RF-08 | 8 |
| TC-23 | P | RF-08, RF-16 | 6 |
| TC-24 | P | RF-09 | 7 |
| TC-25 | P | RF-09 | 16 |
| TC-26 | N | RF-10 | 3 |
| TC-27 | P | RF-09 | 26 |
| TC-28 | E | RF-09 | 5 |
| TC-29 | N | RF-10 | 8 |
| TC-30 | P | RF-11 | 15 |
| TC-31 | P | RF-11 | 12 |
| TC-32 | N | RF-11 | 4 |
| TC-33 | E | RF-11 | 15 |
| TC-34 | P | RF-09, RF-11 | 8 |
| TC-35 | P | RF-12 | 14 |
| TC-36 | N | RF-12 | 7 |
| TC-37 | P | RF-12 | 5 |
| TC-38 | P | RF-12 | 9 |
| TC-39 | P | RF-12, RF-16 | 5 |
| TC-40 | E | RF-12 | 15 |
| TC-41 | E | RF-12 | 17 |
| TC-42 | P | RF-12, RF-16 | 6 |
| TC-43 | P | RF-13 | 9 |
| TC-44 | E | RF-14 | 5 |
| TC-45 | E | RF-14 | 2 |
| TC-46 | N | RF-13 | 13 |
| TC-47 | N | RF-13 | 9 |
| TC-48 | N | RF-13 | 6 |
| TC-49 | N | RF-14 | 5 |
| TC-50 | N | RF-13 | 4 |
| TC-51 | P | RF-13 | 26 |
| TC-52 | N | RF-13 | 10 |
| TC-53 | P | RF-15 | 7 |
| TC-54 | N | RF-15 | 11 |
| TC-55 | N | RF-15 | 7 |
| TC-56 | P | RF-13, RF-15 | 4 |
| TC-57 | P | RF-12, RF-15 | 17 |
| TC-58 | P | RF-15 | 3 |
| TC-59 | P | RF-13, RF-15, RF-16 | 3 |
| TC-60 | E | RF-14, RF-16 | 3 |
| TC-61 | P | RF-16 | 3 |
| TC-62 | P | RF-04, RF-07 | 6 |
| TC-63 | N | RF-04, RF-07 | 4 |
| TC-64 | P | RF-01 | 2 |
| TC-65 | E | RF-12, RF-14 | 3 |
| TC-66 | P | RF-14 | 3 |
| TC-67 | N | RF-13 | 1 |
| TC-68 | P | RF-12, RF-13 | 1 |
| TC-69 | P | RF-17 | 42 |
| TC-70 | N | RF-18 | 18 |
| TC-71 | P | RF-19 | 12 |
| TC-72 | P | RF-17, RF-18, RF-19 | 7 |
| TC-73 | P | RF-20 | 12 |
| TC-74 | E | RF-20 | 8 |
| TC-75 | P | RF-21 | 9 |
| TC-76 | E | RF-21 | 10 |
| TC-77 | E | RF-21 | 4 |
| TC-78 | P | RF-22 | 10 |
| TC-79 | P | RF-22 | 10 |
| TC-80 | P | RF-22 | 12 |
| TC-81 | P | RF-22 | 5 |
| TC-82 | E | RF-22 | 14 |
| TC-83 | P | RF-22 | 4 |
| TC-84 | P | RF-23 | 12 |
| TC-85 | N | RF-23 | 4 |
| TC-86 | P | RF-23 | 1 |
| TC-87 | P | RF-24 | 6 |
| TC-88 | E | RF-24 | 5 |
| TC-89 | P | RF-24 | 7 |
| TC-90 | P | RF-25 | 9 |
| TC-91 | N | RF-25 | 5 |
| TC-92 | P | RF-26 | 6 |
| TC-93 | N | RF-18, RF-26 | 3 |
| TC-94 | P | RF-27 | 5 |
| TC-95 | E | RF-27 | 4 |
| TC-96 | P | RF-16, RF-25, RF-27 | 2 |
| TC-97 | P | RF-24 | 2 |

## 4. Detailed test cases

### 4.1 Ingestion and models

Files: `tests/test_reader.py` and `tests/test_environment.py`.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-01 | P | RF-01 | Read each of the five synthetic resumes, with `str` and `Path`, and load them as fixtures. | The text is returned and is not empty; both path types are accepted. | `reader::test_read_resume_file_reads_each_synthetic_file`, `reader::test_read_resume_file_reads_all_files_without_errors`, `reader::test_fixtures_load_all_resumes_in_memory`, `reader::test_read_accepts_str_path` |
| TC-02 | P | RF-01 | The valid resumes have the sections of the format; the two official examples contain their literal content; `raw_resume_factory` wraps a text. | `Technical Skills:`, `Education:` and `Experience:` are present in each valid resume; the official name, experience sentence and skill line appear unchanged. | `reader::test_valid_resumes_have_expected_sections`, `reader::test_official_examples_literal_content`, `reader::test_raw_resume_factory_wraps_text` |
| TC-03 | N | RF-01 | Read a path that does not exist. | `FileNotFoundError`. | `reader::test_missing_file_raises` |
| TC-04 | E | RF-01 | A file with `\r\n`, `\r` and `\x00` characters. | The text has only `\n` and no NUL. | `reader::test_normalizes_newlines_and_nulls` |
| TC-05 | E | RF-01, RF-07 | The invalid resume has no *Technical Skills* section. | The text is read normally and does not contain the section header. | `reader::test_invalid_resume_has_no_technical_skills` |
| TC-06 | P | RF-02 | Create the models and import every package of `resumelens`. | Models are created and their default lists are independent; the seven packages import. | `reader::test_models_instantiation`, `reader::test_default_lists_not_shared`, `environment::test_module_importable` |

### 4.2 Stage 1 - Extraction with regular expressions

Files: `tests/test_patterns.py` (the compiled regular expressions of `patterns.py`) and `tests/test_extraction.py` (the extractor functions that use them). The formalization of each pattern is in `docs/formalization.md`, Section 1.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-07 | P | RF-03 | **Complex emails**: `juan.perez-2026@sub.domain.edu.co`, `a.b+tag@mail.example.co.uk`, `ana_95@icesi.edu.co`, `x@y.io`. | The email is extracted exactly and the `user` and `domain` groups are correct; a final sentence period is dropped; the Contact section has priority over other emails and, without it, the whole text is searched. | `patterns::test_email_matches`, `extraction::test_contact_extracts_standard_and_complex_emails`, `extraction::test_contact_email_drops_trailing_sentence_period`, `extraction::test_contact_section_has_priority_over_other_emails`, `extraction::test_contact_email_falls_back_to_whole_text` |
| TC-08 | N | RF-03 | **Malformed emails**: `juan.perez at mail`, `user@host`, `@domain.com`, `no email here`. | No match; the contact email is `""`. | `patterns::test_email_rejects`, `extraction::test_contact_rejects_malformed_emails` |
| TC-09 | P | RF-03 | **International and varied phones**: `+57 300 123 4567`, `+1 (555) 123-4567`, `(602) 888-9900`, `+1-800-555-0199`, `555.123.4567`, `3001234567`. | The whole number is extracted; the groups `country`, `area`, `prefix` and `line` are correct (`country` is `None` without a prefix); the match covers the entire number; without a Contact section the whole text is searched. | `patterns::test_phone_matches`, `patterns::test_phone_span_covers_whole_number`, `extraction::test_contact_extracts_international_and_varied_phones`, `extraction::test_contact_phone_falls_back_to_whole_text` |
| TC-10 | N | RF-03 | **Strings that look like phones**: `2019 - 2023`, `12345`, `30012345678`, and a year range inside the Education section. | No phone is reported. | `patterns::test_phone_rejects`, `extraction::test_contact_phone_ignores_year_ranges` |
| TC-11 | P | RF-03 | **Links**: LinkedIn, GitHub and portfolio URLs in one Contact section; the fixtures. | Links are returned in order of appearance; `linkedin` and `github` are filled by kind; every fixture has its expected contact data. | `patterns::test_url_patterns_on_synthetic_text`, `patterns::test_contact_on_fixtures`, `extraction::test_contact_extracts_linkedin_github_and_portfolio_in_order`, `extraction::test_contact_reports_linkedin_and_github_profiles` |
| TC-12 | N | RF-03 | **Links edge cases**: non-URLs; URLs followed by `.` or `,`; repeated URLs; text without contact data. | Non-URLs are rejected; trailing punctuation and duplicates are dropped; without data every field is empty (`""` or `[]`). | `patterns::test_url_rejects_non_urls`, `extraction::test_contact_links_drop_trailing_punctuation_and_duplicates`, `extraction::test_contact_without_data_returns_empty_values`, `extraction::test_contact_without_profiles_leaves_them_empty` |
| TC-13 | P | RF-04 | **Name and sections**: a first line with a name (also accented), headers in any case and header aliases. | The name is extracted; headers split the text into sections keyed by lower-case title and aliases are unified; every fixture has its expected headers. | `patterns::test_name_pattern_accepts`, `patterns::test_section_headers_on_fixtures`, `extraction::test_extract_name`, `extraction::test_extract_name_accepts_accented_names`, `extraction::test_split_sections_segments_text_and_unifies_aliases`, `extraction::test_split_sections_headers_are_case_insensitive` |
| TC-14 | N | RF-04 | **Lines that are not names or headers**; a colon after a word that is not a section title (`Email: a@b.co`); text without any header. | `NAME_PATTERN` rejects them; a colon after a word that is not a section title does not open a section; text without headers stays in the preamble. | `patterns::test_name_pattern_rejects`, `patterns::test_section_header_ignores_inline_colons`, `extraction::test_split_sections_without_headers_keeps_everything_in_preamble` |
| TC-15 | P | RF-05 | **Education**: `B.S. in Computer Science`, `M.S. in Data Science`, `Bachelor of Science in Software Engineering`, `MBA in Finance`, `Ph.D. in Mathematics, 2020`, `BSc in Physics`; institutions such as `Nevermore University` and `Universidad Icesi`; periods such as `2019 - 2023`, `Jan 2020 to Present`, `March 2018 - Dec. 2021`. | Level, field, institution, start and end are extracted; several education records are kept; the section stops at the next header. | `patterns::test_degree_matches`, `patterns::test_institution_matches`, `patterns::test_date_range_matches`, `patterns::test_education_entry_with_graduation_year`, `patterns::test_education_on_fixtures`, `extraction::test_education_returns_section_lines_until_next_header`, `extraction::test_education_supports_multiple_records` |
| TC-16 | N | RF-05 | **No education**: `looking for any job opportunity`, `in Computer Science`, `2023`, `year 3000 - 4000`; no *Education* section; lines without degree, institution or period; a line with only a period. | No match; the list is empty; unrecognized lines are dropped; a line with only a period is kept. | `patterns::test_degree_rejects`, `patterns::test_date_range_rejects`, `extraction::test_education_without_section_is_empty`, `extraction::test_education_drops_lines_without_degree_institution_or_period`, `extraction::test_education_keeps_a_line_with_only_a_period` |
| TC-17 | P | RF-06 | **Experience**: `3 years of experience developing web applications.`, `5+ years of professional experience`, `Data Analyst, Acme Corp (2020 - 2022)`, `Backend Developer at Globant (Jan 2021 - Present)`, `QA Engineer @ Rappi (2019 to 2021)`, `SRE \| Mercado Libre (2022 - 2024)`. | `years`, `plus`, `activity`, `role`, `company`, `start` and `end` are extracted; the `+` and the work-experience alias are accepted; every fixture has its expected experience. | `patterns::test_years_experience_matches`, `patterns::test_experience_entry_matches`, `patterns::test_experience_on_fixtures`, `extraction::test_experience_returns_years_and_job_entries`, `extraction::test_experience_accepts_plus_years_and_work_experience_alias` |
| TC-18 | N | RF-06 | **Not experience**: `- Built a dashboard (2023 - 2024)`, `Nevermore University (2019 - 2023)`, `Full Stack Developer, Raven Labs`, `years of experience`; bullets and education lines inside the section; no section. | No entry is reported; the list is empty without data. | `patterns::test_years_experience_rejects`, `patterns::test_experience_entry_rejects`, `extraction::test_experience_ignores_bullets_and_education_lines`, `extraction::test_experience_without_data_is_empty` |
| TC-19 | P | RF-07 | **Isolation of `raw_skills`**: `C++, .NET, Node.js, React.js, C#`; `JS, React.js, NodeJS, Postgres, Git.`; separators `,` `;` and newline; blank items; `TECHNICAL SKILLS:` and the `Skills:` alias; a section followed by `Experience:`. | Tokens keep their original case, order and symbols (`["C++", ".NET", "Node.js", "React.js", "C#"]`); empty items are dropped; the section ends at the next header and its text never enters a token. | `patterns::test_skill_separator_splits_on_comma_semicolon_and_newline`, `extraction::test_skills_keep_special_symbols_intact`, `extraction::test_skills_tolerate_adjacent_punctuation`, `extraction::test_skills_preserve_original_case_and_order`, `extraction::test_skills_header_is_case_insensitive_and_accepts_skills_alias`, `extraction::test_skills_stop_at_next_section`, `extraction::test_fixture_tokens_do_not_include_text_from_other_sections` |
| TC-20 | N | RF-07 | **No raw skills**: `Python,\nSQL; Git.`; a resume whose summary says `I know Python and Git.` but has no skills section; the invalid resume. | No separator or trailing period inside a token; `[]` and no exception without the section; no pattern matches the invalid resume and its extraction has empty fields. | `extraction::test_skills_never_leak_separators_or_trailing_periods`, `extraction::test_skills_without_section_is_empty`, `extraction::test_extract_resume_on_invalid_fixture_returns_empty_fields`, `extraction::test_invalid_resume_has_no_detected_technologies`, `patterns::test_invalid_resume_yields_no_matches` |
| TC-21 | P | RF-08 | **Skill regex bank**: languages, frameworks, ML libraries, databases, version control, DevOps/cloud, data tools, REST APIs, ML practice and SQL/NoSQL, in several spellings and cases. | Each pattern reports the `skill` group with the spelling found; every skill type is in the registry; the technologies of each fixture are detected without repetitions (ignoring case) and in bank order. | `patterns::test_all_patterns_are_compiled`, `patterns::test_programming_language_matches`, `patterns::test_framework_matches`, `patterns::test_ml_library_matches`, `patterns::test_database_matches`, `patterns::test_version_control_matches`, `patterns::test_devops_cloud_matches`, `patterns::test_new_skill_patterns_match`, `patterns::test_skill_patterns_registry_lists_every_skill_type`, `extraction::test_programming_language_pattern_isolates_symbol_tokens`, `extraction::test_framework_pattern_handles_dots_case_and_punctuation`, `extraction::test_skill_patterns_are_case_and_variant_tolerant`, `extraction::test_technologies_detected_on_fixtures`, `extraction::test_technologies_are_unique_ignoring_case_and_keep_first_spelling`, `extraction::test_technologies_are_reported_in_bank_order_by_type` |
| TC-22 | N | RF-08 | **Token isolation**: a substring such as `js` inside `Node.js`; functional words; a sentence with one skill; `SQL` inside another database name; short case-sensitive languages in free text; contact labels and URLs. | Only the skill is captured, never the surrounding text; `SQL` is not reported twice; dotted framework names are not split; contact labels and URLs are ignored. | `patterns::test_skill_patterns_respect_token_boundaries`, `patterns::test_new_skill_patterns_reject`, `patterns::test_sql_inside_another_database_name_is_not_reported_twice`, `patterns::test_case_sensitive_short_languages_ignore_free_text`, `extraction::test_skill_patterns_do_not_capture_functional_words_or_substrings`, `extraction::test_skill_patterns_isolate_only_the_skill_from_a_sentence`, `extraction::test_language_pattern_does_not_split_dotted_framework_names`, `extraction::test_technologies_ignore_contact_labels_and_urls` |
| TC-23 | P | RF-08, RF-16 | **Whole resume**: `extract_resume` on the five fixtures and on a synthetic text. | `RawResumeData` has the expected name, contact, education, experience and `raw_skills`; the individual extractors agree with `extract_resume`; every raw skill is recognized by a skill pattern; the detected technologies are kept; the result is deterministic. | `extraction::test_extract_resume_on_fixtures_matches_expected_data`, `extraction::test_individual_extractors_agree_with_extract_resume`, `extraction::test_fixture_skill_tokens_are_each_recognized_by_a_skill_pattern`, `extraction::test_extract_resume_on_synthetic_text`, `extraction::test_extract_resume_keeps_detected_technologies`, `extraction::test_extract_resume_is_deterministic` |

### 4.3 Stage 2 - Normalization with transducers

File: `tests/test_normalization.py`. The formal definition of each transducer is in `docs/formalization.md`, Section 2.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-24 | P | RF-09 | **Web transducer**: `JS`, `Javascript`, `TS`, `React.js`, `ReactJS`, `NodeJS`, `Node.js`, `AngularJS`, `Vue.js`, `Spring Boot`, `Django`, `REST APIs`, `RESTful API`; any case (`jAvAsCrIpT`, `REACT.JS`); surrounding whitespace. | Each variant is translated to its canonical name (`JS` -> `JAVASCRIPT`, `React.js` -> `REACT`, `NodeJS` -> `NODE_JS`); a variant that is a prefix of another (`react`, `react.js`) is not ambiguous; the translation is idempotent. | `normalization::TestWebTranslations` |
| TC-25 | P | RF-09 | **AI / data libraries, databases and Cloud / DevOps transducers**: `sklearn`, `Postgres`, `K8s` and every other listed variant. | `sklearn` -> `SCIKIT_LEARN`, `Postgres` -> `POSTGRESQL`, `K8s` -> `KUBERNETES`; `SQL` is a prefix of other databases but stays unambiguous; the expected table covers every canonical name. | `normalization::TestAiTransducer`, `normalization::TestDatabaseTransducer`, `normalization::TestDevopsTransducer`, `normalization::TestFamilyTables` |
| TC-26 | N | RF-10 | **Tokens outside the language or the alphabet**: `""`, `"   "`, `Java`, `Jav`, `JavaScripts`, `React.`, `Spring  Boot` (two spaces), `Spring-Boot`, `react$`, `<EOS>`, `REST API s`; tokens of another family (`Pandas`, `Docker`, `Git`). | No translation (`None`): prefixes, extensions, wrong spacing and symbols outside the alphabet are rejected; a rejection does not break later translations. | `normalization::TestWebRejections` |
| TC-27 | P | RF-09 | **7-tuple M = (Q, Sigma, Gamma, delta, omega, q0, F)** of `T_case` and of the seven family transducers, read from the `pyformlang` object. | One initial state; the states are `q0` plus one final state per canonical name; Gamma is the set of canonical names; Sigma is the set of lower-case spellings and is inside the alphabet of `T_case`; delta is deterministic and every transition leaves `q0`; final states have no outgoing transitions; `T_case` has one state, initial and final, with one loop per character writing its lower case; a whole-word symbol is translated as in the slides. | `normalization::TestWebTransducerStructure`, `normalization::TestAllTransducersStructure`, `normalization::TestCaseFoldingTransducer` |
| TC-28 | E | RF-09 | **Construction of transducers**: fresh builds, shared cached instances and the seven families together. | Fresh builds are equivalent; shared instances are cached and reused by the default families; the tables do not overlap, every spelling is accepted by exactly its own family and the canonical names are unique across families. | `normalization::TestFreshBuildsAndCaching`, `normalization::TestFamiliesAreDisjoint` |
| TC-29 | N | RF-10 | **Invalid tables**: a spelling that belongs to two canonical names (also ignoring case), an empty spelling, an empty canonical name, an empty table, an ambiguous translation. | `ValueError` for each invalid table; an empty table accepts nothing; a repeated spelling of the same canonical name is allowed. | `normalization::TestBuildTransducer` |
| TC-30 | P | RF-11 | **One token through the normalizer**: any family, any case, extra whitespace; categories; `to_record`. | The canonical name and its category are returned; unknown tokens and prefixes of a language are `None`; surrounding whitespace is cleaned; every known spelling has a category; the record keeps the cleaned original spelling in `raw_name`. | `normalization::TestNormalizeSingleSkill`, `normalization::TestCategories`, `normalization::TestToRecord` |
| TC-31 | P | RF-11 | **A list of raw skills**: the project example `Git, NodeJS, JS, Postgres, React.js`; equivalent spellings; exact repetitions; blank tokens; empty input; any iterable. | One record per canonical name in order of appearance with `raw_name` and category; the first spelling is kept and the repeated ones are reported as duplicates; blank tokens are ignored; the input is not modified; the same input gives the same output. | `normalization::TestNormalizeList::test_project_example_keeps_order_of_appearance`, `normalization::TestNormalizeList::test_records_carry_raw_name_and_category`, `normalization::TestNormalizeList::test_equivalent_spellings_collapse_into_the_first_one`, `normalization::TestNormalizeList::test_exact_repetition_is_a_duplicate`, `normalization::TestNormalizeList::test_blank_tokens_are_ignored_everywhere`, `normalization::TestNormalizeList::test_empty_input`, `normalization::TestNormalizeList::test_accepts_any_iterable`, `normalization::TestNormalizeList::test_input_list_is_not_modified`, `normalization::TestNormalizeList::test_normalize_skills_returns_only_the_records`, `normalization::TestNormalizeList::test_same_input_gives_same_output`, `normalization::TestNormalizationResult` |
| TC-32 | N | RF-11 | **Unrecognized tokens**: unknown technologies and `Python and Git` (documented Stage 1 limitation: two skills in one token). | They are reported once (ignoring case) in cleaned form and never become records. | `normalization::TestNormalizeList::test_unrecognized_tokens_are_reported_and_never_become_records`, `normalization::TestNormalizeList::test_unrecognized_tokens_are_deduplicated_ignoring_case`, `normalization::TestNormalizeList::test_unrecognized_tokens_are_reported_in_cleaned_form`, `normalization::TestNormalizeList::test_python_and_git_in_one_token_is_unrecognized` |
| TC-33 | E | RF-11 | **Custom families and default normalizer**: no families, two families with the same canonical name, a family without category, the shared default instance and the module-level functions. | No families recognizes nothing; a duplicated canonical name or an empty category raises `ValueError`; the default normalizer is cached and its functions agree with a fresh normalizer. | `normalization::TestCustomFamilies`, `normalization::TestDefaultNormalizer` |
| TC-34 | P | RF-09, RF-11 | **Integration with Stage 1**: the raw skills extracted from the synthetic resumes. | Every valid resume is fully normalized; the Full Stack resume gives the project example; `SQL` is detected in Stage 1 and normalized in Stage 2; the invalid resume gives no records. | `normalization::TestWebTransducerOnExtractedSkills`, `normalization::TestNormalizationOfExtractedSkills` |

### 4.4 Stage 2 - Canonical order

File: `tests/test_sorter.py`.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-35 | P | RF-12 | **Profiles and their slots**: the four profiles, their slot lists and the resolution of names (`Full Stack Developer`, `full-stack developer`, `FULL_STACK_DEVELOPER`, extra spaces). | Four profiles in the order of the project; every slot is a known category without repetitions; version control is always the last slot; every accepted spelling resolves to the profile identifier. | `sorter::TestProfileDefinitions`, `sorter::TestResolveProfile::test_accepted_spellings`, `sorter::TestResolveProfile::test_identifiers_resolve_to_themselves`, `sorter::TestResolveProfile::test_profile_slots_accepts_display_names` |
| TC-36 | N | RF-12 | **Unknown profile names**: `""`, `"   "`, `Backend Developer`, `Full Stack`, `Data Scientist`, `ML Engineer`. | `UnknownProfileError` (a `ValueError`) whose message names the profile and the valid ones; also raised by the sorting functions, even with an empty list. | `sorter::TestResolveProfile::test_unknown_names_are_rejected`, `sorter::TestResolveProfile::test_error_names_the_profile_and_the_valid_ones`, `sorter::TestResolveProfile::test_unknown_profile_error_is_a_value_error`, `sorter::TestUnknownProfile` |
| TC-37 | P | RF-12 | **Official example**: `Git, NodeJS, JS, Postgres, React.js` for Full Stack. | `JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT` (language -> frontend -> backend -> database -> version control); the original spellings stay in the records. | `sorter::TestOfficialExample` |
| TC-38 | P | RF-12 | **Order inside a slot**: data libraries, ML frameworks, web languages, frontend and backend frameworks, databases, cloud providers and infrastructure-as-code tools. | The names of a slot are in alphabetical order whatever the input order (`NUMPY` before `PANDAS`). | `sorter::TestOrderInsideSlot` |
| TC-39 | P | RF-12, RF-16 | **Independence from the input order**: every permutation of five raw tokens and of seven records, for the four profiles; reversed input; spelling variants; case and spacing. | Every permutation gives the same output. | `sorter::TestOrderIndependence` |
| TC-40 | E | RF-12 | **Duplicated elements and missing categories**: repeated spellings, empty input, a single skill, profiles without database, frontend framework, version control, orchestration or cloud. | The normalizer removes duplicates before the sorter and the sorter keeps the records it receives; unrecognized tokens never reach it; a missing slot is skipped without placeholders and does not alter the order of the other slots. | `sorter::TestDuplicates`, `sorter::TestMissingCategories` |
| TC-41 | E | RF-12 | **Skills outside the profile and general properties**: noise after the profile part; unknown categories; permutation, idempotence, determinism and no mutation of the input. | The profile part is always a prefix; noise is sorted by category and name; the output is a new list that is a permutation of the input; sorting twice changes nothing. | `sorter::TestRemainingPart`, `sorter::TestProperties` |
| TC-42 | P | RF-12, RF-16 | **Synthetic resumes against the four profiles**: Stage 1 -> Stage 2 -> sorter. | Each resume gives the expected sequence for each of the four profiles; a resume without skills gives `[]`; reversed skills give the same order. | `sorter::TestSyntheticResumes` |

### 4.5 Stage 3 - Automata of the four profiles

File: `tests/test_classification.py`. The automata read **canonical** names. The stages of each profile (`classification/automata.py`) are:

| Profile | Stages (required: **R**, optional: **O**) |
|---|---|
| Full Stack Developer | R `web_language` -> R `frontend_framework` -> R `backend_framework` -> R `database` -> O `api` -> R `version_control` |
| Machine Learning Engineer | R `base_language` -> R `data_library` -> R `ml_framework` -> O `ml_practice` -> R `database` -> R `version_control` |
| DevOps Engineer | R `language` -> R `container` -> R `orchestration` -> R `infrastructure_as_code` -> O `ci_cd` -> O `cloud` -> R `version_control` |
| Data Engineer | R `language` -> R `data_processing` -> R `workflow` -> R `database` -> O `cloud` -> R `version_control` |

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-43 | P | RF-13 | **Complete sequences of the four profiles**, e.g. `JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT` (Full Stack), `PYTHON, PANDAS, NUMPY, SCIKIT_LEARN, TENSORFLOW, SQL, GIT` (ML), `PYTHON, DOCKER, KUBERNETES, TERRAFORM, GIT` (DevOps), `PYTHON, SPARK, AIRFLOW, POSTGRESQL, GIT` (Data). | Accepted. Also accepted: every choice of one token per stage, all the tokens of a stage together and repeated tokens inside a stage; the shortest accepted sequence has one skill per required stage. | `classification::TestFullStackProfile::test_accepts_valid_sequences`, `classification::TestMlProfile::test_accepts_valid_sequences`, `classification::TestDevopsProfile::test_accepts_valid_sequences`, `classification::TestDataEngineerProfile::test_accepts_valid_sequences`, `classification::TestAcceptancePathsOfAllProfiles::test_canonical_sequences_are_accepted`, `classification::TestAcceptancePathsOfAllProfiles::test_every_choice_of_stage_tokens_is_accepted`, `classification::TestAcceptancePathsOfAllProfiles::test_all_tokens_of_a_stage_together_are_accepted`, `classification::TestAcceptancePathsOfAllProfiles::test_repeated_tokens_inside_a_stage_are_accepted`, `classification::TestAcceptancePathsOfAllProfiles::test_shortest_accepted_sequence_has_one_skill_per_required_stage` |
| TC-44 | E | RF-14 | **Optional stages and alternatives**: Full Stack with `NOSQL` and `REST_API`; ML with `ML_MODEL_DEVELOPMENT`; DevOps without `ci_cd` and `cloud`; Data without `cloud`; equivalent tokens inside one stage. | Accepted with or without the optional stages; the alternatives of a stage are interchangeable. | `classification::TestOptionalStagesAndNoise::test_full_stack_accepts_nosql_and_optional_rest_api`, `classification::TestOptionalStagesAndNoise::test_ml_accepts_optional_model_development_stage`, `classification::TestDevopsProfile::test_ci_cd_and_cloud_are_optional`, `classification::TestDevopsProfile::test_equivalent_alternatives_inside_a_stage`, `classification::TestDataEngineerProfile::test_cloud_is_optional` |
| TC-45 | E | RF-14 | **Noise after the profile part**: known skills that do not belong to the profile written after the last stage. | Accepted: the automaton reads them in its noise state. | `classification::TestOptionalStagesAndNoise::test_noise_after_the_profile_part_is_accepted`, `classification::TestAcceptancePathsOfAllProfiles::test_known_skills_outside_the_profile_may_follow_the_profile_part` |
| TC-46 | N | RF-13 | **Incomplete sequences**: the empty sequence; a required stage missing (each one in turn); every proper prefix; one skill of any stage; version control alone or with a database. | Rejected. | `classification::TestFullStackProfile::test_rejects_empty_sequence`, `classification::TestMlProfile::test_rejects_empty_sequence`, `classification::TestDevopsProfile::test_rejects_empty_sequence`, `classification::TestDataEngineerProfile::test_rejects_empty_sequence`, `classification::TestFullStackProfile::test_rejects_sequences_with_a_missing_stage`, `classification::TestMlProfile::test_rejects_sequences_with_a_missing_stage`, `classification::TestDevopsProfile::test_rejects_sequences_with_a_missing_required_stage`, `classification::TestDataEngineerProfile::test_rejects_sequences_with_a_missing_required_stage`, `classification::TestRejectionPathsOfAllProfiles::test_empty_sequence`, `classification::TestRejectionPathsOfAllProfiles::test_incomplete_sequences_missing_each_required_stage`, `classification::TestRejectionPathsOfAllProfiles::test_every_proper_prefix_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_a_single_skill_of_any_stage_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_version_control_alone_or_with_a_database_is_rejected` |
| TC-47 | N | RF-13 | **Stages out of order**: two adjacent stages swapped; reversed sequence; going back to an earlier stage; a trailing skill of an earlier stage; optional stages out of order. | Rejected: the stages must be read in the order of the profile. | `classification::TestFullStackProfile::test_rejects_stages_out_of_order`, `classification::TestMlProfile::test_rejects_stages_out_of_order`, `classification::TestDevopsProfile::test_rejects_stages_out_of_order`, `classification::TestDataEngineerProfile::test_rejects_stages_out_of_order`, `classification::TestRejectionPathsOfAllProfiles::test_swapping_two_adjacent_stages_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_reversed_sequences_are_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_returning_to_an_earlier_stage_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_a_trailing_skill_of_an_earlier_stage_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_optional_stages_out_of_order_are_rejected` |
| TC-48 | N | RF-13 | **Foreign and non-canonical tokens**: `COBOL`, `UNKNOWN`, the raw spellings `JS`, `Git`, `git`, `react`, `NODE JS`, `NODE-JS`, the empty string and a blank string, anywhere in a valid sequence. | Rejected: tokens are compared exactly and the raw spellings are not canonical names. | `classification::TestFullStackProfile::test_rejects_foreign_or_non_canonical_tokens`, `classification::TestMlProfile::test_rejects_foreign_or_non_canonical_tokens`, `classification::TestRejectionPathsOfAllProfiles::test_foreign_tokens_anywhere_are_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_a_sequence_made_only_of_foreign_tokens_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_tokens_are_compared_exactly`, `classification::TestRejectionPathsOfAllProfiles::test_raw_spellings_are_not_canonical_names` |
| TC-49 | N | RF-14 | **Noise in the wrong place**: a known skill outside the profile that replaces a required stage or comes before the profile part; a profile skill after skills outside the profile. | Rejected: noise is only tolerated after the profile part and never replaces a required stage. | `classification::TestOptionalStagesAndNoise::test_noise_does_not_replace_a_missing_stage`, `classification::TestOptionalStagesAndNoise::test_profile_skill_after_noise_is_rejected`, `classification::TestRejectionPathsOfAllProfiles::test_a_known_skill_outside_the_profile_cannot_replace_a_required_stage`, `classification::TestRejectionPathsOfAllProfiles::test_skills_outside_the_profile_cannot_come_before_it`, `classification::TestRejectionPathsOfAllProfiles::test_a_profile_skill_after_skills_outside_the_profile_is_rejected` |
| TC-50 | N | RF-13 | **Profiles are distinct**: the accepted sequences of one profile against the automata of the other three. | Rejected by the other profiles; no two profile languages are equivalent; a rejection leaves the shared automaton usable. | `classification::TestProfilesAreDistinct`, `classification::TestRejectionPathsOfAllProfiles::test_canonical_sequences_of_one_profile_are_rejected_by_the_others`, `classification::TestAutomataStructure::test_no_two_profile_languages_are_equivalent`, `classification::TestRejectionPathsOfAllProfiles::test_rejection_leaves_the_shared_automaton_usable` |
| TC-51 | P | RF-13 | **5-tuple M = (Q, Sigma, delta, q0, F)** of the four automata, read from the `pyformlang` object, and the specification of the profiles. | Deterministic automaton; states are one per stage plus the initial and the noise state; one initial state that does not accept; the documented accepting states, transitions (stage and noise) and number of transitions; the alphabet is every canonical name of Stage 2; every state is reachable; the language is not empty; it is equivalent to the regular expression of the stages and the minimal automaton is not larger; fresh builds are equivalent and independent; shared instances are cached; the profile specifications are immutable and their stages are pairwise disjoint. | `classification::TestAutomataStructure`, `classification::TestAutomatonObjects`, `classification::TestProfileSpecifications` |
| TC-52 | N | RF-13 | **Invalid profile specifications** given to `build_automaton`: no name, no stages, no required stage, a stage without tokens, an empty token, a token in two stages. | `ValueError`; a duplicate token inside a stage is harmless; a single-stage profile and a custom profile with an optional stage in the middle are built; the result agrees with Python `re` over every word of a small profile. | `classification::TestBuildAutomatonValidation` |

### 4.6 Stage 3 - Classifier

File: `tests/test_classification.py`. `classify_sequence`, `classify_records` and `classify_all` are in `classification/classifier.py`.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-53 | P | RF-15 | `classify_sequence` with a sequence that the profile accepts. | `EvaluationResult` with the official profile name, `is_accepted = True`, the skills of the profile in `matched_sequence` and a report that starts with `ACCEPTED - <profile>`, lists the satisfied stages, the optional stages used and the skills outside the profile; any iterable is accepted and the input is not modified. | `classification::TestClassifySequenceAccepted` |
| TC-54 | N | RF-15 | `classify_sequence` with a sequence that the profile rejects: empty, too short, missing stage, out of order, going back, foreign token, raw spelling, early noise, profile skill after noise. | `is_accepted = False` and a report that starts with `REJECTED - <profile>` and gives the reason; every proper prefix of a valid sequence gets a reason. | `classification::TestClassifySequenceRejected` |
| TC-55 | N | RF-15 | **Errors**: an unknown profile, a single string instead of a list, items that are not strings; equivalent forms of the profile name. | `UnknownProfileError` (a `ValueError`) and `TypeError`; every form of the profile name gives the same result; `profile_spec` and `verdict_of` behave as documented. | `classification::TestClassifySequenceErrors` |
| TC-56 | P | RF-13, RF-15 | **Oracles**: the verdict of the classifier, of the automaton and of an independent Python `re` expression over all the short words; `matched_sequence`. | The three verdicts coincide; `matched_sequence` only holds skills of the profile. | `classification::TestClassifierAgreesWithTheAutomata`, `classification::TestAutomataStructure::test_equivalent_to_the_regular_expression_of_the_stages`, `classification::TestBuildAutomatonValidation::test_exhaustive_agreement_with_python_re_on_a_small_profile` |
| TC-57 | P | RF-12, RF-15 | `classify_records` and `classify_all` with the `SkillRecord` list of the normalizer; candidates that fit several profiles or none (e.g. `Git` alone, `Cobol, Excel`). | The records are sorted for each profile before the automaton reads them; one result per profile in the order of the sorter; accepted and rejected profiles partition the four profiles; a candidate can be accepted by 0, 1 or several profiles; no skills means no profile; `result_for` accepts every name form and raises for an unknown or missing profile. | `classification::TestClassifyRecords`, `classification::TestClassifyAll` |
| TC-58 | P | RF-15 | Public interface of the package. | Every name in `__all__` is importable; the main entry points are re-exported; the profiles of the sorter and of the automata match. | `classification::TestPackageInterface` |

### 4.7 End to end: resume text -> Stage 1 -> Stage 2 -> Stage 3

File: `tests/test_classification.py`, class `TestEndToEndOnSyntheticResumes`.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-59 | P | RF-13, RF-15, RF-16 | The five synthetic resumes through the whole pipeline. | Each valid resume is accepted by its own profile only (Wednesday Addams: Full Stack; Mary Jane Watson: ML; Peter Parker: DevOps; Gwen Stacy: Data Engineer); the invalid resume is rejected by the four profiles because it has no skills; the reports of the rejected profiles explain why. | `classification::TestEndToEndOnSyntheticResumes::test_each_resume_is_accepted_by_its_profile_only`, `classification::TestEndToEndOnSyntheticResumes::test_reports_of_the_rejected_profiles_explain_why`, `classification::TestEndToEndOnSyntheticResumes::test_invalid_resume_is_rejected_because_it_has_no_skills` |
| TC-60 | E | RF-14, RF-16 | Modified resumes: all the skills of a required stage removed; one alternative of a stage removed; extra skills added (`Docker`, `Cobol`, `Excel`). | Removing every skill of a required stage rejects the candidate; losing one of several alternatives does not; extra skills do not change the verdict. | `classification::TestEndToEndOnSyntheticResumes::test_removing_all_the_skills_of_a_required_stage_rejects_the_candidate`, `classification::TestEndToEndOnSyntheticResumes::test_a_stage_with_alternatives_survives_the_loss_of_one_of_them`, `classification::TestEndToEndOnSyntheticResumes::test_extra_skills_do_not_change_the_verdict_of_the_fullstack_resume` |
| TC-61 | P | RF-16 | Shuffled skills, spelling variants and different case; candidates that fit several profiles. | The verdicts do not change with the order in which the skills were written, with the case or with the spelling variant. | `classification::TestEndToEndOnSyntheticResumes::test_the_order_in_which_skills_are_written_does_not_matter`, `classification::TestEndToEndOnSyntheticResumes::test_spelling_variants_and_case_give_the_same_verdicts`, `classification::TestEndToEndOnSyntheticResumes::test_multi_profile_candidates_do_not_depend_on_the_order_of_skills` |

### 4.8 Layouts of the skills section, bytes and languages outside a profile (Stages 1-3)

Files: `tests/test_patterns.py`, `tests/test_extraction.py`, `tests/test_reader.py`, `tests/test_sorter.py` and `tests/test_classification.py`. These cases cover the requirements that the first version of the plan left too narrow: the *Technical Skills* section may be written in other layouts, and a candidate may list languages that a profile does not read.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-62 | P | RF-04, RF-07 | **Other layouts of the section**: `Technical Skills:` with the list on the same line, without colon, `Skills:`, `Technologies:`, `Tech Stack:`; items separated by `\|` or bullet dots; one item per line with `-`, `*`, `+` or a bullet dot; the aliases `Professional Experience` and `Contact Information`. | Every layout gives the five raw skills of the assignment (`JS`, `React.js`, `NodeJS`, `Postgres`, `Git`); inline content stops at the next section; the aliases are unified. | `patterns::test_section_header_accepts_inline_content_and_colonless_titles`, `patterns::test_skill_bullet_pattern_matches_list_markers`, `extraction::test_skills_accept_other_layouts_of_the_section`, `extraction::test_skills_inline_content_stops_at_next_section`, `extraction::test_aliases_of_experience_and_contact_headers`, `extraction::test_extract_resume_reads_skills_of_an_inline_header` |
| TC-63 | N | RF-04, RF-07 | **Titles inside a sentence and markers that are not markers**: `Skills are important`, `Experience with Python`, `My technical skills`; `C++`, `.NET`, `Scikit-learn`, `-Python`. | A title without colon is a header only if it is the whole line; a marker needs a space after it, so these tokens are not changed and hyphens stay inside tokens. | `patterns::test_section_header_rejects_titles_inside_a_sentence`, `patterns::test_skill_bullet_pattern_leaves_tokens_alone`, `extraction::test_header_without_colon_must_be_the_whole_line`, `extraction::test_skill_list_markers_need_a_space_and_hyphens_stay_inside_tokens` |
| TC-64 | P | RF-01 | **Resume given as bytes** (an uploaded file): a UTF-8 BOM, `\r\n`, `\r` and NUL characters; invalid UTF-8. | The text is cleaned like a file read from disk; invalid bytes are replaced and do not raise. | `reader::test_decode_resume_cleans_bytes_like_read_resume_file`, `reader::test_decode_resume_replaces_invalid_utf8_instead_of_raising` |
| TC-65 | E | RF-12, RF-14 | **Languages that the language stage of the profile does not read**: `Java` or `C++` for Machine Learning, `C++` or `Rust` for DevOps, `Ruby` for Data Engineer, with `Python`. | They go to the remaining part, after the profile part, in alphabetical order; the languages of the stage stay in the profile part; the restrictions only name languages of the category. | `sorter::TestLanguageSlotRestrictions` |
| TC-66 | P | RF-14 | **Extra languages in a valid resume**: `Java, Python, Pandas, TensorFlow, SQL, Git`; `C++, Python, ...`; `Python, Rust, ...`; the same for DevOps and Data Engineer. | Accepted: the extra language is noise after the profile part. | `classification::TestExtraLanguagesAreNoise::test_machine_learning_accepts_extra_languages`, `classification::TestExtraLanguagesAreNoise::test_devops_accepts_extra_languages`, `classification::TestExtraLanguagesAreNoise::test_data_engineer_accepts_extra_languages` |
| TC-67 | N | RF-13 | **Only a foreign language**: `Java, Pandas, sklearn, SQL, Git` for Machine Learning. | Rejected; the report names the missing stage `base_language`. | `classification::TestExtraLanguagesAreNoise::test_resume_with_only_a_foreign_language_is_still_rejected` |
| TC-68 | P | RF-12, RF-13 | **The sorter and the automata agree**: for each profile, the skills that the sorter puts in the profile part are exactly the alphabet of its automaton. | Equal sets for the four profiles (the same check runs when `classifier.py` is imported). | `classification::TestExtraLanguagesAreNoise::test_sorter_and_automata_agree_on_the_profile_skills` |

### 4.9 Stage 4 - Candidate language (textX)

Files: `tests/test_grammar_definition.py` (the grammar file and documents written by hand) and `tests/test_grammar.py` (the parser, the model and the serializer). The grammar is `resumelens/grammar/resume_grammar.tx`; its formalization (G = (V, Sigma, S, P) in EBNF) is in `docs/formalization.md`, Section 4.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-69 | P | RF-17 | **The grammar and its valid documents**: the file exists and loads, the root is the first rule and the expected rules are defined; personal data, repeated education and experience entries, skills with their categories, one verdict per profile in the order of the roadmap; phone, e-mail and URL formats; comments, line endings and strings with quotes, accents or several lines; blocks that may be empty. | The metamodel is loaded once (cached); each document is instantiated as a model with the expected objects and attributes; the four profile results share an abstract type; only the name is mandatory in the personal block. | `grammar_definition::TestGrammarFile`, `grammar_definition::TestValidDocuments`, `grammar_definition::TestComments`, `grammar::test_grammar_path_points_to_the_tx_file`, `grammar::test_package_exports_the_public_api`, `grammar::test_load_metamodel_is_cached`, `grammar::test_metamodel_defines_the_entity_classes`, `grammar::test_handwritten_document_instantiates_the_root_model`, `grammar::test_personal_and_contact_attributes_are_mapped`, `grammar::test_education_and_experience_entries_are_mapped`, `grammar::test_skill_entries_are_mapped`, `grammar::test_classification_block_is_mapped_for_each_profile`, `grammar::test_each_profile_result_has_its_own_class_and_the_abstract_type`, `grammar::test_only_the_name_is_mandatory_in_personal_info`, `grammar::test_education_and_experience_blocks_may_be_empty`, `grammar::test_repeated_elements_are_supported`, `grammar::test_comments_and_free_whitespace_are_ignored`, `grammar::test_strings_support_escaped_quotes_accents_and_multiple_lines`, `grammar::test_phone_formats_accepted_by_the_grammar`, `grammar::test_email_formats_accepted_by_the_grammar` |
| TC-70 | N | RF-18 | **Documents that violate the grammar**: missing or repeated blocks, blocks out of order, an unclosed or followed root block, a document without skills, fewer or more than four verdicts, verdicts out of order, a malformed e-mail, phone, URL or skill name, a comment hiding a mandatory token; a source that is not a string. | `TextXSyntaxError` with line and column (a syntactic error, not a semantic one); `TypeError` for a source that is not a string; the valid base document is the control of every case. | `grammar_definition::TestViolationsAreRejected`, `grammar::test_malformed_documents_raise_syntax_error`, `grammar::test_base_document_is_valid`, `grammar::test_incomplete_or_foreign_texts_are_rejected`, `grammar::test_unclosed_root_block_is_rejected`, `grammar::test_content_after_the_root_block_is_rejected`, `grammar::test_blocks_out_of_order_are_rejected`, `grammar::test_repeated_single_value_fields_are_rejected`, `grammar::test_document_without_skills_is_rejected`, `grammar::test_evaluation_requires_exactly_the_four_profiles`, `grammar::test_evaluation_profiles_must_follow_the_roadmap_order`, `grammar::test_syntax_error_reports_the_location_of_the_violation`, `grammar::test_violations_are_syntactic_not_semantic_errors`, `grammar::test_non_string_sources_raise_type_error` |
| TC-71 | P | RF-19 | **Serializer**: `build_profile_source` with the pipeline data; missing contact fields; profile names; tricky strings; a text that ends in a backslash (documented limit). | The documented layout; the output is deterministic and parses back to the same data; the serializer does not validate or modify its inputs; a text ending in a backslash is a known unrepresentable string. | `grammar::test_serialized_document_has_the_expected_layout`, `grammar::test_serializer_writes_the_pipeline_values`, `grammar::test_serializer_omits_missing_contact_fields`, `grammar::test_serializer_converts_profile_names_to_identifiers`, `grammar::test_serializer_is_deterministic`, `grammar::test_serializer_does_not_validate_its_input`, `grammar::test_serializer_does_not_mutate_its_inputs`, `grammar::test_text_ending_in_a_backslash_is_a_known_unrepresentable_string`, `grammar::test_serializer_output_parses_back_to_the_same_data`, `grammar::test_handwritten_document_round_trips_to_identical_text`, `grammar::test_round_trip_is_a_fixed_point_for_tricky_strings`, `grammar::test_pipeline_output_of_each_fixture_round_trips` |
| TC-72 | P | RF-17, RF-18, RF-19 | **Real data**: the five synthetic resumes through Stages 1-3, serialized and parsed. | Each valid resume is a valid document and its model reports the accepted profile; the reports of the automata survive the round trip; a resume with missing contact data is still valid; the resume without skills cannot be represented. | `grammar_definition::TestGrammarDescribesRealData`, `grammar::test_model_reports_the_accepted_profile_of_each_fixture`, `grammar::test_fixture_with_missing_skills_cannot_be_represented`, `grammar::test_fixture_with_missing_contact_data_is_still_valid` |

### 4.10 Stage 4 - Visualization

File: `tests/test_visualization.py`. The reports are generated from the validated model (`visualization/renderer.py`).

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-73 | P | RF-20 | **HTML report**: the template and its placeholders; a valid model of each profile. | A complete HTML5 document with balanced tags, the sections in order, no unfilled placeholder, no script or external resource; the candidate data, the normalized skills, the verdict of each profile, the matched skills and the report of the automaton are in the page; the output is deterministic. | `visualization::test_package_exports_the_public_api`, `visualization::test_template_exists_and_has_all_placeholders`, `visualization::test_html_is_a_complete_html5_document`, `visualization::test_html_tags_are_balanced`, `visualization::test_html_has_the_sections_in_order`, `visualization::test_html_has_no_unfilled_placeholders`, `visualization::test_html_is_self_contained`, `visualization::test_html_is_deterministic`, `visualization::test_html_injects_candidate_data`, `visualization::test_html_injects_the_normalized_skills`, `visualization::test_html_shows_the_verdict_of_each_profile`, `visualization::test_html_shows_matched_skills_and_automaton_report` |
| TC-74 | E | RF-20 | **HTML with unusual data**: markup in the values, missing contact data, empty education, experience, skills, results, matched skills or details, non-ASCII text, a missing template. | Every value is escaped (no markup injection); missing parts are omitted or replaced by a message and the page stays valid; non-ASCII text is kept; a missing template raises a clear `OSError`. | `visualization::test_html_escapes_values_to_avoid_markup_injection`, `visualization::test_html_handles_null_contact_data`, `visualization::test_html_shows_only_the_contact_data_that_exists`, `visualization::test_html_handles_empty_education_and_experience`, `visualization::test_html_handles_empty_skills_and_results_without_breaking`, `visualization::test_html_handles_empty_matched_and_details`, `visualization::test_html_renders_non_ascii_text`, `visualization::test_html_with_missing_template_raises_a_clear_os_error` |
| TC-75 | P | RF-21 | **Markdown report**: a valid model of each profile. | Title and sections in order; plain Markdown without HTML page markup; the same data as the HTML report; skills in a table; a multi-line report of the automaton quoted line by line; deterministic. | `visualization::test_markdown_has_title_and_sections_in_order`, `visualization::test_markdown_is_plain_markdown_without_html_page_markup`, `visualization::test_markdown_injects_candidate_data`, `visualization::test_markdown_lists_the_normalized_skills_in_a_table`, `visualization::test_markdown_shows_the_verdict_of_each_profile`, `visualization::test_markdown_shows_matched_skills_and_automaton_report`, `visualization::test_markdown_quotes_every_line_of_a_multiline_report`, `visualization::test_markdown_and_html_report_the_same_content`, `visualization::test_markdown_is_deterministic` |
| TC-76 | E | RF-21 | **Markdown with unusual data**: special characters, pipes inside table cells, unsafe URLs, missing contact data or links, empty sections, an empty name, non-ASCII text, a missing HTML template. | Special characters are escaped so that Markdown shows them literally; table rows stay aligned; unsafe URLs are not turned into links; empty parts are replaced by a message; the Markdown export works without the HTML template. | `visualization::test_markdown_escapes_special_characters`, `visualization::test_markdown_keeps_table_rows_aligned_when_values_contain_pipes`, `visualization::test_markdown_does_not_turn_unsafe_urls_into_autolinks`, `visualization::test_markdown_handles_null_contact_data`, `visualization::test_markdown_handles_links_set_to_none`, `visualization::test_markdown_handles_empty_education_experience_skills_and_results`, `visualization::test_markdown_handles_empty_matched_and_details`, `visualization::test_markdown_handles_an_empty_name`, `visualization::test_markdown_renders_non_ascii_text`, `visualization::test_markdown_export_works_when_the_html_template_is_missing` |
| TC-77 | E | RF-21 | **Writing the reports**: HTML and Markdown to files; missing folders; an existing file; a directory as target. | The files are written in UTF-8; missing folders are created; an existing file is overwritten; a directory as target raises `OSError`. | `visualization::test_write_visualization_writes_html_and_markdown_files`, `visualization::test_write_visualization_creates_missing_directories_and_accepts_str`, `visualization::test_write_visualization_overwrites_and_keeps_utf8`, `visualization::test_write_visualization_to_a_directory_raises_os_error` |

### 4.11 Command line and end-to-end runs

Files: `tests/test_cli.py` and `tests/test_e2e_pipeline.py`. The command line is `python main.py --cv FILE [--profile NAME] [--output FILE.html|.md]`.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-78 | P | RF-22 | **Arguments**: `--cv` is required, defaults, all the arguments, the output extensions, profile names in several forms, unknown profiles, options and extensions. | The parser accepts the supported forms; invalid arguments are argument errors (exit status 2); the help names every option. | `cli::TestArguments` |
| TC-79 | P | RF-22 | **`run_pipeline` and `run_pipeline_text`** on the five resumes, on text and on a path given as a string; a missing file; a directory; a resume with only unrecognized skills. | The outputs of the stages are chained; the model holds the four verdicts; text and file give the same run; a document that violates the grammar does not raise: stages 1 to 3 are kept and `dsl_error` explains the problem; a missing file raises `FileNotFoundError`. | `cli::TestRunPipeline` |
| TC-80 | P | RF-22 | **Console report**: the stages in order, the extracted data, each translation and the canonical orders, discarded tokens, verdicts, rejection reasons, the invalid resume, the report line of Stage 4, the profile filter. | Each stage is shown; the profile filter restricts stages 2 and 3 and the final verdict; an unknown profile is an error; the output is plain ASCII. | `cli::TestConsoleReport` |
| TC-81 | P | RF-22 | **`write_report`**: HTML, Markdown, missing folders, an existing report, an unsupported extension. | The format follows the extension; folders are created; an existing report is overwritten; an unsupported extension raises `ValueError`. | `cli::TestWriteReport` |
| TC-82 | E | RF-22 | **`main` and exit statuses**: a valid resume, a report written or not, `--profile`, a resume without skills, a missing file, a directory, an unwritable output, invalid arguments, `sys.argv`, two runs, characters that the console cannot encode. | Exit status `0` on success, `1` on a read error, an invalid DSL document or a report that cannot be written, `2` for invalid arguments; no report is written when the document is invalid; two runs give the same report. | `cli::TestMain` |
| TC-83 | P | RF-22 | **`main.py` as a program** (subprocess). | It runs the pipeline, propagates the exit status and the argument errors, and is a thin wrapper of `resumelens.cli.main`. | `cli::TestEntryPoint` |
| TC-84 | P | RF-23 | **The four valid resumes from disk to the report**: stage by stage, HTML and Markdown files, `main` with `--output` and `--profile`, determinism. | Each stage produces the expected output; the DSL document is valid and matches the model; the report details do not change a verdict; the page has the sections of the example page; the HTML report marks one profile as accepted and three as rejected; two runs give the same result. | `e2e_pipeline::TestValidResumes`, `e2e_pipeline::TestReportFiles`, `e2e_pipeline::test_main_runs_the_whole_pipeline_and_writes_the_report`, `e2e_pipeline::test_profile_option_narrows_the_console_report`, `e2e_pipeline::test_pipeline_is_deterministic` |
| TC-85 | N | RF-23 | **The invalid resume and a missing file**. | Stages 1 to 3 finish and every profile rejects the resume; Stage 4 reports a syntax error instead of raising; the command fails and writes no report; a missing resume gives an error from the subprocess. | `e2e_pipeline::TestInvalidResume`, `e2e_pipeline::test_entry_point_subprocess_with_missing_resume` |
| TC-86 | P | RF-23 | **The program as a subprocess**: `python main.py --cv ...`. | Exit status `0` and the verdicts on the standard output. | `e2e_pipeline::test_entry_point_subprocess` |

### 4.12 Web interface

File: `tests/test_app.py`. The page `app.py` (Streamlit) is run without a browser with `streamlit.testing.v1.AppTest`: the tests choose a resume in the sidebar and read the metrics, tabs, messages and download buttons.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-87 | P | RF-24 | **The page with the example resumes**: first run, the four stage tabs, each example, a valid and the invalid resume, each profile detailed. | No exception; four verdicts per resume with the expected profile accepted (none for the invalid resume); a valid resume shows a valid DSL document and two download buttons (HTML and Markdown); the invalid one shows the syntax error and no download. | `app::TestPage` |
| TC-88 | E | RF-24 | **Pasted and uploaded text**: an inline skills header with an extra language, the default sample, an empty text, text without skills, the upload mode without a file. | The skills are read and the verdict is shown; an empty text or no file asks for a resume; text without skills is reported (all profiles rejected, DSL error) and does not raise. | `app::TestPastedText` |
| TC-89 | P | RF-24 | **Helpers of the page**: the example resumes, the profile names, the table of the transition function, the selected profile and the bullet list that shows a list of the resume. | The five synthetic files; the official profile names; the table lists every transition and symbol of the automaton; the selected profile is recognized by its name; list items become bullets and special characters (`_`, `$`, `*`, `[`) are shown literally. | `app::TestHelpers`, `app::TestMarkdownList` |

### 4.13 Report details: location, current role, summary and job highlights

Files: `tests/test_patterns.py`, `tests/test_extraction.py`, `tests/test_grammar.py`, `tests/test_visualization.py`, `tests/test_e2e_pipeline.py` and `tests/test_app.py`. The four valid resumes have a `Location:` and a `Current role:` line in the *Contact* section, a two-paragraph *Summary* and a job with two bullets, like the example page of the assignment. These details are shown in the report and never decide a verdict.

| TC | Type | RF | Scenario | Expected result | Tests |
|---|---|---|---|---|---|
| TC-90 | P | RF-25 | **Extraction of the details**: `Location: Nevermore Academy, Jericho`, `Current role: DevOps Engineer at Stark Cloud`, bullets with `-`, `*`, `+` or a bullet dot; the four resumes; the *Contact* section before the whole text; empty values skipped; a summary with several paragraphs and irregular whitespace; jobs with their bullets. | Each value is extracted exactly (the label, case and spacing are free); the *Contact* section has priority; every bullet belongs to the entry that precedes it; each resume gives its location, current role, two paragraphs and one job with two bullets. | `patterns::test_location_pattern_accepts`, `patterns::test_current_role_pattern_accepts`, `patterns::test_highlight_pattern_accepts`, `patterns::test_report_details_on_fixtures`, `extraction::test_report_details_of_each_valid_resume`, `extraction::test_location_and_current_role_prefer_the_contact_section`, `extraction::test_location_falls_back_to_the_whole_text_and_skips_empty_values`, `extraction::test_summary_splits_paragraphs_and_collapses_whitespace`, `extraction::test_jobs_keep_the_bullets_of_each_entry_apart` |
| TC-91 | N | RF-25 | **Look-alikes and missing details**: `Relocation: yes`, `My location: Bogota`, `Location Bogota`, `Role: Developer`, `Previous role: QA`, `Built a dashboard`, `-Built`, a job line; the invalid resume; no section. | No match; the values are `""` and the lists are empty; a resume without the sections gives no jobs. | `patterns::test_location_pattern_rejects`, `patterns::test_current_role_pattern_rejects`, `patterns::test_highlight_pattern_rejects`, `extraction::test_report_details_of_the_invalid_resume_are_empty`, `extraction::test_jobs_without_the_section_or_bullets` |
| TC-92 | P | RF-26 | **The details in the candidate language**: `build_profile_source` with and without details; the model; the round trip; the four resumes. | The summary block, `location`, `current_role` and the structured job (`role`, `company`, `period`, `highlight`) are written only when they exist and right after the personal information; the model maps them (an absent summary is `None`); the text is a fixed point of parse and serialize; each resume carries its details into the model. | `grammar::test_serializer_writes_location_role_summary_and_structured_jobs`, `grammar::test_serializer_omits_the_summary_block_and_the_details_when_there_are_none`, `grammar::test_model_maps_location_role_summary_and_structured_jobs`, `grammar::test_summary_block_is_optional`, `grammar::test_details_round_trip_to_the_same_text`, `grammar::test_fixtures_carry_their_report_details_into_the_model` |
| TC-93 | N | RF-18, RF-26 | **Malformed details**: an unquoted location or paragraph, a job with a role but no period or with the company before the role, a `highlight` without text, a block with another name, the summary after the education block, a repeated or swapped `location` / `current_role`. | `TextXSyntaxError` in every case: the structured part of a job is all or nothing and the order of the grammar is fixed. | `grammar::test_malformed_details_are_rejected`, `grammar::test_summary_must_come_right_after_the_personal_information`, `grammar::test_location_and_current_role_may_appear_only_once_and_in_order` |
| TC-94 | P | RF-27 | **Reports with the details**: the four resumes and a model with location, summary and a structured job. | The HTML has `Location`, `Current role`, a *Profile Summary* section with one paragraph per item and, in *Experience*, the role as `h3`, then `company · period` and the bullets; the Markdown has the same data (`### role`, `_company · period_`, bullets); the tags stay balanced. | `visualization::test_html_shows_location_current_role_and_summary_of_the_fixtures`, `visualization::test_html_shows_structured_experience_in_the_order_of_the_example`, `visualization::test_html_sections_stay_balanced_with_the_new_data`, `visualization::test_markdown_shows_location_current_role_and_summary_of_the_fixtures`, `visualization::test_markdown_shows_structured_experience` |
| TC-95 | E | RF-27 | **Reports with unusual details**: markup and `&` in the values, no summary, no location, plain and structured entries together, a job without bullets, no summary in Markdown. | Every value is escaped; without summary the page says `No summary provided.`; plain entries keep the list layout and a job without bullets has no empty list; the order of the entries is kept. | `visualization::test_html_escapes_the_new_values`, `visualization::test_html_without_summary_or_structured_jobs_keeps_the_plain_layout`, `visualization::test_html_mixes_plain_and_structured_entries_in_order`, `visualization::test_markdown_without_summary_or_details` |
| TC-96 | P | RF-16, RF-25, RF-27 | **The details never decide**: each valid resume with and without its location, current role and bullets; the HTML report written to disk. | The verdicts and the canonical sequences are the same; the written page has the six sections of the example page in order, with the extracted location, role, summary, job and bullets. | `e2e_pipeline::TestValidResumes::test_report_details_do_not_change_the_verdict`, `e2e_pipeline::TestReportFiles::test_html_report_has_the_sections_of_the_example_page` |
| TC-97 | P | RF-24 | **The details in the web interface**: the extraction tab with the Full Stack resume and with pasted text that has no details. | The table shows the location and the current role, and the jobs table shows the role and the company; without details the page shows `(not found)`. | `app::TestReportDetails` |

## 5. Coverage of the test plan

The plan has **97 test cases**: 54 positive, 27 negative and 16 edge cases. Every `pytest` function of the repository is traced to at least one test case, as the table shows.

| File | Functions | Traced to a test case |
|---|---|---|
| `tests/test_reader.py` | 14 | 14 |
| `tests/test_patterns.py` | 50 | 50 |
| `tests/test_extraction.py` | 66 | 66 |
| `tests/test_normalization.py` | 119 | 119 |
| `tests/test_sorter.py` | 81 | 81 |
| `tests/test_classification.py` | 149 | 149 |
| `tests/test_grammar_definition.py` | 34 | 34 |
| `tests/test_grammar.py` | 54 | 54 |
| `tests/test_visualization.py` | 52 | 52 |
| `tests/test_cli.py` | 55 | 55 |
| `tests/test_e2e_pipeline.py` | 17 | 17 |
| `tests/test_app.py` | 20 | 20 |
| `tests/test_environment.py` | 1 | 1 |
| **Total** | **712** | **712** |

Limits that the tests document and that are not defects of the plan:

- A token that joins two skills (`Python and Git`) is not split by Stage 1 and is reported as unrecognized by Stage 2 (TC-32).
- The bare transducers read one whole spelling per input symbol, so `Spring  Boot` (two spaces) is rejected by them; the normalizer trims and collapses whitespace first (TC-26, TC-30).
- A text that ends in a backslash cannot be written in the candidate language, because textX only unescapes the double quote (TC-71).
- A resume without any recognized skill cannot be represented in the candidate language: the pipeline reports the syntax error and generates no report (TC-72, TC-85, TC-88).
