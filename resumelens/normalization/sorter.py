"""Stage 2 — Canonical ordering of normalized skills.

Turns the de-duplicated ``SkillRecord`` list produced by the normalizer into the sequence
of canonical names that the profile automata of Stage 3 read. As the assignment says,
the order is fixed by the selected profile so that the result does not depend on the
order in which the candidate wrote the skills.

Each profile is a sequence of *slots*. A slot is one category of
:mod:`resumelens.normalization.normalizer` and corresponds to one bullet of the profile's
qualification list (e.g. "Pandas or NumPy" -> ``data_library``). The output is built as:

1. **Profile part** — the skills whose category is a slot of the profile, slot by slot in
   the profile order; inside a slot, in lexicographic order of the canonical name.
2. **Remaining part** — the skills of any other category (noise for this profile), in
   lexicographic order of ``(category, canonical name)``.

Both rules are total orders on canonical names, so the output is a permutation of the
input that depends only on the *set* of skills. A slot may hold zero, one or several
skills (Mary Jane Watson has both ``NUMPY`` and ``PANDAS`` in ``data_library``).

Example (Full Stack): ``Git, NodeJS, JS, Postgres, React.js`` ->
``JAVASCRIPT, REACT, NODE_JS, POSTGRESQL, GIT``.
"""

from typing import List, Mapping, Sequence, Tuple

from resumelens.core.models import SkillRecord
from resumelens.normalization.normalizer import (
    CATEGORY_API,
    CATEGORY_BACKEND,
    CATEGORY_CI_CD,
    CATEGORY_CLOUD,
    CATEGORY_CONTAINER,
    CATEGORY_DATA_LIBRARY,
    CATEGORY_DATA_PROCESSING,
    CATEGORY_DATABASE,
    CATEGORY_FRONTEND,
    CATEGORY_IAC,
    CATEGORY_LANGUAGE,
    CATEGORY_ML_FRAMEWORK,
    CATEGORY_ML_PRACTICE,
    CATEGORY_ORCHESTRATION,
    CATEGORY_VCS,
    CATEGORY_WEB_LANGUAGE,
    CATEGORY_WORKFLOW,
)

FULL_STACK_DEVELOPER: str = "FULL_STACK_DEVELOPER"
MACHINE_LEARNING_ENGINEER: str = "MACHINE_LEARNING_ENGINEER"
DEVOPS_ENGINEER: str = "DEVOPS_ENGINEER"
DATA_ENGINEER: str = "DATA_ENGINEER"

#: Supported profiles, in the order used by the roadmap.
PROFILES: Tuple[str, ...] = (
    FULL_STACK_DEVELOPER,
    MACHINE_LEARNING_ENGINEER,
    DEVOPS_ENGINEER,
    DATA_ENGINEER,
)

#: Slots of each profile, in order. Full Stack and Machine Learning follow the
#: qualification lists and examples of the assignment (Frontend -> Backend -> Database
#: -> Version control, with "Frontend" split into its language and its framework);
#: DevOps and Data Engineer are the two profiles defined by the team.
PROFILE_SLOTS: Mapping[str, Tuple[str, ...]] = {
    FULL_STACK_DEVELOPER: (
        CATEGORY_WEB_LANGUAGE,  # JavaScript or TypeScript
        CATEGORY_FRONTEND,  # React, Angular, or Vue
        CATEGORY_BACKEND,  # Node.js, Django, Spring Boot
        CATEGORY_DATABASE,  # SQL or NoSQL databases
        CATEGORY_API,  # REST APIs
        CATEGORY_VCS,  # Git
    ),
    MACHINE_LEARNING_ENGINEER: (
        CATEGORY_LANGUAGE,  # Python
        CATEGORY_DATA_LIBRARY,  # Pandas or NumPy
        CATEGORY_ML_FRAMEWORK,  # Scikit-learn, TensorFlow, or PyTorch
        CATEGORY_ML_PRACTICE,  # Machine-learning model development
        CATEGORY_DATABASE,  # SQL
        CATEGORY_VCS,  # Git
    ),
    DEVOPS_ENGINEER: (
        CATEGORY_LANGUAGE,
        CATEGORY_CONTAINER,
        CATEGORY_ORCHESTRATION,
        CATEGORY_IAC,
        CATEGORY_CI_CD,
        CATEGORY_CLOUD,
        CATEGORY_VCS,
    ),
    DATA_ENGINEER: (
        CATEGORY_LANGUAGE,
        CATEGORY_DATA_PROCESSING,
        CATEGORY_WORKFLOW,
        CATEGORY_DATABASE,
        CATEGORY_CLOUD,
        CATEGORY_VCS,
    ),
}


class UnknownProfileError(ValueError):
    """Raised when a profile name is not one of :data:`PROFILES`."""


def resolve_profile(profile: str) -> str:
    """Return the identifier of ``profile``, accepting ``"Full Stack Developer"`` forms.

    Raises:
        UnknownProfileError: If the name matches no supported profile.
    """
    key = "_".join(profile.replace("-", " ").upper().split())
    if key not in PROFILE_SLOTS:
        raise UnknownProfileError(
            f"Unknown profile {profile!r}; expected one of {', '.join(PROFILES)}."
        )
    return key


def profile_slots(profile: str) -> Tuple[str, ...]:
    """Return the slots (categories) of ``profile``, in order.

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    return PROFILE_SLOTS[resolve_profile(profile)]


def sort_records_by_profile(records: Sequence[SkillRecord], profile: str) -> List[SkillRecord]:
    """Return the records in the canonical order of ``profile`` (see the module docstring).

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    slots = profile_slots(profile)
    position = {category: index for index, category in enumerate(slots)}
    in_profile = [record for record in records if record.category in position]
    remaining = [record for record in records if record.category not in position]
    in_profile.sort(key=lambda record: (position[record.category], record.canonical_name))
    remaining.sort(key=lambda record: (record.category, record.canonical_name))
    return in_profile + remaining


def sort_by_profile(records: Sequence[SkillRecord], profile: str) -> List[str]:
    """Return the canonical names of ``records`` in the canonical order of ``profile``.

    Example:
        ``["Git", "NodeJS", "JS", "Postgres", "React.js"]`` normalized and sorted for
        ``FULL_STACK_DEVELOPER`` gives
        ``["JAVASCRIPT", "REACT", "NODE_JS", "POSTGRESQL", "GIT"]``.

    Raises:
        UnknownProfileError: If ``profile`` is not supported.
    """
    return [record.canonical_name for record in sort_records_by_profile(records, profile)]
