"""Tests for Stage 3 — classification with finite automata.

Two layers:

* The automata of the four supported profiles (Full Stack Developer, Machine Learning
  Engineer, DevOps Engineer and Data Engineer): acceptance paths, rejection paths and the
  formal structure ``M = (Q, Sigma, delta, q0, F)`` of each DFA. They read *canonical* skill
  names (the output alphabet of Stage 2), so most sequences are written in canonical form.
* The multi-profile classifier (``classify_sequence``, ``classify_records``,
  ``classify_all``): verdicts, reports, errors and the cross-profile behaviour, ending with
  tests that run the whole pipeline on the synthetic resumes.
"""

import itertools
import random
import re

import pytest
from pyformlang.finite_automaton import DeterministicFiniteAutomaton, State, Symbol
from pyformlang.regular_expression import Regex

from resumelens.classification import (
    ACCEPTED,
    PROFILE_SPECS,
    REJECTED,
    ClassificationReport,
    UnknownProfileError,
    classify_all,
    classify_records,
    classify_sequence,
    profile_spec,
    verdict_of,
)
from resumelens.classification.automata import (
    ALL_PROFILES,
    DATA_PROFILE,
    DATABASE_TOKENS,
    DEVOPS_PROFILE,
    FULL_STACK_PROFILE,
    KNOWN_SKILLS,
    ML_PROFILE,
    OFFICIAL_PROFILES,
    TEAM_PROFILES,
    VERSION_CONTROL_TOKENS,
    ProfileSpec,
    Stage,
    accepts,
    accepts_data,
    accepts_devops,
    accepts_full_stack,
    accepts_ml,
    build_automaton,
    build_data_automaton,
    build_devops_automaton,
    build_full_stack_automaton,
    build_ml_automaton,
    get_data_automaton,
    get_devops_automaton,
    get_full_stack_automaton,
    get_ml_automaton,
)
from resumelens.core.models import EvaluationResult
from resumelens.extraction.extractor import extract_resume
from resumelens.normalization import PROFILES, normalize_with_report, resolve_profile, sort_by_profile

FULL_STACK_ACCEPTED = [
    ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"],
    ["TYPESCRIPT", "ANGULAR", "SPRING_BOOT", "MYSQL", "GIT"],
    ["JAVASCRIPT", "TYPESCRIPT", "REACT", "VUE", "NODE_JS", "DJANGO", "POSTGRESQL", "REDIS", "GIT"],
]

ML_ACCEPTED = [
    ["PYTHON", "PANDAS", "NUMPY", "SCIKIT_LEARN", "TENSORFLOW", "SQL", "GIT"],
    ["PYTHON", "NUMPY", "PYTORCH", "POSTGRESQL", "GIT"],
    ["PYTHON", "MATPLOTLIB", "KERAS", "ML_MODEL_DEVELOPMENT", "MONGODB", "GIT"],
]


class TestFullStackProfile:
    @pytest.mark.parametrize("sequence", FULL_STACK_ACCEPTED)
    def test_accepts_valid_sequences(self, sequence):
        assert accepts_full_stack(sequence)

    def test_rejects_empty_sequence(self):
        assert not accepts_full_stack([])

    @pytest.mark.parametrize(
        "sequence",
        [
            ["JAVASCRIPT", "NODE_JS", "SQL", "GIT"],  # no frontend framework
            ["JAVASCRIPT", "REACT", "SQL", "GIT"],  # no backend framework
            ["REACT", "NODE_JS", "SQL", "GIT"],  # no web language
            ["JAVASCRIPT", "REACT", "NODE_JS", "GIT"],  # no database
            ["JAVASCRIPT", "REACT", "NODE_JS", "SQL"],  # no version control
        ],
    )
    def test_rejects_sequences_with_a_missing_stage(self, sequence):
        assert not accepts_full_stack(sequence)

    def test_rejects_stages_out_of_order(self):
        assert not accepts_full_stack(["JAVASCRIPT", "NODE_JS", "REACT", "POSTGRESQL", "GIT"])
        assert not accepts_full_stack(["GIT", "POSTGRESQL", "NODE_JS", "REACT", "JAVASCRIPT"])

    def test_rejects_foreign_or_non_canonical_tokens(self):
        assert not accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT", "UNKNOWN"])
        assert not accepts_full_stack(["JS", "React.js", "NodeJS", "Postgres", "Git"])


class TestMlProfile:
    @pytest.mark.parametrize("sequence", ML_ACCEPTED)
    def test_accepts_valid_sequences(self, sequence):
        assert accepts_ml(sequence)

    def test_rejects_empty_sequence(self):
        assert not accepts_ml([])

    @pytest.mark.parametrize(
        "sequence",
        [
            ["PANDAS", "SQL", "GIT"],  # no base language
            ["PYTHON", "SQL", "GIT"],  # no data / ML library
            ["PYTHON", "PANDAS", "SQL", "GIT"],  # no ML framework
            ["PYTHON", "TENSORFLOW", "SQL", "GIT"],  # no data library
            ["PYTHON", "PANDAS", "TENSORFLOW", "GIT"],  # no database
            ["PYTHON", "PANDAS", "TENSORFLOW", "SQL"],  # no version control
        ],
    )
    def test_rejects_sequences_with_a_missing_stage(self, sequence):
        assert not accepts_ml(sequence)

    def test_rejects_stages_out_of_order(self):
        assert not accepts_ml(["PYTHON", "SQL", "PANDAS", "GIT"])
        assert not accepts_ml(["GIT", "SQL", "PANDAS", "PYTHON"])

    def test_rejects_foreign_or_non_canonical_tokens(self):
        assert not accepts_ml(["PYTHON", "PANDAS", "TENSORFLOW", "SQL", "GIT", "UNKNOWN"])
        assert not accepts_ml(["Python", "Pandas", "SQL", "Git"])


class TestOptionalStagesAndNoise:
    def test_full_stack_accepts_nosql_and_optional_rest_api(self):
        assert accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "NOSQL", "GIT"])
        assert accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "REST_API", "GIT"])

    def test_ml_accepts_optional_model_development_stage(self):
        assert accepts_ml(["PYTHON", "PANDAS", "TENSORFLOW", "ML_MODEL_DEVELOPMENT", "SQL", "GIT"])

    def test_noise_after_the_profile_part_is_accepted(self):
        assert accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "GIT", "DOCKER", "PYTHON"])
        assert accepts_ml(["PYTHON", "PANDAS", "TENSORFLOW", "SQL", "GIT", "DOCKER"])

    def test_noise_does_not_replace_a_missing_stage(self):
        assert not accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "DOCKER", "GIT"])
        assert not accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "DOCKER"])

    def test_profile_skill_after_noise_is_rejected(self):
        assert not accepts_full_stack(["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "GIT", "DOCKER", "REACT"])


class TestProfilesAreDistinct:
    def test_each_profile_rejects_the_sequences_of_the_other(self):
        for sequence in ML_ACCEPTED:
            assert not accepts_full_stack(sequence)
        for sequence in FULL_STACK_ACCEPTED:
            assert not accepts_ml(sequence)


class TestAutomatonObjects:
    def test_builders_return_deterministic_automata(self):
        for automaton in (build_full_stack_automaton(), build_ml_automaton()):
            assert isinstance(automaton, DeterministicFiniteAutomaton)
            assert automaton.is_deterministic()

    def test_number_of_states_is_stages_plus_initial_and_noise(self):
        assert len(build_full_stack_automaton().states) == len(FULL_STACK_PROFILE.stages) + 2
        assert len(build_ml_automaton().states) == len(ML_PROFILE.stages) + 2

    def test_accepts_function_uses_the_given_automaton(self):
        assert accepts(get_full_stack_automaton(), FULL_STACK_ACCEPTED[0])
        assert not accepts(get_full_stack_automaton(), ML_ACCEPTED[0])
        assert accepts(get_ml_automaton(), ML_ACCEPTED[0])
        assert not accepts(get_ml_automaton(), FULL_STACK_ACCEPTED[0])


# ===========================================================================
# Rigorous suite (Commit 18): the four profiles and the multi-profile classifier
# ===========================================================================

PROFILE_KEYS = ("full_stack", "ml", "devops", "data")

DEVOPS_ACCEPTED = [
    ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT"],
    ["GO", "DOCKER", "KUBERNETES", "ANSIBLE", "JENKINS", "AWS", "GIT"],
    ["JAVA", "DOCKER", "KUBERNETES", "TERRAFORM", "ANSIBLE", "JENKINS", "AZURE", "GCP", "GIT"],
    ["RUBY", "DOCKER", "KUBERNETES", "ANSIBLE", "GIT"],
]

DATA_ACCEPTED = [
    ["PYTHON", "SPARK", "AIRFLOW", "POSTGRESQL", "GIT"],
    ["JAVA", "SPARK", "AIRFLOW", "MONGODB", "AWS", "GIT"],
    ["GO", "SPARK", "AIRFLOW", "SQL", "NOSQL", "AZURE", "GCP", "GIT"],
    ["PYTHON", "JAVA", "SPARK", "AIRFLOW", "REDIS", "GIT"],
]

# key -> (profile, accepts function, accepted canonical sequences)
PROFILE_CASES = {
    "full_stack": (FULL_STACK_PROFILE, accepts_full_stack, FULL_STACK_ACCEPTED),
    "ml": (ML_PROFILE, accepts_ml, ML_ACCEPTED),
    "devops": (DEVOPS_PROFILE, accepts_devops, DEVOPS_ACCEPTED),
    "data": (DATA_PROFILE, accepts_data, DATA_ACCEPTED),
}

# Skills that are not canonical names of Stage 2, or are malformed.
FOREIGN_TOKENS = ["COBOL", "UNKNOWN", "JS", "Git", "git", "react", "", " ", "NODE JS", "NODE-JS"]

# (raw skills, profiles that must accept) for candidates that fit several profiles or none.
MULTI_PROFILE_CASES = [
    (["JS", "React", "Node", "Postgres", "Git", "Python", "Spark", "Airflow"], ["Full Stack Developer", "Data Engineer"]),
    (["Python", "Pandas", "sklearn", "Spark", "Airflow", "SQL", "Git"], ["Machine Learning Engineer", "Data Engineer"]),
    (
        ["Python", "Docker", "K8s", "Terraform", "Spark", "Airflow", "PostgreSQL", "Git"],
        ["DevOps Engineer", "Data Engineer"],
    ),
    (["JS", "React", "Node", "Postgres", "Git", "Python", "Pandas", "sklearn"], ["Full Stack Developer", "Machine Learning Engineer"]),
    (["Git"], []),
    (["Python"], []),
    (["Cobol", "Excel"], []),
]


def _required_tokens(profile: ProfileSpec):
    """Minimal accepted sequence: the first token of every required stage, in order."""
    return [stage.tokens[0] for stage in profile.stages if stage.required]


def _noise_token(profile: ProfileSpec) -> str:
    """A known canonical name that does not belong to the profile."""
    return sorted(KNOWN_SKILLS - set(profile.alphabet))[0]


def _stage_choices(profile: ProfileSpec):
    """For every stage, the options of one choice: its tokens (plus 'omit' if optional)."""
    return [stage.tokens if stage.required else (None,) + stage.tokens for stage in profile.stages]


def _all_choice_sequences(profile: ProfileSpec):
    for combination in itertools.product(*_stage_choices(profile)):
        yield [token for token in combination if token is not None]


def _source_states(profile: ProfileSpec, position: int):
    """States from which a token of stage ``position`` (1-based) is read."""
    sources = {position, position - 1}
    index = position - 1
    while index > 0 and not profile.stages[index - 1].required:
        index -= 1
        sources.add(index)
    return sources


def _accepting_indices(profile: ProfileSpec):
    """Indices ``i`` such that ``q_i`` accepts: every stage after ``i`` is optional."""
    count = len(profile.stages)
    return {i for i in range(count + 1) if all(not stage.required for stage in profile.stages[i:])}


def _python_regex(profile: ProfileSpec) -> "re.Pattern":
    """Independent oracle: profile part, then known skills outside the profile."""
    parts = []
    for stage in profile.stages:
        group = "(?:" + "|".join(stage.tokens) + "),"
        parts.append(f"(?:{group})" + ("+" if stage.required else "*"))
    noise = "|".join(sorted(KNOWN_SKILLS - set(profile.alphabet)))
    parts.append(f"(?:(?:{noise}),)*")
    return re.compile("".join(parts))


def _pyformlang_regex(profile: ProfileSpec) -> str:
    parts = []
    for stage in profile.stages:
        group = "(" + "|".join(stage.tokens) + ")"
        parts.append(f"{group} {group}*" if stage.required else f"{group}*")
    parts.append("(" + "|".join(sorted(KNOWN_SKILLS - set(profile.alphabet))) + ")*")
    return " ".join(parts)


def _records(raw_skills):
    return normalize_with_report(raw_skills).records


# ---------------------------------------------------------------------------
# Acceptance paths: the four profiles
# ---------------------------------------------------------------------------
class TestDevopsProfile:
    @pytest.mark.parametrize("sequence", DEVOPS_ACCEPTED)
    def test_accepts_valid_sequences(self, sequence):
        assert accepts_devops(sequence)

    def test_rejects_empty_sequence(self):
        assert not accepts_devops([])

    @pytest.mark.parametrize(
        "sequence",
        [
            ["DOCKER", "KUBERNETES", "TERRAFORM", "GIT"],  # no language
            ["PYTHON", "KUBERNETES", "TERRAFORM", "GIT"],  # no container
            ["PYTHON", "DOCKER", "TERRAFORM", "GIT"],  # no orchestration
            ["PYTHON", "DOCKER", "KUBERNETES", "GIT"],  # no infrastructure as code
            ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM"],  # no version control
        ],
    )
    def test_rejects_sequences_with_a_missing_required_stage(self, sequence):
        assert not accepts_devops(sequence)

    def test_ci_cd_and_cloud_are_optional(self):
        base = ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT"]
        assert accepts_devops(base)
        assert accepts_devops(["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "JENKINS", "GIT"])
        assert accepts_devops(["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "AWS", "GIT"])
        assert accepts_devops(["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "JENKINS", "AWS", "GIT"])

    def test_equivalent_alternatives_inside_a_stage(self):
        for language in ("PYTHON", "GO", "JAVA", "RUBY"):
            for iac in ("TERRAFORM", "ANSIBLE"):
                assert accepts_devops([language, "DOCKER", "KUBERNETES", iac, "GIT"])

    def test_rejects_stages_out_of_order(self):
        assert not accepts_devops(["PYTHON", "KUBERNETES", "DOCKER", "TERRAFORM", "GIT"])
        assert not accepts_devops(["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "AWS", "JENKINS", "GIT"])
        assert not accepts_devops(["GIT", "TERRAFORM", "KUBERNETES", "DOCKER", "PYTHON"])


class TestDataEngineerProfile:
    @pytest.mark.parametrize("sequence", DATA_ACCEPTED)
    def test_accepts_valid_sequences(self, sequence):
        assert accepts_data(sequence)

    def test_rejects_empty_sequence(self):
        assert not accepts_data([])

    @pytest.mark.parametrize(
        "sequence",
        [
            ["SPARK", "AIRFLOW", "SQL", "GIT"],  # no language
            ["PYTHON", "AIRFLOW", "SQL", "GIT"],  # no data processing
            ["PYTHON", "SPARK", "SQL", "GIT"],  # no workflow orchestration
            ["PYTHON", "SPARK", "AIRFLOW", "GIT"],  # no database
            ["PYTHON", "SPARK", "AIRFLOW", "SQL"],  # no version control
        ],
    )
    def test_rejects_sequences_with_a_missing_required_stage(self, sequence):
        assert not accepts_data(sequence)

    def test_cloud_is_optional(self):
        assert accepts_data(["PYTHON", "SPARK", "AIRFLOW", "SQL", "GIT"])
        assert accepts_data(["PYTHON", "SPARK", "AIRFLOW", "SQL", "AWS", "GIT"])

    def test_rejects_stages_out_of_order(self):
        assert not accepts_data(["PYTHON", "AIRFLOW", "SPARK", "SQL", "GIT"])
        assert not accepts_data(["PYTHON", "SPARK", "AIRFLOW", "AWS", "SQL", "GIT"])
        assert not accepts_data(["GIT", "SQL", "AIRFLOW", "SPARK", "PYTHON"])


class TestAcceptancePathsOfAllProfiles:
    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_canonical_sequences_are_accepted(self, key):
        _, check, sequences = PROFILE_CASES[key]
        assert sequences
        for sequence in sequences:
            assert check(sequence), sequence

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_every_choice_of_stage_tokens_is_accepted(self, key):
        profile, check, _ = PROFILE_CASES[key]
        count = 0
        for sequence in _all_choice_sequences(profile):
            assert check(sequence), sequence
            count += 1
        expected = 1
        for stage in profile.stages:
            expected *= len(stage.tokens) + (0 if stage.required else 1)
        assert count == expected

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_all_tokens_of_a_stage_together_are_accepted(self, key):
        profile, check, _ = PROFILE_CASES[key]
        for index, stage in enumerate(profile.stages):
            sequence = _required_tokens(profile)
            at = sum(1 for s in profile.stages[:index] if s.required)
            if stage.required:
                sequence[at:at + 1] = list(stage.tokens)
            else:
                sequence[at:at] = list(stage.tokens)
            assert check(sequence), (stage.name, sequence)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_repeated_tokens_inside_a_stage_are_accepted(self, key):
        profile, check, _ = PROFILE_CASES[key]
        sequence = []
        for token in _required_tokens(profile):
            sequence += [token, token]
        assert check(sequence)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_known_skills_outside_the_profile_may_follow_the_profile_part(self, key):
        profile, check, _ = PROFILE_CASES[key]
        noise = sorted(KNOWN_SKILLS - set(profile.alphabet))
        assert check(_required_tokens(profile) + noise[:1])
        assert check(_required_tokens(profile) + noise)
        assert check(_required_tokens(profile) + noise + noise)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_shortest_accepted_sequence_has_one_skill_per_required_stage(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        assert check(minimal)
        assert len(minimal) == sum(1 for stage in profile.stages if stage.required)
        for index in range(len(minimal)):
            assert not check(minimal[:index] + minimal[index + 1:])


# ---------------------------------------------------------------------------
# Rejection paths: the four profiles
# ---------------------------------------------------------------------------
class TestRejectionPathsOfAllProfiles:
    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_empty_sequence(self, key):
        assert not PROFILE_CASES[key][1]([])

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_incomplete_sequences_missing_each_required_stage(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for index in range(len(minimal)):
            assert not check(minimal[:index] + minimal[index + 1:]), index

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_every_proper_prefix_is_rejected(self, key):
        profile, check, sequences = PROFILE_CASES[key]
        for sequence in [_required_tokens(profile)] + sequences:
            for cut in range(len(sequence)):
                assert not check(sequence[:cut]), (sequence, cut)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_a_single_skill_of_any_stage_is_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        for stage in profile.stages:
            for token in stage.tokens:
                assert not check([token]), token

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_version_control_alone_or_with_a_database_is_rejected(self, key):
        check = PROFILE_CASES[key][1]
        assert not check(["GIT"])
        assert not check(["SQL", "GIT"])

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    @pytest.mark.parametrize("foreign", FOREIGN_TOKENS)
    def test_foreign_tokens_anywhere_are_rejected(self, key, foreign):
        profile, check, _ = PROFILE_CASES[key]
        base = _required_tokens(profile)
        noisy = base + [_noise_token(profile)]
        assert check(base) and check(noisy)
        for sequence in (base, noisy):
            for position in range(len(sequence) + 1):
                mutated = sequence[:position] + [foreign] + sequence[position:]
                assert not check(mutated), (foreign, position)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_a_sequence_made_only_of_foreign_tokens_is_rejected(self, key):
        check = PROFILE_CASES[key][1]
        assert not check(["COBOL"])
        assert not check(["COBOL", "FORTRAN", "ASSEMBLY"])
        assert not check(["", ""])

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_swapping_two_adjacent_stages_is_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for index in range(len(minimal) - 1):
            swapped = list(minimal)
            swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
            assert not check(swapped), (swapped, index)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_reversed_sequences_are_rejected(self, key):
        profile, check, sequences = PROFILE_CASES[key]
        for sequence in [_required_tokens(profile)] + sequences:
            assert not check(list(reversed(sequence)))

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_returning_to_an_earlier_stage_is_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for index in range(len(minimal) - 1):
            broken = minimal[: index + 2] + [minimal[index]] + minimal[index + 2:]
            assert not check(broken), (broken, index)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_a_trailing_skill_of_an_earlier_stage_is_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for token in minimal[:-1]:
            assert not check(minimal + [token]), token

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_optional_stages_out_of_order_are_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for position, stage in enumerate(profile.stages):
            if stage.required:
                continue
            before = sum(1 for s in profile.stages[:position] if s.required)
            in_place = minimal[:before] + [stage.tokens[0]] + minimal[before:]
            # Moved behind the skill of the next required stage: the stages are out of order.
            moved = minimal[: before + 1] + [stage.tokens[0]] + minimal[before + 1:]
            assert check(in_place), (stage.name, in_place)
            assert not check(moved), (stage.name, moved)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_a_known_skill_outside_the_profile_cannot_replace_a_required_stage(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        noise = _noise_token(profile)
        for index in range(len(minimal)):
            replaced = list(minimal)
            replaced[index] = noise
            assert not check(replaced), (index, noise)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_skills_outside_the_profile_cannot_come_before_it(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        noise = _noise_token(profile)
        assert not check([noise] + minimal)
        for index in range(1, len(minimal)):
            assert not check(minimal[:index] + [noise] + minimal[index:]), index

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_a_profile_skill_after_skills_outside_the_profile_is_rejected(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        noise = _noise_token(profile)
        assert check(minimal + [noise])
        for token in minimal:
            assert not check(minimal + [noise, token]), token

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_tokens_are_compared_exactly(self, key):
        profile, check, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for index, token in enumerate(minimal):
            for variant in (token.lower(), token.capitalize(), f" {token}", f"{token} ", token + "S", token[:-1]):
                mutated = list(minimal)
                mutated[index] = variant
                assert not check(mutated), variant

    def test_raw_spellings_are_not_canonical_names(self):
        # Stage 2 must run first: the automata do not unify spellings.
        assert not accepts_full_stack(["JS", "React.js", "NodeJS", "Postgres", "Git"])
        assert not accepts_ml(["Python", "Pandas", "NumPy", "scikit-learn", "SQL", "Git"])
        assert not accepts_devops(["Python", "Docker", "K8s", "Terraform", "Git"])
        assert not accepts_data(["Python", "Spark", "Airflow", "Postgres", "Git"])

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_canonical_sequences_of_one_profile_are_rejected_by_the_others(self, key):
        _, _, sequences = PROFILE_CASES[key]
        for other in PROFILE_KEYS:
            if other == key:
                continue
            check = PROFILE_CASES[other][1]
            for sequence in sequences:
                assert not check(sequence), (key, other, sequence)

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_rejection_leaves_the_shared_automaton_usable(self, key):
        profile, check, sequences = PROFILE_CASES[key]
        assert not check(["NOT_A_SKILL"])
        assert check(sequences[0])


# ---------------------------------------------------------------------------
# Formal structure of the four automata: M = (Q, Sigma, delta, q0, F)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", params=ALL_PROFILES, ids=lambda p: p.name)
def built(request):
    return request.param, build_automaton(request.param)


class TestAutomataStructure:
    def test_is_a_deterministic_pyformlang_automaton(self, built):
        _, automaton = built
        assert isinstance(automaton, DeterministicFiniteAutomaton)
        assert automaton.is_deterministic()

    def test_states_are_the_stage_states_plus_the_noise_state(self, built):
        profile, automaton = built
        expected = {State(f"q{i}") for i in range(len(profile.stages) + 1)} | {State("q_noise")}
        assert set(automaton.states) == expected
        assert len(automaton.states) == len(profile.stages) + 2

    def test_single_initial_state_that_does_not_accept(self, built):
        _, automaton = built
        assert automaton.start_state == State("q0")
        assert not automaton.is_final_state(State("q0"))
        assert not automaton.accepts([])

    def test_accepting_states(self, built):
        profile, automaton = built
        expected = {State(f"q{i}") for i in _accepting_indices(profile)} | {State("q_noise")}
        assert set(automaton.final_states) == expected

    def test_alphabet_is_every_canonical_name_of_stage_2(self, built):
        profile, automaton = built
        assert {symbol.value for symbol in automaton.symbols} == set(KNOWN_SKILLS)
        assert set(profile.alphabet) <= set(KNOWN_SKILLS)

    def test_stage_transitions(self, built):
        profile, automaton = built
        table = automaton.to_dict()
        for position, stage in enumerate(profile.stages, start=1):
            for token in stage.tokens:
                for origin in _source_states(profile, position):
                    assert table[State(f"q{origin}")][Symbol(token)] == State(f"q{position}"), (stage.name, token, origin)

    def test_noise_transitions(self, built):
        profile, automaton = built
        table = automaton.to_dict()
        noise = KNOWN_SKILLS - set(profile.alphabet)
        for index in _accepting_indices(profile):
            for token in noise:
                assert table[State(f"q{index}")][Symbol(token)] == State("q_noise")
        for token in noise:
            assert table[State("q_noise")][Symbol(token)] == State("q_noise")
        assert set(table[State("q_noise")]) == {Symbol(token) for token in noise}

    def test_number_of_transitions(self, built):
        profile, automaton = built
        stage_transitions = sum(
            len(stage.tokens) * len(_source_states(profile, position))
            for position, stage in enumerate(profile.stages, start=1)
        )
        noise = len(KNOWN_SKILLS - set(profile.alphabet))
        noise_transitions = noise * (len(_accepting_indices(profile)) + 1)
        assert automaton.get_number_transitions() == stage_transitions + noise_transitions

    def test_every_state_is_reachable_from_the_initial_state(self, built):
        _, automaton = built
        table = automaton.to_dict()
        reached, frontier = {State("q0")}, [State("q0")]
        while frontier:
            for target in table.get(frontier.pop(), {}).values():
                if target not in reached:
                    reached.add(target)
                    frontier.append(target)
        assert reached == set(automaton.states)

    def test_language_is_not_empty(self, built):
        assert not built[1].is_empty()

    def test_equivalent_to_the_regular_expression_of_the_stages(self, built):
        profile, automaton = built
        oracle = Regex(_pyformlang_regex(profile)).to_epsilon_nfa().to_deterministic()
        assert automaton.is_equivalent_to(oracle)

    def test_minimal_automaton_is_not_larger(self, built):
        profile, automaton = built
        assert len(automaton.minimize().states) <= len(profile.stages) + 2

    def test_fresh_builds_are_equivalent_and_independent(self, built):
        profile, automaton = built
        other = build_automaton(profile)
        assert other is not automaton
        assert other.is_equivalent_to(automaton)

    def test_shared_instances_are_cached(self):
        for getter in (get_full_stack_automaton, get_ml_automaton, get_devops_automaton, get_data_automaton):
            assert getter() is getter()

    def test_builders_and_getters_agree_with_the_generic_builder(self):
        pairs = [
            (build_full_stack_automaton(), FULL_STACK_PROFILE),
            (build_ml_automaton(), ML_PROFILE),
            (build_devops_automaton(), DEVOPS_PROFILE),
            (build_data_automaton(), DATA_PROFILE),
        ]
        for automaton, profile in pairs:
            assert automaton.is_equivalent_to(build_automaton(profile))

    def test_no_two_profile_languages_are_equivalent(self):
        automata = [build_automaton(profile) for profile in ALL_PROFILES]
        for first, second in itertools.combinations(automata, 2):
            assert not first.is_equivalent_to(second)


class TestProfileSpecifications:
    def test_registry_of_profiles(self):
        assert ALL_PROFILES == OFFICIAL_PROFILES + TEAM_PROFILES
        assert OFFICIAL_PROFILES == (FULL_STACK_PROFILE, ML_PROFILE)
        assert TEAM_PROFILES == (DEVOPS_PROFILE, DATA_PROFILE)
        assert [profile.name for profile in ALL_PROFILES] == [
            "Full Stack Developer",
            "Machine Learning Engineer",
            "DevOps Engineer",
            "Data Engineer",
        ]

    def test_stage_names_of_each_profile(self):
        assert [s.name for s in FULL_STACK_PROFILE.stages] == [
            "web_language",
            "frontend_framework",
            "backend_framework",
            "database",
            "api",
            "version_control",
        ]
        assert [s.name for s in ML_PROFILE.stages] == [
            "base_language",
            "data_library",
            "ml_framework",
            "ml_practice",
            "database",
            "version_control",
        ]
        assert [s.name for s in DEVOPS_PROFILE.stages] == [
            "language",
            "container",
            "orchestration",
            "infrastructure_as_code",
            "ci_cd",
            "cloud",
            "version_control",
        ]
        assert [s.name for s in DATA_PROFILE.stages] == [
            "language",
            "data_processing",
            "workflow",
            "database",
            "cloud",
            "version_control",
        ]

    def test_required_and_optional_stages(self):
        optional = {
            profile.name: {s.name for s in profile.stages if not s.required} for profile in ALL_PROFILES
        }
        assert optional == {
            "Full Stack Developer": {"api"},
            "Machine Learning Engineer": {"ml_practice"},
            "DevOps Engineer": {"ci_cd", "cloud"},
            "Data Engineer": {"cloud"},
        }

    def test_stages_of_a_profile_are_pairwise_disjoint(self):
        for profile in ALL_PROFILES:
            assert len(profile.alphabet) == len(set(profile.alphabet)), profile.name

    def test_every_profile_ends_with_version_control(self):
        for profile in ALL_PROFILES:
            assert profile.stages[-1].name == "version_control"
            assert profile.stages[-1].required
            assert profile.stages[-1].tokens == VERSION_CONTROL_TOKENS

    def test_database_vocabulary(self):
        assert len(DATABASE_TOKENS) == len(set(DATABASE_TOKENS))
        assert {"SQL", "NOSQL", "POSTGRESQL", "MONGODB", "SQL_SERVER"} <= set(DATABASE_TOKENS)
        assert set(DATABASE_TOKENS) <= set(KNOWN_SKILLS)

    def test_specifications_are_immutable(self):
        with pytest.raises(AttributeError):
            FULL_STACK_PROFILE.name = "Other"
        with pytest.raises(AttributeError):
            FULL_STACK_PROFILE.stages[0].name = "other"
        assert Stage("s", ("X",)).required is True


class TestBuildAutomatonValidation:
    def test_profile_without_name(self):
        with pytest.raises(ValueError, match="non-empty name"):
            build_automaton(ProfileSpec("", (Stage("one", ("PYTHON",)),)))

    def test_profile_without_stages(self):
        with pytest.raises(ValueError, match="no stages"):
            build_automaton(ProfileSpec("Empty", ()))

    def test_profile_without_required_stage(self):
        spec = ProfileSpec("Optional", (Stage("one", ("PYTHON",), required=False),))
        with pytest.raises(ValueError, match="no required stage"):
            build_automaton(spec)

    def test_stage_without_tokens(self):
        with pytest.raises(ValueError, match="has no tokens"):
            build_automaton(ProfileSpec("Bad", (Stage("one", ()),)))

    def test_empty_token(self):
        with pytest.raises(ValueError, match="empty token"):
            build_automaton(ProfileSpec("Bad", (Stage("one", ("",)),)))

    def test_token_in_two_stages(self):
        spec = ProfileSpec("Bad", (Stage("one", ("PYTHON",)), Stage("two", ("PYTHON",))))
        with pytest.raises(ValueError, match="belongs to both"):
            build_automaton(spec)

    def test_duplicate_token_inside_a_stage_is_harmless(self):
        spec = ProfileSpec("Dup", (Stage("one", ("PYTHON", "PYTHON")), Stage("two", ("GIT",))))
        automaton = build_automaton(spec)
        assert automaton.is_deterministic()
        assert accepts(automaton, ["PYTHON", "GIT"])

    def test_single_stage_profile(self):
        automaton = build_automaton(ProfileSpec("One", (Stage("only", ("PYTHON", "GO")),)))
        assert accepts(automaton, ["PYTHON"])
        assert accepts(automaton, ["GO", "PYTHON", "GO"])
        assert accepts(automaton, ["PYTHON", "DOCKER"])  # known skill outside the profile
        assert not accepts(automaton, [])
        assert not accepts(automaton, ["DOCKER"])
        assert not accepts(automaton, ["UNKNOWN"])

    def test_a_custom_profile_with_optional_stage_in_the_middle(self):
        spec = ProfileSpec(
            "Toy",
            (Stage("a", ("PYTHON", "GO")), Stage("b", ("DOCKER",), required=False), Stage("c", ("GIT",))),
        )
        automaton = build_automaton(spec)
        assert accepts(automaton, ["PYTHON", "GIT"])
        assert accepts(automaton, ["GO", "DOCKER", "DOCKER", "GIT"])
        assert not accepts(automaton, ["DOCKER", "GIT"])  # the required first stage is missing
        assert not accepts(automaton, ["PYTHON", "GIT", "DOCKER"])  # optional stage after the last one
        assert not accepts(automaton, ["PYTHON", "GIT", "PYTHON"])

    def test_exhaustive_agreement_with_python_re_on_a_small_profile(self):
        spec = ProfileSpec(
            "Toy",
            (Stage("a", ("PYTHON", "GO")), Stage("b", ("DOCKER",), required=False), Stage("c", ("GIT",))),
        )
        automaton = build_automaton(spec)
        oracle = _python_regex(spec)
        alphabet = ["PYTHON", "GO", "DOCKER", "GIT", "AWS", "ZZZ"]
        checked = 0
        for length in range(0, 7):
            for word in itertools.product(alphabet, repeat=length):
                expected = bool(oracle.fullmatch("".join(token + "," for token in word)))
                assert accepts(automaton, word) == expected, word
                checked += 1
        assert checked == sum(6**n for n in range(0, 7))


# ---------------------------------------------------------------------------
# Classifier: classify_sequence
# ---------------------------------------------------------------------------
class TestClassifySequenceAccepted:
    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_accepted_result(self, key):
        profile, _, sequences = PROFILE_CASES[key]
        for sequence in sequences:
            result = classify_sequence(sequence, profile.name)
            assert isinstance(result, EvaluationResult)
            assert result.profile_name == profile.name
            assert result.is_accepted is True
            assert result.matched_sequence == sequence
            assert result.details.splitlines()[0] == f"{ACCEPTED} - {profile.name}"
            assert "Sequence read: " + ", ".join(sequence) in result.details
            assert "Stages satisfied:" in result.details
            assert "Reason" not in result.details

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_every_choice_of_stage_tokens_is_accepted_by_the_classifier(self, key):
        profile, _, _ = PROFILE_CASES[key]
        for sequence in _all_choice_sequences(profile):
            assert classify_sequence(sequence, profile.name).is_accepted, sequence

    def test_report_lists_the_satisfied_stages(self):
        result = classify_sequence(["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"], "Full Stack Developer")
        assert (
            "Stages satisfied: web_language (JAVASCRIPT); frontend_framework (REACT); "
            "backend_framework (NODE_JS); database (POSTGRESQL); version_control (GIT)"
        ) in result.details
        assert "Optional stages not used: api" in result.details

    def test_report_mentions_the_optional_stages_that_were_used(self):
        result = classify_sequence(
            ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "JENKINS", "AWS", "GIT"], "DevOps Engineer"
        )
        assert result.is_accepted
        assert "ci_cd (JENKINS)" in result.details
        assert "cloud (AWS)" in result.details
        assert "Optional stages not used" not in result.details

    def test_skills_outside_the_profile_are_ignored_and_reported(self):
        sequence = ["PYTHON", "SPARK", "AIRFLOW", "SQL", "GIT", "DOCKER", "REACT"]
        result = classify_sequence(sequence, "Data Engineer")
        assert result.is_accepted
        assert result.matched_sequence == ["PYTHON", "SPARK", "AIRFLOW", "SQL", "GIT"]
        assert "Skills outside the profile (ignored): DOCKER, REACT" in result.details

    def test_accepts_any_iterable(self):
        sequence = ("JAVASCRIPT", "REACT", "NODE_JS", "SQL", "GIT")
        assert classify_sequence(sequence, "Full Stack Developer").is_accepted
        assert classify_sequence(iter(sequence), "Full Stack Developer").is_accepted
        assert classify_sequence((t for t in sequence), "Full Stack Developer").is_accepted

    def test_input_sequence_is_not_modified(self):
        sequence = ["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "GIT", "DOCKER"]
        snapshot = list(sequence)
        classify_sequence(sequence, "Full Stack Developer")
        assert sequence == snapshot


class TestClassifySequenceRejected:
    def test_rejected_result(self):
        result = classify_sequence(["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL"], "Full Stack Developer")
        assert isinstance(result, EvaluationResult)
        assert result.profile_name == "Full Stack Developer"
        assert result.is_accepted is False
        assert result.details.splitlines()[0] == f"{REJECTED} - Full Stack Developer"
        assert result.matched_sequence == ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL"]
        assert "Stages satisfied" not in result.details

    def test_reason_for_an_empty_sequence(self):
        result = classify_sequence([], "Machine Learning Engineer")
        assert not result.is_accepted
        assert result.matched_sequence == []
        assert "Sequence read: (empty)" in result.details
        assert "the sequence is empty" in result.details

    def test_reason_for_a_sequence_that_ends_too_early(self):
        result = classify_sequence(["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL"], "Full Stack Developer")
        assert "ends before the required stage(s) version_control" in result.details

    def test_reason_for_a_missing_required_stage(self):
        result = classify_sequence(["JAVASCRIPT", "NODE_JS", "POSTGRESQL", "GIT"], "Full Stack Developer")
        assert not result.is_accepted
        assert "NODE_JS (position 2)" in result.details
        assert "required stage(s) frontend_framework must come before it" in result.details
        assert result.matched_sequence == ["JAVASCRIPT"]

    def test_reason_for_stages_out_of_order(self):
        result = classify_sequence(["JAVASCRIPT", "REACT", "NODE_JS", "GIT", "POSTGRESQL"], "Full Stack Developer")
        assert not result.is_accepted
        assert "GIT (position 4)" in result.details
        assert "required stage(s) database must come before it" in result.details

    def test_reason_for_going_back_to_an_earlier_stage(self):
        sequence = ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT", "AWS"]
        result = classify_sequence(sequence, "DevOps Engineer")
        assert not result.is_accepted
        assert "which comes before the stage already reached ('version_control')" in result.details
        assert "the stages must be in order" in result.details

    def test_reason_for_a_foreign_token(self):
        sequence = ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT", "COBOL"]
        result = classify_sequence(sequence, "Full Stack Developer")
        assert not result.is_accepted
        assert "COBOL (position 6) is not a canonical skill name produced by Stage 2" in result.details

    def test_reason_for_raw_spellings(self):
        result = classify_sequence(["JS", "React.js", "NodeJS", "Postgres", "Git"], "Full Stack Developer")
        assert not result.is_accepted
        assert "JS (position 1) is not a canonical skill name" in result.details
        assert result.matched_sequence == []

    def test_reason_for_a_skill_outside_the_profile_that_comes_too_early(self):
        sequence = ["DOCKER", "JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]
        result = classify_sequence(sequence, "Full Stack Developer")
        assert not result.is_accepted
        assert "DOCKER (position 1) is outside the profile and appears before the required stage(s)" in result.details

    def test_reason_for_a_profile_skill_after_skills_outside_the_profile(self):
        sequence = ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT", "DOCKER", "REACT"]
        result = classify_sequence(sequence, "Full Stack Developer")
        assert not result.is_accepted
        assert "appears after skills outside the profile; the profile part must come first" in result.details

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_every_proper_prefix_gets_a_reason(self, key):
        profile, _, _ = PROFILE_CASES[key]
        minimal = _required_tokens(profile)
        for cut in range(len(minimal)):
            result = classify_sequence(minimal[:cut], profile.name)
            assert not result.is_accepted
            assert result.details.splitlines()[0] == f"{REJECTED} - {profile.name}"
            assert "Reason: " in result.details
            assert "the automaton does not accept the sequence" not in result.details


class TestClassifySequenceErrors:
    @pytest.mark.parametrize("name", ["Backend Developer", "", "Full Stack", "Data Scientist", "DEVOPS"])
    def test_unknown_profile(self, name):
        with pytest.raises(UnknownProfileError, match="Unknown profile"):
            classify_sequence(["GIT"], name)

    def test_unknown_profile_error_is_a_value_error(self):
        assert issubclass(UnknownProfileError, ValueError)

    def test_a_single_string_is_not_a_sequence(self):
        with pytest.raises(TypeError, match="not a single string"):
            classify_sequence("JAVASCRIPT", "Full Stack Developer")

    @pytest.mark.parametrize("sequence", [["GIT", 3], [None], ["GIT", None], [1, 2, 3], [["GIT"]]])
    def test_items_must_be_strings(self, sequence):
        with pytest.raises(TypeError, match="must be a string"):
            classify_sequence(sequence, "Data Engineer")

    @pytest.mark.parametrize(
        "name",
        ["Full Stack Developer", "FULL_STACK_DEVELOPER", "full stack developer", "Full-Stack Developer", "  full   stack developer "],
    )
    def test_profile_name_forms_are_equivalent(self, name):
        sequence = ["JAVASCRIPT", "REACT", "NODE_JS", "SQL", "GIT"]
        result = classify_sequence(sequence, name)
        assert result.profile_name == "Full Stack Developer"
        assert result.is_accepted

    def test_profile_spec_lookup(self):
        for profile in ALL_PROFILES:
            assert profile_spec(profile.name) is profile
            assert PROFILE_SPECS[resolve_profile(profile.name)] is profile
        with pytest.raises(UnknownProfileError):
            profile_spec("Nope")

    def test_verdict_of(self):
        accepted = classify_sequence(FULL_STACK_ACCEPTED[0], "Full Stack Developer")
        rejected = classify_sequence([], "Full Stack Developer")
        assert verdict_of(accepted) == ACCEPTED == "ACCEPTED"
        assert verdict_of(rejected) == REJECTED == "REJECTED"


class TestClassifierAgreesWithTheAutomata:
    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_verdict_of_classifier_automaton_and_python_re_over_all_short_words(self, key):
        profile, check, _ = PROFILE_CASES[key]
        oracle = _python_regex(profile)
        alphabet = _required_tokens(profile) + [_noise_token(profile), "ZZZ_FOREIGN"]
        accepted_seen = 0
        for length in range(0, 6):
            for word in itertools.product(alphabet, repeat=length):
                expected = bool(oracle.fullmatch("".join(token + "," for token in word)))
                result = classify_sequence(word, profile.name)
                assert result.is_accepted == expected == check(word), word
                if not expected:
                    assert "the automaton does not accept the sequence" not in result.details, word
                else:
                    accepted_seen += 1
        assert accepted_seen > 0

    @pytest.mark.parametrize("key", PROFILE_KEYS)
    def test_matched_sequence_only_holds_skills_of_the_profile(self, key):
        profile, _, sequences = PROFILE_CASES[key]
        alphabet = set(profile.alphabet)
        for sequence in sequences + [_required_tokens(profile) + [_noise_token(profile)]]:
            result = classify_sequence(sequence, profile.name)
            assert set(result.matched_sequence) <= alphabet


# ---------------------------------------------------------------------------
# Classifier: classify_records and classify_all (Stage 2 -> Stage 3)
# ---------------------------------------------------------------------------
class TestClassifyRecords:
    def test_sorts_the_records_before_classifying(self):
        records = _records(["Git", "NodeJS", "JS", "Postgres", "React.js"])
        result = classify_records(records, "Full Stack Developer")
        assert result.is_accepted
        assert result.matched_sequence == ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]

    def test_equals_classifying_the_sorted_sequence(self):
        records = _records(["Git", "NodeJS", "JS", "Postgres", "React.js", "Docker"])
        for profile in ALL_PROFILES:
            direct = classify_records(records, profile.name)
            via_sequence = classify_sequence(sort_by_profile(records, profile.name), profile.name)
            assert direct == via_sequence

    def test_result_does_not_depend_on_the_order_of_the_records(self):
        raw = ["Git", "NodeJS", "JS", "Postgres", "React.js"]
        expected = classify_records(_records(raw), "Full Stack Developer")
        for permutation in itertools.permutations(raw):
            assert classify_records(_records(list(permutation)), "Full Stack Developer") == expected

    def test_empty_records_are_rejected_by_every_profile(self):
        for profile in ALL_PROFILES:
            result = classify_records([], profile.name)
            assert not result.is_accepted
            assert "the sequence is empty" in result.details

    def test_unknown_profile(self):
        with pytest.raises(UnknownProfileError):
            classify_records(_records(["Git"]), "Nope")

    def test_profile_name_forms(self):
        records = _records(["Python", "Docker", "Kubernetes", "Terraform", "Git"])
        assert classify_records(records, "devops engineer") == classify_records(records, "DEVOPS_ENGINEER")


class TestClassifyAll:
    def test_one_result_per_profile_in_the_order_of_the_sorter(self):
        report = classify_all(_records(["Git"]))
        assert isinstance(report, ClassificationReport)
        assert [resolve_profile(result.profile_name) for result in report.results] == list(PROFILES)
        assert [result.profile_name for result in report.results] == [p.name for p in ALL_PROFILES]

    def test_accepted_and_rejected_profiles_partition_the_four_profiles(self):
        report = classify_all(_records(["JS", "React", "Node", "Postgres", "Git"]))
        assert report.accepted_profiles == ["Full Stack Developer"]
        assert report.rejected_profiles == ["Machine Learning Engineer", "DevOps Engineer", "Data Engineer"]
        assert sorted(report.accepted_profiles + report.rejected_profiles) == sorted(p.name for p in ALL_PROFILES)

    def test_verdicts_map(self):
        report = classify_all(_records(["JS", "React", "Node", "Postgres", "Git"]))
        assert report.verdicts() == {
            "Full Stack Developer": ACCEPTED,
            "Machine Learning Engineer": REJECTED,
            "DevOps Engineer": REJECTED,
            "Data Engineer": REJECTED,
        }

    def test_result_for_accepts_every_name_form(self):
        report = classify_all(_records(["Python", "Spark", "Airflow", "SQL", "Git"]))
        for name in ("Data Engineer", "DATA_ENGINEER", "data engineer"):
            assert report.result_for(name).profile_name == "Data Engineer"
            assert report.result_for(name).is_accepted

    def test_result_for_unknown_profile(self):
        with pytest.raises(UnknownProfileError):
            classify_all(_records(["Git"])).result_for("Nope")

    def test_result_for_a_profile_missing_from_the_report(self):
        with pytest.raises(KeyError, match="no result for profile"):
            ClassificationReport(results=[]).result_for("Data Engineer")

    def test_empty_report(self):
        report = ClassificationReport()
        assert report.results == []
        assert report.accepted_profiles == []
        assert report.rejected_profiles == []
        assert report.verdicts() == {}

    def test_equals_classifying_each_profile_separately(self):
        records = _records(["Python", "Pandas", "sklearn", "SQL", "Git", "Docker"])
        report = classify_all(records)
        for profile in ALL_PROFILES:
            assert report.result_for(profile.name) == classify_records(records, profile.name)

    def test_no_skills_means_no_profile(self):
        report = classify_all([])
        assert report.accepted_profiles == []
        assert len(report.rejected_profiles) == 4
        assert all(verdict == REJECTED for verdict in report.verdicts().values())

    @pytest.mark.parametrize("raw, expected", MULTI_PROFILE_CASES)
    def test_candidates_that_fit_several_profiles_or_none(self, raw, expected):
        report = classify_all(_records(raw))
        assert report.accepted_profiles == expected
        for name in expected:
            assert report.result_for(name).details.startswith(f"{ACCEPTED} - {name}")
        for name in report.rejected_profiles:
            assert report.result_for(name).details.startswith(f"{REJECTED} - {name}")

    def test_a_candidate_can_be_accepted_by_more_than_one_profile(self):
        report = classify_all(_records(["Python", "Pandas", "sklearn", "Spark", "Airflow", "SQL", "Git"]))
        assert len(report.accepted_profiles) == 2


# ---------------------------------------------------------------------------
# End to end: resume text -> extraction -> normalization -> classification
# ---------------------------------------------------------------------------
def _classify_text(text):
    raw = extract_resume(text).raw_skills
    return classify_all(normalize_with_report(raw).records)


class TestEndToEndOnSyntheticResumes:
    @pytest.mark.parametrize(
        "fixture_name, expected",
        [
            ("fullstack_text", ["Full Stack Developer"]),
            ("ml_text", ["Machine Learning Engineer"]),
            ("devops_text", ["DevOps Engineer"]),
            ("data_text", ["Data Engineer"]),
            ("invalid_text", []),
        ],
    )
    def test_each_resume_is_accepted_by_its_profile_only(self, fixture_name, expected, request):
        report = _classify_text(request.getfixturevalue(fixture_name))
        assert report.accepted_profiles == expected
        assert len(report.rejected_profiles) == 4 - len(expected)

    def test_reports_of_the_rejected_profiles_explain_why(self, fullstack_text):
        report = _classify_text(fullstack_text)
        ml = report.result_for("Machine Learning Engineer")
        assert not ml.is_accepted
        assert ml.details.startswith("REJECTED - Machine Learning Engineer")
        assert "Reason: " in ml.details

    def test_invalid_resume_is_rejected_because_it_has_no_skills(self, invalid_text):
        report = _classify_text(invalid_text)
        for result in report.results:
            assert not result.is_accepted
            assert "the sequence is empty" in result.details

    @pytest.mark.parametrize("fixture_name", ["fullstack_text", "ml_text", "devops_text", "data_text"])
    def test_the_order_in_which_skills_are_written_does_not_matter(self, fixture_name, request):
        raw = extract_resume(request.getfixturevalue(fixture_name)).raw_skills
        expected = classify_all(normalize_with_report(raw).records).verdicts()
        generator = random.Random(2026)
        for _ in range(25):
            shuffled = list(raw)
            generator.shuffle(shuffled)
            assert classify_all(normalize_with_report(shuffled).records).verdicts() == expected

    @pytest.mark.parametrize(
        "fixture_name, dropped, profile",
        [
            ("fullstack_text", ["Postgres"], "Full Stack Developer"),
            ("fullstack_text", ["React.js"], "Full Stack Developer"),
            ("fullstack_text", ["NodeJS"], "Full Stack Developer"),
            ("fullstack_text", ["Git"], "Full Stack Developer"),
            ("ml_text", ["Pandas", "NumPy"], "Machine Learning Engineer"),
            ("ml_text", ["Scikit-learn", "TensorFlow"], "Machine Learning Engineer"),
            ("ml_text", ["SQL"], "Machine Learning Engineer"),
            ("devops_text", ["Terraform"], "DevOps Engineer"),
            ("devops_text", ["Docker"], "DevOps Engineer"),
            ("data_text", ["Airflow"], "Data Engineer"),
            ("data_text", ["PostgreSQL"], "Data Engineer"),
        ],
    )
    def test_removing_all_the_skills_of_a_required_stage_rejects_the_candidate(
        self, fixture_name, dropped, profile, request
    ):
        raw = extract_resume(request.getfixturevalue(fixture_name)).raw_skills
        kept = [skill for skill in raw if skill not in dropped]
        assert len(kept) == len(raw) - len(dropped)
        assert classify_all(normalize_with_report(raw).records).result_for(profile).is_accepted
        assert not classify_all(normalize_with_report(kept).records).result_for(profile).is_accepted

    @pytest.mark.parametrize("dropped", [["NumPy"], ["Pandas"], ["TensorFlow"], ["Scikit-learn"]])
    def test_a_stage_with_alternatives_survives_the_loss_of_one_of_them(self, dropped, ml_text):
        raw = extract_resume(ml_text).raw_skills
        kept = [skill for skill in raw if skill not in dropped]
        assert classify_all(normalize_with_report(kept).records).result_for("Machine Learning Engineer").is_accepted

    @pytest.mark.parametrize("extra", [["Docker"], ["Python", "Docker"], ["Cobol"], ["Docker", "Cobol", "Excel"]])
    def test_extra_skills_do_not_change_the_verdict_of_the_fullstack_resume(self, extra, fullstack_text):
        raw = extract_resume(fullstack_text).raw_skills + extra
        report = classify_all(normalize_with_report(raw).records)
        assert report.result_for("Full Stack Developer").is_accepted

    def test_spelling_variants_and_case_give_the_same_verdicts(self):
        canonical = classify_all(_records(["JS", "React.js", "NodeJS", "Postgres", "Git"])).verdicts()
        variants = classify_all(_records(["javascript", "REACT", "node", "postgresql", "GIT"])).verdicts()
        assert canonical == variants

    @pytest.mark.parametrize("raw, expected", MULTI_PROFILE_CASES)
    def test_multi_profile_candidates_do_not_depend_on_the_order_of_skills(self, raw, expected):
        generator = random.Random(7)
        for _ in range(10):
            shuffled = list(raw)
            generator.shuffle(shuffled)
            assert classify_all(_records(shuffled)).accepted_profiles == expected


# ---------------------------------------------------------------------------
# Public interface of the package
# ---------------------------------------------------------------------------
class TestPackageInterface:
    def test_every_name_in_all_is_importable(self):
        import resumelens.classification as package
        import resumelens.classification.classifier as classifier_module

        for module in (package, classifier_module):
            for name in module.__all__:
                assert hasattr(module, name), (module.__name__, name)

    def test_package_reexports_the_main_entry_points(self):
        import resumelens.classification as package

        assert package.classify_all is classify_all
        assert package.classify_sequence is classify_sequence
        assert package.classify_records is classify_records
        assert package.ALL_PROFILES is ALL_PROFILES

    def test_sorter_and_automata_profiles_match(self):
        assert set(PROFILE_SPECS) == set(PROFILES)
        assert [resolve_profile(profile.name) for profile in ALL_PROFILES] == list(PROFILES)
