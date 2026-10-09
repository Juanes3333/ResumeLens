"""Stage 2 — Finite-state transducers that normalize technology names.

Following the course definition, a deterministic FST is the 7-tuple
``M = (Q, Sigma, Gamma, delta, omega, q0, F)``:

* ``Q``      finite set of states;
* ``Sigma``  finite input alphabet;
* ``Gamma``  finite output alphabet;
* ``delta``  transition function ``Q x (Sigma U {lambda}) -> Q``;
* ``omega``  output function ``Q x (Sigma U {lambda}) -> Gamma*``;
* ``q0``     initial state;
* ``F``      set of accepting states.

``pyformlang.fst.FST`` stores ``delta`` and ``omega`` together: every transition
``(q, u, q', [v])`` means ``delta(q, u) = q'`` and ``omega(q, u) = v``, drawn ``u:v``.

Normalization is the composition of two transducers, as in the class examples:

1. **Case folding** :math:`T_{case}` — one state ``q0``, initial and accepting, with a
   loop ``c:lower(c)`` for every character ``c`` of :data:`INPUT_ALPHABET` (the identity
   transducer of the slides, but writing lower-case letters). It reads the token one
   character at a time and rejects tokens with characters outside the alphabet.
2. **Family transducer** :math:`T_{family}` — the "whole word" construction of the
   slides (``('q1', 'ar', 'q2', ['o'])`` with ``translate(['llor', 'ar'])``): its input
   symbols are complete lower-case spellings, so each transition ``variant:CANONICAL``
   goes from ``q0`` to the accepting state ``f_<CANONICAL>`` of its canonical name.

So ``JS`` is first folded to ``js`` and then translated by ``js:JAVASCRIPT``. A token is
recognized only if both transducers accept it.

There is one family transducer per technology family: Web, AI / data libraries,
databases, Cloud / DevOps, version control, programming languages and data engineering.
"""

from functools import lru_cache
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple

from pyformlang.fst import FST

#: Name of the initial state ``q0`` of every transducer built by this module.
INITIAL_STATE: str = "q0"

#: Canonical name -> accepted spellings. Case is ignored (the case-folding transducer
#: runs first), so each spelling is listed once (``"JS"`` also covers ``js`` and ``Js``).
WEB_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "JAVASCRIPT": ("JS", "JavaScript"),
    "TYPESCRIPT": ("TS", "TypeScript"),
    "REACT": ("React", "React.js", "ReactJS"),
    "NODE_JS": ("Node", "Node.js", "NodeJS"),
    "ANGULAR": ("Angular", "AngularJS", "Angular.js"),
    "VUE": ("Vue", "Vue.js", "VueJS"),
    "SPRING_BOOT": ("Spring Boot", "SpringBoot"),
    "DJANGO": ("Django",),
    "REST_API": ("REST", "REST API", "REST APIs", "RESTful", "RESTful API", "RESTful APIs"),
}

#: Canonical names produced by the Web transducer.
WEB_CANONICAL_FORMS: Tuple[str, ...] = tuple(WEB_VARIANTS)

#: Artificial-intelligence, machine-learning and data-processing libraries, plus the
#: machine-learning practice listed by the Machine Learning Engineer profile.
AI_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "PANDAS": ("Pandas",),
    "NUMPY": ("NumPy", "Num Py"),
    "SCIKIT_LEARN": ("Scikit-learn", "Scikit learn", "Scikitlearn", "sklearn", "sk-learn"),
    "TENSORFLOW": ("TensorFlow", "Tensor Flow", "TF"),
    "PYTORCH": ("PyTorch", "Py Torch", "Torch"),
    "KERAS": ("Keras",),
    "MATPLOTLIB": ("Matplotlib",),
    "ML_MODEL_DEVELOPMENT": (
        "Machine-learning model development",
        "Machine learning model development",
        "ML model development",
        "Machine learning",
        "Machine-learning",
    ),
}

#: Canonical names produced by the AI transducer.
AI_CANONICAL_FORMS: Tuple[str, ...] = tuple(AI_VARIANTS)

#: Relational and NoSQL databases.
DB_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "SQL": ("SQL",),
    "NOSQL": ("NoSQL",),
    "POSTGRESQL": ("PostgreSQL", "Postgres", "Postgre SQL", "PSQL"),
    "MYSQL": ("MySQL", "My SQL"),
    "MARIADB": ("MariaDB",),
    "SQLITE": ("SQLite", "SQLite3"),
    "SQL_SERVER": ("SQL Server", "SQLServer", "MSSQL", "MS SQL"),
    "ORACLE": ("Oracle", "Oracle DB"),
    "MONGODB": ("MongoDB", "Mongo", "Mongo DB"),
    "REDIS": ("Redis",),
    "CASSANDRA": ("Cassandra",),
}

#: Canonical names produced by the database transducer.
DB_CANONICAL_FORMS: Tuple[str, ...] = tuple(DB_VARIANTS)

#: Cloud, containerization, infrastructure-as-code and CI/CD tools.
DEVOPS_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "DOCKER": ("Docker",),
    "KUBERNETES": ("Kubernetes", "K8s", "Kube"),
    "TERRAFORM": ("Terraform",),
    "JENKINS": ("Jenkins",),
    "ANSIBLE": ("Ansible",),
    "AWS": ("AWS", "Amazon Web Services"),
    "AZURE": ("Azure", "Microsoft Azure"),
    "GCP": ("GCP", "Google Cloud", "Google Cloud Platform"),
}

#: Canonical names produced by the Cloud / DevOps transducer.
DEVOPS_CANONICAL_FORMS: Tuple[str, ...] = tuple(DEVOPS_VARIANTS)

#: Version-control tools and Git hosting platforms, all normalized to ``GIT``.
VCS_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "GIT": ("Git", "GitHub", "GitLab", "Bitbucket"),
}

#: Canonical names produced by the version-control transducer.
VCS_CANONICAL_FORMS: Tuple[str, ...] = tuple(VCS_VARIANTS)

#: General-purpose programming languages. JavaScript and TypeScript belong to the Web
#: transducer.
LANGUAGE_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "PYTHON": ("Python", "Python3"),
    "JAVA": ("Java",),
    "C": ("C",),
    "C_PLUS_PLUS": ("C++", "CPP"),
    "C_SHARP": ("C#", "CSharp"),
    "GO": ("Go", "Golang"),
    "RUST": ("Rust",),
    "KOTLIN": ("Kotlin",),
    "SWIFT": ("Swift",),
    "PHP": ("PHP",),
    "RUBY": ("Ruby",),
}

#: Canonical names produced by the programming-language transducer.
LANGUAGE_CANONICAL_FORMS: Tuple[str, ...] = tuple(LANGUAGE_VARIANTS)

#: Data-engineering tools.
DATA_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "SPARK": ("Spark", "Apache Spark", "PySpark"),
    "AIRFLOW": ("Airflow", "Apache Airflow"),
}

#: Canonical names produced by the data-engineering transducer.
DATA_CANONICAL_FORMS: Tuple[str, ...] = tuple(DATA_VARIANTS)

#: Every family table, by family label, in the order the normalizer tries them.
FAMILY_VARIANTS: Mapping[str, Mapping[str, Tuple[str, ...]]] = {
    "web": WEB_VARIANTS,
    "ai": AI_VARIANTS,
    "database": DB_VARIANTS,
    "devops": DEVOPS_VARIANTS,
    "vcs": VCS_VARIANTS,
    "language": LANGUAGE_VARIANTS,
    "data": DATA_VARIANTS,
}


def _case_forms(char: str) -> List[str]:
    """Return the distinct lower-case and upper-case forms of a single character."""
    forms = [char.lower()]
    upper = char.upper()
    if len(upper) == 1 and upper != forms[0]:
        forms.append(upper)
    return forms


def _alphabet_of(tables: Iterable[Mapping[str, Iterable[str]]]) -> FrozenSet[str]:
    """Characters of every spelling of ``tables``, in lower and upper case."""
    chars: Set[str] = set()
    for table in tables:
        for spellings in table.values():
            for spelling in spellings:
                for char in spelling:
                    chars.update(_case_forms(char))
    return frozenset(chars)


#: Input alphabet of the case-folding transducer: the characters (in both cases) that
#: appear in some spelling of some family. Any other character makes a token rejected.
INPUT_ALPHABET: FrozenSet[str] = _alphabet_of(FAMILY_VARIANTS.values())


def build_case_folding_transducer(alphabet: Iterable[str] = INPUT_ALPHABET) -> FST:
    """Build the one-state transducer that writes every character in lower case.

    ``Q = F = {q0}``; for each ``c`` in ``alphabet`` there is the loop
    ``delta(q0, c) = q0`` with output ``omega(q0, c) = lower(c)``.
    """
    fst = FST()
    fst.add_start_state(INITIAL_STATE)
    fst.add_final_state(INITIAL_STATE)
    fst.add_transitions(
        [(INITIAL_STATE, char, INITIAL_STATE, [char.lower()]) for char in sorted(set(alphabet))]
    )
    return fst


@lru_cache(maxsize=1)
def get_case_folding_transducer() -> FST:
    """Return the shared case-folding transducer. Callers must not modify it."""
    return build_case_folding_transducer()


def fold_case(token: str) -> Optional[str]:
    """Run ``token`` through the case-folding transducer, one character per symbol.

    Returns:
        The token in lower case, or ``None`` if it is empty or has a character outside
        :data:`INPUT_ALPHABET`.
    """
    if not token:
        return None
    outputs = list(get_case_folding_transducer().translate(list(token)))
    if not outputs:
        return None
    return "".join(outputs[0])


def final_state_of(canonical: str) -> str:
    """Name of the accepting state of a canonical name (``f_<CANONICAL>``)."""
    return f"f_{canonical}"


def build_transducer(variants: Mapping[str, Iterable[str]]) -> FST:
    """Build the deterministic family transducer of a ``canonical -> spellings`` table.

    ``Q = {q0} U {f_C | C canonical}``, ``F = Q - {q0}``, ``Sigma`` = the lower-case
    spellings and ``Gamma`` = the canonical names. Each spelling ``s`` of ``C`` adds the
    transition ``(q0, lower(s), f_C, [C])``, i.e. ``s:C``.

    Raises:
        ValueError: If a canonical name or a spelling is empty, or if the same spelling
            (ignoring case) is assigned to two different canonical names, which would make
            the transducer non-deterministic.
    """
    owner: Dict[str, str] = {}
    transitions: List[Tuple[str, str, str, List[str]]] = []
    final_states: Set[str] = set()
    for canonical, spellings in variants.items():
        if not canonical:
            raise ValueError("Canonical names must be non-empty.")
        for spelling in spellings:
            if not spelling:
                raise ValueError(f"Empty variant for canonical name {canonical!r}.")
            symbol = spelling.lower()
            previous = owner.get(symbol)
            if previous is not None and previous != canonical:
                raise ValueError(
                    f"Variant {spelling!r} maps to both {previous!r} and {canonical!r}."
                )
            if previous is None:
                owner[symbol] = canonical
                transitions.append((INITIAL_STATE, symbol, final_state_of(canonical), [canonical]))
                final_states.add(final_state_of(canonical))

    fst = FST()
    fst.add_start_state(INITIAL_STATE)
    for final_state in sorted(final_states):
        fst.add_final_state(final_state)
    fst.add_transitions(transitions)
    return fst


def apply_transducer(fst: FST, token: str) -> Optional[str]:
    """Translate ``token`` with the composition ``T_case`` then ``fst``.

    The token is folded to lower case by :func:`fold_case` and the result is given to
    ``fst`` as a single input symbol.

    Returns:
        The canonical name, or ``None`` if either transducer rejects the token.

    Raises:
        ValueError: If ``fst`` produces more than one different translation, that is, if
            it is not deterministic on this token.
    """
    folded = fold_case(token)
    if folded is None:
        return None
    translations = {"".join(output) for output in fst.translate([folded])}
    if not translations:
        return None
    if len(translations) > 1:
        raise ValueError(f"Ambiguous translation for {token!r}: {sorted(translations)}")
    return translations.pop()


def build_web_transducer() -> FST:
    """Build the transducer of the Web / Frontend / Backend stack (:data:`WEB_VARIANTS`)."""
    return build_transducer(WEB_VARIANTS)


def build_ai_transducer() -> FST:
    """Build the transducer of AI / ML / data libraries (:data:`AI_VARIANTS`)."""
    return build_transducer(AI_VARIANTS)


def build_db_transducer() -> FST:
    """Build the transducer of databases (:data:`DB_VARIANTS`)."""
    return build_transducer(DB_VARIANTS)


def build_devops_transducer() -> FST:
    """Build the transducer of Cloud / DevOps tools (:data:`DEVOPS_VARIANTS`)."""
    return build_transducer(DEVOPS_VARIANTS)


def build_vcs_transducer() -> FST:
    """Build the transducer of version-control tools (:data:`VCS_VARIANTS`)."""
    return build_transducer(VCS_VARIANTS)


def build_language_transducer() -> FST:
    """Build the transducer of programming languages (:data:`LANGUAGE_VARIANTS`)."""
    return build_transducer(LANGUAGE_VARIANTS)


def build_data_transducer() -> FST:
    """Build the transducer of data-engineering tools (:data:`DATA_VARIANTS`)."""
    return build_transducer(DATA_VARIANTS)


@lru_cache(maxsize=1)
def get_web_transducer() -> FST:
    """Return the shared Web transducer, built on first use. Callers must not modify it."""
    return build_web_transducer()


@lru_cache(maxsize=1)
def get_ai_transducer() -> FST:
    """Return the shared AI transducer, built on first use. Callers must not modify it."""
    return build_ai_transducer()


@lru_cache(maxsize=1)
def get_db_transducer() -> FST:
    """Return the shared database transducer, built on first use. Callers must not modify it."""
    return build_db_transducer()


@lru_cache(maxsize=1)
def get_devops_transducer() -> FST:
    """Return the shared Cloud / DevOps transducer, built on first use. Callers must not modify it."""
    return build_devops_transducer()


@lru_cache(maxsize=1)
def get_vcs_transducer() -> FST:
    """Return the shared version-control transducer, built on first use."""
    return build_vcs_transducer()


@lru_cache(maxsize=1)
def get_language_transducer() -> FST:
    """Return the shared programming-language transducer, built on first use."""
    return build_language_transducer()


@lru_cache(maxsize=1)
def get_data_transducer() -> FST:
    """Return the shared data-engineering transducer, built on first use."""
    return build_data_transducer()


def normalize_web_skill(token: str) -> Optional[str]:
    """Normalize one raw skill token of the Web stack to its canonical name.

    Leading and trailing whitespace is ignored and letter case does not matter.

    Examples:
        ``"JS"`` -> ``"JAVASCRIPT"``, ``"React.js"`` -> ``"REACT"``,
        ``"NodeJS"`` -> ``"NODE_JS"``, ``"REST APIs"`` -> ``"REST_API"``.

    Returns:
        The canonical name, or ``None`` if the token is not a Web-stack technology.
    """
    return apply_transducer(get_web_transducer(), token.strip())


def normalize_ai_skill(token: str) -> Optional[str]:
    """Normalize one raw token of the AI / data libraries to its canonical name.

    Examples:
        ``"sklearn"`` -> ``"SCIKIT_LEARN"``, ``"NumPy"`` -> ``"NUMPY"``.

    Returns:
        The canonical name, or ``None`` if the token is not an AI library.
    """
    return apply_transducer(get_ai_transducer(), token.strip())


def normalize_db_skill(token: str) -> Optional[str]:
    """Normalize one raw database token to its canonical name.

    Examples:
        ``"Postgres"`` -> ``"POSTGRESQL"``, ``"Mongo"`` -> ``"MONGODB"``.

    Returns:
        The canonical name, or ``None`` if the token is not a known database.
    """
    return apply_transducer(get_db_transducer(), token.strip())


def normalize_devops_skill(token: str) -> Optional[str]:
    """Normalize one raw Cloud / DevOps token to its canonical name.

    Examples:
        ``"K8s"`` -> ``"KUBERNETES"``, ``"Google Cloud"`` -> ``"GCP"``.

    Returns:
        The canonical name, or ``None`` if the token is not a Cloud / DevOps tool.
    """
    return apply_transducer(get_devops_transducer(), token.strip())


def normalize_vcs_skill(token: str) -> Optional[str]:
    """Normalize one raw version-control token (``"GitHub"`` -> ``"GIT"``)."""
    return apply_transducer(get_vcs_transducer(), token.strip())


def normalize_language_skill(token: str) -> Optional[str]:
    """Normalize one raw programming-language token (``"Golang"`` -> ``"GO"``)."""
    return apply_transducer(get_language_transducer(), token.strip())


def normalize_data_skill(token: str) -> Optional[str]:
    """Normalize one raw data-engineering token (``"PySpark"`` -> ``"SPARK"``)."""
    return apply_transducer(get_data_transducer(), token.strip())
