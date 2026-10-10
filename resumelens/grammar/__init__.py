"""Stage 4 — candidate specification language (textX grammar, parser and serializer)."""

from resumelens.grammar.parser import (
    GRAMMAR_PATH,
    build_profile_source,
    is_valid_profile_source,
    load_metamodel,
    parse_candidate_profile,
)

__all__ = [
    "GRAMMAR_PATH",
    "build_profile_source",
    "is_valid_profile_source",
    "load_metamodel",
    "parse_candidate_profile",
]
