"""Tests for the canonical ordering of Stage 2 (``resumelens/normalization/sorter.py``).

The sorter receives the de-duplicated ``SkillRecord`` list of the normalizer and returns it
in the order of the selected profile, so that the sequence read by the automata of Stage 3
does not depend on the order in which the candidate wrote the skills.

The tests check: the definition of the profiles and of their slots, the resolution of
profile names, the order of the assignment's example, independence from the input order
(all the permutations), the order inside a slot, duplicated elements, profiles with missing
categories, the remaining (noise) part, the permutation / idempotence properties, unknown
profiles and the full path from the synthetic resumes (Stage 1 -> Stage 2).
"""

import itertools
from typing import List

import pytest

from resumelens.core.models import SkillRecord
from resumelens.extraction.extractor import extract_resume
from resumelens.normalization.normalizer import (
    CATEGORIES,
    CATEGORY_BACKEND,
    CATEGORY_DATABASE,
    CATEGORY_FRONTEND,
    CATEGORY_LANGUAGE,
    CATEGORY_VCS,
    CATEGORY_WEB_LANGUAGE,
    normalize_skills,
)
from resumelens.normalization.sorter import (
    DATA_ENGINEER,
    DEVOPS_ENGINEER,
    FULL_STACK_DEVELOPER,
    MACHINE_LEARNING_ENGINEER,
    PROFILE_SLOTS,
    PROFILES,
    UnknownProfileError,
    profile_slots,
    resolve_profile,
    sort_by_profile,
    sort_records_by_profile,
)

OFFICIAL_RAW = ["Git", "NodeJS", "JS", "Postgres", "React.js"]
OFFICIAL_SORTED = ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]

# Synthetic resume alias -> profile it was written for.
OWN_PROFILE = {
    "fullstack": FULL_STACK_DEVELOPER,
    "ml": MACHINE_LEARNING_ENGINEER,
    "devops": DEVOPS_ENGINEER,
    "data": DATA_ENGINEER,
}

# (resume alias, profile) -> canonical order. The diagonal is the order for the profile the
# resume was written for; the rest shows how the same skills are laid out for another profile
# (the profile part first, then the remaining skills by category and name).
EXPECTED_ORDER = {
    ("fullstack", FULL_STACK_DEVELOPER): ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"],
    ("fullstack", MACHINE_LEARNING_ENGINEER): ["POSTGRESQL", "GIT", "NODE_JS", "REACT", "JAVASCRIPT"],
    ("fullstack", DEVOPS_ENGINEER): ["GIT", "NODE_JS", "POSTGRESQL", "REACT", "JAVASCRIPT"],
    ("fullstack", DATA_ENGINEER): ["POSTGRESQL", "GIT", "NODE_JS", "REACT", "JAVASCRIPT"],
    ("ml", FULL_STACK_DEVELOPER): [
        "SQL", "GIT", "NUMPY", "PANDAS", "PYTHON", "SCIKIT_LEARN", "TENSORFLOW",
    ],
    ("ml", MACHINE_LEARNING_ENGINEER): [
        "PYTHON", "NUMPY", "PANDAS", "SCIKIT_LEARN", "TENSORFLOW", "SQL", "GIT",
    ],
    ("ml", DEVOPS_ENGINEER): [
        "PYTHON", "GIT", "NUMPY", "PANDAS", "SQL", "SCIKIT_LEARN", "TENSORFLOW",
    ],
    ("ml", DATA_ENGINEER): [
        "PYTHON", "SQL", "GIT", "NUMPY", "PANDAS", "SCIKIT_LEARN", "TENSORFLOW",
    ],
    ("devops", FULL_STACK_DEVELOPER): ["GIT", "DOCKER", "TERRAFORM", "PYTHON", "KUBERNETES"],
    ("devops", MACHINE_LEARNING_ENGINEER): ["PYTHON", "GIT", "DOCKER", "TERRAFORM", "KUBERNETES"],
    ("devops", DEVOPS_ENGINEER): ["PYTHON", "DOCKER", "KUBERNETES", "TERRAFORM", "GIT"],
    ("devops", DATA_ENGINEER): ["PYTHON", "GIT", "DOCKER", "TERRAFORM", "KUBERNETES"],
    ("data", FULL_STACK_DEVELOPER): ["POSTGRESQL", "GIT", "SPARK", "PYTHON", "AIRFLOW"],
    ("data", MACHINE_LEARNING_ENGINEER): ["PYTHON", "POSTGRESQL", "GIT", "SPARK", "AIRFLOW"],
    ("data", DEVOPS_ENGINEER): ["PYTHON", "GIT", "SPARK", "POSTGRESQL", "AIRFLOW"],
    ("data", DATA_ENGINEER): ["PYTHON", "SPARK", "AIRFLOW", "POSTGRESQL", "GIT"],
}


def sorted_names(raw_skills: List[str], profile: str) -> List[str]:
    """Normalize raw tokens (Stage 2) and sort them for ``profile``."""
    return sort_by_profile(normalize_skills(raw_skills), profile)


def make_record(canonical: str, category: str) -> SkillRecord:
    """Build a record directly, to test the sorter without the transducers."""
    return SkillRecord(raw_name=canonical.lower(), canonical_name=canonical, category=category)


def names_of(records: List[SkillRecord]) -> List[str]:
    return [record.canonical_name for record in records]


# ---------------------------------------------------------------------------
# Definition of the profiles
# ---------------------------------------------------------------------------
class TestProfileDefinitions:
    def test_four_profiles_in_roadmap_order(self):
        assert PROFILES == (
            FULL_STACK_DEVELOPER,
            MACHINE_LEARNING_ENGINEER,
            DEVOPS_ENGINEER,
            DATA_ENGINEER,
        )

    def test_profile_identifiers(self):
        assert FULL_STACK_DEVELOPER == "FULL_STACK_DEVELOPER"
        assert MACHINE_LEARNING_ENGINEER == "MACHINE_LEARNING_ENGINEER"
        assert DEVOPS_ENGINEER == "DEVOPS_ENGINEER"
        assert DATA_ENGINEER == "DATA_ENGINEER"

    def test_slots_are_defined_exactly_for_the_profiles(self):
        assert set(PROFILE_SLOTS) == set(PROFILES)

    @pytest.mark.parametrize("profile", PROFILES)
    def test_slots_are_known_categories(self, profile):
        assert set(PROFILE_SLOTS[profile]) <= set(CATEGORIES)

    @pytest.mark.parametrize("profile", PROFILES)
    def test_slots_have_no_repetitions(self, profile):
        slots = PROFILE_SLOTS[profile]
        assert len(slots) == len(set(slots))

    @pytest.mark.parametrize("profile", PROFILES)
    def test_version_control_is_the_last_slot(self, profile):
        assert PROFILE_SLOTS[profile][-1] == CATEGORY_VCS

    def test_full_stack_slots_follow_frontend_backend_database_vcs(self):
        slots = PROFILE_SLOTS[FULL_STACK_DEVELOPER]
        assert slots == (
            "web_language",
            "frontend",
            "backend",
            "database",
            "api",
            "vcs",
        )

    def test_machine_learning_slots(self):
        assert PROFILE_SLOTS[MACHINE_LEARNING_ENGINEER] == (
            "language",
            "data_library",
            "ml_framework",
            "ml_practice",
            "database",
            "vcs",
        )

    def test_devops_slots(self):
        assert PROFILE_SLOTS[DEVOPS_ENGINEER] == (
            "language",
            "container",
            "orchestration",
            "iac",
            "ci_cd",
            "cloud",
            "vcs",
        )

    def test_data_engineer_slots(self):
        assert PROFILE_SLOTS[DATA_ENGINEER] == (
            "language",
            "data_processing",
            "workflow",
            "database",
            "cloud",
            "vcs",
        )

    @pytest.mark.parametrize("profile", PROFILES)
    def test_profile_slots_function_matches_the_table(self, profile):
        assert profile_slots(profile) == PROFILE_SLOTS[profile]


# ---------------------------------------------------------------------------
# Resolution of profile names
# ---------------------------------------------------------------------------
class TestResolveProfile:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("FULL_STACK_DEVELOPER", FULL_STACK_DEVELOPER),
            ("Full Stack Developer", FULL_STACK_DEVELOPER),
            ("full stack developer", FULL_STACK_DEVELOPER),
            ("full-stack developer", FULL_STACK_DEVELOPER),
            ("Machine Learning Engineer", MACHINE_LEARNING_ENGINEER),
            ("  machine   learning engineer  ", MACHINE_LEARNING_ENGINEER),
            ("Machine-Learning-Engineer", MACHINE_LEARNING_ENGINEER),
            ("DevOps Engineer", DEVOPS_ENGINEER),
            ("devops_engineer", DEVOPS_ENGINEER),
            ("Data Engineer", DATA_ENGINEER),
            ("DATA ENGINEER", DATA_ENGINEER),
        ],
    )
    def test_accepted_spellings(self, name, expected):
        assert resolve_profile(name) == expected

    @pytest.mark.parametrize("profile", PROFILES)
    def test_identifiers_resolve_to_themselves(self, profile):
        assert resolve_profile(profile) == profile

    @pytest.mark.parametrize(
        "name",
        ["", "   ", "Backend Developer", "Full Stack", "Data Scientist", "DevOps", "ML Engineer"],
    )
    def test_unknown_names_are_rejected(self, name):
        with pytest.raises(UnknownProfileError):
            resolve_profile(name)

    def test_error_names_the_profile_and_the_valid_ones(self):
        with pytest.raises(UnknownProfileError) as error:
            resolve_profile("Backend Developer")
        message = str(error.value)
        assert "Backend Developer" in message
        for profile in PROFILES:
            assert profile in message

    def test_unknown_profile_error_is_a_value_error(self):
        assert issubclass(UnknownProfileError, ValueError)

    def test_profile_slots_accepts_display_names(self):
        assert profile_slots("Full Stack Developer") == PROFILE_SLOTS[FULL_STACK_DEVELOPER]


# ---------------------------------------------------------------------------
# Example of the assignment
# ---------------------------------------------------------------------------
class TestOfficialExample:
    def test_official_example_for_full_stack(self):
        assert sorted_names(OFFICIAL_RAW, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_official_example_with_display_name(self):
        assert sorted_names(OFFICIAL_RAW, "Full Stack Developer") == OFFICIAL_SORTED

    def test_official_example_goes_frontend_backend_database_vcs(self):
        records = normalize_skills(OFFICIAL_RAW)
        ordered = sort_records_by_profile(records, FULL_STACK_DEVELOPER)
        assert [record.category for record in ordered] == [
            CATEGORY_WEB_LANGUAGE,
            CATEGORY_FRONTEND,
            CATEGORY_BACKEND,
            CATEGORY_DATABASE,
            CATEGORY_VCS,
        ]

    def test_sort_by_profile_returns_the_names_of_sort_records_by_profile(self):
        records = normalize_skills(OFFICIAL_RAW)
        assert sort_by_profile(records, FULL_STACK_DEVELOPER) == names_of(
            sort_records_by_profile(records, FULL_STACK_DEVELOPER)
        )

    def test_original_spellings_are_kept_in_the_records(self):
        records = normalize_skills(OFFICIAL_RAW)
        ordered = sort_records_by_profile(records, FULL_STACK_DEVELOPER)
        assert [record.raw_name for record in ordered] == ["JS", "React.js", "NodeJS", "Postgres", "Git"]


# ---------------------------------------------------------------------------
# Independence from the input order
# ---------------------------------------------------------------------------
class TestOrderIndependence:
    def test_every_permutation_of_the_raw_tokens_gives_the_official_order(self):
        for permutation in itertools.permutations(OFFICIAL_RAW):
            assert sorted_names(list(permutation), FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_every_permutation_of_the_records_gives_the_same_output_for_every_profile(self):
        records = normalize_skills(
            ["Python", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "SQL", "Git"]
        )
        for profile in PROFILES:
            expected = sort_by_profile(records, profile)
            for permutation in itertools.permutations(records):
                assert sort_by_profile(list(permutation), profile) == expected

    @pytest.mark.parametrize("profile", PROFILES)
    def test_reversed_input_gives_the_same_output(self, profile):
        raw = ["Python", "Docker", "Kubernetes", "Terraform", "Git", "JS", "AWS"]
        assert sorted_names(raw, profile) == sorted_names(list(reversed(raw)), profile)

    def test_spelling_variants_do_not_change_the_order(self):
        variants = ["github", "NODE", "javascript", "PostgreSQL", "ReactJS"]
        assert sorted_names(variants, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_case_and_spacing_of_the_tokens_do_not_change_the_order(self):
        messy = ["  git ", "POSTGRES", "reactjs", "Js", "node"]
        assert sorted_names(messy, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED


# ---------------------------------------------------------------------------
# Order inside a slot
# ---------------------------------------------------------------------------
class TestOrderInsideSlot:
    def test_data_libraries_are_alphabetical(self):
        assert sorted_names(["Pandas", "NumPy"], MACHINE_LEARNING_ENGINEER) == ["NUMPY", "PANDAS"]
        assert sorted_names(["NumPy", "Pandas"], MACHINE_LEARNING_ENGINEER) == ["NUMPY", "PANDAS"]

    def test_ml_frameworks_are_alphabetical(self):
        raw = ["TensorFlow", "PyTorch", "Scikit-learn"]
        assert sorted_names(raw, MACHINE_LEARNING_ENGINEER) == [
            "PYTORCH",
            "SCIKIT_LEARN",
            "TENSORFLOW",
        ]

    def test_web_languages_are_alphabetical(self):
        assert sorted_names(["TS", "JS"], FULL_STACK_DEVELOPER) == ["JAVASCRIPT", "TYPESCRIPT"]

    def test_frontend_frameworks_are_alphabetical(self):
        assert sorted_names(["Vue", "React", "Angular"], FULL_STACK_DEVELOPER) == [
            "ANGULAR",
            "REACT",
            "VUE",
        ]

    def test_backend_frameworks_are_alphabetical(self):
        assert sorted_names(["Spring Boot", "NodeJS", "Django"], FULL_STACK_DEVELOPER) == [
            "DJANGO",
            "NODE_JS",
            "SPRING_BOOT",
        ]

    def test_several_databases_are_alphabetical(self):
        assert sorted_names(["Redis", "Postgres", "Mongo"], FULL_STACK_DEVELOPER) == [
            "MONGODB",
            "POSTGRESQL",
            "REDIS",
        ]

    def test_cloud_providers_are_alphabetical(self):
        assert sorted_names(["GCP", "AWS", "Azure"], DEVOPS_ENGINEER) == ["AWS", "AZURE", "GCP"]

    def test_infrastructure_as_code_tools_are_alphabetical(self):
        assert sorted_names(["Terraform", "Ansible"], DEVOPS_ENGINEER) == ["ANSIBLE", "TERRAFORM"]

    def test_slots_keep_their_profile_order_even_with_several_skills(self):
        raw = ["Git", "TensorFlow", "Pandas", "Python", "SQL", "NumPy", "Scikit-learn"]
        assert sorted_names(raw, MACHINE_LEARNING_ENGINEER) == [
            "PYTHON",
            "NUMPY",
            "PANDAS",
            "SCIKIT_LEARN",
            "TENSORFLOW",
            "SQL",
            "GIT",
        ]


# ---------------------------------------------------------------------------
# Duplicated elements
# ---------------------------------------------------------------------------
class TestDuplicates:
    def test_spelling_variants_of_one_skill_appear_once(self):
        assert sorted_names(["JS", "JavaScript", "js"], FULL_STACK_DEVELOPER) == ["JAVASCRIPT"]

    def test_duplicates_inside_a_larger_list_appear_once(self):
        raw = ["Git", "JS", "React.js", "git", "NodeJS", "JavaScript", "Postgres", "ReactJS", "GitHub"]
        assert sorted_names(raw, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_duplicates_do_not_change_the_order_of_the_rest(self):
        with_duplicates = ["Git", "Git", "NodeJS", "JS", "JS", "Postgres", "React.js", "Postgres"]
        assert sorted_names(with_duplicates, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_sorter_keeps_repeated_records_it_receives(self):
        # De-duplication is the normalizer's job; the sorter only permutes its input.
        record = make_record("GIT", CATEGORY_VCS)
        other = make_record("PYTHON", CATEGORY_LANGUAGE)
        ordered = sort_records_by_profile([record, other, record], MACHINE_LEARNING_ENGINEER)
        assert names_of(ordered) == ["PYTHON", "GIT", "GIT"]

    def test_unrecognized_tokens_never_reach_the_sorter(self):
        raw = ["Git", "COBOL", "NodeJS", "Excel", "JS", "Postgres", "React.js", "Pythön"]
        assert sorted_names(raw, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED


# ---------------------------------------------------------------------------
# Missing categories
# ---------------------------------------------------------------------------
class TestMissingCategories:
    def test_empty_input(self):
        for profile in PROFILES:
            assert sort_records_by_profile([], profile) == []
            assert sort_by_profile([], profile) == []

    def test_single_skill(self):
        assert sorted_names(["Git"], FULL_STACK_DEVELOPER) == ["GIT"]

    def test_full_stack_without_database(self):
        assert sorted_names(["Git", "NodeJS", "JS", "React.js"], FULL_STACK_DEVELOPER) == [
            "JAVASCRIPT",
            "REACT",
            "NODE_JS",
            "GIT",
        ]

    def test_full_stack_without_frontend_framework(self):
        assert sorted_names(["Git", "Postgres", "NodeJS", "JS"], FULL_STACK_DEVELOPER) == [
            "JAVASCRIPT",
            "NODE_JS",
            "POSTGRESQL",
            "GIT",
        ]

    def test_full_stack_without_version_control(self):
        assert sorted_names(["Postgres", "NodeJS", "React.js", "JS"], FULL_STACK_DEVELOPER) == [
            "JAVASCRIPT",
            "REACT",
            "NODE_JS",
            "POSTGRESQL",
        ]

    def test_full_stack_with_only_backend_and_database(self):
        assert sorted_names(["Postgres", "NodeJS"], FULL_STACK_DEVELOPER) == ["NODE_JS", "POSTGRESQL"]

    def test_machine_learning_without_machine_learning_frameworks(self):
        assert sorted_names(["Git", "SQL", "Pandas", "Python"], MACHINE_LEARNING_ENGINEER) == [
            "PYTHON",
            "PANDAS",
            "SQL",
            "GIT",
        ]

    def test_devops_without_orchestration_and_cloud(self):
        assert sorted_names(["Git", "Terraform", "Docker", "Python"], DEVOPS_ENGINEER) == [
            "PYTHON",
            "DOCKER",
            "TERRAFORM",
            "GIT",
        ]

    def test_data_engineer_without_workflow_and_cloud(self):
        assert sorted_names(["Git", "Postgres", "Spark", "Python"], DATA_ENGINEER) == [
            "PYTHON",
            "SPARK",
            "POSTGRESQL",
            "GIT",
        ]

    def test_missing_slots_leave_no_placeholders(self):
        output = sorted_names(["Git"], DEVOPS_ENGINEER)
        assert output == ["GIT"]
        assert all(name for name in output)


# ---------------------------------------------------------------------------
# Remaining (noise) part
# ---------------------------------------------------------------------------
class TestRemainingPart:
    def test_skills_outside_the_profile_go_after_the_profile_part(self):
        raw = ["Docker", "Python", "Kubernetes", "Git", "Terraform"]
        assert sorted_names(raw, MACHINE_LEARNING_ENGINEER) == [
            "PYTHON",
            "GIT",
            "DOCKER",
            "TERRAFORM",
            "KUBERNETES",
        ]

    def test_remaining_part_is_sorted_by_category_then_name(self):
        raw = ["Kubernetes", "AWS", "Docker", "Terraform", "Ansible"]
        records = normalize_skills(raw)
        ordered = sort_records_by_profile(records, FULL_STACK_DEVELOPER)
        keys = [(record.category, record.canonical_name) for record in ordered]
        assert keys == sorted(keys)
        assert names_of(ordered) == ["AWS", "DOCKER", "ANSIBLE", "TERRAFORM", "KUBERNETES"]

    def test_profile_part_is_always_a_prefix(self):
        raw = ["Docker", "NodeJS", "Spark", "JS", "Git", "Pandas", "Postgres", "React.js"]
        slots = set(PROFILE_SLOTS[FULL_STACK_DEVELOPER])
        ordered = sort_records_by_profile(normalize_skills(raw), FULL_STACK_DEVELOPER)
        flags = [record.category in slots for record in ordered]
        assert flags == sorted(flags, reverse=True)
        assert any(flags) and not all(flags)

    def test_only_noise_gives_only_the_remaining_part(self):
        assert sorted_names(["Docker", "Terraform"], FULL_STACK_DEVELOPER) == ["DOCKER", "TERRAFORM"]

    def test_unknown_category_is_treated_as_noise(self):
        mystery = make_record("MYSTERY", "mystery")
        git = make_record("GIT", CATEGORY_VCS)
        assert names_of(sort_records_by_profile([mystery, git], FULL_STACK_DEVELOPER)) == [
            "GIT",
            "MYSTERY",
        ]

    def test_unknown_categories_are_sorted_by_category_name(self):
        zeta = make_record("AAA", "zeta")
        alpha = make_record("ZZZ", "alpha")
        assert names_of(sort_records_by_profile([zeta, alpha], DATA_ENGINEER)) == ["ZZZ", "AAA"]

    def test_a_skill_can_be_profile_part_for_one_profile_and_noise_for_another(self):
        raw = ["Postgres", "Git", "Python"]
        assert sorted_names(raw, FULL_STACK_DEVELOPER) == ["POSTGRESQL", "GIT", "PYTHON"]
        assert sorted_names(raw, DATA_ENGINEER) == ["PYTHON", "POSTGRESQL", "GIT"]


# ---------------------------------------------------------------------------
# General properties
# ---------------------------------------------------------------------------
class TestProperties:
    RAW = ["Python", "Docker", "Pandas", "JS", "Git", "AWS", "Postgres", "Spark", "React.js", "Airflow"]

    @pytest.mark.parametrize("profile", PROFILES)
    def test_output_is_a_permutation_of_the_input(self, profile):
        records = normalize_skills(self.RAW)
        ordered = sort_records_by_profile(records, profile)
        assert len(ordered) == len(records)
        assert sorted(names_of(ordered)) == sorted(names_of(records))

    @pytest.mark.parametrize("profile", PROFILES)
    def test_records_are_returned_unchanged(self, profile):
        records = normalize_skills(self.RAW)
        ordered = sort_records_by_profile(records, profile)
        assert all(any(item is record for record in records) for item in ordered)

    @pytest.mark.parametrize("profile", PROFILES)
    def test_input_list_is_not_modified(self, profile):
        records = normalize_skills(self.RAW)
        before = list(records)
        sort_records_by_profile(records, profile)
        assert records == before
        assert all(a is b for a, b in zip(records, before))

    @pytest.mark.parametrize("profile", PROFILES)
    def test_a_new_list_is_returned(self, profile):
        records = normalize_skills(self.RAW)
        assert sort_records_by_profile(records, profile) is not records

    @pytest.mark.parametrize("profile", PROFILES)
    def test_sorting_is_idempotent(self, profile):
        records = normalize_skills(self.RAW)
        once = sort_records_by_profile(records, profile)
        twice = sort_records_by_profile(once, profile)
        assert names_of(once) == names_of(twice)

    @pytest.mark.parametrize("profile", PROFILES)
    def test_sorting_is_deterministic(self, profile):
        first = sorted_names(self.RAW, profile)
        for _ in range(5):
            assert sorted_names(self.RAW, profile) == first

    @pytest.mark.parametrize("profile", PROFILES)
    def test_profile_part_follows_the_slot_order(self, profile):
        slots = list(PROFILE_SLOTS[profile])
        ordered = sort_records_by_profile(normalize_skills(self.RAW), profile)
        positions = [slots.index(record.category) for record in ordered if record.category in slots]
        assert positions == sorted(positions)

    def test_different_profiles_can_give_different_orders(self):
        records = normalize_skills(self.RAW)
        orders = {tuple(sort_by_profile(records, profile)) for profile in PROFILES}
        assert len(orders) > 1

    def test_accepts_tuples(self):
        records = tuple(normalize_skills(OFFICIAL_RAW))
        assert sort_by_profile(records, FULL_STACK_DEVELOPER) == OFFICIAL_SORTED

    def test_return_types(self):
        records = normalize_skills(OFFICIAL_RAW)
        assert isinstance(sort_records_by_profile(records, FULL_STACK_DEVELOPER), list)
        names = sort_by_profile(records, FULL_STACK_DEVELOPER)
        assert isinstance(names, list)
        assert all(isinstance(name, str) for name in names)


# ---------------------------------------------------------------------------
# Unknown profiles
# ---------------------------------------------------------------------------
class TestUnknownProfile:
    def test_sort_records_by_profile_rejects_unknown_profiles(self):
        with pytest.raises(UnknownProfileError):
            sort_records_by_profile(normalize_skills(OFFICIAL_RAW), "Backend Developer")

    def test_sort_by_profile_rejects_unknown_profiles(self):
        with pytest.raises(UnknownProfileError):
            sort_by_profile(normalize_skills(OFFICIAL_RAW), "Backend Developer")

    def test_unknown_profile_is_rejected_even_with_an_empty_list(self):
        with pytest.raises(UnknownProfileError):
            sort_by_profile([], "Backend Developer")

    def test_profile_slots_rejects_unknown_profiles(self):
        with pytest.raises(UnknownProfileError):
            profile_slots("")


# ---------------------------------------------------------------------------
# Synthetic resumes: Stage 1 -> Stage 2 -> canonical order
# ---------------------------------------------------------------------------
class TestSyntheticResumes:
    @pytest.mark.parametrize("alias", sorted(OWN_PROFILE))
    def test_own_profile_order(self, resume_texts, alias):
        raw_skills = extract_resume(resume_texts[alias]).raw_skills
        profile = OWN_PROFILE[alias]
        assert sorted_names(raw_skills, profile) == EXPECTED_ORDER[(alias, profile)]

    @pytest.mark.parametrize("alias, profile", sorted(EXPECTED_ORDER))
    def test_every_resume_against_every_profile(self, resume_texts, alias, profile):
        raw_skills = extract_resume(resume_texts[alias]).raw_skills
        assert sorted_names(raw_skills, profile) == EXPECTED_ORDER[(alias, profile)]

    @pytest.mark.parametrize("alias", sorted(OWN_PROFILE))
    def test_all_skills_of_the_own_profile_are_in_the_profile_part(self, resume_texts, alias):
        profile = OWN_PROFILE[alias]
        slots = set(PROFILE_SLOTS[profile])
        records = normalize_skills(extract_resume(resume_texts[alias]).raw_skills)
        ordered = sort_records_by_profile(records, profile)
        assert len(ordered) == len(records) == 5 + 2 * (alias == "ml")
        assert all(record.category in slots for record in ordered)

    @pytest.mark.parametrize("alias", sorted(OWN_PROFILE))
    def test_reversed_resume_skills_give_the_same_order(self, resume_texts, alias):
        raw_skills = extract_resume(resume_texts[alias]).raw_skills
        profile = OWN_PROFILE[alias]
        assert sorted_names(list(reversed(raw_skills)), profile) == sorted_names(raw_skills, profile)

    def test_resume_without_skills_gives_an_empty_sequence(self, resume_texts):
        raw_skills = extract_resume(resume_texts["invalid"]).raw_skills
        for profile in PROFILES:
            assert sorted_names(raw_skills, profile) == []

    def test_machine_learning_resume_has_two_skills_in_the_data_library_slot(self, resume_texts):
        raw_skills = extract_resume(resume_texts["ml"]).raw_skills
        order = sorted_names(raw_skills, MACHINE_LEARNING_ENGINEER)
        assert order[1:3] == ["NUMPY", "PANDAS"]
