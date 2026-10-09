"""Stage 2 — Normalization pipeline.

Coordinates the finite-state transducers of :mod:`resumelens.normalization.transducers`
over the raw skill tokens produced by Stage 1 (``RawResumeData.raw_skills``).

Each raw token is offered, in a fixed order, to one transducer per technology family
(Web, AI / data libraries, databases, Cloud / DevOps, version control, programming
languages and data engineering). The first transducer that translates the token decides
its canonical name and, through the category table, its category. Tokens that no
transducer accepts (unknown technologies, misspellings, characters outside the input
alphabet) are reported as *unrecognized* and never reach the classification stage.

The categories follow the qualification lists of the assignment: each bullet of a profile
("JavaScript or TypeScript", "React, Angular, or Vue", "Pandas or NumPy", ...) is one
category, so that the sorter can place the skills of each bullet together.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pyformlang.fst import FST

from resumelens.core.models import SkillRecord
from resumelens.normalization.transducers import (
    DB_CANONICAL_FORMS,
    LANGUAGE_CANONICAL_FORMS,
    VCS_CANONICAL_FORMS,
    apply_transducer,
    get_ai_transducer,
    get_data_transducer,
    get_db_transducer,
    get_devops_transducer,
    get_language_transducer,
    get_vcs_transducer,
    get_web_transducer,
)

#: Category names (values of ``SkillRecord.category``).
CATEGORY_WEB_LANGUAGE: str = "web_language"
CATEGORY_FRONTEND: str = "frontend"
CATEGORY_BACKEND: str = "backend"
CATEGORY_API: str = "api"
CATEGORY_DATA_LIBRARY: str = "data_library"
CATEGORY_ML_FRAMEWORK: str = "ml_framework"
CATEGORY_ML_PRACTICE: str = "ml_practice"
CATEGORY_DATABASE: str = "database"
CATEGORY_CONTAINER: str = "container"
CATEGORY_ORCHESTRATION: str = "orchestration"
CATEGORY_IAC: str = "iac"
CATEGORY_CI_CD: str = "ci_cd"
CATEGORY_CLOUD: str = "cloud"
CATEGORY_VCS: str = "vcs"
CATEGORY_LANGUAGE: str = "language"
CATEGORY_DATA_PROCESSING: str = "data_processing"
CATEGORY_WORKFLOW: str = "workflow"

#: Every category, in no particular order.
CATEGORIES: Tuple[str, ...] = (
    CATEGORY_WEB_LANGUAGE,
    CATEGORY_FRONTEND,
    CATEGORY_BACKEND,
    CATEGORY_API,
    CATEGORY_DATA_LIBRARY,
    CATEGORY_ML_FRAMEWORK,
    CATEGORY_ML_PRACTICE,
    CATEGORY_DATABASE,
    CATEGORY_CONTAINER,
    CATEGORY_ORCHESTRATION,
    CATEGORY_IAC,
    CATEGORY_CI_CD,
    CATEGORY_CLOUD,
    CATEGORY_VCS,
    CATEGORY_LANGUAGE,
    CATEGORY_DATA_PROCESSING,
    CATEGORY_WORKFLOW,
)

#: Category of each canonical name produced by the Web transducer.
WEB_CATEGORIES: Mapping[str, str] = {
    "JAVASCRIPT": CATEGORY_WEB_LANGUAGE,
    "TYPESCRIPT": CATEGORY_WEB_LANGUAGE,
    "REACT": CATEGORY_FRONTEND,
    "ANGULAR": CATEGORY_FRONTEND,
    "VUE": CATEGORY_FRONTEND,
    "NODE_JS": CATEGORY_BACKEND,
    "SPRING_BOOT": CATEGORY_BACKEND,
    "DJANGO": CATEGORY_BACKEND,
    "REST_API": CATEGORY_API,
}

#: Category of each canonical name produced by the AI transducer.
AI_CATEGORIES: Mapping[str, str] = {
    "PANDAS": CATEGORY_DATA_LIBRARY,
    "NUMPY": CATEGORY_DATA_LIBRARY,
    "MATPLOTLIB": CATEGORY_DATA_LIBRARY,
    "SCIKIT_LEARN": CATEGORY_ML_FRAMEWORK,
    "TENSORFLOW": CATEGORY_ML_FRAMEWORK,
    "PYTORCH": CATEGORY_ML_FRAMEWORK,
    "KERAS": CATEGORY_ML_FRAMEWORK,
    "ML_MODEL_DEVELOPMENT": CATEGORY_ML_PRACTICE,
}

#: Category of each canonical name produced by the Cloud / DevOps transducer.
DEVOPS_CATEGORIES: Mapping[str, str] = {
    "DOCKER": CATEGORY_CONTAINER,
    "KUBERNETES": CATEGORY_ORCHESTRATION,
    "TERRAFORM": CATEGORY_IAC,
    "ANSIBLE": CATEGORY_IAC,
    "JENKINS": CATEGORY_CI_CD,
    "AWS": CATEGORY_CLOUD,
    "AZURE": CATEGORY_CLOUD,
    "GCP": CATEGORY_CLOUD,
}

#: Category of each canonical name produced by the data-engineering transducer.
DATA_CATEGORIES: Mapping[str, str] = {
    "SPARK": CATEGORY_DATA_PROCESSING,
    "AIRFLOW": CATEGORY_WORKFLOW,
}


@dataclass(frozen=True)
class TechnologyFamily:
    """One transducer together with the category of each canonical name it emits.

    Attributes:
        name: Label of the family, used in error messages.
        get_transducer: Function returning the (shared) transducer of the family.
        categories: Mapping ``canonical name -> SkillRecord.category``.
    """

    name: str
    get_transducer: Callable[[], FST]
    categories: Mapping[str, str]


def _uniform(canonical_names: Iterable[str], category: str) -> Dict[str, str]:
    """Assign the same ``category`` to every canonical name."""
    return {canonical: category for canonical in canonical_names}


#: Families in the order in which they are tried. Their variant tables are disjoint, so
#: the order only affects speed, never the result.
DEFAULT_FAMILIES: Tuple[TechnologyFamily, ...] = (
    TechnologyFamily("web", get_web_transducer, WEB_CATEGORIES),
    TechnologyFamily("ai", get_ai_transducer, AI_CATEGORIES),
    TechnologyFamily("database", get_db_transducer, _uniform(DB_CANONICAL_FORMS, CATEGORY_DATABASE)),
    TechnologyFamily("devops", get_devops_transducer, DEVOPS_CATEGORIES),
    TechnologyFamily("vcs", get_vcs_transducer, _uniform(VCS_CANONICAL_FORMS, CATEGORY_VCS)),
    TechnologyFamily(
        "language", get_language_transducer, _uniform(LANGUAGE_CANONICAL_FORMS, CATEGORY_LANGUAGE)
    ),
    TechnologyFamily("data", get_data_transducer, DATA_CATEGORIES),
)


@dataclass
class NormalizationResult:
    """Outcome of normalizing a list of raw skill tokens.

    Attributes:
        records: One ``SkillRecord`` per distinct canonical name, in order of first
            appearance in the input.
        unrecognized: Raw tokens that no transducer accepts, without repetitions
            (compared ignoring case), in order of appearance.
        duplicates: Raw tokens dropped because their canonical name had already
            appeared (e.g. ``"JS"`` after ``"JavaScript"``), in order of appearance.
    """

    records: List[SkillRecord] = field(default_factory=list)
    unrecognized: List[str] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)

    @property
    def canonical_names(self) -> List[str]:
        """Canonical names of ``records``, in the same order."""
        return [record.canonical_name for record in self.records]


def _clean_token(raw: str) -> str:
    """Trim a token and collapse inner whitespace runs into single spaces."""
    return " ".join(raw.split())


class SkillNormalizer:
    """Normalizes raw skill tokens by running them through the family transducers.

    Args:
        families: Families to try, in order. Defaults to :data:`DEFAULT_FAMILIES`.

    Raises:
        ValueError: If a family has no category for one of its canonical names, or if
            two families emit the same canonical name.
    """

    def __init__(self, families: Sequence[TechnologyFamily] = DEFAULT_FAMILIES) -> None:
        self._families: Tuple[TechnologyFamily, ...] = tuple(families)
        self._category_by_canonical: Dict[str, str] = {}
        for family in self._families:
            for canonical, category in family.categories.items():
                if not category:
                    raise ValueError(f"Empty category for {canonical!r} in family {family.name!r}.")
                if canonical in self._category_by_canonical:
                    raise ValueError(
                        f"Canonical name {canonical!r} is declared by more than one family."
                    )
                self._category_by_canonical[canonical] = category

    @property
    def families(self) -> Tuple[TechnologyFamily, ...]:
        """The families tried by this normalizer, in order."""
        return self._families

    def category_of(self, canonical_name: str) -> Optional[str]:
        """Return the category of a canonical name, or ``None`` if it is unknown."""
        return self._category_by_canonical.get(canonical_name)

    def normalize_skill(self, raw: str) -> Optional[str]:
        """Translate one raw token to its canonical name.

        Surrounding whitespace is ignored, inner whitespace runs are collapsed and letter
        case does not matter.

        Returns:
            The canonical name, or ``None`` if no transducer accepts the token (empty
            token, unknown technology, or characters outside the input alphabet).
        """
        token = _clean_token(raw)
        if not token:
            return None
        for family in self._families:
            canonical = apply_transducer(family.get_transducer(), token)
            if canonical is not None:
                return canonical
        return None

    def to_record(self, raw: str) -> Optional[SkillRecord]:
        """Return the ``SkillRecord`` of one raw token, or ``None`` if unrecognized."""
        canonical = self.normalize_skill(raw)
        if canonical is None:
            return None
        category = self._category_by_canonical.get(canonical)
        if category is None:
            raise ValueError(f"No category defined for canonical name {canonical!r}.")
        return SkillRecord(raw_name=_clean_token(raw), canonical_name=canonical, category=category)

    def normalize(self, raw_skills: Iterable[str]) -> NormalizationResult:
        """Normalize a list of raw tokens and report what was dropped and why.

        Equivalent spellings are unified under one canonical name and only the first
        occurrence is kept; the order of the survivors is the order of appearance.
        """
        result = NormalizationResult()
        seen_canonical: Set[str] = set()
        seen_unrecognized: Set[str] = set()
        for raw in raw_skills:
            token = _clean_token(raw)
            if not token:
                continue
            record = self.to_record(token)
            if record is None:
                key = token.casefold()
                if key not in seen_unrecognized:
                    seen_unrecognized.add(key)
                    result.unrecognized.append(token)
            elif record.canonical_name in seen_canonical:
                result.duplicates.append(token)
            else:
                seen_canonical.add(record.canonical_name)
                result.records.append(record)
        return result

    def normalize_skills(self, raw_skills: Iterable[str]) -> List[SkillRecord]:
        """Return only the ``SkillRecord`` list of :meth:`normalize`."""
        return self.normalize(raw_skills).records


@lru_cache(maxsize=1)
def get_default_normalizer() -> SkillNormalizer:
    """Return the shared normalizer built with :data:`DEFAULT_FAMILIES`."""
    return SkillNormalizer()


def normalize_skill(raw: str) -> Optional[str]:
    """Translate one raw token to its canonical name with the default normalizer."""
    return get_default_normalizer().normalize_skill(raw)


def normalize_skills(raw_skills: Iterable[str]) -> List[SkillRecord]:
    """Normalize raw tokens into de-duplicated ``SkillRecord`` objects (default normalizer)."""
    return get_default_normalizer().normalize_skills(raw_skills)


def normalize_with_report(raw_skills: Iterable[str]) -> NormalizationResult:
    """Normalize raw tokens and also report unrecognized tokens and dropped duplicates."""
    return get_default_normalizer().normalize(raw_skills)
