"""Tests for Stage 2 — normalization with finite-state transducers.

This first version covers the Web / Frontend / Backend transducer. Tests for the other
technology families are added together with their transducers.
"""

import pytest
from pyformlang.fst import FST

from resumelens.extraction.extractor import extract_resume
from resumelens.normalization.transducers import (
    END_OF_TOKEN,
    INITIAL_STATE,
    WEB_CANONICAL_FORMS,
    WEB_VARIANTS,
    apply_transducer,
    build_transducer,
    build_web_transducer,
    get_web_transducer,
    normalize_web_skill,
)

# Mapping required by the project: variant -> canonical name.
WEB_EXPECTED = [
    ("JS", "JAVASCRIPT"),
    ("Javascript", "JAVASCRIPT"),
    ("js", "JAVASCRIPT"),
    ("TS", "TYPESCRIPT"),
    ("TypeScript", "TYPESCRIPT"),
    ("ts", "TYPESCRIPT"),
    ("React.js", "REACT"),
    ("ReactJS", "REACT"),
    ("react", "REACT"),
    ("NodeJS", "NODE_JS"),
    ("Node.js", "NODE_JS"),
    ("node", "NODE_JS"),
    ("AngularJS", "ANGULAR"),
    ("Angular.js", "ANGULAR"),
    ("Vue.js", "VUE"),
    ("VueJS", "VUE"),
    ("Spring Boot", "SPRING_BOOT"),
    ("SpringBoot", "SPRING_BOOT"),
    ("Django", "DJANGO"),
]


# ---------------------------------------------------------------------------
# Web transducer: translations
# ---------------------------------------------------------------------------
class TestWebTranslations:
    @pytest.mark.parametrize("raw, canonical", WEB_EXPECTED)
    def test_required_variants(self, raw, canonical):
        assert normalize_web_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw, canonical",
        [
            ("Angular", "ANGULAR"),
            ("Vue", "VUE"),
            ("Node", "NODE_JS"),
            ("React", "REACT"),
            ("JavaScript", "JAVASCRIPT"),
        ],
    )
    def test_bare_and_official_spellings(self, raw, canonical):
        assert normalize_web_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw, canonical",
        [
            ("jAvAsCrIpT", "JAVASCRIPT"),
            ("REACT.JS", "REACT"),
            ("nodejs", "NODE_JS"),
            ("SPRING BOOT", "SPRING_BOOT"),
            ("django", "DJANGO"),
            ("vUe.JS", "VUE"),
        ],
    )
    def test_case_is_ignored(self, raw, canonical):
        assert normalize_web_skill(raw) == canonical

    @pytest.mark.parametrize("raw", ["  JS", "JS  ", "\tReact.js\n", " Spring Boot "])
    def test_surrounding_whitespace_is_ignored(self, raw):
        assert normalize_web_skill(raw) is not None

    def test_every_listed_variant_is_translated_to_its_canonical_name(self):
        for canonical, spellings in WEB_VARIANTS.items():
            for spelling in spellings:
                assert normalize_web_skill(spelling) == canonical

    def test_variant_that_is_prefix_of_another_is_not_ambiguous(self):
        # "react" is a prefix of "react.js" / "reactjs"; "node" of "nodejs"; same canonical.
        assert normalize_web_skill("react") == "REACT"
        assert normalize_web_skill("react.js") == "REACT"
        assert normalize_web_skill("reactjs") == "REACT"
        assert normalize_web_skill("node") == "NODE_JS"
        assert normalize_web_skill("nodejs") == "NODE_JS"

    def test_translation_is_idempotent_on_the_same_input(self):
        assert normalize_web_skill("JS") == normalize_web_skill("JS")


# ---------------------------------------------------------------------------
# Web transducer: rejections
# ---------------------------------------------------------------------------
class TestWebRejections:
    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "Python",
            "Java",  # a prefix of JavaScript is not a variant
            "Jav",
            "JavaScripts",
            "React.",
            "Reactjs.",
            "Node.jss",
            "Spring  Boot",  # two spaces
            "Spring-Boot",
            "Spring",
            "Djang",
            "Vue.",
            "Angular.jss",
            "TypeScripts",
            "react$",  # '$' must not behave as the end marker
            END_OF_TOKEN,
            "react" + END_OF_TOKEN,
        ],
    )
    def test_tokens_outside_the_language_have_no_translation(self, raw):
        assert normalize_web_skill(raw) is None

    @pytest.mark.parametrize(
        "raw",
        [
            # AI / data libraries, databases and DevOps tools belong to other transducers.
            "Pandas",
            "TensorFlow",
            "Scikit-learn",
            "Postgres",
            "MongoDB",
            "Docker",
            "Kubernetes",
            "Git",
            "AWS",
        ],
    )
    def test_other_technology_families_are_not_handled_here(self, raw):
        assert normalize_web_skill(raw) is None

    def test_rejection_does_not_break_later_translations(self):
        assert normalize_web_skill("Python") is None
        assert normalize_web_skill("JS") == "JAVASCRIPT"


# ---------------------------------------------------------------------------
# Formal structure: 7-tuple (Q, Sigma, Gamma, delta, omega, q0, F)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def fst():
    """Web transducer shared by the structural tests of this module."""
    return build_web_transducer()


class TestWebTransducerStructure:
    def test_returns_pyformlang_fst(self, fst):
        assert isinstance(fst, FST)

    def test_single_initial_state(self, fst):
        assert set(fst.start_states) == {INITIAL_STATE}

    def test_one_final_state_per_canonical_name(self, fst):
        assert set(fst.final_states) == {f"f_{name}" for name in WEB_CANONICAL_FORMS}
        assert set(fst.final_states) <= set(fst.states)

    def test_output_alphabet_is_the_set_of_canonical_names(self, fst):
        assert set(fst.output_symbols) == set(WEB_CANONICAL_FORMS)

    def test_input_alphabet_is_characters_plus_end_marker(self, fst):
        symbols = set(fst.input_symbols)
        assert END_OF_TOKEN in symbols
        assert all(len(s) == 1 for s in symbols - {END_OF_TOKEN})

    def test_input_alphabet_contains_both_cases_of_letters(self, fst):
        symbols = set(fst.input_symbols)
        assert {"j", "J", "r", "R", "s", "S"} <= symbols
        assert {".", " "} <= symbols

    def test_transition_function_is_deterministic(self, fst):
        for (state, symbol), targets in fst.transitions.items():
            assert len(targets) == 1, (state, symbol)

    def test_only_end_marker_transitions_produce_output(self, fst):
        for (_, symbol), targets in fst.transitions.items():
            for _, output in targets:
                if symbol == END_OF_TOKEN:
                    assert len(output) == 1 and output[0] in WEB_CANONICAL_FORMS
                else:
                    assert output == []

    def test_end_marker_transitions_go_to_final_states_only(self, fst):
        for (_, symbol), targets in fst.transitions.items():
            if symbol == END_OF_TOKEN:
                assert all(target in fst.final_states for target, _ in targets)

    def test_final_states_have_no_outgoing_transitions(self, fst):
        sources = {state for state, _ in fst.transitions}
        assert not (sources & set(fst.final_states))

    def test_canonical_forms_follow_declaration_order(self):
        assert WEB_CANONICAL_FORMS == (
            "JAVASCRIPT",
            "TYPESCRIPT",
            "REACT",
            "NODE_JS",
            "ANGULAR",
            "VUE",
            "SPRING_BOOT",
            "DJANGO",
        )

    def test_shared_instance_is_cached(self):
        assert get_web_transducer() is get_web_transducer()

    def test_fresh_builds_are_equivalent(self):
        first, second = build_web_transducer(), build_web_transducer()
        assert first is not second
        assert set(first.states) == set(second.states)
        assert dict(first.transitions) == dict(second.transitions)


# ---------------------------------------------------------------------------
# Generic builder and apply_transducer
# ---------------------------------------------------------------------------
class TestBuildTransducer:
    def test_custom_table(self):
        fst = build_transducer({"ALPHA": ["a", "Alpha"], "BETA": ["b"]})
        assert apply_transducer(fst, "ALPHA") == "ALPHA"
        assert apply_transducer(fst, "a") == "ALPHA"
        assert apply_transducer(fst, "B") == "BETA"
        assert apply_transducer(fst, "al") is None

    def test_duplicate_spelling_for_same_canonical_is_allowed(self):
        fst = build_transducer({"ALPHA": ["a", "A", "a"]})
        assert apply_transducer(fst, "a") == "ALPHA"

    def test_conflicting_spelling_raises(self):
        with pytest.raises(ValueError, match="maps to both"):
            build_transducer({"ONE": ["x"], "TWO": ["x"]})

    def test_conflict_is_detected_ignoring_case(self):
        with pytest.raises(ValueError, match="maps to both"):
            build_transducer({"ONE": ["JS"], "TWO": ["js"]})

    def test_empty_variant_raises(self):
        with pytest.raises(ValueError, match="Empty variant"):
            build_transducer({"ONE": [""]})

    def test_empty_canonical_name_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            build_transducer({"": ["x"]})

    def test_empty_table_accepts_nothing(self):
        fst = build_transducer({})
        assert apply_transducer(fst, "anything") is None
        assert apply_transducer(fst, "") is None

    def test_apply_transducer_rejects_ambiguous_translation(self):
        fst = FST()
        fst.add_start_state("s")
        fst.add_final_state("f")
        fst.add_transitions(
            [
                ("s", "a", "m", []),
                ("s", "a", "n", []),
                ("m", END_OF_TOKEN, "f", ["ONE"]),
                ("n", END_OF_TOKEN, "f", ["TWO"]),
            ]
        )
        with pytest.raises(ValueError, match="Ambiguous translation"):
            apply_transducer(fst, "a")


# ---------------------------------------------------------------------------
# Integration with Stage 1 (raw skills extracted from the synthetic resumes)
# ---------------------------------------------------------------------------
class TestWebTransducerOnExtractedSkills:
    def test_fullstack_resume(self, fullstack_text):
        raw = extract_resume(fullstack_text).raw_skills
        assert raw == ["JS", "React.js", "NodeJS", "Postgres", "Git"]
        assert [normalize_web_skill(s) for s in raw] == [
            "JAVASCRIPT",
            "REACT",
            "NODE_JS",
            None,  # Postgres: database transducer
            None,  # Git: version-control transducer
        ]

    @pytest.mark.parametrize("fixture_name", ["ml_text", "devops_text", "data_text"])
    def test_resumes_without_web_skills_translate_to_nothing(self, fixture_name, request):
        text = request.getfixturevalue(fixture_name)
        raw = extract_resume(text).raw_skills
        assert raw
        assert all(normalize_web_skill(s) is None for s in raw)

    def test_invalid_resume_has_no_skills(self, invalid_text):
        assert extract_resume(invalid_text).raw_skills == []
