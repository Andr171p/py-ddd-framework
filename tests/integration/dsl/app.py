"""A small HTTP application exercising the real SQLAlchemy DSL compiler."""

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from ddf.application.dsl import Expression
from ddf.infra.database.sqlalchemy.base import Base
from ddf.infra.database.sqlalchemy.filters import compile_filter


class Ticket(Base):
    __tablename__ = "dsl_test_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    priority: Mapped[int]
    assignee_name: Mapped[str | None] = mapped_column(String, nullable=True)
    internal_note: Mapped[str] = mapped_column(String)


def make_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Ticket.__table__])
    with Session(engine) as session:
        session.add_all(
            [
                Ticket(
                    id=1,
                    title="Printer offline",
                    status="open",
                    priority=3,
                    assignee_name="Ada",
                    internal_note="a",
                ),
                Ticket(
                    id=2,
                    title="Paper jam",
                    status="pending",
                    priority=2,
                    assignee_name=None,
                    internal_note="b",
                ),
                Ticket(
                    id=3,
                    title="PRINTER fixed",
                    status="closed",
                    priority=1,
                    assignee_name="Bob",
                    internal_note="c",
                ),
                Ticket(
                    id=4,
                    title="New monitor",
                    status="open",
                    priority=2,
                    assignee_name=None,
                    internal_note="d",
                ),
            ]
        )
        session.commit()

    app = FastAPI()

    @app.post("/tickets/search")
    def search(expression: Expression) -> list[dict]:
        try:
            predicate = compile_filter(
                Ticket,
                expression,
                ("id", "title", "status", "priority", "assigneeName"),
                search=lambda query: Ticket.title.ilike(f"%{query}%"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        with Session(engine) as session:
            tickets = session.scalars(select(Ticket).where(predicate).order_by(Ticket.id))
            return [
                {
                    "id": ticket.id,
                    "title": ticket.title,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "assigneeName": ticket.assignee_name,
                }
                for ticket in tickets
            ]

    return app, engine
