from dataclasses import dataclass

from .models import ContextItem


@dataclass(frozen=True, slots=True)
class ContextSlice:
    start: int
    stop: int

    def __len__(self) -> int:
        return self.stop - self.start


def select_oldest_reducible_slice[T](  # noqa: C901
    items: tuple[ContextItem[T], ...],
    *,
    keep_last: int,
    min_items: int,
) -> ContextSlice | None:
    """Выбирает старейший непрерывный участок, который можно заменить.

    Не включает:
    - pinned items;
    - последние ``keep_last`` элементов;
    - частично попавшие atomic groups.
    """

    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")

    cutoff = max(0, len(items) - keep_last)

    if cutoff == 0:
        return None

    start: int | None = None
    stop: int | None = None

    for index in range(cutoff):
        item = items[index]

        if item.pinned:
            if start is not None:
                break

            continue

        if start is None:
            start = index

        stop = index + 1

    if start is None or stop is None:
        return None

    last_group_id = items[stop - 1].group_id

    if last_group_id is not None:
        group_indexes = [
            index
            for index, item in enumerate(items)
            if item.group_id == last_group_id
        ]

        if any(index >= stop for index in group_indexes):
            first_group_index = min(group_indexes)

            if first_group_index <= start:
                return None

            stop = first_group_index

    if stop - start < min_items:
        return None

    return ContextSlice(start=start, stop=stop)
