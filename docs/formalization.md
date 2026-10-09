# ResumeLens — Formalization

This document formalizes the computational models of each stage of the pipeline. The notation
follows the course: given an alphabet Σ, regular languages are built from
∅, {λ} and {a} (a ∈ Σ) with union (A ∪ B), concatenation (A · B) and Kleene closure (A\*);
A⁺ = A · A\* is the positive closure and Aⁿ the n‑th power.

---

## Section 1. Regular expressions (Stage 1)

Stage 1 (`resumelens/extraction/`) extracts from the plain text of the resume the information
that is later normalized, classified and represented. Each type of information has a regular
expression compiled with `re.compile` in `resumelens/extraction/patterns.py`, with named
groups `(?P<name>...)` and, when needed, the modifiers `re.MULTILINE` and
`re.IGNORECASE`. The engine `resumelens/extraction/extractor.py` applies them with `match`,
`search`, `finditer`, `split` and `sub`, as in the classes on regex in Python.

### 1.1 Alphabets and notation

| Symbol | Set |
|---|---|
| Σ | Unicode characters of the resume text |
| M | Upper-case letters {A, …, Z} |
| m | Lower-case letters {a, …, z} |
| L | M ∪ m |
| D | Digits {0, …, 9} |
| W | Python word characters (`\w`): letters, digits and `_` |
| E | Horizontal whitespace {␣, ⇥} (`[ \t]`) |
| N | Line break {↵} |

For brevity, a word written between quotes denotes the singleton language of that string
(`"to"` = {to}), a list between braces with `|` denotes the union of singleton languages
({Jan | Feb} = {Jan} ∪ {Feb}) and `X?` = X ∪ {λ}. With `re.IGNORECASE` each letter
`a` is read as {a, A}.

### 1.2 Reusable fragments

| Fragment | Regular expression (Python) | Language |
|---|---|---|
| `_YEAR` | `(?:19\|20)\d{2}` | YEAR = {19, 20} · D² |
| `_MONTH` | `Jan(?:uary)?\|Feb(?:ruary)?\|…\|Dec(?:ember)?` | MONTH = {Jan, January, Feb, …, Dec, December} (abbreviation or full English name) |
| `_DATE` | `(?:MONTH\.?[ \t]+)?YEAR` | DATE = (MONTH · {., λ} · E⁺)? · YEAR |
| `_OPEN_END` | `Present\|Current\|Now\|Ongoing` | OPEN = {Present, Current, Now, Ongoing} |
| `_SEPARATOR` | `[ \t]*(?:[-–—]\|\bto\b)[ \t]*` | SEP = E\* · {-, –, —, to} · E\* |
| `_RANGE` | `DATE SEP (DATE\|OPEN)\b` | RANGE = DATE · SEP · (DATE ∪ OPEN) |
| `_LEVEL` | `(?:Bachelor\|Master\|…\|B\.?S\|M\.?S\|…)\.?` | LEVEL = {Bachelor, Master, Associate, Doctorate, PhD, Ph.D, MBA, BSc, MSc, BS, B.S, MS, M.S, BA, B.A, MA, M.A, BEng, B.Eng, MEng, M.Eng} · {., λ} |
| `_DEGREE` | `LEVEL (?:[ \t]+of[ \t]+[A-Za-z]+)? [ \t]+(?:in\|of)[ \t]+FIELD` | DEGREE = LEVEL · (E⁺ · "of" · E⁺ · L⁺)? · E⁺ · {in, of} · E⁺ · FIELD, with FIELD = (Σ − {↵ , ; (})\* · (Σ − {whitespace , ; (}) |

`YEAR` accepts exactly the years 1900–2099, so a range such as `2019 - 2023` is never
mistaken for a phone number (which requires 3‑3‑4 digit groups).

### 1.3 Contact data

| Pattern | Recognized language | Accepted example | Rejected example |
|---|---|---|---|
| `EMAIL_PATTERN` | USER · {@} · LABEL · ({.} · LABEL)\* · {.} · L² · L\*, with USER = (L ∪ D ∪ {. _ % + -})⁺ and LABEL = (L ∪ D ∪ {-})⁺ | `mj.watson@dailybugle.com` | `juan.perez at mail` (has no `@`) |
| `PHONE_PATTERN` | ({+} · D¹⁻³ · {␣ . - λ})? · {( λ} · D³ · {) λ} · {␣ . - λ} · D³ · {␣ . - λ} · D⁴ | `+1 555 123 4567`, `(555) 123-4567` | `2019 - 2023` (not of the 3‑3‑4 form) |
| `URL_PATTERN` | {http, https} · {://} · HOST · PATH, with HOST = LABEL · ({.} · LABEL)⁺ and PATH = ({/} · SEG · ({.} · SEG)\*)\* | `https://github.com/gstacy` | `github.com/gstacy` (no scheme) |
| `LINKEDIN_URL_PATTERN` | {http, https} · {://} · {www., λ} · {linkedin.com/} · {in, company} · {/} · (W ∪ {% -})⁺ | `https://www.linkedin.com/in/gwen-stacy` | `https://linkedin.com/feed` |
| `GITHUB_URL_PATTERN` | {http, https} · {://} · {www., λ} · {github.com/} · (W ∪ {-})⁺ · ({/} · REPO)? | `https://github.com/mjwatson` | `https://gitlab.com/x` |

In `PHONE_PATTERN`, D¹⁻³ = D ∪ D² ∪ D³ (a country code of 1 to 3 digits).

### 1.4 Resume structure

| Pattern | Recognized language | Use |
|---|---|---|
| `SECTION_HEADER_PATTERN` (`MULTILINE`, `IGNORECASE`) | A whole line E\* · TITLE · E\* · {:} · E\*, with TITLE = {Contact, Summary, Technical Skills, Skills, Education, Experience, Work Experience, Projects, Certifications} | `split_sections` splits the text into sections with `finditer` |
| `NAME_PATTERN` | WORD · (E⁺ · WORD)ⁿ with 1 ≤ n ≤ 3, and WORD = (M ∪ {Á É Í Ó Ú Ñ Ü}) · (LETTER ∪ {' ’ . -})\*; LETTER is any Unicode letter (`[^\W\d_]`) | `extract_name`: `Mary Jane Watson`, `José Núñez`; rejects `juan perez` |
| `SKILL_SEPARATOR_PATTERN` | {, ; ↵} | `extract_skills` splits the *Technical Skills* section with `split` |

`SKILL_SEPARATOR_PATTERN` is a delimiter, not an extraction pattern; that is why it is not in
the `PATTERNS` registry.

### 1.5 Education and experience

| Pattern | Recognized language | Use |
|---|---|---|
| `DATE_RANGE_PATTERN` | RANGE (see 1.2) | `extract_education` keeps the lines with a period |
| `DEGREE_PATTERN` | DEGREE (see 1.2). Groups: `level`, `field` | `extract_education` keeps the lines with a degree |
| `INSTITUTION_PATTERN` | {University} · E⁺ · {of} · E⁺ · CAP · (E⁺ · CAP)\* ∪ {Universidad} · E⁺ · ({de} · E⁺ · ({la} · E⁺)?)? · CAP ∪ (CAP · E⁺)\* · {University, Institute, College, School, Academy, Polytechnic, Tech}, with CAP = M · (W ∪ {& ' -})\* | `extract_education` keeps the lines with an institution |
| `EDUCATION_ENTRY_PATTERN` (`MULTILINE`) | E\* · DEGREE · E\* · N · E\* · INST · E\* · {(} · (RANGE ∪ YEAR) · {)}: a complete two-line record | Reference pattern to validate complete records (tests) |
| `YEARS_EXPERIENCE_PATTERN` | D¹⁻² · {+, λ} · E⁺ · {year, years} · E⁺ · {of} · E⁺ · ({professional} · E⁺)? · {experience} · (E⁺ · (Σ − {↵ .})⁺)? | `extract_experience`: `3 years of experience developing web applications` |
| `EXPERIENCE_ENTRY_PATTERN` (`MULTILINE`) | E\* · ROLE · E\* · {, at @ \|} · E\* · COMPANY · E\* · {(} · RANGE · {)}, with ROLE = L · (Σ − {↵ , ( ) @ \|})\* | `extract_experience`: `Full Stack Developer, Raven Labs (2023 - 2026)`; rejects bullets `- ...` |

### 1.6 Technical skill bank

Each pattern of the bank recognizes a **finite** language: the union of the accepted
spellings of each technology. All of them have the group `skill`. The registry `SKILL_PATTERNS`
groups them by type and `extract_technologies` runs them with `finditer` over the whole
resume (except the *Contact* section and the URLs, which are removed with `URL_PATTERN.sub`).
The result is stored in `RawResumeData.detected_skills`, grouped by type and without
repetitions.

| Pattern (`SKILL_PATTERNS`) | Language (case-insensitive, unless stated otherwise) |
|---|---|
| `programming_language` | {Python, JavaScript, JS, TypeScript, TS, Java, Golang, Rust, Kotlin, Swift, PHP, Ruby} ∪ {Go, C++, C#, C} (this last group **is** case-sensitive) |
| `framework` | {React, React.js, ReactJS, Angular, Angular.js, Vue, Vue.js, Node, Node.js, NodeJS, Django, Spring·E⁺·Boot, Express, Express.js, Next, Next.js, NextJS, Flask, FastAPI, Laravel} |
| `ml_library` | {Pandas, NumPy, Scikit-learn, Scikit learn, sklearn, Keras, Matplotlib, TensorFlow, Tensor·E⁺·Flow, PyTorch, Py·E⁺·Torch} |
| `ml_practice` | {Machine-learning, Machine learning} · (E⁺ · {model} · E⁺ · {development})? ∪ {ML} · E⁺ · {model} · E⁺ · {development}, if it is not followed by E⁺ · Engineer |
| `database` | {PostgreSQL, Postgres, MySQL, MariaDB, Oracle, SQLite, SQL·E⁺·Server, MongoDB, Mongo, Redis, Cassandra, NoSQL, SQL} |
| `data_tool` | ({Apache} · E⁺)? · {Spark} ∪ {PySpark} ∪ ({Apache} · E⁺)? · {Airflow} |
| `api` | {REST, RESTful} · (E⁺ · {API, APIs})?, case-sensitive |
| `version_control` | {Git, GitHub, GitLab, Bitbucket} |
| `devops_cloud` | {Docker, Kubernetes, Terraform, Jenkins, Ansible, AWS, Amazon·E⁺·Web·E⁺·Services, Azure, Microsoft·E⁺·Azure, GCP, Google·E⁺·Cloud·(E⁺·Platform)?} |

The raw tokens that go to Stage 2 (`raw_skills`) are those of the *Technical Skills*
section, split with `SKILL_SEPARATOR_PATTERN` and in the order in which they appear, as in the
example of the assignment (`JS`, `React.js`, `NodeJS`, `Postgres`, `Git`). The bank does not
decide whether two spellings are equivalent (`JS` and `JavaScript` are reported separately);
that is the task of the transducers of Stage 2.

### 1.7 Implicit automata

By Kleene's theorem, every regular language is accepted by a finite automaton. Each pattern
of this section therefore has an equivalent DFA that the `re` engine simulates over the text.
Two examples:

- **`_YEAR`** = {19, 20} · D². DFA with Q = {p0, p1, p2, p3, p4, p5}, initial state p0,
  F = {p5} and δ(p0, 1) = p1, δ(p1, 9) = p3, δ(p0, 2) = p2, δ(p2, 0) = p3, δ(p3, d) = p4,
  δ(p4, d) = p5 for every d ∈ D. Missing transitions go to an implicit error state.
- **Skill bank** (finite languages). The automaton is a prefix tree (trie) whose leaves are
  the accepted spellings. For example, `version_control` shares the prefix `git` among `Git`,
  `GitHub` and `GitLab`: from the state that reads `git` there is an accepting edge
  (end of word) and two other edges towards `hub` and `lab`.

Python's alternation tries the options from left to right. So that the whole token is
reported, as an automaton that only accepts at the end of the token would do, one of two
techniques is used:

- put the longer spelling before its prefix (`JavaScript` before `Java`,
  `SQL Server` before `SQL`, `Golang` before `Go`); or
- let the final delimiter fail and force backtracking. In `Git|GitHub`, the option `Git`
  cannot end inside `GitHub` because `\b` requires that no letter follows `Git`, so the engine
  tries `GitHub`.

### 1.8 Lexical delimiters

A skill must be recognized as a **whole token**, not as a substring of another word.
For that, zero-width assertions are used: they consume no characters and only restrict the
context. Formally, the language of the token remains the one in the table. The assertion is
equivalent to intersecting the text with a regular language of contexts (for example, "the
previous character is not in W").

| Delimiter | Meaning | What it is used for |
|---|---|---|
| `\b` | Boundary between a character of W and one that is not in W | `Reactive` does not produce `React`, `githubprofile` does not produce `Git`; the `SQL` of `MySQL` is not reported on its own |
| `(?<![\w.])` | The previous character is neither in W nor a dot | The `js` of `Node.js` / `React.js` is not reported as a language; `cargo` and `ago` do not produce `Go` |
| `(?!\w)` | The next character is not in W | `C++` and `C#` end in a symbol, so `\b` would not work; `C(?![+#])` separates `C` from `C++` |
| `(?-i:...)` | Disables `IGNORECASE` in that group | `Go`, `C`, `C++`, `C#` and `REST` are only accepted in upper case, so that the English words *go* and *rest* are not captured |
| `(?![ \t]+Engineer)` | Not followed by " Engineer" | `Machine Learning Engineer` is a job title, not a practice |
| `^ … $` with `MULTILINE` | Start and end of a **line** | Section headers and experience entries occupy a whole line |

The tests of `tests/test_patterns.py` and `tests/test_extraction.py` verify each pattern
with strings inside and outside its language, including the invalid resume, in which no
pattern finds matches.
