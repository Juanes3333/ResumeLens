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

---

## Section 2. Finite-state transducers (Stage 2)

Stage 2 (`resumelens/normalization/`) turns each raw token of `raw_skills` into the canonical
name of the technology it denotes (`JS` → `JAVASCRIPT`, `Postgres` → `POSTGRESQL`) and puts
the result in the canonical order of the selected profile. The mapping is defined with
deterministic finite-state transducers (FST) built with `pyformlang.fst.FST` in
`resumelens/normalization/transducers.py` and applied with `translate`.

### 2.1 Definition

A transducer is the 7-tuple **M = (Q, Σ, Γ, δ, ω, q₀, F)**, where:

| Component | Meaning |
|---|---|
| Q | Finite set of states |
| Σ | Finite input alphabet |
| Γ | Finite output alphabet |
| δ : Q × (Σ ∪ {λ}) → Q | Transition function |
| ω : Q × (Σ ∪ {λ}) → Γ\* | Output function |
| q₀ ∈ Q | Initial state |
| F ⊆ Q | Set of accepting states |

`pyformlang` stores δ and ω together: the call `add_transitions([(q, u, q', [v])])` means
δ(q, u) = q' and ω(q, u) = v, and the transition is drawn **u:v**. The output of a word
u₁u₂…uₙ is ω(q₀, u₁)·ω(q₁, u₂)·…·ω(qₙ₋₁, uₙ), where qᵢ = δ(qᵢ₋₁, uᵢ), and it is defined only
if qₙ ∈ F. If some transition is missing or the last state is not in F, the transducer
**rejects** the word and `translate` returns no output (an implicit error state, as in the
automata of Section 1.7).

All the transducers below are **deterministic**: for every pair (q, u) there is at most one
transition. `build_transducer` guarantees it by raising `ValueError` when two canonical names
claim the same spelling.

### 2.2 Normalization as a composition of two transducers

Normalization of a token w is the composition **T = T_family ∘ T_case**, following the two
kinds of examples of the classes (the identity transducer that copies character by character
and the one that translates whole words):

1. **T_case** reads the token one character at a time and writes it in lower case.
2. **T_family** receives the whole folded token as **one** input symbol and writes the canonical
   name as **one** output symbol.

`apply_transducer(fst, token)` runs both: it calls `fold_case` (T_case) and then
`fst.translate([folded])`. A token is recognized only if **both** accept it. If `translate`
produced two different outputs, `apply_transducer` raises `ValueError`; with a deterministic
T_family that cannot happen.

### 2.3 Case-folding transducer T_case

`build_case_folding_transducer()` builds M_case = (Q, Σ, Γ, δ, ω, q₀, F) with:

| Component | Value |
|---|---|
| Q | {q0} |
| Σ = `INPUT_ALPHABET` | The 57 characters that appear in some spelling of some family, in both cases: the 25 letters a–z except `x`, their 25 upper-case forms and the symbols `␣ # + - . 3 8` |
| Γ | The lower-case forms of Σ: the 25 letters and the 7 symbols (32 characters) |
| δ | δ(q0, c) = q0 for every c ∈ Σ |
| ω | ω(q0, c) = lower(c) for every c ∈ Σ |
| q₀ | q0 |
| F | {q0} |

It has one state and 57 transitions (all of them loops), so it is the identity transducer of
the slides except that it writes lower-case letters. Its domain is Σ\*: a token with a
character outside Σ (`Pythön`, `C$`, `🙂`) is rejected, and so is the empty token (`fold_case`
returns `None`).

Example: `React.js` is read as R:r, e:e, a:a, c:c, t:t, ".":".", j:j, s:s and the result is
`react.js`.

### 2.4 Family transducers T_family

Each family has a table *canonical name → accepted spellings* (`WEB_VARIANTS`, `AI_VARIANTS`,
`DB_VARIANTS`, `DEVOPS_VARIANTS`, `VCS_VARIANTS`, `LANGUAGE_VARIANTS`, `DATA_VARIANTS`). Let 𝒞
be its set of canonical names and S(C) the set of lower-case spellings of C ∈ 𝒞.
`build_transducer(variants)` builds M = (Q, Σ, Γ, δ, ω, q₀, F) with:

| Component | Value |
|---|---|
| Q | {q0} ∪ {f_C : C ∈ 𝒞} |
| Σ | ⋃ S(C) over C ∈ 𝒞: each element is a **complete** lower-case spelling (`react.js`, `spring boot`), not a character |
| Γ | 𝒞: each element is a complete canonical name (`NODE_JS`) |
| δ | δ(q0, s) = f_C for every C ∈ 𝒞 and s ∈ S(C); undefined elsewhere |
| ω | ω(q0, s) = C for every C ∈ 𝒞 and s ∈ S(C) |
| q₀ | q0 |
| F | {f_C : C ∈ 𝒞} = Q − {q0} |

Because the states f_C have no outgoing transitions, a word is accepted only if it has exactly
one symbol, and the language accepted by M is Σ itself, a **finite** language: the set of
spellings of the family. The translation is the function that sends each spelling s ∈ S(C) to
C. No spelling appears in two families and `SkillNormalizer` checks that no canonical name is
declared by two families, so the order in which the families are tried never changes the result.

The five properties of T = T_family ∘ T_case on a token w are:

- T(w) = C if and only if lower(w) ∈ S(C) and every character of w is in `INPUT_ALPHABET`.
- Case does not matter: `jAvAsCrIpT`, `JAVASCRIPT` and `javascript` give `JAVASCRIPT`.
- Spacing inside a name matters (`spring boot` is in Σ, `spring  boot` is not), except that the
  normalizer first trims the token and collapses runs of whitespace (`SkillNormalizer`).
- Partial matches are rejected: `Reactive`, `JavaScripts` and `Postgres 14` are not in Σ.
- A token that belongs to another family is rejected by this one (`Postgres` is rejected by the
  Web transducer and accepted by the database one).

Sizes of the seven transducers (|δ| is the number of different lower-case spellings):

| Family | Builder | \|Q\| | \|F\| = \|Γ\| | \|Σ\| = \|δ\| |
|---|---|---|---|---|
| Web / Frontend / Backend | `build_web_transducer` | 10 | 9 | 25 |
| AI / ML / data libraries | `build_ai_transducer` | 9 | 8 | 21 |
| Databases | `build_db_transducer` | 12 | 11 | 22 |
| Cloud / DevOps | `build_devops_transducer` | 9 | 8 | 14 |
| Version control | `build_vcs_transducer` | 2 | 1 | 4 |
| Programming languages | `build_language_transducer` | 12 | 11 | 15 |
| Data engineering | `build_data_transducer` | 3 | 2 | 5 |

The following tables give δ and ω: each row is a state f_C, the output C and the input symbols s
with δ(q0, s) = f_C and ω(q0, s) = C.

#### Web / Frontend / Backend

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_JAVASCRIPT | JAVASCRIPT | `js`, `javascript` |
| f_TYPESCRIPT | TYPESCRIPT | `ts`, `typescript` |
| f_REACT | REACT | `react`, `react.js`, `reactjs` |
| f_NODE_JS | NODE_JS | `node`, `node.js`, `nodejs` |
| f_ANGULAR | ANGULAR | `angular`, `angularjs`, `angular.js` |
| f_VUE | VUE | `vue`, `vue.js`, `vuejs` |
| f_SPRING_BOOT | SPRING_BOOT | `spring boot`, `springboot` |
| f_DJANGO | DJANGO | `django` |
| f_REST_API | REST_API | `rest`, `rest api`, `rest apis`, `restful`, `restful api`, `restful apis` |

#### AI / ML / data libraries

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_PANDAS | PANDAS | `pandas` |
| f_NUMPY | NUMPY | `numpy`, `num py` |
| f_SCIKIT_LEARN | SCIKIT_LEARN | `scikit-learn`, `scikit learn`, `scikitlearn`, `sklearn`, `sk-learn` |
| f_TENSORFLOW | TENSORFLOW | `tensorflow`, `tensor flow`, `tf` |
| f_PYTORCH | PYTORCH | `pytorch`, `py torch`, `torch` |
| f_KERAS | KERAS | `keras` |
| f_MATPLOTLIB | MATPLOTLIB | `matplotlib` |
| f_ML_MODEL_DEVELOPMENT | ML_MODEL_DEVELOPMENT | `machine-learning model development`, `machine learning model development`, `ml model development`, `machine learning`, `machine-learning` |

#### Databases

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_SQL | SQL | `sql` |
| f_NOSQL | NOSQL | `nosql` |
| f_POSTGRESQL | POSTGRESQL | `postgresql`, `postgres`, `postgre sql`, `psql` |
| f_MYSQL | MYSQL | `mysql`, `my sql` |
| f_MARIADB | MARIADB | `mariadb` |
| f_SQLITE | SQLITE | `sqlite`, `sqlite3` |
| f_SQL_SERVER | SQL_SERVER | `sql server`, `sqlserver`, `mssql`, `ms sql` |
| f_ORACLE | ORACLE | `oracle`, `oracle db` |
| f_MONGODB | MONGODB | `mongodb`, `mongo`, `mongo db` |
| f_REDIS | REDIS | `redis` |
| f_CASSANDRA | CASSANDRA | `cassandra` |

#### Cloud / DevOps

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_DOCKER | DOCKER | `docker` |
| f_KUBERNETES | KUBERNETES | `kubernetes`, `k8s`, `kube` |
| f_TERRAFORM | TERRAFORM | `terraform` |
| f_JENKINS | JENKINS | `jenkins` |
| f_ANSIBLE | ANSIBLE | `ansible` |
| f_AWS | AWS | `aws`, `amazon web services` |
| f_AZURE | AZURE | `azure`, `microsoft azure` |
| f_GCP | GCP | `gcp`, `google cloud`, `google cloud platform` |

#### Version control

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_GIT | GIT | `git`, `github`, `gitlab`, `bitbucket` |

#### Programming languages

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_PYTHON | PYTHON | `python`, `python3` |
| f_JAVA | JAVA | `java` |
| f_C | C | `c` |
| f_C_PLUS_PLUS | C_PLUS_PLUS | `c++`, `cpp` |
| f_C_SHARP | C_SHARP | `c#`, `csharp` |
| f_GO | GO | `go`, `golang` |
| f_RUST | RUST | `rust` |
| f_KOTLIN | KOTLIN | `kotlin` |
| f_SWIFT | SWIFT | `swift` |
| f_PHP | PHP | `php` |
| f_RUBY | RUBY | `ruby` |

JavaScript and TypeScript belong to the Web transducer, not to this one.

#### Data engineering

| State f_C | Output C | Input symbols s ∈ S(C) |
|---|---|---|
| f_SPARK | SPARK | `spark`, `apache spark`, `pyspark` |
| f_AIRFLOW | AIRFLOW | `airflow`, `apache airflow` |

### 2.5 Traces

| Token | T_case | T_family | Result |
|---|---|---|---|
| `JS` | `js` | q0 —js:JAVASCRIPT→ f_JAVASCRIPT ∈ F | `JAVASCRIPT` |
| `React.js` | `react.js` | q0 —react.js:REACT→ f_REACT ∈ F | `REACT` |
| `Postgres` | `postgres` | q0 —postgres:POSTGRESQL→ f_POSTGRESQL ∈ F | `POSTGRESQL` |
| `K8s` | `k8s` | q0 —k8s:KUBERNETES→ f_KUBERNETES ∈ F | `KUBERNETES` |
| `Reactive` | `reactive` | no transition from q0 with `reactive` | rejected |
| `Pythön` | `ö` ∉ Σ: no transition | not reached | rejected |
| `Rust$` | `$` ∉ Σ: no transition | not reached | rejected |

The normalizer (`SkillNormalizer` in `normalizer.py`) offers the token to the seven family
transducers in a fixed order and keeps the first translation. It assigns to the canonical name a
**category** (`SkillRecord.category`) that is not produced by the transducer but by a table
(`WEB_CATEGORIES`, `AI_CATEGORIES`, `DEVOPS_CATEGORIES`, `DATA_CATEGORIES`, or one fixed
category for databases, version control and languages). Then it removes repeated canonical
names, keeping the first occurrence. Tokens rejected by all the transducers are reported as
*unrecognized* and do not continue to Stage 3.

### 2.6 Canonical order

The sorter (`sorter.py`) makes the sequence read by the automata of Stage 3 independent of the
order in which the candidate wrote the skills. For a profile P let (k₁, …, kₘ) be its **slots**
(`PROFILE_SLOTS`): each slot is a category and corresponds to one item of the qualification
list of the profile (for example, Full Stack: `web_language`, `frontend`, `backend`,
`database`, `api`, `vcs`). Let pos_P(k) be the index of k in the list of slots. For a record r
with category k(r) and canonical name n(r), the sorting key is:

- key_P(r) = (0, pos_P(k(r)), n(r)) if k(r) is a slot of P (**profile part**);
- key_P(r) = (1, k(r), n(r)) otherwise (**remaining part**, noise for this profile).

Keys are compared lexicographically, with the natural order of integers and of strings
(alphabetical). `sort_records_by_profile` sorts the records with key_P. Since n is injective on
a de-duplicated list, key_P is a total order, and therefore:

1. the output is a **permutation** of the input;
2. the output depends only on the **set** of records, not on their order in the input;
3. the profile part comes first, slot by slot; inside a slot the names are alphabetical, so a
   slot with several skills (`NUMPY` and `PANDAS`) is also deterministic;
4. a slot without skills is skipped: the order of the other slots is not altered;
5. sorting an already sorted list does not change it (idempotence).

Example of the assignment, Full Stack: `Git, NodeJS, JS, Postgres, React.js` is normalized to
{GIT, NODE_JS, JAVASCRIPT, POSTGRESQL, REACT} and sorted to `JAVASCRIPT, REACT, NODE_JS,
POSTGRESQL, GIT`. An unknown profile name raises `UnknownProfileError`.

The properties 1–5 and the examples of this section are verified by `tests/test_normalization.py`
(transducers and normalizer) and `tests/test_sorter.py` (canonical order).
