# ResumeLens - Test Cases and Traceability Matrix

Test plan of Stages 1 (regular expressions), 2 (finite-state transducers and canonical order) and 3 (finite automata) of the pipeline, plus the ingestion that feeds them. Every test case (`TC-xx`) is tied to the functional requirement it verifies (`RF-xx`), to the `pytest` functions that implement it and to an acceptance criterion. Stage 4 (DSL and visualization) is not covered here; its test cases are added when its code exists.

## 1. Introduction and scope

### 1.1 Validation strategy

The validation is **formal**: each stage is tested against the model that defines it in `docs/formalization.md`, not only against examples.

| Layer | What is checked | Stage |
|---|---|---|
| Language membership | Every regular expression, every spelling of a transducer and every sequence of an automaton is tested with strings **inside** the language (positive cases) and **outside** it (negative cases). | 1, 2, 3 |
| Boundaries | Empty input, one-character tokens, case, whitespace, punctuation, prefixes of valid words, symbols outside the alphabet, missing sections. | 1, 2, 3 |
| Formal structure | The 7-tuple M = (Q, Σ, Γ, δ, ω, q₀, F) of every transducer and the 5-tuple M = (Q, Σ, δ, q₀, F) of every automaton are read from the `pyformlang` object and compared with the definition: states, alphabets, transitions, initial and final states, determinism. | 2, 3 |
| Oracles | The automata are compared, over every short word, with independent oracles: a Python `re` regular expression and a `pyformlang` `Regex`. | 3 |
| Properties | Idempotence, determinism, independence from the order in which the skills were written, permutation of the sorter output, no mutation of the input. | 2, 3 |
| Integration | The five synthetic resumes (`data/input_resumes/`) go through Stage 1, 2 and 3: each valid resume is accepted by its own profile only and the invalid resume is rejected by all of them. | 1-3 |

The system **does not rank candidates**: no test compares candidates; each test checks the verdict *accepted / rejected* of a profile or an intermediate result of a stage.

### 1.2 Test inventory

Tests are `pytest` functions. A function with `@pytest.mark.parametrize` runs once per parameter set, so the number of executed cases is larger than the number of functions.

| File | Functions | Subject |
|---|---|---|
| `tests/test_reader.py` | 12 | Ingestion (`read_resume_file`) and domain models |
| `tests/test_patterns.py` | 39 | Compiled regular expressions of `extraction/patterns.py` |
| `tests/test_extraction.py` | 53 | Extractor functions of `extraction/extractor.py` |
| `tests/test_normalization.py` | 119 | Transducers (`transducers.py`) and `SkillNormalizer` (`normalizer.py`) |
| `tests/test_sorter.py` | 78 | Canonical order (`sorter.py`) |
| `tests/test_classification.py` | 144 | Automata (`automata.py`) and classifier (`classifier.py`) |
| `tests/test_environment.py` | 1 | Every package of `resumelens` can be imported |
| **Total** | **446** | |

Shared fixtures are in `tests/conftest.py`: `resume_texts`, `valid_resume_texts`, `fullstack_text`, `ml_text`, `devops_text`, `data_text`, `invalid_text` and `raw_resume_factory`.

### 1.3 Notation

- **Type:** **P** positive (valid input, accepted or translated), **N** negative (invalid input, rejected or error), **E** edge case (boundary or special situation).
- **Tests:** `file::function` or `file::Class::function`, where `file` is the name of the test file without the `test_` prefix and the `.py` extension (`patterns`, `extraction`, `reader`, `normalization`, `sorter`, `classification`, `environment`). A class alone, such as `normalization::TestWebTranslations`, stands for **all** the tests of that class.
- **Acceptance criterion:** a test case passes when all its tests pass.

### 1.4 How to run

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q                            # whole suite
python3 -m pytest tests/test_sorter.py -q       # one file
python3 -m pytest -k "TestWebTranslations" -q   # one class
```

The suite must finish with **0 failures and 0 errors**.

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

## 3. Traceability matrix

Each requirement is traced to its test cases, to the files where they are implemented and to its acceptance criterion. *Functions* is the number of `pytest` functions that implement the requirement.

| RF | Test cases | Test files | Functions | Acceptance criterion |
|---|---|---|---|---|
| RF-01 | TC-01, TC-02, TC-03, TC-04, TC-05 | `test_reader.py` | 10 | The five synthetic files are read with `str` and `Path`; a missing file raises `FileNotFoundError`; `\r\n`, `\r` and `\x00` are normalized. |
| RF-02 | TC-06 | `test_reader.py`, `test_environment.py` | 3 | Models are created with independent default lists; the seven packages import without errors. |
| RF-03 | TC-07, TC-08, TC-09, TC-10, TC-11, TC-12 | `test_patterns.py`, `test_extraction.py` | 21 | Valid emails, phones and links are extracted exactly; malformed or look-alike strings give an empty value; the Contact section has priority. |
| RF-04 | TC-13, TC-14 | `test_patterns.py`, `test_extraction.py` | 9 | Names, including accented ones, and section headers are recognized; text without headers stays in the preamble. |
| RF-05 | TC-15, TC-16 | `test_patterns.py`, `test_extraction.py` | 12 | Degree, institution and period are recognized; lines that have none of them are dropped. |
| RF-06 | TC-17, TC-18 | `test_patterns.py`, `test_extraction.py` | 9 | Years of experience and job entries are recognized; bullets and education lines are not. |
| RF-07 | TC-05, TC-19, TC-20 | `test_reader.py`, `test_patterns.py`, `test_extraction.py` | 13 | `raw_skills` keeps order, case and symbols; separators never leak; a resume without the section gives `[]`. |
| RF-08 | TC-21, TC-22, TC-23 | `test_patterns.py`, `test_extraction.py` | 29 | Every skill pattern matches its spellings and only them; `extract_resume` returns the expected data for the five resumes. |
| RF-09 | TC-24, TC-25, TC-27, TC-28, TC-34 | `test_normalization.py` | 62 | Every listed variant is translated to its canonical name; the transducers have the documented 7-tuple structure. |
| RF-10 | TC-26, TC-29 | `test_normalization.py` | 11 | Tokens outside the language or the alphabet have no translation; invalid tables raise `ValueError`. |
| RF-11 | TC-30, TC-31, TC-32, TC-33, TC-34 | `test_normalization.py` | 54 | Records are unique, ordered and categorized; unrecognized tokens are reported and never become records. |
| RF-12 | TC-35, TC-36, TC-37, TC-38, TC-39, TC-40, TC-41, TC-42, TC-57 | `test_sorter.py`, `test_classification.py` | 95 | The output is the canonical order of the profile for every permutation of the input. |
| RF-13 | TC-43, TC-46, TC-47, TC-48, TC-50, TC-51, TC-52, TC-56, TC-59 | `test_classification.py` | 81 | Complete sequences are accepted, every rejection path is rejected and the automata match the formal definition and the independent oracles. |
| RF-14 | TC-44, TC-45, TC-49, TC-60 | `test_classification.py` | 15 | Optional stages may be missing, the alternatives of a stage are interchangeable and trailing noise is accepted. |
| RF-15 | TC-53, TC-54, TC-55, TC-56, TC-57, TC-58, TC-59 | `test_classification.py` | 52 | The verdict is the automaton's; the report states the satisfied stages or the reason for the rejection; errors are typed. |
| RF-16 | TC-23, TC-39, TC-42, TC-59, TC-60, TC-61 | `test_extraction.py`, `test_sorter.py`, `test_classification.py` | 26 | Shuffled, re-cased or re-spelled skills give the same verdicts; each resume is accepted by its own profile only. |

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
| TC-14 | N | RF-04 | **Lines that are not names or headers**; a colon inside a sentence; text without any header. | `NAME_PATTERN` rejects them; an inline colon is not a header; text without headers stays in the preamble. | `patterns::test_name_pattern_rejects`, `patterns::test_section_header_ignores_inline_colons`, `extraction::test_split_sections_without_headers_keeps_everything_in_preamble` |
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

## 5. Coverage of the test plan

The plan has **61 test cases**: 31 positive, 21 negative and 9 edge cases. Every `pytest` function of the repository is traced to at least one test case, as the table shows.

| File | Functions | Traced to a test case |
|---|---|---|
| `tests/test_reader.py` | 12 | 12 |
| `tests/test_patterns.py` | 39 | 39 |
| `tests/test_extraction.py` | 53 | 53 |
| `tests/test_normalization.py` | 119 | 119 |
| `tests/test_sorter.py` | 78 | 78 |
| `tests/test_classification.py` | 144 | 144 |
| `tests/test_environment.py` | 1 | 1 |
| **Total** | **446** | **446** |

Limits that the tests document and that are not defects of the plan:

- A token that joins two skills (`Python and Git`) is not split by Stage 1 and is reported as unrecognized by Stage 2 (TC-32).
- The bare transducers read one whole spelling per input symbol, so `Spring  Boot` (two spaces) is rejected by them; the normalizer trims and collapses whitespace first (TC-26, TC-30).
- Stage 4 (textX grammar, validation of the DSL, HTML and Markdown rendering) and the command line are outside this plan.
