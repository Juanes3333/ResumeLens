"""Initial tests for Stage 3 — finite automata of the official profiles.

Covers acceptance and rejection of canonical skill sequences for the Full Stack Developer
and Machine Learning Engineer automata. The automata read canonical names (the output
alphabet of Stage 2), so the sequences below are written directly in canonical form.
"""

import pytest
from pyformlang.finite_automaton import DeterministicFiniteAutomaton

from resumelens.classification.automata import (
    FULL_STACK_PROFILE,
    ML_PROFILE,
    accepts,
    accepts_full_stack,
    accepts_ml,
    build_full_stack_automaton,
    build_ml_automaton,
    get_full_stack_automaton,
    get_ml_automaton,
)

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
