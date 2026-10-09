"""Tests for Stage 2 — normalization with finite-state transducers.

Covers the four transducer families defined in ``transducers.py`` (Web, AI / data
libraries, databases and Cloud / DevOps), their formal 7-tuple structure, and the
``SkillNormalizer`` pipeline of ``normalizer.py`` that coordinates them (categories,
duplicates, unrecognized tokens and integration with the Stage 1 extractor).

Canonical ordering of the normalized skills is the job of the sorter (a later stage),
so these tests only check the order of first appearance.
"""

import pytest
from pyformlang.fst import FST

import resumelens.normalization as normalization
from resumelens.core.models import SkillRecord
from resumelens.extraction.extractor import extract_resume
from resumelens.normalization.normalizer import (
    DATA_VARIANTS,
    DEFAULT_FAMILIES,
    LANGUAGE_VARIANTS,
    VCS_VARIANTS,
    WEB_CATEGORIES,
    NormalizationResult,
    SkillNormalizer,
    TechnologyFamily,
    get_default_normalizer,
    normalize_skill,
    normalize_skills,
    normalize_with_report,
)
from resumelens.normalization.transducers import (
    AI_CANONICAL_FORMS,
    AI_VARIANTS,
    DB_CANONICAL_FORMS,
    DB_VARIANTS,
    DEVOPS_CANONICAL_FORMS,
    DEVOPS_VARIANTS,
    END_OF_TOKEN,
    INITIAL_STATE,
    WEB_CANONICAL_FORMS,
    WEB_VARIANTS,
    apply_transducer,
    build_ai_transducer,
    build_db_transducer,
    build_devops_transducer,
    build_transducer,
    build_web_transducer,
    get_web_transducer,
    normalize_ai_skill,
    normalize_db_skill,
    normalize_devops_skill,
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


# ===========================================================================
# Other technology families: AI / data libraries, databases, Cloud / DevOps
# ===========================================================================
AI_EXPECTED = [
    ("Pandas", "PANDAS"),
    ("pandas", "PANDAS"),
    ("NumPy", "NUMPY"),
    ("numpy", "NUMPY"),
    ("Num Py", "NUMPY"),
    ("Scikit-learn", "SCIKIT_LEARN"),
    ("Scikit learn", "SCIKIT_LEARN"),
    ("Scikitlearn", "SCIKIT_LEARN"),
    ("sklearn", "SCIKIT_LEARN"),
    ("sk-learn", "SCIKIT_LEARN"),
    ("TensorFlow", "TENSORFLOW"),
    ("Tensor Flow", "TENSORFLOW"),
    ("TF", "TENSORFLOW"),
    ("tf", "TENSORFLOW"),
    ("PyTorch", "PYTORCH"),
    ("Py Torch", "PYTORCH"),
    ("Torch", "PYTORCH"),
    ("Keras", "KERAS"),
    ("Matplotlib", "MATPLOTLIB"),
]

DB_EXPECTED = [
    ("SQL", "SQL"),
    ("sql", "SQL"),
    ("PostgreSQL", "POSTGRESQL"),
    ("Postgres", "POSTGRESQL"),
    ("Postgre SQL", "POSTGRESQL"),
    ("PSQL", "POSTGRESQL"),
    ("MySQL", "MYSQL"),
    ("My SQL", "MYSQL"),
    ("MariaDB", "MARIADB"),
    ("SQLite", "SQLITE"),
    ("SQLite3", "SQLITE"),
    ("SQL Server", "SQL_SERVER"),
    ("SQLServer", "SQL_SERVER"),
    ("MSSQL", "SQL_SERVER"),
    ("MS SQL", "SQL_SERVER"),
    ("Oracle", "ORACLE"),
    ("Oracle DB", "ORACLE"),
    ("MongoDB", "MONGODB"),
    ("Mongo", "MONGODB"),
    ("Mongo DB", "MONGODB"),
    ("Redis", "REDIS"),
    ("Cassandra", "CASSANDRA"),
]

DEVOPS_EXPECTED = [
    ("Docker", "DOCKER"),
    ("docker", "DOCKER"),
    ("Kubernetes", "KUBERNETES"),
    ("K8s", "KUBERNETES"),
    ("k8s", "KUBERNETES"),
    ("Kube", "KUBERNETES"),
    ("Terraform", "TERRAFORM"),
    ("Jenkins", "JENKINS"),
    ("Ansible", "ANSIBLE"),
    ("AWS", "AWS"),
    ("aws", "AWS"),
    ("Amazon Web Services", "AWS"),
    ("Azure", "AZURE"),
    ("Microsoft Azure", "AZURE"),
    ("GCP", "GCP"),
    ("Google Cloud", "GCP"),
    ("Google Cloud Platform", "GCP"),
]

# family label -> (normalize function, expected pairs, variant table, canonical names)
FAMILY_CASES = {
    "ai": (normalize_ai_skill, AI_EXPECTED, AI_VARIANTS, AI_CANONICAL_FORMS),
    "database": (normalize_db_skill, DB_EXPECTED, DB_VARIANTS, DB_CANONICAL_FORMS),
    "devops": (normalize_devops_skill, DEVOPS_EXPECTED, DEVOPS_VARIANTS, DEVOPS_CANONICAL_FORMS),
}


class TestAiTransducer:
    @pytest.mark.parametrize("raw, canonical", AI_EXPECTED)
    def test_required_variants(self, raw, canonical):
        assert normalize_ai_skill(raw) == canonical

    @pytest.mark.parametrize("raw", ["", "   ", "Scikit", "Tensor", "Pand", "Py", "Num  Py", "PyTorch2"])
    def test_tokens_outside_the_language_have_no_translation(self, raw):
        assert normalize_ai_skill(raw) is None

    @pytest.mark.parametrize("raw", ["Python", "JS", "Postgres", "Docker", "Git", "Spark"])
    def test_other_technology_families_are_not_handled_here(self, raw):
        assert normalize_ai_skill(raw) is None

    def test_surrounding_whitespace_is_ignored(self):
        assert normalize_ai_skill("  sklearn\n") == "SCIKIT_LEARN"


class TestDatabaseTransducer:
    @pytest.mark.parametrize("raw, canonical", DB_EXPECTED)
    def test_required_variants(self, raw, canonical):
        assert normalize_db_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "SQ", "SQLit", "SQL  Server", "SQL Serve", "Postgre", "Mongo-DB", "Oracle DBA"],
    )
    def test_tokens_outside_the_language_have_no_translation(self, raw):
        assert normalize_db_skill(raw) is None

    @pytest.mark.parametrize("raw", ["Pandas", "JS", "Docker", "Git", "Python", "Airflow"])
    def test_other_technology_families_are_not_handled_here(self, raw):
        assert normalize_db_skill(raw) is None

    def test_sql_is_a_prefix_of_other_databases_but_stays_unambiguous(self):
        # "SQL" is a complete variant and also a prefix of "SQLite" / "SQL Server".
        assert normalize_db_skill("SQL") == "SQL"
        assert normalize_db_skill("SQLite") == "SQLITE"
        assert normalize_db_skill("SQL Server") == "SQL_SERVER"
        assert normalize_db_skill("SQLServer") == "SQL_SERVER"

    def test_surrounding_whitespace_is_ignored(self):
        assert normalize_db_skill("\tPostgres ") == "POSTGRESQL"


class TestDevopsTransducer:
    @pytest.mark.parametrize("raw, canonical", DEVOPS_EXPECTED)
    def test_required_variants(self, raw, canonical):
        assert normalize_devops_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "Dock", "Kubernete", "K8", "Amazon", "Amazon Web", "Google", "Microsoft", "AWS3"],
    )
    def test_tokens_outside_the_language_have_no_translation(self, raw):
        assert normalize_devops_skill(raw) is None

    @pytest.mark.parametrize("raw", ["Pandas", "JS", "Postgres", "Git", "Python", "Spark"])
    def test_other_technology_families_are_not_handled_here(self, raw):
        assert normalize_devops_skill(raw) is None

    def test_surrounding_whitespace_is_ignored(self):
        assert normalize_devops_skill(" Docker\n") == "DOCKER"


@pytest.mark.parametrize("family", sorted(FAMILY_CASES))
class TestFamilyTables:
    def test_every_listed_variant_is_translated_to_its_canonical_name(self, family):
        normalize, _, variants, _ = FAMILY_CASES[family]
        for canonical, spellings in variants.items():
            for spelling in spellings:
                assert normalize(spelling) == canonical

    def test_canonical_forms_follow_declaration_order(self, family):
        _, _, variants, canonical_forms = FAMILY_CASES[family]
        assert canonical_forms == tuple(variants)

    def test_expected_table_covers_every_canonical_name(self, family):
        _, expected, _, canonical_forms = FAMILY_CASES[family]
        assert {canonical for _, canonical in expected} == set(canonical_forms)


# ---------------------------------------------------------------------------
# Formal structure of the other transducers: 7-tuple (Q, Sigma, Gamma, delta, omega, q0, F)
# ---------------------------------------------------------------------------
STRUCTURE_CASES = [
    ("web", build_web_transducer, WEB_CANONICAL_FORMS),
    ("ai", build_ai_transducer, AI_CANONICAL_FORMS),
    ("database", build_db_transducer, DB_CANONICAL_FORMS),
    ("devops", build_devops_transducer, DEVOPS_CANONICAL_FORMS),
]


@pytest.fixture(scope="module", params=STRUCTURE_CASES, ids=[case[0] for case in STRUCTURE_CASES])
def built_family(request):
    """(transducer, canonical names) of each family, built once per family."""
    _, builder, canonical_forms = request.param
    return builder(), canonical_forms


class TestAllTransducersStructure:
    def test_returns_pyformlang_fst(self, built_family):
        fst, _ = built_family
        assert isinstance(fst, FST)

    def test_single_initial_state(self, built_family):
        fst, _ = built_family
        assert set(fst.start_states) == {INITIAL_STATE}

    def test_one_final_state_per_canonical_name(self, built_family):
        fst, canonical_forms = built_family
        assert set(fst.final_states) == {f"f_{name}" for name in canonical_forms}
        assert set(fst.final_states) <= set(fst.states)

    def test_output_alphabet_is_the_set_of_canonical_names(self, built_family):
        fst, canonical_forms = built_family
        assert set(fst.output_symbols) == set(canonical_forms)

    def test_input_alphabet_is_characters_plus_end_marker(self, built_family):
        fst, _ = built_family
        symbols = set(fst.input_symbols)
        assert END_OF_TOKEN in symbols
        assert all(len(s) == 1 for s in symbols - {END_OF_TOKEN})

    def test_transition_function_is_deterministic(self, built_family):
        fst, _ = built_family
        for (state, symbol), targets in fst.transitions.items():
            assert len(targets) == 1, (state, symbol)

    def test_only_end_marker_transitions_produce_output(self, built_family):
        fst, canonical_forms = built_family
        for (_, symbol), targets in fst.transitions.items():
            for _, output in targets:
                if symbol == END_OF_TOKEN:
                    assert len(output) == 1 and output[0] in canonical_forms
                else:
                    assert output == []

    def test_end_marker_transitions_go_to_final_states_only(self, built_family):
        fst, _ = built_family
        for (_, symbol), targets in fst.transitions.items():
            if symbol == END_OF_TOKEN:
                assert all(target in fst.final_states for target, _ in targets)

    def test_final_states_have_no_outgoing_transitions(self, built_family):
        fst, _ = built_family
        sources = {state for state, _ in fst.transitions}
        assert not (sources & set(fst.final_states))


class TestFreshBuildsAndCaching:
    @pytest.mark.parametrize(
        "builder", [build_ai_transducer, build_db_transducer, build_devops_transducer]
    )
    def test_fresh_builds_are_equivalent(self, builder):
        first, second = builder(), builder()
        assert first is not second
        assert set(first.states) == set(second.states)
        assert dict(first.transitions) == dict(second.transitions)

    def test_default_families_reuse_cached_transducers(self):
        for family in DEFAULT_FAMILIES:
            assert family.get_transducer() is family.get_transducer()
        assert DEFAULT_FAMILIES[0].get_transducer() is get_web_transducer()


# ---------------------------------------------------------------------------
# The seven families together: the tables must not overlap
# ---------------------------------------------------------------------------
FAMILY_TABLES = {
    "web": WEB_VARIANTS,
    "ai": AI_VARIANTS,
    "database": DB_VARIANTS,
    "devops": DEVOPS_VARIANTS,
    "vcs": VCS_VARIANTS,
    "language": LANGUAGE_VARIANTS,
    "data": DATA_VARIANTS,
}


class TestFamiliesAreDisjoint:
    def test_default_families_and_tables_match(self):
        assert [family.name for family in DEFAULT_FAMILIES] == list(FAMILY_TABLES)

    def test_every_spelling_is_accepted_by_exactly_its_own_family(self):
        # This is what makes the order in which the families are tried irrelevant.
        for family_name, table in FAMILY_TABLES.items():
            for canonical, spellings in table.items():
                for spelling in spellings:
                    accepted = {
                        family.name: apply_transducer(family.get_transducer(), spelling)
                        for family in DEFAULT_FAMILIES
                    }
                    accepted = {name: out for name, out in accepted.items() if out is not None}
                    assert accepted == {family_name: canonical}, spelling

    def test_canonical_names_are_unique_across_families(self):
        names = [canonical for table in FAMILY_TABLES.values() for canonical in table]
        assert len(names) == len(set(names))


# ===========================================================================
# SkillNormalizer: the pipeline that coordinates the transducers
# ===========================================================================
NORMALIZER_EXPECTED = [
    # web
    ("JS", "JAVASCRIPT"),
    ("React.js", "REACT"),
    ("NodeJS", "NODE_JS"),
    ("Spring Boot", "SPRING_BOOT"),
    # ai
    ("sklearn", "SCIKIT_LEARN"),
    ("TensorFlow", "TENSORFLOW"),
    # database
    ("Postgres", "POSTGRESQL"),
    ("SQL", "SQL"),
    ("Mongo", "MONGODB"),
    # devops
    ("K8s", "KUBERNETES"),
    ("Docker", "DOCKER"),
    ("Google Cloud", "GCP"),
    # vcs
    ("Git", "GIT"),
    ("GitHub", "GIT"),
    ("GitLab", "GIT"),
    # languages
    ("Python", "PYTHON"),
    ("Python3", "PYTHON"),
    ("Java", "JAVA"),
    ("C", "C"),
    ("C++", "C_PLUS_PLUS"),
    ("CPP", "C_PLUS_PLUS"),
    ("C#", "C_SHARP"),
    ("Golang", "GO"),
    ("Rust", "RUST"),
    ("Kotlin", "KOTLIN"),
    ("Swift", "SWIFT"),
    ("PHP", "PHP"),
    ("Ruby", "RUBY"),
    # data engineering
    ("Spark", "SPARK"),
    ("Apache Spark", "SPARK"),
    ("PySpark", "SPARK"),
    ("Airflow", "AIRFLOW"),
    ("Apache Airflow", "AIRFLOW"),
]

CATEGORY_EXPECTED = [
    ("JAVASCRIPT", "frontend"),
    ("TYPESCRIPT", "frontend"),
    ("REACT", "frontend"),
    ("ANGULAR", "frontend"),
    ("VUE", "frontend"),
    ("NODE_JS", "backend"),
    ("SPRING_BOOT", "backend"),
    ("DJANGO", "backend"),
    ("PANDAS", "ml"),
    ("SCIKIT_LEARN", "ml"),
    ("TENSORFLOW", "ml"),
    ("SQL", "database"),
    ("POSTGRESQL", "database"),
    ("MONGODB", "database"),
    ("DOCKER", "cloud"),
    ("KUBERNETES", "cloud"),
    ("AWS", "cloud"),
    ("GIT", "vcs"),
    ("PYTHON", "language"),
    ("C_PLUS_PLUS", "language"),
    ("SPARK", "data"),
    ("AIRFLOW", "data"),
]


@pytest.fixture
def normalizer():
    return SkillNormalizer()


class TestNormalizeSingleSkill:
    @pytest.mark.parametrize("raw, canonical", NORMALIZER_EXPECTED)
    def test_translation_through_every_family(self, normalizer, raw, canonical):
        assert normalizer.normalize_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw, canonical",
        [
            ("gITHUB", "GIT"),
            ("PYTHON3", "PYTHON"),
            ("apache spark", "SPARK"),
            ("react.JS", "REACT"),
            ("k8S", "KUBERNETES"),
        ],
    )
    def test_case_is_ignored(self, normalizer, raw, canonical):
        assert normalizer.normalize_skill(raw) == canonical

    @pytest.mark.parametrize(
        "raw, canonical",
        [
            ("  Docker  ", "DOCKER"),
            ("\tGit\n", "GIT"),
            ("Spring   Boot", "SPRING_BOOT"),  # inner whitespace runs are collapsed
            ("  Apache \t Spark ", "SPARK"),
        ],
    )
    def test_whitespace_is_cleaned_before_translation(self, normalizer, raw, canonical):
        assert normalizer.normalize_skill(raw) == canonical

    def test_inner_whitespace_run_is_rejected_by_the_bare_transducer_only(self, normalizer):
        assert normalize_web_skill("Spring  Boot") is None
        assert normalizer.normalize_skill("Spring  Boot") == "SPRING_BOOT"

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "\n", "COBOL", "Fortran", "Reactt", "Python 3", "Rust!", "Pythön", "C--", END_OF_TOKEN],
    )
    def test_unknown_tokens_are_rejected(self, normalizer, raw):
        assert normalizer.normalize_skill(raw) is None

    def test_prefix_of_a_language_is_not_the_language(self, normalizer):
        # "Java" is a language, "Jav" is not; "JavaScript" belongs to the web family.
        assert normalizer.normalize_skill("Java") == "JAVA"
        assert normalizer.normalize_skill("Jav") is None
        assert normalizer.normalize_skill("JavaScript") == "JAVASCRIPT"


class TestCategories:
    @pytest.mark.parametrize("canonical, category", CATEGORY_EXPECTED)
    def test_category_of_canonical_name(self, normalizer, canonical, category):
        assert normalizer.category_of(canonical) == category

    def test_unknown_canonical_name_has_no_category(self, normalizer):
        assert normalizer.category_of("COBOL") is None
        assert normalizer.category_of("javascript") is None  # canonical names are upper-case
        assert normalizer.category_of("") is None

    def test_web_categories_cover_exactly_the_web_canonical_names(self):
        assert set(WEB_CATEGORIES) == set(WEB_CANONICAL_FORMS)
        assert set(WEB_CATEGORIES.values()) == {"frontend", "backend"}

    def test_every_known_spelling_has_a_category(self, normalizer):
        for table in FAMILY_TABLES.values():
            for spellings in table.values():
                for spelling in spellings:
                    record = normalizer.to_record(spelling)
                    assert record is not None, spelling
                    assert record.category, spelling


class TestToRecord:
    def test_record_fields(self, normalizer):
        assert normalizer.to_record("Postgres") == SkillRecord(
            raw_name="Postgres", canonical_name="POSTGRESQL", category="database"
        )

    def test_raw_name_is_the_cleaned_token_not_the_canonical_name(self, normalizer):
        record = normalizer.to_record("  Spring   Boot ")
        assert record.raw_name == "Spring Boot"
        assert record.canonical_name == "SPRING_BOOT"
        assert record.category == "backend"

    def test_original_spelling_and_case_are_preserved_in_raw_name(self, normalizer):
        assert normalizer.to_record("nOdEjS").raw_name == "nOdEjS"

    @pytest.mark.parametrize("raw", ["", "  ", "COBOL"])
    def test_unrecognized_token_has_no_record(self, normalizer, raw):
        assert normalizer.to_record(raw) is None


class TestNormalizeList:
    def test_project_example_keeps_order_of_appearance(self, normalizer):
        # Official example. Putting it in profile order is the sorter's job, not this stage's.
        result = normalizer.normalize(["Git", "NodeJS", "JS", "Postgres", "React.js"])
        assert result.canonical_names == ["GIT", "NODE_JS", "JAVASCRIPT", "POSTGRESQL", "REACT"]
        assert set(result.canonical_names) == {"JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"}
        assert result.unrecognized == []
        assert result.duplicates == []

    def test_records_carry_raw_name_and_category(self, normalizer):
        records = normalizer.normalize(["Git", "NodeJS", "JS"]).records
        assert records == [
            SkillRecord("Git", "GIT", "vcs"),
            SkillRecord("NodeJS", "NODE_JS", "backend"),
            SkillRecord("JS", "JAVASCRIPT", "frontend"),
        ]

    def test_equivalent_spellings_collapse_into_the_first_one(self, normalizer):
        result = normalizer.normalize(["JS", "JavaScript", "Python", "js", "Python3"])
        assert result.canonical_names == ["JAVASCRIPT", "PYTHON"]
        assert [record.raw_name for record in result.records] == ["JS", "Python"]
        assert result.duplicates == ["JavaScript", "js", "Python3"]

    def test_exact_repetition_is_a_duplicate(self, normalizer):
        result = normalizer.normalize(["Docker", "Docker"])
        assert result.canonical_names == ["DOCKER"]
        assert result.duplicates == ["Docker"]

    def test_unrecognized_tokens_are_reported_and_never_become_records(self, normalizer):
        result = normalizer.normalize(["Python", "COBOL", "Git", "Fortran"])
        assert result.canonical_names == ["PYTHON", "GIT"]
        assert result.unrecognized == ["COBOL", "Fortran"]

    def test_unrecognized_tokens_are_deduplicated_ignoring_case(self, normalizer):
        result = normalizer.normalize(["COBOL", "cobol", " Cobol ", "Fortran", "COBOL"])
        assert result.records == []
        assert result.unrecognized == ["COBOL", "Fortran"]

    def test_unrecognized_tokens_are_reported_in_cleaned_form(self, normalizer):
        assert normalizer.normalize(["  Visual   Basic "]).unrecognized == ["Visual Basic"]

    def test_blank_tokens_are_ignored_everywhere(self, normalizer):
        result = normalizer.normalize(["", "   ", "\t", "Git", "\n"])
        assert result.canonical_names == ["GIT"]
        assert result.unrecognized == []
        assert result.duplicates == []

    def test_empty_input(self, normalizer):
        result = normalizer.normalize([])
        assert result.records == []
        assert result.unrecognized == []
        assert result.duplicates == []
        assert result.canonical_names == []

    def test_accepts_any_iterable(self, normalizer):
        expected = ["GIT", "DOCKER"]
        assert normalizer.normalize(("Git", "Docker")).canonical_names == expected
        assert normalizer.normalize(iter(["Git", "Docker"])).canonical_names == expected
        assert normalizer.normalize(s for s in ["Git", "Docker"]).canonical_names == expected

    def test_input_list_is_not_modified(self, normalizer):
        raw = [" Git ", "COBOL", "git"]
        snapshot = list(raw)
        normalizer.normalize(raw)
        assert raw == snapshot

    def test_normalize_skills_returns_only_the_records(self, normalizer):
        raw = ["Git", "COBOL", "JS", "js"]
        assert normalizer.normalize_skills(raw) == normalizer.normalize(raw).records

    def test_same_input_gives_same_output(self, normalizer):
        raw = ["Git", "NodeJS", "JS", "Postgres", "React.js"]
        assert normalizer.normalize(raw) == normalizer.normalize(raw)

    def test_python_and_git_in_one_token_is_unrecognized(self, normalizer):
        # Documented Stage 1 limitation: "Python and Git." is not split into two skills.
        result = normalizer.normalize(["Python and Git"])
        assert result.records == []
        assert result.unrecognized == ["Python and Git"]


class TestNormalizationResult:
    def test_defaults_are_empty_and_independent(self):
        first, second = NormalizationResult(), NormalizationResult()
        assert first.records == [] and first.unrecognized == [] and first.duplicates == []
        first.unrecognized.append("x")
        assert second.unrecognized == []

    def test_canonical_names_follow_records(self):
        result = NormalizationResult(
            records=[SkillRecord("JS", "JAVASCRIPT", "frontend"), SkillRecord("Git", "GIT", "vcs")]
        )
        assert result.canonical_names == ["JAVASCRIPT", "GIT"]


# ---------------------------------------------------------------------------
# Custom families: construction rules of SkillNormalizer
# ---------------------------------------------------------------------------
def _family(name, variants, categories):
    return TechnologyFamily(name, lambda: build_transducer(variants), categories)


class TestCustomFamilies:
    def test_single_custom_family(self):
        family = _family("letters", {"ALPHA": ["a", "alpha"], "BETA": ["b"]}, {"ALPHA": "x", "BETA": "y"})
        custom = SkillNormalizer([family])
        assert custom.normalize_skill("Alpha") == "ALPHA"
        assert custom.to_record("B") == SkillRecord("B", "BETA", "y")
        assert custom.normalize_skill("JS") is None  # default families are not consulted

    def test_families_property_keeps_the_given_order(self):
        first = _family("one", {"ALPHA": ["a"]}, {"ALPHA": "x"})
        second = _family("two", {"BETA": ["b"]}, {"BETA": "y"})
        assert SkillNormalizer([first, second]).families == (first, second)

    def test_no_families_recognizes_nothing(self):
        custom = SkillNormalizer([])
        assert custom.normalize_skill("JS") is None
        result = custom.normalize(["JS", "Git"])
        assert result.records == []
        assert result.unrecognized == ["JS", "Git"]

    def test_canonical_name_declared_by_two_families_raises(self):
        first = _family("one", {"ALPHA": ["a"]}, {"ALPHA": "x"})
        second = _family("two", {"ALPHA": ["z"]}, {"ALPHA": "y"})
        with pytest.raises(ValueError, match="more than one family"):
            SkillNormalizer([first, second])

    def test_empty_category_raises(self):
        family = _family("one", {"ALPHA": ["a"]}, {"ALPHA": ""})
        with pytest.raises(ValueError, match="Empty category"):
            SkillNormalizer([family])

    def test_canonical_name_without_category_raises_when_a_record_is_requested(self):
        family = _family("one", {"ALPHA": ["a"]}, {})
        custom = SkillNormalizer([family])
        assert custom.normalize_skill("a") == "ALPHA"  # translation still works
        with pytest.raises(ValueError, match="No category defined"):
            custom.to_record("a")

    def test_default_families_construct_without_errors(self):
        assert SkillNormalizer(DEFAULT_FAMILIES).families == DEFAULT_FAMILIES


# ---------------------------------------------------------------------------
# Module-level helpers (default shared normalizer)
# ---------------------------------------------------------------------------
class TestDefaultNormalizer:
    def test_is_cached(self):
        assert get_default_normalizer() is get_default_normalizer()

    def test_uses_the_default_families(self):
        assert get_default_normalizer().families == DEFAULT_FAMILIES

    def test_family_labels_and_order(self):
        assert [family.name for family in DEFAULT_FAMILIES] == [
            "web",
            "ai",
            "database",
            "devops",
            "vcs",
            "language",
            "data",
        ]

    def test_normalize_skill_function(self):
        assert normalize_skill("JS") == "JAVASCRIPT"
        assert normalize_skill("COBOL") is None

    def test_normalize_skills_function(self):
        records = normalize_skills(["Git", "NodeJS", "JS", "Postgres", "React.js"])
        assert all(isinstance(record, SkillRecord) for record in records)
        assert [record.canonical_name for record in records] == [
            "GIT",
            "NODE_JS",
            "JAVASCRIPT",
            "POSTGRESQL",
            "REACT",
        ]

    def test_normalize_with_report_function(self):
        report = normalize_with_report(["JS", "js", "COBOL"])
        assert isinstance(report, NormalizationResult)
        assert report.canonical_names == ["JAVASCRIPT"]
        assert report.duplicates == ["js"]
        assert report.unrecognized == ["COBOL"]

    def test_functions_agree_with_a_fresh_normalizer(self):
        raw = ["Docker", "k8s", "Kubernetes", "Terraform", "Git", "Haskell"]
        assert normalize_with_report(raw) == SkillNormalizer().normalize(raw)

    def test_package_exports_resolve(self):
        for name in normalization.__all__:
            assert hasattr(normalization, name), name


# ---------------------------------------------------------------------------
# Integration with Stage 1 (raw skills extracted from the synthetic resumes)
# ---------------------------------------------------------------------------
PIPELINE_EXPECTED = {
    "fullstack": (
        ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"],
        ["frontend", "frontend", "backend", "database", "vcs"],
    ),
    "ml": (
        ["PYTHON", "PANDAS", "NUMPY", "SCIKIT_LEARN", "TENSORFLOW", "SQL", "GIT"],
        ["language", "ml", "ml", "ml", "ml", "database", "vcs"],
    ),
    "devops": (
        ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT"],
        ["language", "cloud", "cloud", "cloud", "vcs"],
    ),
    "data": (
        ["PYTHON", "SPARK", "AIRFLOW", "POSTGRESQL", "GIT"],
        ["language", "data", "data", "database", "vcs"],
    ),
}


class TestNormalizationOfExtractedSkills:
    @pytest.mark.parametrize("alias", sorted(PIPELINE_EXPECTED))
    def test_every_valid_resume_is_fully_normalized(self, alias, request):
        text = request.getfixturevalue(f"{alias}_text")
        result = normalize_with_report(extract_resume(text).raw_skills)
        canonical, categories = PIPELINE_EXPECTED[alias]
        assert result.canonical_names == canonical
        assert [record.category for record in result.records] == categories
        assert result.unrecognized == []
        assert result.duplicates == []

    @pytest.mark.parametrize("alias", sorted(PIPELINE_EXPECTED))
    def test_raw_names_are_the_extracted_tokens(self, alias, request):
        text = request.getfixturevalue(f"{alias}_text")
        raw_skills = extract_resume(text).raw_skills
        records = normalize_skills(raw_skills)
        assert [record.raw_name for record in records] == raw_skills

    def test_fullstack_resume_matches_the_project_example(self, fullstack_text):
        names = normalize_with_report(extract_resume(fullstack_text).raw_skills).canonical_names
        assert set(names) == {"JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"}

    def test_sql_alone_is_normalized_even_though_stage_1_pattern_ignores_it(self, ml_text):
        # DATABASE_PATTERN does not match a bare "SQL", but the skills section is split
        # by commas, so the token reaches Stage 2 and the database transducer accepts it.
        raw_skills = extract_resume(ml_text).raw_skills
        assert "SQL" in raw_skills
        assert normalize_skill("SQL") == "SQL"

    def test_invalid_resume_normalizes_to_nothing(self, invalid_text):
        result = normalize_with_report(extract_resume(invalid_text).raw_skills)
        assert result.records == []
        assert result.unrecognized == []
        assert result.duplicates == []
