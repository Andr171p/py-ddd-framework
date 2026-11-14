from typing import Annotated, Literal

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ddf.application.dsl import Expression
from ddf.application.dtos import Page, PaginationQuery, Sort
from ddf.infra.database.sqlalchemy.configs import PostgresConfig
from tests.helpers.dsl.dataset import Ticket
from tests.helpers.dsl.sql_catalog import TicketRepository, create_schema, replace_rows

SORTABLE = {
    "code": "code",
    "title": "title",
    "status": "status",
    "priority": "priority",
    "assigneeName": "assignee_name",
    "urgent": "urgent",
    "dueAt": "due_at",
}


class TicketView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    title: str
    status: str
    priority: int
    assignee_name: str | None = Field(alias="assigneeName")
    urgent: bool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_async_engine(PostgresConfig().uri)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    await create_schema(engine)
    async with sessions() as session:
        await replace_rows(session)
    app.state.sessions = sessions
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session


@app.post("/tickets/search")
async def search(
    expression: Expression,
    session: Annotated[AsyncSession, Depends(get_session)],
    pagination: PaginationQuery,
    field: Annotated[str | None, Query()] = None,
    direction: Annotated[Literal["asc", "desc"], Query()] = "asc",
) -> Page[TicketView]:
    sort = _sort(field, direction)
    try:
        page = await TicketRepository(session).find(pagination, expression, sort)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return page.map(_view)


def _sort(field: str | None, direction: Literal["asc", "desc"]) -> Sort | None:
    if field is None:
        return None
    column = SORTABLE.get(field)
    if column is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown sort field.")
    return Sort(field=column, direction=direction)


def _view(ticket: Ticket) -> TicketView:
    return TicketView.model_validate(
        {
            "code": ticket.code,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "assigneeName": ticket.assignee_name,
            "urgent": ticket.urgent,
        }
    )
