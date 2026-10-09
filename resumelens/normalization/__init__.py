"""Stage 2 — normalization of raw skills with finite-state transducers."""

from resumelens.normalization.normalizer import (
    DEFAULT_FAMILIES,
    NormalizationResult,
    SkillNormalizer,
    TechnologyFamily,
    get_default_normalizer,
    normalize_skill,
    normalize_skills,
    normalize_with_report,
)
from resumelens.normalization.transducers import (
    END_OF_TOKEN,
    apply_transducer,
    build_ai_transducer,
    build_db_transducer,
    build_devops_transducer,
    build_transducer,
    build_web_transducer,
    normalize_ai_skill,
    normalize_db_skill,
    normalize_devops_skill,
    normalize_web_skill,
)

__all__ = [
    "DEFAULT_FAMILIES",
    "END_OF_TOKEN",
    "NormalizationResult",
    "SkillNormalizer",
    "TechnologyFamily",
    "apply_transducer",
    "build_ai_transducer",
    "build_db_transducer",
    "build_devops_transducer",
    "build_transducer",
    "build_web_transducer",
    "get_default_normalizer",
    "normalize_ai_skill",
    "normalize_db_skill",
    "normalize_devops_skill",
    "normalize_skill",
    "normalize_skills",
    "normalize_web_skill",
    "normalize_with_report",
]
