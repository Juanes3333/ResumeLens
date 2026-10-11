"""Unit tests for the Stage 4 candidate DSL (``resumelens.grammar``).

Covers the parser API (``parse_candidate_profile``, ``is_valid_profile_source``,
``load_metamodel``) and the serializer (``build_profile_source``):

* positive parsing: valid documents instantiate a textX model whose attributes map
  exactly to the candidate data;
* negative parsing: malformed documents raise ``TextXSyntaxError``;
* serialization: pipeline data -> DSL text -> model -> pipeline data round trips.

The grammar file itself is exercised directly in ``tests/test_grammar_definition.py``.
"""

from pathlib import Path

import pytest
from textx import textx_isinstance
from textx.exceptions import TextXError, TextXSemanticError, TextXSyntaxError

import resumelens.grammar as grammar
from resumelens.classification import classify_all
from resumelens.core.models import CandidateInfo, EvaluationResult, SkillRecord
from resumelens.extraction.extractor import extract_resume
from resumelens.grammar import (
    GRAMMAR_PATH,
    build_profile_source,
    is_valid_profile_source,
    load_metamodel,
    parse_candidate_profile,
)
from resumelens.normalization import normalize_with_report

PROFILE_IDS = (
    "FULL_STACK_DEVELOPER",
    "MACHINE_LEARNING_ENGINEER",
    "DEVOPS_ENGINEER",
    "DATA_ENGINEER",
)
RESULT_CLASSES = ("FullStackResult", "MachineLearningResult", "DevOpsResult", "DataEngineerResult")
ACCEPTED_PROFILE_BY_ALIAS = {
    "fullstack": "FULL_STACK_DEVELOPER",
    "ml": "MACHINE_LEARNING_ENGINEER",
    "devops": "DEVOPS_ENGINEER",
    "data": "DATA_ENGINEER",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_info(**overrides):
    values = dict(
        name="Ana Gomez",
        email="ana.gomez@icesi.edu.co",
        phone="+57 300 123 4567",
        links=["https://www.linkedin.com/in/ana-gomez", "https://github.com/anagomez"],
        education=["B.S. in Software Engineering", "Universidad Icesi (2016 - 2021)"],
        experience=["Backend Developer, Globant (2021 - 2024)"],
    )
    values.update(overrides)
    return CandidateInfo(**values)


def make_records():
    return [
        SkillRecord(raw_name="JS", canonical_name="JAVASCRIPT", category="web_language"),
        SkillRecord(raw_name="Git", canonical_name="GIT", category="vcs"),
    ]


def make_results(accepted=("FULL_STACK_DEVELOPER",), details="report"):
    return [
        EvaluationResult(
            profile_name=name,
            is_accepted=name in accepted,
            matched_sequence=["JAVASCRIPT", "GIT"] if name in accepted else [],
            details=details,
        )
        for name in PROFILE_IDS
    ]


def make_source(**overrides):
    info = overrides.pop("info", None) or make_info()
    records = overrides.pop("records", None)
    results = overrides.pop("results", None)
    return build_profile_source(
        info,
        make_records() if records is None else records,
        make_results() if results is None else results,
    )


def pipeline(text):
    """Run Stages 1-3 over a resume text and return the inputs of the DSL serializer."""
    raw = extract_resume(text)
    records = normalize_with_report(raw.raw_skills).records
    return raw.candidate_info, records, classify_all(records).results


def model_to_inputs(model):
    """Rebuild the serializer inputs from a parsed model (the inverse of the serializer)."""
    info = CandidateInfo(
        name=model.personal.name,
        email=model.personal.email or "",
        phone=model.personal.phone or "",
        links=list(model.personal.links),
        education=[e.description for e in model.education.entries],
        experience=[e.description for e in model.experience.entries],
    )
    records = [
        SkillRecord(raw_name=s.raw, canonical_name=s.canonical, category=s.category)
        for s in model.skills.skills
    ]
    results = [
        EvaluationResult(
            profile_name=r.name,
            is_accepted=r.verdict == "ACCEPTED",
            matched_sequence=list(r.matched),
            details=r.details,
        )
        for r in model.evaluation.results
    ]
    return info, records, results


# A document written by hand, independent of the serializer.
HANDWRITTEN = """\
candidate {
    personal {
        name: "Mary Jane Watson"
        email: mj.watson@dailybugle.com
        phone: +1 555 123 4567
        link: https://www.linkedin.com/in/mary-jane-watson
        link: https://github.com/mjwatson
    }
    education {
        study "M.S. in Data Science"
        study "Empire State University (2022 - 2024)"
    }
    experience {
        job "Machine Learning Engineer, Oscorp Analytics (2024 - 2026)"
    }
    skills {
        skill PYTHON category base_language raw "Python"
        skill PANDAS category data_library raw "Pandas"
        skill GIT category vcs raw "Git"
    }
    evaluation {
        profile FULL_STACK_DEVELOPER: REJECTED
            matched []
            details "REJECTED - Full Stack Developer"
        profile MACHINE_LEARNING_ENGINEER: ACCEPTED
            matched [PYTHON, PANDAS, GIT]
            details "ACCEPTED - Machine Learning Engineer"
        profile DEVOPS_ENGINEER: REJECTED
            matched []
            details "REJECTED - DevOps Engineer"
        profile DATA_ENGINEER: REJECTED
            matched [PYTHON]
            details "REJECTED - Data Engineer"
    }
}
"""


# ---------------------------------------------------------------------------
# Module API and metamodel
# ---------------------------------------------------------------------------
def test_grammar_path_points_to_the_tx_file():
    assert isinstance(GRAMMAR_PATH, Path)
    assert GRAMMAR_PATH.name == "resume_grammar.tx"
    assert GRAMMAR_PATH.is_file()


def test_package_exports_the_public_api():
    assert set(grammar.__all__) == {
        "GRAMMAR_PATH",
        "build_profile_source",
        "is_valid_profile_source",
        "load_metamodel",
        "parse_candidate_profile",
    }
    assert all(hasattr(grammar, name) for name in grammar.__all__)


def test_load_metamodel_is_cached():
    assert load_metamodel() is load_metamodel()


@pytest.mark.parametrize(
    "rule",
    [
        "CandidateReport",
        "PersonalInfo",
        "EducationSection",
        "ExperienceSection",
        "SkillSection",
        "SkillEntry",
        "EvaluationSection",
        "ProfileResult",
    ],
)
def test_metamodel_defines_the_entity_classes(rule):
    assert load_metamodel()[rule] is not None


# ---------------------------------------------------------------------------
# Positive parsing — handwritten document
# ---------------------------------------------------------------------------
def test_handwritten_document_instantiates_the_root_model():
    model = parse_candidate_profile(HANDWRITTEN)
    assert type(model).__name__ == "CandidateReport"
    assert textx_isinstance(model, load_metamodel()["CandidateReport"])


def test_personal_and_contact_attributes_are_mapped():
    personal = parse_candidate_profile(HANDWRITTEN).personal
    assert personal.name == "Mary Jane Watson"
    assert personal.email == "mj.watson@dailybugle.com"
    assert personal.phone == "+1 555 123 4567"
    assert personal.links == [
        "https://www.linkedin.com/in/mary-jane-watson",
        "https://github.com/mjwatson",
    ]


def test_education_and_experience_entries_are_mapped():
    model = parse_candidate_profile(HANDWRITTEN)
    assert [e.description for e in model.education.entries] == [
        "M.S. in Data Science",
        "Empire State University (2022 - 2024)",
    ]
    assert [e.description for e in model.experience.entries] == [
        "Machine Learning Engineer, Oscorp Analytics (2024 - 2026)"
    ]


def test_skill_entries_are_mapped():
    skills = parse_candidate_profile(HANDWRITTEN).skills.skills
    assert [(s.canonical, s.category, s.raw) for s in skills] == [
        ("PYTHON", "base_language", "Python"),
        ("PANDAS", "data_library", "Pandas"),
        ("GIT", "vcs", "Git"),
    ]


def test_classification_block_is_mapped_for_each_profile():
    results = parse_candidate_profile(HANDWRITTEN).evaluation.results
    assert [r.name for r in results] == list(PROFILE_IDS)
    assert [r.verdict for r in results] == ["REJECTED", "ACCEPTED", "REJECTED", "REJECTED"]
    assert [r.matched for r in results] == [[], ["PYTHON", "PANDAS", "GIT"], [], ["PYTHON"]]
    assert results[1].details == "ACCEPTED - Machine Learning Engineer"


def test_each_profile_result_has_its_own_class_and_the_abstract_type():
    mm = load_metamodel()
    results = parse_candidate_profile(HANDWRITTEN).evaluation.results
    assert [type(r).__name__ for r in results] == list(RESULT_CLASSES)
    assert all(textx_isinstance(r, mm["ProfileResult"]) for r in results)


def test_only_the_name_is_mandatory_in_personal_info():
    source = HANDWRITTEN.replace("        email: mj.watson@dailybugle.com\n", "")
    source = source.replace("        phone: +1 555 123 4567\n", "")
    source = source.replace("        link: https://www.linkedin.com/in/mary-jane-watson\n", "")
    source = source.replace("        link: https://github.com/mjwatson\n", "")
    personal = parse_candidate_profile(source).personal
    assert personal.name == "Mary Jane Watson"
    assert personal.email is None and personal.phone is None and personal.links == []


def test_education_and_experience_blocks_may_be_empty():
    model = parse_candidate_profile(make_source(info=make_info(education=[], experience=[])))
    assert model.education.entries == [] and model.experience.entries == []


@pytest.mark.parametrize("count", [1, 3, 10])
def test_repeated_elements_are_supported(count):
    info = make_info(
        links=[f"https://example.com/p{i}" for i in range(count)],
        education=[f"Degree {i}" for i in range(count)],
        experience=[f"Role {i}, Company {i} (2020 - 2021)" for i in range(count)],
    )
    records = [
        SkillRecord(raw_name=f"s{i}", canonical_name=f"SKILL_{i}", category="web_language")
        for i in range(count)
    ]
    model = parse_candidate_profile(make_source(info=info, records=records))
    assert len(model.personal.links) == count
    assert len(model.education.entries) == count
    assert len(model.experience.entries) == count
    assert len(model.skills.skills) == count


def test_comments_and_free_whitespace_are_ignored():
    source = HANDWRITTEN.replace("candidate {", "// resume of a candidate\ncandidate { // start", 1)
    source = source.replace("\n    ", "\n\t\t", 3).replace("}\n", "}   \n\n\n")
    assert parse_candidate_profile(source).personal.name == "Mary Jane Watson"


def test_strings_support_escaped_quotes_accents_and_multiple_lines():
    info = make_info(name='Ana "The Dev" María Núñez')
    results = make_results(details='line one\nline two with "quotes"')
    model = parse_candidate_profile(make_source(info=info, results=results))
    assert model.personal.name == 'Ana "The Dev" María Núñez'
    assert model.evaluation.results[0].details == 'line one\nline two with "quotes"'


@pytest.mark.parametrize(
    "phone",
    ["+57 300 123 4567", "(602) 888-9900", "+1-800-555-0199", "555.123.4567", "3001234567"],
)
def test_phone_formats_accepted_by_the_grammar(phone):
    model = parse_candidate_profile(make_source(info=make_info(phone=phone)))
    assert model.personal.phone == phone


@pytest.mark.parametrize(
    "email",
    ["juan.perez-2026@sub.domain.edu.co", "a.b+tag@mail.example.co.uk", "x@y.io"],
)
def test_email_formats_accepted_by_the_grammar(email):
    model = parse_candidate_profile(make_source(info=make_info(email=email)))
    assert model.personal.email == email


# ---------------------------------------------------------------------------
# Negative parsing — TextXSyntaxError
# ---------------------------------------------------------------------------
BASE = make_source()

# (id, text to replace, replacement). Each case must change the base document.
MUTATIONS = [
    ("missing_root_keyword", "candidate {", "{"),
    ("uppercase_root_keyword", "candidate {", "CANDIDATE {"),
    ("missing_opening_brace", "candidate {", "candidate"),
    ("missing_personal_block", "personal {", "contact {"),
    ("missing_name_keyword", 'name: "Ana Gomez"', '"Ana Gomez"'),
    ("missing_name_colon", 'name: "Ana Gomez"', 'name "Ana Gomez"'),
    ("unquoted_name", 'name: "Ana Gomez"', "name: Ana"),
    ("unterminated_name", 'name: "Ana Gomez"', 'name: "Ana Gomez'),
    ("email_without_at_sign", "ana.gomez@icesi.edu.co", "ana.gomez.icesi.edu.co"),
    ("email_without_tld", "ana.gomez@icesi.edu.co", "ana.gomez@icesi"),
    ("email_before_name", 'name: "Ana Gomez"\n        email:', 'email:'),
    ("phone_too_short", "+57 300 123 4567", "12345"),
    ("phone_with_letters", "+57 300 123 4567", "call-me-maybe"),
    ("link_with_ftp_scheme", "https://github.com/anagomez", "ftp://github.com/anagomez"),
    ("link_without_scheme", "https://github.com/anagomez", "github.com/anagomez"),
    ("link_without_host_dot", "https://github.com/anagomez", "https://localhost/anagomez"),
    ("study_without_string", 'study "B.S. in Software Engineering"', "study B.S."),
    ("job_with_wrong_keyword", 'job "Backend Developer, Globant (2021 - 2024)"', 'work "Backend Developer"'),
    ("lowercase_skill_name", "skill JAVASCRIPT", "skill javascript"),
    ("skill_name_with_symbol", "skill JAVASCRIPT", "skill JAVA-SCRIPT"),
    ("uppercase_category", "category web_language", "category WEB"),
    ("category_starting_with_digit", "category web_language", "category 1web"),
    ("missing_category_keyword", "category web_language", "web_language"),
    ('missing_raw_part', ' raw "JS"', ""),
    ("unquoted_raw", 'raw "JS"', "raw JS"),
    ("unknown_verdict", "FULL_STACK_DEVELOPER: ACCEPTED", "FULL_STACK_DEVELOPER: MAYBE"),
    ("lowercase_verdict", "FULL_STACK_DEVELOPER: ACCEPTED", "FULL_STACK_DEVELOPER: accepted"),
    ("unknown_profile", "DATA_ENGINEER", "QA_ENGINEER"),
    ("lowercase_profile", "DEVOPS_ENGINEER", "devops_engineer"),
    ("missing_profile_colon", "FULL_STACK_DEVELOPER: ACCEPTED", "FULL_STACK_DEVELOPER ACCEPTED"),
    ("matched_without_brackets", "matched [JAVASCRIPT, GIT]", "matched JAVASCRIPT, GIT"),
    ("matched_unclosed", "matched [JAVASCRIPT, GIT]", "matched [JAVASCRIPT, GIT"),
    ("matched_lowercase_item", "matched [JAVASCRIPT, GIT]", "matched [javascript, GIT]"),
    ("matched_missing_comma", "matched [JAVASCRIPT, GIT]", "matched [JAVASCRIPT GIT]"),
    ("matched_double_comma", "matched [JAVASCRIPT, GIT]", "matched [JAVASCRIPT,, GIT]"),
    ("missing_details_keyword", 'details "report"', '"report"'),
    ("unquoted_details", 'details "report"', "details report"),
]


@pytest.mark.parametrize("old, new", [m[1:] for m in MUTATIONS], ids=[m[0] for m in MUTATIONS])
def test_malformed_documents_raise_syntax_error(old, new):
    assert old in BASE, "the mutation does not apply to the base document"
    mutated = BASE.replace(old, new, 1)
    assert mutated != BASE
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(mutated)
    assert is_valid_profile_source(mutated) is False


def test_base_document_is_valid():
    assert is_valid_profile_source(BASE) is True


@pytest.mark.parametrize(
    "source",
    ["", "   \n\n  ", "hello world", "candidate", "candidate { }", "{}", "// only a comment\n"],
    ids=["empty", "whitespace", "plain_text", "keyword_only", "empty_candidate", "braces", "comment"],
)
def test_incomplete_or_foreign_texts_are_rejected(source):
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(source)


def test_unclosed_root_block_is_rejected():
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(BASE.rstrip()[:-1])


def test_content_after_the_root_block_is_rejected():
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(BASE + "extra")
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(BASE + BASE)


def test_blocks_out_of_order_are_rejected():
    experience = "    experience {\n        job \"Backend Developer, Globant (2021 - 2024)\"\n    }\n"
    assert experience in BASE
    swapped = BASE.replace(experience, "", 1).replace("    education {", experience + "    education {", 1)
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(swapped)


def test_repeated_single_value_fields_are_rejected():
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(BASE.replace('name: "Ana Gomez"', 'name: "A"\n        name: "B"', 1))
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(BASE.replace("email: ", "email: a@b.co\n        email: ", 1))


def test_document_without_skills_is_rejected():
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(make_source(records=[]))


@pytest.mark.parametrize("count", [0, 1, 3, 5])
def test_evaluation_requires_exactly_the_four_profiles(count):
    results = make_results()
    results = (results * 2)[:count] if count > 4 else results[:count]
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(make_source(results=results))


def test_evaluation_profiles_must_follow_the_roadmap_order():
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(make_source(results=list(reversed(make_results()))))


def test_syntax_error_reports_the_location_of_the_violation():
    mutated = BASE.replace("ana.gomez@icesi.edu.co", "ana.gomez.icesi.edu.co", 1)
    email_line = mutated.splitlines().index(
        next(line for line in mutated.splitlines() if "email:" in line)
    ) + 1
    with pytest.raises(TextXSyntaxError) as info:
        parse_candidate_profile(mutated)
    assert info.value.line == email_line
    assert info.value.col > 0
    assert "Email" in str(info.value)


def test_violations_are_syntactic_not_semantic_errors():
    with pytest.raises(TextXSyntaxError) as info:
        parse_candidate_profile("not a candidate")
    assert isinstance(info.value, TextXError)
    assert not isinstance(info.value, TextXSemanticError)


@pytest.mark.parametrize("value", [None, 123, b"candidate {}", ["candidate"], {"name": "Ana"}])
def test_non_string_sources_raise_type_error(value):
    with pytest.raises(TypeError):
        parse_candidate_profile(value)
    with pytest.raises(TypeError):
        is_valid_profile_source(value)


# ---------------------------------------------------------------------------
# Serialization — build_profile_source
# ---------------------------------------------------------------------------
def test_serialized_document_has_the_expected_layout():
    lines = make_source().splitlines()
    assert lines[0] == "candidate {" and lines[-1] == "}"
    blocks = [
        line.split()[0]
        for line in lines
        if line.startswith("    ") and not line.startswith("     ") and line.endswith("{")
    ]
    assert blocks == ["personal", "education", "experience", "skills", "evaluation"]
    assert make_source().endswith("}\n")


def test_serializer_writes_the_pipeline_values():
    source = make_source()
    assert 'name: "Ana Gomez"' in source
    assert "email: ana.gomez@icesi.edu.co" in source
    assert "phone: +57 300 123 4567" in source
    assert source.count("link: ") == 2
    assert 'study "B.S. in Software Engineering"' in source
    assert 'job "Backend Developer, Globant (2021 - 2024)"' in source
    assert 'skill JAVASCRIPT category web_language raw "JS"' in source
    assert "profile FULL_STACK_DEVELOPER: ACCEPTED" in source
    assert "matched [JAVASCRIPT, GIT]" in source
    assert "profile MACHINE_LEARNING_ENGINEER: REJECTED" in source


def test_serializer_omits_missing_contact_fields():
    source = make_source(info=make_info(email="", phone="", links=[]))
    assert "email:" not in source and "phone:" not in source and "link:" not in source
    assert is_valid_profile_source(source)


@pytest.mark.parametrize(
    "profile_name",
    ["Full Stack Developer", "FULL_STACK_DEVELOPER", "full stack developer"],
)
def test_serializer_converts_profile_names_to_identifiers(profile_name):
    results = make_results()
    results[0].profile_name = profile_name
    assert "profile FULL_STACK_DEVELOPER: " in make_source(results=results)


def test_serializer_is_deterministic():
    assert make_source() == make_source()


def test_serializer_does_not_validate_its_input():
    # An e-mail without '@' is written as is; the parser is the one that rejects it.
    source = make_source(info=make_info(email="not-an-email"))
    assert "email: not-an-email" in source
    assert is_valid_profile_source(source) is False


def test_serializer_does_not_mutate_its_inputs():
    info, records, results = make_info(), make_records(), make_results()
    snapshot = (repr(info), repr(records), repr(results))
    build_profile_source(info, records, results)
    assert (repr(info), repr(records), repr(results)) == snapshot


def test_text_ending_in_a_backslash_is_a_known_unrepresentable_string():
    results = make_results(details="ends with a backslash \\")
    assert is_valid_profile_source(make_source(results=results)) is False


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------
def test_serializer_output_parses_back_to_the_same_data():
    info, records, results = make_info(), make_records(), make_results(details="two\nlines")
    model = parse_candidate_profile(build_profile_source(info, records, results))
    assert model_to_inputs(model) == (info, records, results)


def test_handwritten_document_round_trips_to_identical_text():
    rebuilt = build_profile_source(*model_to_inputs(parse_candidate_profile(HANDWRITTEN)))
    assert rebuilt == HANDWRITTEN.replace("\n\n", "\n")


def test_round_trip_is_a_fixed_point_for_tricky_strings():
    info = make_info(name='Ana "The Dev" María', education=['Says "hi"'], experience=["a\nb"])
    source = make_source(info=info, results=make_results(details='x "y"\nz'))
    again = build_profile_source(*model_to_inputs(parse_candidate_profile(source)))
    assert again == source


@pytest.mark.parametrize("alias", list(ACCEPTED_PROFILE_BY_ALIAS))
def test_pipeline_output_of_each_fixture_round_trips(resume_texts, alias):
    info, records, results = pipeline(resume_texts[alias])
    source = build_profile_source(info, records, results)
    model = parse_candidate_profile(source)

    # DSL -> pipeline data
    rebuilt_info, rebuilt_records, rebuilt_results = model_to_inputs(model)
    assert rebuilt_info == info
    assert rebuilt_records == records
    assert [r.matched_sequence for r in rebuilt_results] == [r.matched_sequence for r in results]
    assert [r.details for r in rebuilt_results] == [r.details for r in results]
    # pipeline data -> DSL text again (bidirectional, text is a fixed point)
    assert build_profile_source(rebuilt_info, rebuilt_records, rebuilt_results) == source


@pytest.mark.parametrize("alias, accepted", list(ACCEPTED_PROFILE_BY_ALIAS.items()))
def test_model_reports_the_accepted_profile_of_each_fixture(resume_texts, alias, accepted):
    model = parse_candidate_profile(build_profile_source(*pipeline(resume_texts[alias])))
    verdicts = {r.name: r.verdict for r in model.evaluation.results}
    assert [name for name, verdict in verdicts.items() if verdict == "ACCEPTED"] == [accepted]
    assert list(verdicts) == list(PROFILE_IDS)


def test_fixture_with_missing_skills_cannot_be_represented(invalid_text):
    info, records, results = pipeline(invalid_text)
    assert records == []
    source = build_profile_source(info, records, results)
    assert is_valid_profile_source(source) is False
    with pytest.raises(TextXSyntaxError):
        parse_candidate_profile(source)


def test_fixture_with_missing_contact_data_is_still_valid(fullstack_text):
    info, records, results = pipeline(fullstack_text)
    info.email, info.phone, info.links = "", "", []
    model = parse_candidate_profile(build_profile_source(info, records, results))
    assert model.personal.email is None
    assert model.personal.phone is None
    assert model.personal.links == []
