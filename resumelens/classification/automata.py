"""Stage 3 — Finite automata for the official profiles (Full Stack and Machine Learning).

A deterministic finite automaton (DFA) is the 5-tuple ``M = (Q, Sigma, delta, q0, F)``:

* ``Q``      finite set of states;
* ``Sigma``  input alphabet: here, the *canonical skill names* produced by Stage 2
  (``JAVASCRIPT``, ``REACT``, ``POSTGRESQL`` ...);
* ``delta``  transition function ``Q x Sigma -> Q`` (partial: a missing transition leads
  to an implicit dead state, so the word is rejected);
* ``q0``     initial state;
* ``F``      set of accepting states.

A profile is a sequence of *stages*, in canonical order. Every stage is a set of canonical
names, and a candidate satisfies the profile when its canonical sequence contains **at
least one skill of every stage, with the stages in order**; several skills of the same
stage may follow each other. With ``S_1, ..., S_n`` the stage alphabets, the language of a
profile is the regular language

    L = S_1+ S_2+ ... S_n+

and its minimal DFA has ``n + 1`` states: ``q0`` (nothing read yet), ``q_i`` (the stages
``1..i`` are satisfied and the last skill read belongs to ``S_i``) and ``q_n`` (accepting).
For the Full Stack profile::

    q0 --web language--> q1 --frontend--> q2 --backend--> q3 --database--> q4 --GIT--> q5
                         (loops on its own stage at q1 ... q5)               q5 = accepting

Any symbol that has no transition from the current state (a skill of a later stage that
arrives too early, a skill of the wrong profile, an unknown name) rejects the word.

This module only defines the official profiles. The automata of the additional profiles
are defined separately and reuse :func:`build_automaton`.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Tuple

from pyformlang.finite_automaton import DeterministicFiniteAutomaton, State, Symbol

#: Canonical names of the databases produced by Stage 2.
DATABASE_TOKENS: Tuple[str, ...] = (
    "SQL",
    "POSTGRESQL",
    "MYSQL",
    "MARIADB",
    "SQLITE",
    "SQL_SERVER",
    "ORACLE",
    "MONGODB",
    "REDIS",
    "CASSANDRA",
)

#: Canonical name of the version-control tools produced by Stage 2.
VERSION_CONTROL_TOKENS: Tuple[str, ...] = ("GIT",)


@dataclass(frozen=True)
class Stage:
    """One stage of a profile: a named, non-empty set of canonical skill names.

    Attributes:
        name: Label of the stage, used in error messages and reports.
        tokens: Canonical names that satisfy the stage.
    """

    name: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class ProfileSpec:
    """A profile: its name and its ordered stages.

    Attributes:
        name: Official name of the profile.
        stages: Stages in canonical order; all of them are required.
    """

    name: str
    stages: Tuple[Stage, ...]

    @property
    def alphabet(self) -> Tuple[str, ...]:
        """All canonical names that appear in some stage, in stage order."""
        return tuple(token for stage in self.stages for token in stage.tokens)


#: Full Stack Developer: web language -> frontend -> backend -> database -> version control.
FULL_STACK_PROFILE = ProfileSpec(
    name="Full Stack Developer",
    stages=(
        Stage("web_language", ("JAVASCRIPT", "TYPESCRIPT")),
        Stage("frontend_framework", ("REACT", "ANGULAR", "VUE")),
        Stage("backend_framework", ("NODE_JS", "SPRING_BOOT", "DJANGO")),
        Stage("database", DATABASE_TOKENS),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: Machine Learning Engineer: base language -> data / ML libraries -> database -> version control.
ML_PROFILE = ProfileSpec(
    name="Machine Learning Engineer",
    stages=(
        Stage("base_language", ("PYTHON",)),
        Stage(
            "ml_library",
            ("PANDAS", "NUMPY", "SCIKIT_LEARN", "TENSORFLOW", "PYTORCH", "KERAS", "MATPLOTLIB"),
        ),
        Stage("database", DATABASE_TOKENS),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: The two official profiles of the project.
OFFICIAL_PROFILES: Tuple[ProfileSpec, ...] = (FULL_STACK_PROFILE, ML_PROFILE)


def _validate(profile: ProfileSpec) -> None:
    """Check that ``profile`` describes a deterministic staged automaton.

    Raises:
        ValueError: If the profile has no stages, a stage has no tokens or an empty token,
            or the same canonical name appears in more than one stage (the automaton
            would not be deterministic).
    """
    if not profile.name:
        raise ValueError("A profile needs a non-empty name.")
    if not profile.stages:
        raise ValueError(f"Profile {profile.name!r} has no stages.")
    owner = {}
    for stage in profile.stages:
        if not stage.tokens:
            raise ValueError(f"Stage {stage.name!r} of profile {profile.name!r} has no tokens.")
        for token in stage.tokens:
            if not token:
                raise ValueError(f"Stage {stage.name!r} of profile {profile.name!r} has an empty token.")
            if owner.setdefault(token, stage.name) != stage.name:
                raise ValueError(
                    f"Token {token!r} belongs to both {owner[token]!r} and {stage.name!r} "
                    f"in profile {profile.name!r}."
                )


def build_automaton(profile: ProfileSpec) -> DeterministicFiniteAutomaton:
    """Build the DFA of a staged profile.

    Construction, for stages ``S_1 ... S_n``:

    1. States ``q0 ... qn``; ``q0`` is the initial state and ``qn`` the only accepting one.
    2. For every token ``t`` of stage ``S_i``: the transition ``q_{i-1} --t--> q_i``
       (stage ``i`` becomes satisfied) and the loop ``q_i --t--> q_i`` (more skills of the
       same stage).
    3. Nothing else: every other (state, symbol) pair goes to the implicit dead state.

    Args:
        profile: The profile to translate.

    Returns:
        A ``pyformlang`` deterministic finite automaton with ``len(stages) + 1`` states.

    Raises:
        ValueError: If the profile is not valid (see :func:`_validate`).
    """
    _validate(profile)
    states = [State(f"q{i}") for i in range(len(profile.stages) + 1)]
    automaton = DeterministicFiniteAutomaton()
    automaton.add_start_state(states[0])
    automaton.add_final_state(states[-1])
    for index, stage in enumerate(profile.stages):
        for token in stage.tokens:
            automaton.add_transition(states[index], Symbol(token), states[index + 1])
            automaton.add_transition(states[index + 1], Symbol(token), states[index + 1])
    return automaton


def build_full_stack_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the Full Stack Developer profile (:data:`FULL_STACK_PROFILE`)."""
    return build_automaton(FULL_STACK_PROFILE)


def build_ml_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the Machine Learning Engineer profile (:data:`ML_PROFILE`)."""
    return build_automaton(ML_PROFILE)


@lru_cache(maxsize=1)
def get_full_stack_automaton() -> DeterministicFiniteAutomaton:
    """Return the shared Full Stack automaton, built on first use. Callers must not modify it."""
    return build_full_stack_automaton()


@lru_cache(maxsize=1)
def get_ml_automaton() -> DeterministicFiniteAutomaton:
    """Return the shared ML automaton, built on first use. Callers must not modify it."""
    return build_ml_automaton()


def accepts(automaton: DeterministicFiniteAutomaton, tokens: Iterable[str]) -> bool:
    """Decide whether ``automaton`` accepts a sequence of canonical skill names.

    The sequence is read from left to right, one symbol per token. Names are compared
    exactly: canonical names are upper-case and ``Stage 2`` is the only place where
    spelling variants are unified. The empty sequence is never accepted.

    Args:
        automaton: An automaton built by :func:`build_automaton`.
        tokens: Canonical skill names, in the order in which they must be read.

    Returns:
        ``True`` if the whole sequence leads from the initial state to an accepting state.
    """
    return bool(automaton.accepts(list(tokens)))


def accepts_full_stack(tokens: Iterable[str]) -> bool:
    """Return ``True`` if the canonical sequence satisfies the Full Stack Developer profile."""
    return accepts(get_full_stack_automaton(), tokens)


def accepts_ml(tokens: Iterable[str]) -> bool:
    """Return ``True`` if the canonical sequence satisfies the Machine Learning Engineer profile."""
    return accepts(get_ml_automaton(), tokens)
