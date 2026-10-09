"""Stage 2 — Normalization pipeline.

Coordinates the finite-state transducers of :mod:`resumelens.normalization.transducers`
over the raw skill tokens produced by Stage 1 (``RawResumeData.raw_skills``).

Each raw token is offered, in a fixed order, to one transducer per technology family.
The first transducer that translates the token decides its canonical name and, through
the family's category table, its category. Tokens that no transducer accepts (unknown
technologies, misspellings, characters outside the input alphabet) are reported as
*unrecognized* and never reach the classification stage.

The families defined in ``transducers.py`` are Web, AI / data libraries, databases and
Cloud / DevOps. Three more families are declared here, with the same
:func:`~resumelens.normalization.transducers.build_transducer` construction, because the
supported profiles also need them: version control (``Git``), programming languages
(``Python`` ...) and data-engineering tools (``Spark``, ``Airflow``).
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pyformlang.fst import FST

from resumelens.core.models import SkillRecord
from resumelens.normalization.transducers import (
    AI_CANONICAL_FORMS,
    DB_CANONICAL_FORMS,
    DEVOPS_CANONICAL_FORMS,
    apply_transducer,
    build_transducer,
    get_ai_transducer,
    get_db_transducer,
    get_devops_transducer,
    get_web_transducer,
)

#: Version-control tools and hosting platforms, all normalized to ``GIT``.
VCS_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "GIT": ("Git", "GitHub", "GitLab"),
}

#: General-purpose programming languages recognized by the Stage 1 skill bank.
#: ``JavaScript`` and ``TypeScript`` belong to the Web transducer.
LANGUAGE_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "PYTHON": ("Python", "Python3"),
    "JAVA": ("Java",),
    "C": ("C",),
    "C_PLUS_PLUS": ("C++", "CPP"),
    "C_SHARP": ("C#", "CSharp"),
    "GO": ("Go", "Golang"),
    "RUST": ("Rust",),
    "KOTLIN": ("Kotlin",),
    "SWIFT": ("Swift",),
    "PHP": ("PHP",),
    "RUBY": ("Ruby",),
}

#: Data-engineering tools.
DATA_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "SPARK": ("Spark", "Apache Spark", "PySpark"),
    "AIRFLOW": ("Airflow", "Apache Airflow"),
}

#: Category of each canonical name produced by the Web transducer.
WEB_CATEGORIES: Mapping[str, str] = {
    "JAVASCRIPT": "frontend",
    "TYPESCRIPT": "frontend",
    "REACT": "frontend",
    "ANGULAR": "frontend",
    "VUE": "frontend",
    "NODE_JS": "backend",
    "SPRING_BOOT": "backend",
    "DJANGO": "backend",
}


@lru_cache(maxsize=1)
def get_vcs_transducer() -> FST:
    """Return the shared version-control transducer, built on first use."""
    return build_transducer(VCS_VARIANTS)


@lru_cache(maxsize=1)
def get_language_transducer() -> FST:
    """Return the shared programming-language transducer, built on first use."""
    return build_transducer(LANGUAGE_VARIANTS)


@lru_cache(maxsize=1)
def get_data_transducer() -> FST:
    """Return the shared data-engineering transducer, built on first use."""
    return build_transducer(DATA_VARIANTS)


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
    TechnologyFamily("ai", get_ai_transducer, _uniform(AI_CANONICAL_FORMS, "ml")),
    TechnologyFamily("database", get_db_transducer, _uniform(DB_CANONICAL_FORMS, "database")),
    TechnologyFamily("devops", get_devops_transducer, _uniform(DEVOPS_CANONICAL_FORMS, "cloud")),
    TechnologyFamily("vcs", get_vcs_transducer, _uniform(VCS_VARIANTS, "vcs")),
    TechnologyFamily("language", get_language_transducer, _uniform(LANGUAGE_VARIANTS, "language")),
    TechnologyFamily("data", get_data_transducer, _uniform(DATA_VARIANTS, "data")),
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
