# SQLAlchemy-интеграция

Интеграция рассчитана на SQLAlchemy 2.x в async-режиме. Она сохраняет разделение между доменной сущностью и ORM-моделью через Data Mapper.

## Базовая ORM-модель

Наследуйте таблицу от `Base`. Она добавляет UUIDv7 primary key и временные метки с часовым поясом.

```python
from sqlalchemy.orm import Mapped, mapped_column
from ddf.infra.database.sqlalchemy import Base


class UserRow(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True)
    status: Mapped[str] = mapped_column(default="active")
```

`Base` задаёт server default `uuid_generate_v7()`. Убедитесь, что PostgreSQL умеет выполнить эту функцию до миграции: на разных версиях сервера/расширениях её доступность отличается. В приложении default использует `uuid.uuid7()` из Python 3.14.

## Data Mapper

Mapper — тонкий явный перевод между двумя моделями. Он не должен содержать правила бизнеса, но это лучшее место для преобразования Value Object, enum и вложенных представлений.

```python
from ddf.infra.database.sqlalchemy import DataMapper


class UserMapper(DataMapper[User, UserRow]):
    def to_model(self, entity: User) -> UserRow:
        return UserRow(
            id=entity.id, email=str(entity.email), status=entity.status,
            created_at=entity.created_at, updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    def from_model(self, model: UserRow) -> User:
        return User(
            id=model.id, email=Email(model.email), status=model.status,
            created_at=model.created_at, updated_at=model.updated_at,
            deleted_at=model.deleted_at,
        )
```

Проверяйте mapper round-trip отдельным тестом: `from_model(to_model(entity))` должен сохранять значимые поля. События обычно не сохраняют и не восстанавливают — это очередь текущего экземпляра агрегата.

## Репозиторий

```python
from ddf.infra.database.sqlalchemy import SqlAlchemyRepository


class UserRepository(SqlAlchemyRepository[User, UserRow]):
    model = UserRow
    data_mapper = UserMapper()
    filter_whitelist = ("email", "status", "createdAt")
```

Передайте экземпляр `AsyncSession` в конструктор. Методы `create()` и `update()` не делают commit; транзакцией управляет Unit of Work/dispatcher. `create()` делает `flush`, чтобы вернуть сущность, отражающую сгенерированные БД значения.

Для полнотекстового поиска присвойте `search` функции `Callable[[str], ColumnElement[bool]]`, например `lambda query: UserRow.search_vector.op("@@")(func.plainto_tsquery(query))` для PostgreSQL. Конкретное выражение остаётся инфраструктурным, так как зависит от БД и индексов.

!!! warning "Не смешивайте модели"

    Не возвращайте `UserRow` из use case и не передавайте доменный `User` в SQLAlchemy relationship. ORM-модель отражает схему хранения и жизненный цикл сессии; доменная модель отражает правила. Data Mapper делает эту стоимость явной и локальной.
