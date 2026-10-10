"""Stage 3 — Finite automata for the four profiles (official and team-defined).

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

A stage may be declared *optional* (``Stage.required = False``): its skills are allowed
but not needed, i.e. ``S_i`` becomes ``S_i*`` in the pattern. The automaton stays
deterministic with ``n + 1`` states: a skill of stage ``k`` may be read from state ``q_j``
whenever the stages ``j + 1 ... k - 1`` that are skipped are all optional, and ``q_i`` is
accepting when every stage after ``i`` is optional. DevOps uses it for CI/CD and cloud,
Data Engineer for cloud.

The stages describe the *profile part* of the sequence. Stage 2 writes the skills of any
other category (noise for this profile) after it, so once the automaton is in an accepting
state it also reads any known canonical name that is not part of the profile and moves to
an extra accepting state ``q_noise``, where only more noise is allowed. Names that Stage 2
never produces, and skills of the profile that arrive out of order, are still rejected.

The official profiles (Full Stack, Machine Learning) and the team-defined ones (DevOps,
Data Engineer) are all built by :func:`build_automaton`.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import FrozenSet, Iterable, Tuple

from pyformlang.finite_automaton import DeterministicFiniteAutomaton, State, Symbol

from resumelens.normalization.transducers import FAMILY_VARIANTS

#: Canonical names of the databases produced by Stage 2.
DATABASE_TOKENS: Tuple[str, ...] = (
    "SQL",
    "NOSQL",
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

#: Every canonical name that Stage 2 can produce; the symbols that can appear in a word.
KNOWN_SKILLS: FrozenSet[str] = frozenset(
    canonical for variants in FAMILY_VARIANTS.values() for canonical in variants
)

#: Canonical names of the cloud providers produced by Stage 2.
CLOUD_TOKENS: Tuple[str, ...] = ("AWS", "AZURE", "GCP")


@dataclass(frozen=True)
class Stage:
    """One stage of a profile: a named, non-empty set of canonical skill names.

    Attributes:
        name: Label of the stage, used in error messages and reports.
        tokens: Canonical names that satisfy the stage.
        required: ``False`` if a candidate may omit the stage entirely.
    """

    name: str
    tokens: Tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class ProfileSpec:
    """A profile: its name and its ordered stages.

    Attributes:
        name: Official name of the profile.
        stages: Stages in canonical order; the required ones must all be satisfied.
    """

    name: str
    stages: Tuple[Stage, ...]

    @property
    def alphabet(self) -> Tuple[str, ...]:
        """All canonical names that appear in some stage, in stage order."""
        return tuple(token for stage in self.stages for token in stage.tokens)


#: Full Stack Developer: web language -> frontend -> backend -> database -> [REST API] ->
#: version control.
FULL_STACK_PROFILE = ProfileSpec(
    name="Full Stack Developer",
    stages=(
        Stage("web_language", ("JAVASCRIPT", "TYPESCRIPT")),
        Stage("frontend_framework", ("REACT", "ANGULAR", "VUE")),
        Stage("backend_framework", ("NODE_JS", "SPRING_BOOT", "DJANGO")),
        Stage("database", DATABASE_TOKENS),
        Stage("api", ("REST_API",), required=False),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: Machine Learning Engineer: base language -> data library -> ML framework ->
#: [ML model development] -> database -> version control.
ML_PROFILE = ProfileSpec(
    name="Machine Learning Engineer",
    stages=(
        Stage("base_language", ("PYTHON",)),
        Stage("data_library", ("PANDAS", "NUMPY", "MATPLOTLIB")),
        Stage("ml_framework", ("SCIKIT_LEARN", "TENSORFLOW", "PYTORCH", "KERAS")),
        Stage("ml_practice", ("ML_MODEL_DEVELOPMENT",), required=False),
        Stage("database", DATABASE_TOKENS),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: The two official profiles of the project.
OFFICIAL_PROFILES: Tuple[ProfileSpec, ...] = (FULL_STACK_PROFILE, ML_PROFILE)

#: DevOps Engineer: language -> container -> orchestration -> infrastructure as code ->
#: [CI/CD] -> [cloud] -> version control. IaC and cloud accept equivalent alternatives
#: (Terraform or Ansible; AWS, Azure or GCP).
DEVOPS_PROFILE = ProfileSpec(
    name="DevOps Engineer",
    stages=(
        Stage("language", ("PYTHON", "GO", "JAVA", "RUBY")),
        Stage("container", ("DOCKER",)),
        Stage("orchestration", ("KUBERNETES",)),
        Stage("infrastructure_as_code", ("TERRAFORM", "ANSIBLE")),
        Stage("ci_cd", ("JENKINS",), required=False),
        Stage("cloud", CLOUD_TOKENS, required=False),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: Data Engineer: language -> data processing -> workflow orchestration -> database ->
#: [cloud] -> version control. The language, database and cloud stages accept equivalent
#: alternatives.
DATA_PROFILE = ProfileSpec(
    name="Data Engineer",
    stages=(
        Stage("language", ("PYTHON", "JAVA", "GO")),
        Stage("data_processing", ("SPARK",)),
        Stage("workflow", ("AIRFLOW",)),
        Stage("database", DATABASE_TOKENS),
        Stage("cloud", CLOUD_TOKENS, required=False),
        Stage("version_control", VERSION_CONTROL_TOKENS),
    ),
)

#: The two profiles defined by the team.
TEAM_PROFILES: Tuple[ProfileSpec, ...] = (DEVOPS_PROFILE, DATA_PROFILE)

#: The four supported profiles, in the order used by the roadmap.
ALL_PROFILES: Tuple[ProfileSpec, ...] = OFFICIAL_PROFILES + TEAM_PROFILES


def _validate(profile: ProfileSpec) -> None:
    """Check that ``profile`` describes a deterministic staged automaton.

    Raises:
        ValueError: If the profile has no stages or no required stage (it would accept the
            empty word), a stage has no tokens or an empty token, or the same canonical name appears in more than one stage (the automaton
            would not be deterministic).
    """
    if not profile.name:
        raise ValueError("A profile needs a non-empty name.")
    if not profile.stages:
        raise ValueError(f"Profile {profile.name!r} has no stages.")
    if not any(stage.required for stage in profile.stages):
        raise ValueError(f"Profile {profile.name!r} has no required stage.")
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

    1. States ``q0 ... qn``; ``q0`` is the initial state. ``qn`` is accepting, and so is
       every ``q_i`` whose following stages ``S_{i+1} ... S_n`` are all optional.
    2. For every token ``t`` of stage ``S_i``: the transition ``q_{i-1} --t--> q_i``
       (stage ``i`` becomes satisfied) and the loop ``q_i --t--> q_i`` (more skills of the
       same stage). If the stages right before ``S_i`` are optional, ``t`` is also read
       from the states that skip them (``q_{i-2}``, ``q_{i-3}`` ...).
    3. An extra accepting state ``q_noise`` (so ``n + 2`` states in total): every accepting
       state reads each known skill outside the profile alphabet and goes to ``q_noise``,
       which loops on those same skills.
    4. Nothing else: every other (state, symbol) pair goes to the implicit dead state.

    Args:
        profile: The profile to translate.

    Returns:
        A ``pyformlang`` deterministic finite automaton with ``len(stages) + 2`` states
        (``q0 ... qn`` and ``q_noise``).

    Raises:
        ValueError: If the profile is not valid (see :func:`_validate`).
    """
    _validate(profile)
    states = [State(f"q{i}") for i in range(len(profile.stages) + 1)]
    noise_state = State("q_noise")
    noise = sorted(KNOWN_SKILLS - set(profile.alphabet))
    automaton = DeterministicFiniteAutomaton()
    automaton.add_start_state(states[0])
    automaton.add_final_state(noise_state)
    last = len(profile.stages)
    accepting = [last]
    while last > 0 and not profile.stages[last - 1].required:
        last -= 1
        accepting.append(last)
    for index in accepting:
        automaton.add_final_state(states[index])
        for token in noise:
            automaton.add_transition(states[index], Symbol(token), noise_state)
    for token in noise:
        automaton.add_transition(noise_state, Symbol(token), noise_state)
    for position, stage in enumerate(profile.stages, start=1):
        sources = [position, position - 1]
        source = position - 1
        while source > 0 and not profile.stages[source - 1].required:
            source -= 1
            sources.append(source)
        for token in stage.tokens:
            for origin in sources:
                automaton.add_transition(states[origin], Symbol(token), states[position])
    return automaton


def build_full_stack_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the Full Stack Developer profile (:data:`FULL_STACK_PROFILE`)."""
    return build_automaton(FULL_STACK_PROFILE)


def build_ml_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the Machine Learning Engineer profile (:data:`ML_PROFILE`)."""
    return build_automaton(ML_PROFILE)


def build_devops_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the DevOps Engineer profile (:data:`DEVOPS_PROFILE`)."""
    return build_automaton(DEVOPS_PROFILE)


def build_data_automaton() -> DeterministicFiniteAutomaton:
    """Build the DFA of the Data Engineer profile (:data:`DATA_PROFILE`)."""
    return build_automaton(DATA_PROFILE)


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


@lru_cache(maxsize=1)
def get_devops_automaton() -> DeterministicFiniteAutomaton:
    """Return the shared DevOps automaton, built on first use. Callers must not modify it."""
    return build_devops_automaton()


@lru_cache(maxsize=1)
def get_data_automaton() -> DeterministicFiniteAutomaton:
    """Return the shared Data Engineer automaton, built on first use. Callers must not modify it."""
    return build_data_automaton()


def accepts_devops(tokens: Iterable[str]) -> bool:
    """Return ``True`` if the canonical sequence satisfies the DevOps Engineer profile."""
    return accepts(get_devops_automaton(), tokens)


def accepts_data(tokens: Iterable[str]) -> bool:
    """Return ``True`` if the canonical sequence satisfies the Data Engineer profile."""
    return accepts(get_data_automaton(), tokens)
