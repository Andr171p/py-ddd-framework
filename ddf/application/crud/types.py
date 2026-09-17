from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from ddf.domain.models import Entity

# =================================================================================================
# Handlers - выполняют доменную логику (DTO -> Domain model).
# =================================================================================================

type CreateHandler[EntityT: Entity, CreateT: BaseModel, CreateOptionsT] = Callable[
    [CreateT, CreateOptionsT | None], Awaitable[EntityT],
]

type UpdateHandler[EntityT: Entity, UpdateT: BaseModel, UpdateOptionsT] = Callable[
    [EntityT, UpdateT, UpdateOptionsT | None], Awaitable[EntityT],
]

type DeleteHandler[EntityT: Entity, DeleteOptionsT] = Callable[
    [EntityT, DeleteOptionsT | None], Awaitable[EntityT],
]

# =================================================================================================
# Wrappers - дополнительная PRE/POST логика для CRUD методов.
# =================================================================================================

type CreateWrapper[EntityT: Entity, CreateT: BaseModel, CreateOptionsT] = Callable[
    [
        Callable[
            [CreateT, CreateOptionsT | None],
            Awaitable[EntityT],
        ],
        CreateT,
        CreateOptionsT | None,
    ],
    Awaitable[EntityT],
]

type ReadWrapper[EntityT: Entity, ReadOptionsT] = Callable[
    [
        Callable[
            [EntityT, ReadOptionsT | None],
            Awaitable[EntityT],
        ],
        EntityT,
        ReadOptionsT | None,
    ],
    Awaitable[EntityT],
]


type UpdateWrapper[EntityT: Entity, UpdateT: BaseModel, UpdateOptionsT] = Callable[
    [
        Callable[
            [EntityT, UpdateT, UpdateOptionsT | None],
            Awaitable[EntityT],
        ],
        EntityT,
        UpdateT,
        UpdateOptionsT | None,
    ],
    Awaitable[EntityT],
]

type DeleteWrapper[EntityT: Entity, DeleteOptionsT] = Callable[
    [
        Callable[
            [EntityT, DeleteOptionsT | None],
            Awaitable[EntityT],
        ],
        EntityT,
        DeleteOptionsT | None,
    ],
    Awaitable[EntityT],
]

__all__ = [
    "CreateHandler",
    "CreateWrapper",
    "DeleteHandler",
    "DeleteWrapper",
    "ReadWrapper",
    "UpdateHandler",
    "UpdateWrapper",
]
