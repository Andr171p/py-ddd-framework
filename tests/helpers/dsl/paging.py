from collections.abc import Callable, Sequence

from .dataset import TicketSeed, load_tickets

RESULT_PAGE_SIZE = 50
SAMPLE_PAGE_SIZE = 2


def ordered(predicate: Callable[[TicketSeed], bool]) -> tuple[TicketSeed, ...]:
    rows = [ticket for ticket in load_tickets() if predicate(ticket)]
    return tuple(sorted(rows, key=lambda ticket: (ticket.priority, ticket.id)))


def page_count(total: int, size: int) -> int:
    if total == 0:
        return 0
    return (total + size - 1) // size


def code_pages(rows: Sequence[TicketSeed], size: int) -> tuple[tuple[str, ...], ...]:
    codes = tuple(ticket.code for ticket in rows)
    if not codes:
        return ((),)
    return tuple(codes[index : index + size] for index in range(0, len(codes), size))
