import pytest

from ddf.application.dtos.sorting import parse_sort_query_param


@pytest.mark.parametrize(
    ("raw", "field", "direction"),
    [
        ("createdAt", "createdAt", "asc"),
        ("  createdAt  ", "createdAt", "asc"),
        ("createdAt:desc", "createdAt", "desc"),
        ("createdAt:ASC", "createdAt", "asc"),
        ("-createdAt", "createdAt", "desc"),
        ("  -priority  ", "priority", "desc"),
    ],
)
def test_sort_query_parses_documented_forms(raw, field, direction):
    sort = parse_sort_query_param(raw)

    assert sort.field == field
    assert sort.direction == direction


@pytest.mark.parametrize("raw", ["", "   ", "-", "createdAt:", "createdAt:sideways", ":desc"])
def test_sort_query_rejects_unknown_forms(raw):
    with pytest.raises(ValueError):
        parse_sort_query_param(raw)
