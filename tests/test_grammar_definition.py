"""Preliminary syntax validation of the textX grammar ``resume_grammar.tx``.

The grammar file is loaded directly with ``textx.metamodel_from_file`` and exercised with
small documents: valid ones must produce a model, and each kind of lexical or syntactic
violation must raise ``TextXSyntaxError``. A last group serializes the output of the
earlier stages (the synthetic resumes) into the language to check that the grammar can
describe real data. The serializer used there is test scaffolding only.
"""

from pathlib import Path

import pytest
from textx import metamodel_from_file, textx_isinstance
from textx.exceptions import TextXSyntaxError

from resumelens.classification import classify_all
from resumelens.extraction.extractor import extract_resume
from resumelens.normalization import normalize_with_report

GRAMMAR_PATH = Path(__file__).resolve().parent.parent / "resumelens" / "grammar" / "resume_grammar.tx"

PROFILE_NAMES = (
    "FULL_STACK_DEVELOPER",
    "MACHINE_LEARNING_ENGINEER",
    "DEVOPS_ENGINEER",
    "DATA_ENGINEER",
)


@pytest.fixture(scope="module")
def metamodel():
    return metamodel_from_file(str(GRAMMAR_PATH))


# ---------------------------------------------------------------------------
# Document builder
# ---------------------------------------------------------------------------
PERSONAL = """personal {
        name: "WEDNESDAY ADDAMS"
        email: wednesday.addams@nevermore.edu
        phone: +1 555 666 7777
        link: https://www.linkedin.com/in/wednesday-addams
        link: https://github.com/wednesday-addams
    }"""

EDUCATION = """education {
        study "B.S. in Computer Science"
        study "Nevermore University (2019 - 2023)"
    }"""

EXPERIENCE = """experience {
        job "Full Stack Developer, Raven Labs (2023 - 2026)"
    }"""

SKILLS = """skills {
        skill JAVASCRIPT category web_language raw "JS"
        skill REACT category frontend raw "React.js"
        skill NODE_JS category backend raw "NodeJS"
        skill POSTGRESQL category database raw "Postgres"
        skill GIT category vcs raw "Git"
    }"""

EVALUATION = """evaluation {
        profile FULL_STACK_DEVELOPER: ACCEPTED
            matched [JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT]
            details "ACCEPTED - Full Stack Developer"
        profile MACHINE_LEARNING_ENGINEER: REJECTED
            matched []
            details "REJECTED - Machine Learning Engineer"
        profile DEVOPS_ENGINEER: REJECTED
            matched []
            details "REJECTED - DevOps Engineer"
        profile DATA_ENGINEER: REJECTED
            matched []
            details "REJECTED - Data Engineer"
    }"""


def document(personal=PERSONAL, education=EDUCATION, experience=EXPERIENCE, skills=SKILLS, evaluation=EVALUATION):
    blocks = [personal, education, experience, skills, evaluation]
    body = "\n    ".join(block for block in blocks if block)
    return f"candidate {{\n    {body}\n}}\n"


VALID = document()


def parse(metamodel, text):
    return metamodel.model_from_str(text)


# ---------------------------------------------------------------------------
# The grammar file
# ---------------------------------------------------------------------------
class TestGrammarFile:
    def test_file_exists_next_to_the_grammar_package(self):
        assert GRAMMAR_PATH.is_file()
        assert GRAMMAR_PATH.parent.name == "grammar"
        assert GRAMMAR_PATH.stat().st_size > 0

    def test_file_defines_the_comment_rule(self):
        text = GRAMMAR_PATH.read_text(encoding="utf-8")
        assert r"Comment: /\/\/.*$/;" in text

    def test_grammar_loads_without_error(self, metamodel):
        assert metamodel is not None

    def test_root_rule_is_the_first_rule(self, metamodel):
        assert type(parse(metamodel, VALID)).__name__ == "CandidateReport"

    def test_expected_rules_are_defined(self, metamodel):
        names = set(metamodel.namespaces["resume_grammar"])
        assert {
            "CandidateReport",
            "PersonalInfo",
            "EducationSection",
            "EducationEntry",
            "ExperienceSection",
            "ExperienceEntry",
            "SkillSection",
            "SkillEntry",
            "EvaluationSection",
            "ProfileResult",
            "FullStackResult",
            "MachineLearningResult",
            "DevOpsResult",
            "DataEngineerResult",
            "Verdict",
            "CanonicalName",
            "Category",
            "Email",
            "Phone",
            "Url",
            "Comment",
        } <= names

    def test_grammar_has_no_python_dependencies_besides_textx(self):
        text = GRAMMAR_PATH.read_text(encoding="utf-8")
        assert "import" not in text


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------
class TestValidDocuments:
    def test_personal_information(self, metamodel):
        personal = parse(metamodel, VALID).personal
        assert personal.name == "WEDNESDAY ADDAMS"
        assert personal.email == "wednesday.addams@nevermore.edu"
        assert personal.phone == "+1 555 666 7777"
        assert personal.links == [
            "https://www.linkedin.com/in/wednesday-addams",
            "https://github.com/wednesday-addams",
        ]

    def test_repeated_education_and_experience_entries(self, metamodel):
        model = parse(metamodel, VALID)
        assert [e.description for e in model.education.entries] == [
            "B.S. in Computer Science",
            "Nevermore University (2019 - 2023)",
        ]
        assert [e.description for e in model.experience.entries] == ["Full Stack Developer, Raven Labs (2023 - 2026)"]

    def test_several_education_and_experience_entries(self, metamodel):
        text = document(
            education='education { study "A" study "B" study "C" }',
            experience='experience { job "X" job "Y" }',
        )
        model = parse(metamodel, text)
        assert len(model.education.entries) == 3
        assert len(model.experience.entries) == 2

    def test_skills(self, metamodel):
        skills = parse(metamodel, VALID).skills.skills
        assert [(s.canonical, s.category, s.raw) for s in skills] == [
            ("JAVASCRIPT", "web_language", "JS"),
            ("REACT", "frontend", "React.js"),
            ("NODE_JS", "backend", "NodeJS"),
            ("POSTGRESQL", "database", "Postgres"),
            ("GIT", "vcs", "Git"),
        ]

    def test_one_verdict_per_profile_in_roadmap_order(self, metamodel):
        results = parse(metamodel, VALID).evaluation.results
        assert [r.name for r in results] == list(PROFILE_NAMES)
        assert [r.verdict for r in results] == ["ACCEPTED", "REJECTED", "REJECTED", "REJECTED"]
        assert results[0].matched == ["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]
        assert results[1].matched == []
        assert results[0].details == "ACCEPTED - Full Stack Developer"

    def test_results_share_the_abstract_profile_result_type(self, metamodel):
        results = parse(metamodel, VALID).evaluation.results
        assert [type(r).__name__ for r in results] == [
            "FullStackResult",
            "MachineLearningResult",
            "DevOpsResult",
            "DataEngineerResult",
        ]
        assert all(textx_isinstance(r, metamodel["ProfileResult"]) for r in results)

    def test_minimal_document_without_optional_parts(self, metamodel):
        text = document(
            personal='personal { name: "A" }',
            education="education { }",
            experience="experience { }",
        )
        model = parse(metamodel, text)
        assert model.personal.email is None
        assert model.personal.phone is None
        assert model.personal.links == []
        assert model.education.entries == []
        assert model.experience.entries == []

    @pytest.mark.parametrize("phone", ["+1 555 666 7777", "(555) 123-4567", "555.123.4567", "5551234567", "+57 300 123 4567"])
    def test_phone_formats(self, metamodel, phone):
        text = document(personal=f'personal {{ name: "A" phone: {phone} }}')
        assert parse(metamodel, text).personal.phone == phone

    @pytest.mark.parametrize(
        "url",
        ["https://github.com/u/repo.name", "http://example.com", "HTTPS://WWW.LINKEDIN.COM/in/x-y"],
    )
    def test_url_formats(self, metamodel, url):
        text = document(personal=f'personal {{ name: "A" link: {url} }}')
        assert parse(metamodel, text).personal.links == [url]

    def test_email_formats(self, metamodel):
        text = document(personal='personal { name: "A" email: A.B+c@Sub.Example.COM }')
        assert parse(metamodel, text).personal.email == "A.B+c@Sub.Example.COM"

    def test_strings_may_span_lines_hold_quotes_and_unicode(self, metamodel):
        evaluation = EVALUATION.replace('"ACCEPTED - Full Stack Developer"', '"line one\nline \\"two\\" ñandú"', 1)
        text = document(personal='personal { name: "Ana María Gómez" }', evaluation=evaluation)
        model = parse(metamodel, text)
        assert model.personal.name == "Ana María Gómez"
        assert model.evaluation.results[0].details == 'line one\nline "two" ñandú'

    def test_matched_list_may_be_spread_over_several_lines(self, metamodel):
        evaluation = EVALUATION.replace("[JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT]", "[\n JAVASCRIPT ,\n REACT\n]")
        assert parse(metamodel, document(evaluation=evaluation)).evaluation.results[0].matched == ["JAVASCRIPT", "REACT"]

    def test_line_endings_and_whitespace_do_not_matter(self, metamodel):
        assert parse(metamodel, VALID.replace("\n", "\r\n")).skills.skills
        assert parse(metamodel, VALID.replace("    ", "\t\n\n")).skills.skills

    def test_each_skill_category_of_stage_2_is_a_valid_category(self, metamodel):
        for category in ("web_language", "data_library", "ml_framework", "ml_practice", "iac", "ci_cd", "vcs"):
            skills = f'skills {{ skill GIT category {category} raw "x" }}'
            assert parse(metamodel, document(skills=skills)).skills.skills[0].category == category


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class TestComments:
    def test_comment_lines_are_ignored(self, metamodel):
        text = "// header\n" + VALID.replace("education {", "// the studies\n    education {") + "// footer"
        assert parse(metamodel, text).skills.skills

    def test_trailing_comment_after_a_token(self, metamodel):
        text = VALID.replace('name: "WEDNESDAY ADDAMS"', 'name: "WEDNESDAY ADDAMS" // the candidate')
        assert parse(metamodel, text).personal.name == "WEDNESDAY ADDAMS"

    def test_comment_between_every_pair_of_blocks(self, metamodel):
        text = document().replace("\n    ", "\n    // block\n    ")
        assert len(parse(metamodel, text).skills.skills) == 5

    def test_double_slash_inside_a_string_or_a_url_is_not_a_comment(self, metamodel):
        evaluation = EVALUATION.replace('"REJECTED - DevOps Engineer"', '"see https://x.org // not a comment"')
        model = parse(metamodel, document(evaluation=evaluation))
        assert model.evaluation.results[2].details == "see https://x.org // not a comment"
        assert parse(metamodel, VALID).personal.links[0].startswith("https://")

    def test_comment_cannot_hide_a_mandatory_token(self, metamodel):
        with pytest.raises(TextXSyntaxError):
            parse(metamodel, VALID.replace("personal {", "// personal {"))


# ---------------------------------------------------------------------------
# Syntactic violations
# ---------------------------------------------------------------------------
def _without(block):
    return document(**{block: ""})


SYNTAX_VIOLATIONS = {
    "empty document": "",
    "only a comment": "// nothing else",
    "no root keyword": VALID.replace("candidate", "person", 1),
    "unclosed root": VALID.rstrip()[:-1],
    "trailing garbage": VALID + "\nextra",
    "two candidates": VALID + VALID,
    "missing personal": _without("personal"),
    "missing education": _without("education"),
    "missing experience": _without("experience"),
    "missing skills": _without("skills"),
    "missing evaluation": _without("evaluation"),
    "blocks out of order": document(education=EXPERIENCE, experience=EDUCATION),
    "skills before experience": document(experience=SKILLS, skills=EXPERIENCE),
    "empty skills block": document(skills="skills { }"),
    "personal without name": document(personal="personal { email: a@b.co }"),
    "name without quotes": document(personal="personal { name: Wednesday }"),
    "phone before email": document(personal='personal { name: "A" phone: 555 123 4567 email: a@b.co }'),
    "two emails": document(personal='personal { name: "A" email: a@b.co email: c@d.co }'),
    "link before phone": document(personal='personal { name: "A" link: https://a.com phone: 555 123 4567 }'),
    "study without text": document(education="education { study }"),
    "unknown entry keyword": document(education='education { degree "x" }'),
    "job in education": document(education='education { job "x" }'),
    "skill without raw": document(skills="skills { skill GIT category vcs }"),
    "skill without category": document(skills='skills { skill GIT raw "Git" }'),
    "skill raw without quotes": document(skills="skills { skill GIT category vcs raw Git }"),
    "skill fields out of order": document(skills='skills { skill GIT raw "Git" category vcs }'),
    "unknown keyword": document(personal='personal { name: "A" nickname: "B" }'),
}

LEXICAL_VIOLATIONS = {
    "e-mail without domain": document(personal='personal { name: "A" email: wednesday }'),
    "e-mail without tld": document(personal='personal { name: "A" email: a@b }'),
    "e-mail with one-letter tld": document(personal='personal { name: "A" email: a@b.c }'),
    "phone too short": document(personal='personal { name: "A" phone: 12345 }'),
    "phone with wrong grouping": document(personal='personal { name: "A" phone: 555-12-34567 }'),
    "ftp url": document(personal='personal { name: "A" link: ftp://x.com }'),
    "url without dot in host": document(personal='personal { name: "A" link: http://localhost }'),
    "url without scheme": document(personal='personal { name: "A" link: github.com/x }'),
    "lower case canonical name": document(skills='skills { skill git category vcs raw "Git" }'),
    "canonical name with dash": document(skills='skills { skill NODE-JS category backend raw "x" }'),
    "canonical name starting with digit": document(skills='skills { skill 1GIT category vcs raw "x" }'),
    "upper case category": document(skills='skills { skill GIT category VCS raw "x" }'),
    "category with dash": document(skills='skills { skill GIT category web-language raw "x" }'),
    "category starting with underscore": document(skills='skills { skill GIT category _vcs raw "x" }'),
    "lower case verdict": document(evaluation=EVALUATION.replace("ACCEPTED", "accepted", 1)),
    "unknown verdict": document(evaluation=EVALUATION.replace("ACCEPTED", "MAYBE", 1)),
    "lower case matched skill": document(evaluation=EVALUATION.replace("[JAVASCRIPT,", "[javascript,", 1)),
    "unterminated string": document(personal='personal { name: "A }'),
}

EVALUATION_VIOLATIONS = {
    "only three profiles": document(evaluation=EVALUATION.replace(
        '        profile DATA_ENGINEER: REJECTED\n            matched []\n            details "REJECTED - Data Engineer"\n', ""
    )),
    "no profiles": document(evaluation="evaluation { }"),
    "profile repeated": document(evaluation=EVALUATION.replace("profile DATA_ENGINEER", "profile DEVOPS_ENGINEER")),
    "two profiles swapped": document(
        evaluation=EVALUATION.replace("DEVOPS_ENGINEER", "TMP").replace("DATA_ENGINEER", "DEVOPS_ENGINEER").replace("TMP", "DATA_ENGINEER")
    ),
    "unknown profile": document(evaluation=EVALUATION.replace("DATA_ENGINEER", "DATA_SCIENTIST", 1)),
    "profile name in mixed case": document(evaluation=EVALUATION.replace("FULL_STACK_DEVELOPER", "Full_Stack_Developer", 1)),
    "five profiles": document(
        evaluation=EVALUATION.rstrip()[:-1] + '    profile FULL_STACK_DEVELOPER: ACCEPTED matched [] details "x"\n    }'
    ),
    "missing matched": document(evaluation=EVALUATION.replace("            matched []\n", "", 1)),
    "missing details": document(evaluation=EVALUATION.replace('            details "REJECTED - Data Engineer"\n', "", 1)),
    "details before matched": document(
        evaluation=EVALUATION.replace(
            'matched [JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT]\n            details "ACCEPTED - Full Stack Developer"',
            'details "ACCEPTED - Full Stack Developer"\n            matched [JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT]',
        )
    ),
    "matched without brackets": document(evaluation=EVALUATION.replace("[JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT]", "JAVASCRIPT")),
    "matched with trailing comma": document(evaluation=EVALUATION.replace("GIT]", "GIT,]", 1)),
    "matched without commas": document(evaluation=EVALUATION.replace("[JAVASCRIPT, REACT,", "[JAVASCRIPT REACT,", 1)),
}


class TestViolationsAreRejected:
    @pytest.mark.parametrize("label", list(SYNTAX_VIOLATIONS))
    def test_syntactic_violations(self, metamodel, label):
        with pytest.raises(TextXSyntaxError):
            parse(metamodel, SYNTAX_VIOLATIONS[label])

    @pytest.mark.parametrize("label", list(LEXICAL_VIOLATIONS))
    def test_lexical_violations(self, metamodel, label):
        with pytest.raises(TextXSyntaxError):
            parse(metamodel, LEXICAL_VIOLATIONS[label])

    @pytest.mark.parametrize("label", list(EVALUATION_VIOLATIONS))
    def test_incomplete_or_malformed_evaluations(self, metamodel, label):
        with pytest.raises(TextXSyntaxError):
            parse(metamodel, EVALUATION_VIOLATIONS[label])

    def test_the_valid_document_is_the_base_of_every_violation(self, metamodel):
        # Guard: the violations above are variations of a document that does parse.
        assert parse(metamodel, VALID)
        for text in list(SYNTAX_VIOLATIONS.values()) + list(LEXICAL_VIOLATIONS.values()) + list(EVALUATION_VIOLATIONS.values()):
            assert text != VALID

    def test_error_messages_give_a_position(self, metamodel):
        with pytest.raises(TextXSyntaxError) as error:
            parse(metamodel, document(skills="skills { }"))
        assert error.value.line is not None
        assert error.value.col is not None


# ---------------------------------------------------------------------------
# The grammar describes the output of the earlier stages
# ---------------------------------------------------------------------------
def _quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _serialize(raw_resume_data, records, results):
    """Test scaffolding: write stage outputs in the language of the grammar."""
    info = raw_resume_data.candidate_info
    personal = [f"name: {_quote(info.name)}"]
    if info.email:
        personal.append(f"email: {info.email}")
    if info.phone:
        personal.append(f"phone: {info.phone}")
    personal += [f"link: {link}" for link in info.links]
    lines = ["candidate {", "  personal {", *[f"    {item}" for item in personal], "  }"]
    lines += ["  education {", *[f"    study {_quote(item)}" for item in info.education], "  }"]
    lines += ["  experience {", *[f"    job {_quote(item)}" for item in info.experience], "  }"]
    lines += ["  skills {"]
    lines += [f"    skill {r.canonical_name} category {r.category} raw {_quote(r.raw_name)}" for r in records]
    lines += ["  }", "  evaluation {"]
    for result in results:
        verdict = "ACCEPTED" if result.is_accepted else "REJECTED"
        identifier = "_".join(result.profile_name.upper().split())
        lines.append(f"    profile {identifier}: {verdict}")
        lines.append(f"      matched [{', '.join(result.matched_sequence)}]")
        lines.append(f"      details {_quote(result.details)}")
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def _pipeline(text):
    raw = extract_resume(text)
    records = normalize_with_report(raw.raw_skills).records
    return raw, records, classify_all(records).results


class TestGrammarDescribesRealData:
    @pytest.mark.parametrize(
        "fixture_name, accepted",
        [
            ("fullstack_text", "FULL_STACK_DEVELOPER"),
            ("ml_text", "MACHINE_LEARNING_ENGINEER"),
            ("devops_text", "DEVOPS_ENGINEER"),
            ("data_text", "DATA_ENGINEER"),
        ],
    )
    def test_each_valid_resume_is_a_valid_document(self, metamodel, fixture_name, accepted, request):
        raw, records, results = _pipeline(request.getfixturevalue(fixture_name))
        model = parse(metamodel, _serialize(raw, records, results))
        assert model.personal.name == raw.candidate_info.name
        assert model.personal.email == raw.candidate_info.email
        assert model.personal.phone == raw.candidate_info.phone
        assert model.personal.links == raw.candidate_info.links
        assert [e.description for e in model.education.entries] == raw.candidate_info.education
        assert [e.description for e in model.experience.entries] == raw.candidate_info.experience
        assert [s.canonical for s in model.skills.skills] == [r.canonical_name for r in records]
        assert [s.raw for s in model.skills.skills] == [r.raw_name for r in records]
        assert [r.name for r in model.evaluation.results] == list(PROFILE_NAMES)
        assert [r.name for r in model.evaluation.results if r.verdict == "ACCEPTED"] == [accepted]

    def test_reports_of_the_automata_survive_the_round_trip(self, metamodel, ml_text):
        raw, records, results = _pipeline(ml_text)
        model = parse(metamodel, _serialize(raw, records, results))
        assert [r.details for r in model.evaluation.results] == [r.details for r in results]
        assert [r.matched for r in model.evaluation.results] == [r.matched_sequence for r in results]

    def test_resume_without_skills_is_an_incomplete_representation(self, metamodel, invalid_text):
        raw, records, results = _pipeline(invalid_text)
        assert records == []
        with pytest.raises(TextXSyntaxError):
            parse(metamodel, _serialize(raw, records, results))

    def test_a_valid_resume_with_missing_contact_data_is_still_valid(self, metamodel, fullstack_text):
        raw, records, results = _pipeline(fullstack_text)
        raw.candidate_info.email = ""
        raw.candidate_info.phone = ""
        raw.candidate_info.links = []
        model = parse(metamodel, _serialize(raw, records, results))
        assert model.personal.email is None
        assert model.personal.phone is None
        assert model.personal.links == []
