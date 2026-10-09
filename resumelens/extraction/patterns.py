"""Stage 1 — Regular-expression patterns for ResumeLens.

This module only *defines and compiles* the patterns (``re.compile``); the extractor
(:mod:`resumelens.extraction.extractor`) applies them to the text of a resume.

Each pattern documents the language of strings it recognizes. All of them use named
groups ``(?P<name>...)`` so that the consumer can read the result with ``.groupdict()``.

Reusable fragments (plain strings, not compiled):
    YEAR   = (19|20) digit digit              -> L = {1900, ..., 2099}
    MONTH  = English month name or abbreviation (Jan, January, Sept, ...)
    DATE   = [MONTH [.] space] YEAR           -> "2023", "Mar 2023", "March 2023"
    RANGE  = DATE separator (DATE | Present)  -> "2019 - 2023", "Jan 2020 to Present"
             with separator ``-``, ``–``, ``—`` or the word ``to``.
"""

import re
from typing import Dict, Pattern

# ---------------------------------------------------------------------------
# Building fragments (plain strings)
# ---------------------------------------------------------------------------
_YEAR = r"(?:19|20)\d{2}"
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE = r"(?:" + _MONTH + r"\.?[ \t]+)?" + _YEAR
_OPEN_END = r"(?:Present|Current|Now|Ongoing)"
_SEPARATOR = r"[ \t]*(?:[-\u2013\u2014]|\bto\b)[ \t]*"
# start/end are named groups; each pattern uses this fragment only once.
_RANGE = r"(?P<start>" + _DATE + r")" + _SEPARATOR + r"(?P<end>" + _DATE + r"|" + _OPEN_END + r")\b"

_LEVEL = (
    r"(?P<level>(?:Bachelor|Master|Associate|Doctorate|Ph\.?D|MBA|BSc|MSc|"
    r"B\.?S|M\.?S|B\.?A|M\.?A|B\.?Eng|M\.?Eng)\.?)"
)
_DEGREE = (
    r"(?P<degree>" + _LEVEL + r"(?:[ \t]+of[ \t]+[A-Za-z]+)?"
    r"[ \t]+(?:in|of)[ \t]+(?P<field>[^\n,;(]*[^\s,;(]))"
)

# ---------------------------------------------------------------------------
# 1. CONTACT
# ---------------------------------------------------------------------------

#: Email address.
#: Language: user ([A-Za-z0-9._%+-]+) '@' domain with at least one dot and a TLD of
#: 2+ letters. E.g.: ``mj.watson@dailybugle.com``. Does not match ``juan.perez at mail``.
EMAIL_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<user>[A-Za-z0-9._%+-]+)@"
    r"(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b"
)

#: Phone number with a 3-3-4 digit structure (NANP / Colombian mobile format) and an
#: optional country prefix. Allowed separators: space, dot or hyphen; the area code may
#: be wrapped in parentheses. E.g.: ``+1 555 123 4567``, ``(555) 123-4567``,
#: ``+57 300 123 4567``. Year strings such as ``2019 - 2023`` are not in the language.
PHONE_PATTERN: Pattern[str] = re.compile(
    r"(?:(?P<country>\+\d{1,3})[ .-]?)?"
    r"\(?\b(?P<area>\d{3})\)?[ .-]?"
    r"(?P<prefix>\d{3})[ .-]?"
    r"(?P<line>\d{4})\b"
)

#: Generic http/https URL: scheme, host with at least one dot, and an optional path.
#: A sentence-ending period is not included in the path.
URL_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<scheme>https?)://"
    r"(?P<host>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"
    r"(?P<path>(?:/[\w%~+-]+(?:\.[\w%~+-]+)*)*)",
    re.IGNORECASE,
)

#: LinkedIn profile: ``https://[www.]linkedin.com/(in|company)/<handle>``.
LINKEDIN_URL_PATTERN: Pattern[str] = re.compile(
    r"\bhttps?://(?P<host>(?:www\.)?linkedin\.com)/(?P<kind>in|company)/"
    r"(?P<handle>[\w%-]+)",
    re.IGNORECASE,
)

#: GitHub profile or repository: ``https://[www.]github.com/<user>[/<repo>]``.
GITHUB_URL_PATTERN: Pattern[str] = re.compile(
    r"\bhttps?://(?P<host>(?:www\.)?github\.com)/(?P<user>[\w-]+)"
    r"(?:/(?P<repo>[\w-]+(?:\.[\w-]+)*))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 2. STRUCTURE
# ---------------------------------------------------------------------------

#: Section header: a line holding a keyword followed by ``:``.
#: E.g.: ``Contact:``, ``Technical Skills:``, ``Education:``, ``Experience:``.
SECTION_HEADER_PATTERN: Pattern[str] = re.compile(
    r"^[ \t]*(?P<title>Contact|Summary|Technical Skills|Skills|Education|"
    r"Experience|Work Experience|Projects|Certifications)[ \t]*:[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 3. EDUCATION
# ---------------------------------------------------------------------------

#: Date range or period (``2019 - 2023``, ``Jan 2020 to Present``).
DATE_RANGE_PATTERN: Pattern[str] = re.compile(r"\b" + _RANGE, re.IGNORECASE)

#: Academic degree on a single line: level (B.S., M.S., Ph.D., Bachelor, Master, MBA...)
#: followed by ``in``/``of`` and the field of study. E.g.: ``B.S. in Computer Science``
#: -> level=``B.S.``, field=``Computer Science``.
DEGREE_PATTERN: Pattern[str] = re.compile(r"\b" + _DEGREE)

#: Institution by keyword: ``<Capitalized names> University|Institute|College|
#: School|Academy|Polytechnic|Tech``, ``University of <Name>`` or ``Universidad <Name>``.
INSTITUTION_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<institution>"
    r"University[ \t]+of[ \t]+[A-Z][\w&'-]*(?:[ \t]+[A-Z][\w&'-]*)*"
    r"|Universidad[ \t]+(?:de[ \t]+(?:la[ \t]+)?)?[A-Z][\w&'-]*"
    r"|(?:[A-Z][\w&'-]*[ \t]+)*(?:University|Institute|College|School|Academy|"
    r"Polytechnic|Tech)\b"
    r")"
)

#: Two-line education record:
#:     <degree>\n<institution> (<start> - <end>)   or   <institution> (<graduation year>)
#: E.g.: ``B.S. in Computer Science\nNevermore University (2019 - 2023)``.
EDUCATION_ENTRY_PATTERN: Pattern[str] = re.compile(
    r"^[ \t]*" + _DEGREE + r"[ \t]*\n"
    r"[ \t]*(?P<institution>[^\n(]+?)[ \t]*"
    r"\((?:" + _RANGE + r"|(?P<graduation>" + _YEAR + r"))\)",
    re.MULTILINE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 4. TECHNICAL SKILLS
# ---------------------------------------------------------------------------

#: Programming languages commonly used in the supported professional profiles.
#: The language recognizes canonical names and common textual variants, ignoring case.
#: ``Go`` and ``C`` / ``C++`` / ``C#`` are case-sensitive (``(?-i:...)``) so that the
#: English word "go" or a stray letter "c" in free text are not reported as languages.
#: The look-behind ``(?<![\w.])`` rejects the ``js`` of ``Node.js`` / ``React.js``.
PROGRAMMING_LANGUAGE_PATTERN: Pattern[str] = re.compile(
    r"(?<![\w.])(?P<skill>"
    r"Python|JavaScript|JS|TypeScript|TS|Java|Golang|Rust|Kotlin|Swift|PHP|Ruby|"
    r"(?-i:Go|C\+\+|C#|C(?![+#]))"
    r")(?!\w)",
    re.IGNORECASE,
)

#: Frontend and backend frameworks commonly appearing in technical resumes.
FRAMEWORK_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"React(?:\.js|JS)?|Angular(?:\.js)?|Vue(?:\.js)?|"
    r"Node(?:\.js|JS)?|Django|Spring[ \t]+Boot|Express(?:\.js)?|"
    r"Next(?:\.js|JS)?|Flask|FastAPI|Laravel"
    r")\b",
    re.IGNORECASE,
)

#: Machine-learning and data-processing libraries relevant to ResumeLens.
ML_LIBRARY_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"Pandas|NumPy|Scikit[- ]learn|sklearn|Keras|Matplotlib|"
    r"TensorFlow|Tensor[ \t]+Flow|PyTorch|Py[ \t]+Torch"
    r")\b",
    re.IGNORECASE,
)

#: Relational and NoSQL database technologies, plus the query language ``SQL`` and the
#: generic term ``NoSQL``. ``\b`` keeps the ``SQL`` inside ``MySQL`` / ``PostgreSQL``
#: from being reported on its own.
DATABASE_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"PostgreSQL|Postgres|MySQL|MariaDB|Oracle|SQLite|"
    r"SQL[ \t]+Server|MongoDB|Mongo|Redis|Cassandra|NoSQL|SQL"
    r")\b",
    re.IGNORECASE,
)

#: Version-control platforms and tools.
VERSION_CONTROL_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"Git|GitHub|GitLab|Bitbucket"
    r")\b",
    re.IGNORECASE,
)

#: DevOps and cloud technologies relevant to the supported profiles.
DEVOPS_CLOUD_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"Docker|Kubernetes|Terraform|Jenkins|Ansible|"
    r"AWS|Amazon[ \t]+Web[ \t]+Services|"
    r"Azure|Microsoft[ \t]+Azure|"
    r"GCP|Google[ \t]+Cloud(?:[ \t]+Platform)?"
    r")\b",
    re.IGNORECASE,
)

#: Data-engineering tools (distributed processing and workflow orchestration).
#: E.g.: ``Apache Spark``, ``PySpark``, ``Airflow``.
DATA_TOOL_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"(?:Apache[ \t]+)?Spark|PySpark|(?:Apache[ \t]+)?Airflow"
    r")\b",
    re.IGNORECASE,
)

#: REST web APIs. Case-sensitive on purpose: ``REST`` / ``RESTful`` are acronyms, while
#: the English word "rest" must not be captured.
#: E.g.: ``REST``, ``REST API``, ``REST APIs``, ``RESTful APIs``.
API_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>REST(?:ful)?(?:[ \t]+APIs?)?)\b"
)

#: Machine-learning practice listed by the Machine Learning Engineer profile.
#: E.g.: ``Machine-learning model development``, ``ML model development``,
#: ``machine learning``. The job title ``Machine Learning Engineer`` is not a practice,
#: so a following ``Engineer`` is rejected by the look-ahead.
ML_PRACTICE_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<skill>"
    r"Machine[- ]learning(?:[ \t]+model[ \t]+development)?|ML[ \t]+model[ \t]+development"
    r")\b(?![ \t]+Engineer)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 5. CAREER / EXPERIENCE
# ---------------------------------------------------------------------------

#: Declared years of experience: ``<n>[+] years of [professional] experience
#: [<activity>]``. E.g.: ``3 years of experience developing web applications.``
#: -> years=``3``, activity=``developing web applications``.
YEARS_EXPERIENCE_PATTERN: Pattern[str] = re.compile(
    r"\b(?P<years>\d{1,2})(?P<plus>\+)?[ \t]+years?[ \t]+of[ \t]+"
    r"(?:professional[ \t]+)?experience\b"
    r"(?:[ \t]+(?P<activity>[^\n.]+))?",
    re.IGNORECASE,
)

#: Job entry: ``<role>, <company> (<start> - <end|Present>)``; the role/company
#: separator may be ``,``, ``at``, ``@`` or ``|``. Lines starting with a bullet
#: (``- ...``) are not in the language.
#: E.g.: ``Full Stack Developer, Raven Labs (2023 - 2026)``.
EXPERIENCE_ENTRY_PATTERN: Pattern[str] = re.compile(
    r"^[ \t]*(?P<role>[A-Za-z][^\n,()@|]*?)[ \t]*"
    r"(?:,|\bat\b|@|\|)[ \t]*"
    r"(?P<company>[^\n()]+?)[ \t]*"
    r"\(" + _RANGE + r"\)",
    re.MULTILINE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# 6. CANDIDATE NAME AND SKILL LIST
# ---------------------------------------------------------------------------

#: Candidate name on its own line: 2 to 4 words, each starting with an upper-case letter
#: (accented capitals included) and followed by letters of any alphabet (``[^\W\d_]``),
#: apostrophes, dots or hyphens. E.g.: ``Mary Jane Watson``, ``José Núñez``,
#: ``WEDNESDAY ADDAMS``. ``juan perez`` is not in the language.
NAME_PATTERN: Pattern[str] = re.compile(
    r"^(?P<name>[A-ZÁÉÍÓÚÑÜ](?:[^\W\d_]|['’.-])*"
    r"(?:[ \t]+[A-ZÁÉÍÓÚÑÜ](?:[^\W\d_]|['’.-])*){1,3})$"
)

#: Separator of the items of a skill list: comma, semicolon or line break. It is a
#: delimiter, not an extraction pattern, so it is not part of :data:`PATTERNS`.
SKILL_SEPARATOR_PATTERN: Pattern[str] = re.compile(r"[,;\n]")
#: Technical-skill patterns by type, in the order the extractor reports them.
SKILL_PATTERNS: Dict[str, Pattern[str]] = {
    "programming_language": PROGRAMMING_LANGUAGE_PATTERN,
    "framework": FRAMEWORK_PATTERN,
    "ml_library": ML_LIBRARY_PATTERN,
    "ml_practice": ML_PRACTICE_PATTERN,
    "database": DATABASE_PATTERN,
    "data_tool": DATA_TOOL_PATTERN,
    "api": API_PATTERN,
    "version_control": VERSION_CONTROL_PATTERN,
    "devops_cloud": DEVOPS_CLOUD_PATTERN,
}

#: Registry of all extraction patterns by name (useful for tests and for the extractor).
PATTERNS: Dict[str, Pattern[str]] = {
    "email": EMAIL_PATTERN,
    "phone": PHONE_PATTERN,
    "url": URL_PATTERN,
    "linkedin": LINKEDIN_URL_PATTERN,
    "github": GITHUB_URL_PATTERN,
    "section_header": SECTION_HEADER_PATTERN,
    "date_range": DATE_RANGE_PATTERN,
    "degree": DEGREE_PATTERN,
    "institution": INSTITUTION_PATTERN,
    "education_entry": EDUCATION_ENTRY_PATTERN,
    "programming_language": PROGRAMMING_LANGUAGE_PATTERN,
    "framework": FRAMEWORK_PATTERN,
    "ml_library": ML_LIBRARY_PATTERN,
    "database": DATABASE_PATTERN,
    "version_control": VERSION_CONTROL_PATTERN,
    "devops_cloud": DEVOPS_CLOUD_PATTERN,
    "years_experience": YEARS_EXPERIENCE_PATTERN,
    "experience_entry": EXPERIENCE_ENTRY_PATTERN,
    "data_tool": DATA_TOOL_PATTERN,
    "api": API_PATTERN,
    "ml_practice": ML_PRACTICE_PATTERN,
    "name": NAME_PATTERN,
}
