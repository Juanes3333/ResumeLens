"""Stage 2 — Finite-state transducers for the Web / Frontend / Backend stack.

A finite-state transducer (FST) is the 7-tuple ``M = (Q, Sigma, Gamma, delta, omega, q0, F)``:

* ``Q``      finite set of states;
* ``Sigma``  input alphabet (here: single characters plus one end-of-token marker);
* ``Gamma``  output alphabet (here: canonical technology names);
* ``delta``  transition function, ``delta(q, u) -> (q', v)`` written ``u:v``;
* ``omega``  output produced when the input ends in a final state;
* ``q0``     initial state;
* ``F``      set of final states.

``pyformlang.fst.FST`` has no separate ``omega``: all output is attached to transitions.
The role of ``omega`` is therefore played by an explicit end-of-token symbol
(:data:`END_OF_TOKEN`). The canonical name is emitted by the transition that reads that
symbol, which guarantees that a variant that is a prefix of another one (``react`` and
``react.js``) is translated correctly: nothing is output until the whole token was read.

The transducer is built as a *trie*: one path of character-level transitions per variant,
with shared prefixes. Matching is case-insensitive because every letter has an upper-case
and a lower-case transition that lead to the same state.

The module defines one transducer per technology family (Web, AI / data libraries,
databases and Cloud / DevOps tools), all produced by :func:`build_transducer`.
"""

from functools import lru_cache
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from pyformlang.fst import FST

#: Input symbol that closes a token. It has more than one character, so it can never be
#: confused with a character of the token itself.
END_OF_TOKEN: str = "<EOS>"

#: Name of the initial state ``q0`` of every transducer built by this module.
INITIAL_STATE: str = "q0"

#: Canonical name -> accepted spellings. Case is ignored by the transducer, so each
#: spelling is listed once (``"JS"`` also covers ``js`` and ``Js``).
WEB_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "JAVASCRIPT": ("JS", "JavaScript"),
    "TYPESCRIPT": ("TS", "TypeScript"),
    "REACT": ("React", "React.js", "ReactJS"),
    "NODE_JS": ("Node", "Node.js", "NodeJS"),
    "ANGULAR": ("Angular", "AngularJS", "Angular.js"),
    "VUE": ("Vue", "Vue.js", "VueJS"),
    "SPRING_BOOT": ("Spring Boot", "SpringBoot"),
    "DJANGO": ("Django",),
}

#: Canonical names produced by the Web transducer.
WEB_CANONICAL_FORMS: Tuple[str, ...] = tuple(WEB_VARIANTS)

#: Artificial-intelligence, machine-learning and data-processing libraries.
AI_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "PANDAS": ("Pandas",),
    "NUMPY": ("NumPy", "Num Py"),
    "SCIKIT_LEARN": ("Scikit-learn", "Scikit learn", "Scikitlearn", "sklearn", "sk-learn"),
    "TENSORFLOW": ("TensorFlow", "Tensor Flow", "TF"),
    "PYTORCH": ("PyTorch", "Py Torch", "Torch"),
    "KERAS": ("Keras",),
    "MATPLOTLIB": ("Matplotlib",),
}

#: Canonical names produced by the AI transducer.
AI_CANONICAL_FORMS: Tuple[str, ...] = tuple(AI_VARIANTS)

#: Relational and NoSQL databases.
DB_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "SQL": ("SQL",),
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


def _case_variants(char: str) -> List[str]:
    """Return the distinct lower-case and upper-case forms of a single character."""
    forms = [char.lower()]
    upper = char.upper()
    if len(upper) == 1 and upper != forms[0]:
        forms.append(upper)
    return forms


def build_transducer(variants: Mapping[str, Iterable[str]]) -> FST:
    """Build a deterministic, case-insensitive FST from a ``canonical -> variants`` table.

    Construction:

    1. ``q0`` is the initial state and the root of a trie. Each variant is read character
       by character; the transition for character ``c`` outputs nothing (``c:epsilon``).
       Both the lower-case and the upper-case form of ``c`` lead to the same state.
    2. After its last character, a variant reaches a state with one transition on
       :data:`END_OF_TOKEN` towards the final state of its canonical name; that transition
       outputs the canonical name (``<EOS>:CANONICAL``).
    3. There is one final state per canonical name, called ``f_<CANONICAL>``.

    Args:
        variants: Mapping from canonical name to the spellings that must be normalized
            to it.

    Returns:
        The transducer. A token outside the language of the table has no translation.

    Raises:
        ValueError: If a canonical name or a variant is empty, or if the same spelling
            (ignoring case) is assigned to two different canonical names.
    """
    child: Dict[Tuple[str, str], str] = {}
    end_output: Dict[str, str] = {}
    next_id = 1

    for canonical, spellings in variants.items():
        if not canonical:
            raise ValueError("Canonical names must be non-empty.")
        for spelling in spellings:
            if not spelling:
                raise ValueError(f"Empty variant for canonical name {canonical!r}.")
            state = INITIAL_STATE
            for char in spelling.lower():
                key = (state, char)
                if key not in child:
                    child[key] = f"q{next_id}"
                    next_id += 1
                state = child[key]
            previous = end_output.get(state)
            if previous is not None and previous != canonical:
                raise ValueError(
                    f"Variant {spelling!r} maps to both {previous!r} and {canonical!r}."
                )
            end_output[state] = canonical

    transitions: List[Tuple[str, str, str, List[str]]] = []
    for (source, char), target in child.items():
        for form in _case_variants(char):
            transitions.append((source, form, target, []))

    final_states: Set[str] = set()
    for state, canonical in end_output.items():
        final_state = f"f_{canonical}"
        final_states.add(final_state)
        transitions.append((state, END_OF_TOKEN, final_state, [canonical]))

    fst = FST()
    fst.add_start_state(INITIAL_STATE)
    for final_state in sorted(final_states):
        fst.add_final_state(final_state)
    fst.add_transitions(transitions)
    return fst


def build_web_transducer() -> FST:
    """Build the transducer of the Web / Frontend / Backend stack (:data:`WEB_VARIANTS`)."""
    return build_transducer(WEB_VARIANTS)


@lru_cache(maxsize=1)
def get_web_transducer() -> FST:
    """Return the shared Web transducer, built on first use. Callers must not modify it."""
    return build_web_transducer()


def build_ai_transducer() -> FST:
    """Build the transducer of AI / ML / data libraries (:data:`AI_VARIANTS`)."""
    return build_transducer(AI_VARIANTS)


def build_db_transducer() -> FST:
    """Build the transducer of databases (:data:`DB_VARIANTS`)."""
    return build_transducer(DB_VARIANTS)


def build_devops_transducer() -> FST:
    """Build the transducer of Cloud / DevOps tools (:data:`DEVOPS_VARIANTS`)."""
    return build_transducer(DEVOPS_VARIANTS)


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


def apply_transducer(fst: FST, token: str) -> Optional[str]:
    """Translate ``token`` with ``fst`` and return the canonical string.

    The token is fed to the transducer one character at a time, followed by
    :data:`END_OF_TOKEN`.

    Returns:
        The canonical name, or ``None`` if the transducer does not accept the token.

    Raises:
        ValueError: If the transducer produces more than one different translation, that
            is, if it is not deterministic on this token.
    """
    translations = {"".join(output) for output in fst.translate(list(token) + [END_OF_TOKEN])}
    if not translations:
        return None
    if len(translations) > 1:
        raise ValueError(f"Ambiguous translation for {token!r}: {sorted(translations)}")
    return translations.pop()


def normalize_web_skill(token: str) -> Optional[str]:
    """Normalize one raw skill token of the Web stack to its canonical name.

    Leading and trailing whitespace is ignored and letter case does not matter.

    Examples:
        ``"JS"`` -> ``"JAVASCRIPT"``, ``"React.js"`` -> ``"REACT"``,
        ``"NodeJS"`` -> ``"NODE_JS"``, ``"Spring Boot"`` -> ``"SPRING_BOOT"``.

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
