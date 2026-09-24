from .exceptions import InvalidContextReductionError
from .models import ContextItem


def validate_reduction[T](
    *,
    before: tuple[ContextItem[T], ...],
    after: tuple[ContextItem[T], ...],
    reducer: str,
) -> None:
    _validate_pinned(before=before, after=after, reducer=reducer)
    _validate_groups(before=before, after=after, reducer=reducer)


def _validate_pinned[T](
    *,
    before: tuple[ContextItem[T], ...],
    after: tuple[ContextItem[T], ...],
    reducer: str,
) -> None:
    for item in before:
        if not item.pinned:
            continue

        if any(candidate is item for candidate in after):
            continue

        raise InvalidContextReductionError(f"Reducer {reducer!r} removed a pinned context item")


def _validate_groups[T](
    *,
    before: tuple[ContextItem[T], ...],
    after: tuple[ContextItem[T], ...],
    reducer: str,
) -> None:
    groups: dict[str, list[ContextItem[T]]] = {}

    for item in before:
        if item.group_id is not None:
            groups.setdefault(item.group_id, []).append(item)

    for group_id, group_items in groups.items():
        retained = sum(any(candidate is item for candidate in after) for item in group_items)

        if retained not in {0, len(group_items)}:
            msg = f"Reducer {reducer!r} partially removed atomic context group {group_id!r}"
            raise InvalidContextReductionError(msg)
