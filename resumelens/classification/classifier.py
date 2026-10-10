"""Stage 3 — Profile classification engine.

Runs the canonical skill sequence of Stage 2 through the automaton of a profile and builds
an :class:`~resumelens.core.models.EvaluationResult` with the formal verdict
(``ACCEPTED`` / ``REJECTED``) and a report of why.

The acceptance decision is always made by the automaton: ``pyformlang``'s ``accepts``,
called through :func:`resumelens.classification.automata.accepts`. The report only explains
that decision. For this, the sequence is replayed over the stages of the profile with the
same transition rule as :func:`resumelens.classification.automata.build_automaton`, which
tells where the word left the language of the profile or which required stages were never
reached. If the replay and the automaton ever disagreed, the verdict would still be the
automaton's and the report would say so instead of inventing a reason.

Contract with the previous stage: the sequence must be in the canonical order of the
profile that is evaluated (:func:`resumelens.normalization.sorter.sort_by_profile`), because
the profile automata read the skills stage by stage. :func:`classify_records` sorts the
``SkillRecord`` list of the normalizer before running the automaton, and
:func:`classify_all` does it once for each profile.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from pyformlang.finite_automaton import DeterministicFiniteAutomaton

from resumelens.classification.automata import (
    ALL_PROFILES,
    KNOWN_SKILLS,
    ProfileSpec,
    accepts,
    get_data_automaton,
    get_devops_automaton,
    get_full_stack_automaton,
    get_ml_automaton,
)
from resumelens.core.models import EvaluationResult, SkillRecord
from resumelens.normalization.sorter import (
    DATA_ENGINEER,
    DEVOPS_ENGINEER,
    FULL_STACK_DEVELOPER,
    MACHINE_LEARNING_ENGINEER,
    PROFILES,
    UnknownProfileError,
    resolve_profile,
    sort_by_profile,
)

#: Verdict of a profile whose automaton accepts the sequence.
ACCEPTED: str = "ACCEPTED"

#: Verdict of a profile whose automaton rejects the sequence.
REJECTED: str = "REJECTED"

#: Shared automaton of each profile, by profile identifier (see ``sorter.PROFILES``).
_AUTOMATON_GETTERS: Dict[str, Callable[[], DeterministicFiniteAutomaton]] = {
    FULL_STACK_DEVELOPER: get_full_stack_automaton,
    MACHINE_LEARNING_ENGINEER: get_ml_automaton,
    DEVOPS_ENGINEER: get_devops_automaton,
    DATA_ENGINEER: get_data_automaton,
}

#: Staged specification of each profile, by profile identifier.
PROFILE_SPECS: Dict[str, ProfileSpec] = {
    resolve_profile(spec.name): spec for spec in ALL_PROFILES
}

if set(PROFILE_SPECS) != set(PROFILES) or set(_AUTOMATON_GETTERS) != set(PROFILES):
    raise ValueError("The profiles of the automata and of the sorter do not match.")


def profile_spec(profile: str) -> ProfileSpec:
    """Return the staged specification of ``profile``.

    Args:
        profile: Any form accepted by the sorter (``"Full Stack Developer"``,
            ``"FULL_STACK_DEVELOPER"`` ...).

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    return PROFILE_SPECS[resolve_profile(profile)]


def verdict_of(result: EvaluationResult) -> str:
    """Return :data:`ACCEPTED` or :data:`REJECTED` for an evaluation result."""
    return ACCEPTED if result.is_accepted else REJECTED


@dataclass
class _Replay:
    """Result of replaying a sequence over the stages of a profile (explanation only).

    Attributes:
        accepted: Whether the replay ends in an accepting state.
        stages: Skills read by each satisfied stage, in order of first appearance.
        matched: Skills of the profile alphabet read before the replay stopped.
        outside: Skills read that do not belong to the profile (accepted noise).
        failure: Description of the first symbol with no transition, if any.
        missing: Required stages not reached when the replay ended.
    """

    accepted: bool = False
    stages: Dict[str, List[str]] = field(default_factory=dict)
    matched: List[str] = field(default_factory=list)
    outside: List[str] = field(default_factory=list)
    failure: Optional[str] = None
    missing: List[str] = field(default_factory=list)


def _accepting_states(spec: ProfileSpec) -> Set[int]:
    """Indices ``i`` of the states ``q_i`` that are accepting (see ``build_automaton``)."""
    last = len(spec.stages)
    accepting = {last}
    while last > 0 and not spec.stages[last - 1].required:
        last -= 1
        accepting.add(last)
    return accepting


def _sources(spec: ProfileSpec, position: int) -> Set[int]:
    """Indices of the states from which a skill of stage ``position`` can be read."""
    sources = {position, position - 1}
    source = position - 1
    while source > 0 and not spec.stages[source - 1].required:
        source -= 1
        sources.add(source)
    return sources


def _required_after(spec: ProfileSpec, state: int) -> List[str]:
    """Names of the required stages that come after state ``q_state``."""
    return [stage.name for stage in spec.stages[state:] if stage.required]


def _replay(spec: ProfileSpec, tokens: Sequence[str]) -> _Replay:
    """Replay ``tokens`` over the stages of ``spec`` with the transition rule of the DFA."""
    stage_of = {
        token: (position, stage)
        for position, stage in enumerate(spec.stages, start=1)
        for token in stage.tokens
    }
    noise: FrozenSet[str] = frozenset(KNOWN_SKILLS - set(spec.alphabet))
    accepting = _accepting_states(spec)
    replay = _Replay()
    state = 0
    in_noise = False
    for index, token in enumerate(tokens, start=1):
        where = f"{token} (position {index})"
        located = stage_of.get(token)
        if located is not None:
            position, stage = located
            if in_noise:
                replay.failure = (
                    f"{where} belongs to stage '{stage.name}' but appears after skills outside "
                    f"the profile; the profile part must come first"
                )
                return replay
            if state in _sources(spec, position):
                state = position
                replay.stages.setdefault(stage.name, []).append(token)
                replay.matched.append(token)
                continue
            if position < state:
                replay.failure = (
                    f"{where} belongs to stage '{stage.name}', which comes before the stage "
                    f"already reached ('{spec.stages[state - 1].name}'); the stages must be in order"
                )
            else:
                skipped = [s.name for s in spec.stages[state : position - 1] if s.required]
                replay.failure = (
                    f"{where} belongs to stage '{stage.name}' but the required stage(s) "
                    f"{', '.join(skipped)} must come before it"
                )
            return replay
        if token in noise:
            if in_noise or state in accepting:
                in_noise = True
                replay.outside.append(token)
                continue
            replay.failure = (
                f"{where} is outside the profile and appears before the required stage(s) "
                f"{', '.join(_required_after(spec, state))} are satisfied"
            )
            return replay
        replay.failure = f"{where} is not a canonical skill name produced by Stage 2"
        return replay
    replay.accepted = in_noise or state in accepting
    if not replay.accepted:
        replay.missing = _required_after(spec, state)
    return replay


def _reason(replay: _Replay, tokens: Sequence[str]) -> str:
    """Describe why a sequence was rejected."""
    if replay.failure is not None:
        return replay.failure
    if not tokens:
        return "the sequence is empty; every required stage needs at least one skill"
    if replay.missing:
        return f"the sequence ends before the required stage(s) {', '.join(replay.missing)}"
    return "the automaton does not accept the sequence"


def _details(spec: ProfileSpec, tokens: Sequence[str], accepted: bool, replay: _Replay) -> str:
    """Build the text report of one evaluation."""
    lines = [
        f"{ACCEPTED if accepted else REJECTED} - {spec.name}",
        f"Sequence read: {', '.join(tokens) if tokens else '(empty)'}",
    ]
    if accepted:
        satisfied = "; ".join(f"{name} ({', '.join(skills)})" for name, skills in replay.stages.items())
        lines.append(f"Stages satisfied: {satisfied}")
        unused = [s.name for s in spec.stages if not s.required and s.name not in replay.stages]
        if unused:
            lines.append(f"Optional stages not used: {', '.join(unused)}")
        if replay.outside:
            lines.append(f"Skills outside the profile (ignored): {', '.join(replay.outside)}")
    else:
        lines.append(f"Reason: {_reason(replay, tokens)}")
    return "\n".join(lines)


def classify_sequence(sequence: Iterable[str], profile: str) -> EvaluationResult:
    """Evaluate a canonical skill sequence against one profile.

    Args:
        sequence: Canonical skill names in the canonical order of ``profile`` (output of
            Stage 2). A single string is rejected: it would be read character by character.
        profile: Profile name, in any form accepted by the sorter.

    Returns:
        An ``EvaluationResult`` with:

        * ``profile_name``: official name of the profile (``"Full Stack Developer"``);
        * ``is_accepted``: the verdict of the automaton;
        * ``matched_sequence``: the skills of the sequence that belong to the stages of the
          profile, in the order read (up to the failure point for a rejected sequence);
        * ``details``: report whose first line is ``ACCEPTED - <profile>`` or
          ``REJECTED - <profile>``, followed by the sequence read and the satisfied stages
          or the reason for the rejection.

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
        TypeError: If ``sequence`` is a string or has an item that is not a string.
    """
    if isinstance(sequence, str):
        raise TypeError("The sequence must be an iterable of skill names, not a single string.")
    tokens = list(sequence)
    if not all(isinstance(token, str) for token in tokens):
        raise TypeError("Every item of the sequence must be a string.")
    identifier = resolve_profile(profile)
    spec = PROFILE_SPECS[identifier]
    accepted = accepts(_AUTOMATON_GETTERS[identifier](), tokens)
    replay = _replay(spec, tokens)
    return EvaluationResult(
        profile_name=spec.name,
        is_accepted=accepted,
        matched_sequence=list(replay.matched),
        details=_details(spec, tokens, accepted, replay),
    )


def classify_records(records: Sequence[SkillRecord], profile: str) -> EvaluationResult:
    """Sort the normalized records for ``profile`` (Stage 2) and evaluate them.

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    return classify_sequence(sort_by_profile(records, profile), profile)


@dataclass
class ClassificationReport:
    """Evaluation of one candidate against every supported profile.

    Attributes:
        results: One result per profile, in the order of ``sorter.PROFILES``.
    """

    results: List[EvaluationResult] = field(default_factory=list)

    @property
    def accepted_profiles(self) -> List[str]:
        """Names of the profiles whose automaton accepted the candidate."""
        return [result.profile_name for result in self.results if result.is_accepted]

    @property
    def rejected_profiles(self) -> List[str]:
        """Names of the profiles whose automaton rejected the candidate."""
        return [result.profile_name for result in self.results if not result.is_accepted]

    def result_for(self, profile: str) -> EvaluationResult:
        """Return the result of ``profile`` (any form accepted by the sorter).

        Raises:
            UnknownProfileError: If ``profile`` is not supported.
        """
        identifier = resolve_profile(profile)
        for result in self.results:
            if resolve_profile(result.profile_name) == identifier:
                return result
        raise KeyError(f"The report has no result for profile {profile!r}.")

    def verdicts(self) -> Dict[str, str]:
        """Map each profile name to :data:`ACCEPTED` or :data:`REJECTED`."""
        return {result.profile_name: verdict_of(result) for result in self.results}


def classify_all(records: Sequence[SkillRecord]) -> ClassificationReport:
    """Evaluate the normalized records against the four profiles.

    The records are sorted separately for each profile, because the canonical order depends
    on the profile that is evaluated.
    """
    return ClassificationReport(results=[classify_records(records, profile) for profile in PROFILES])


__all__: Tuple[str, ...] = (
    "ACCEPTED",
    "REJECTED",
    "PROFILE_SPECS",
    "ClassificationReport",
    "UnknownProfileError",
    "classify_all",
    "classify_records",
    "classify_sequence",
    "profile_spec",
    "verdict_of",
)
