# Репозитории и Unit of Work

Репозиторий даёт прикладному слою коллекционное представление агрегатов. Он прячет SQL, сессию и формат хранения, но не должен становиться универсальным запросником со строками SQL из контроллера.

## Контракт репозитория

`ddf.application.repositories.Repository[EntityT]` задаёт асинхронные операции:

```python
async def create(entity) -> Entity: ...
async def read(uid) -> Entity | None: ...
async def find(pagination, query=None, sort=None) -> Page[Entity]: ...
async def update(entity) -> None: ...
async def delete(uid) -> None: ...
async def exists(uid) -> bool: ...
async def get_by_ids(ids) -> tuple[Entity, ...]: ...
```

Используйте `read()` для загрузки по идентификатору, а `find()` — для списка с явной пагинацией. Метод `get_or_raise_not_found()` превращает `None` из `read()` в `NotFoundError` на уровне use case.

Если контексту нужен предметный запрос (`find_overdue_invoices`), добавьте узкий `Protocol` рядом с use case. Не расширяйте базовый контракт методами, полезными лишь одному агрегату.

## Unit of Work

`UnitOfWork` — структурный контракт транзакции: контекстный менеджер, `flush`, `commit` и `rollback`. DDF намеренно не создаёт сессию сам: приложение выбирает жизненный цикл и реализацию.

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@asynccontextmanager
async def request_uow(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

Передавать в use case настоящую SQLAlchemy-сессию допустимо в composition root, но сам use case лучше зависеть от `UnitOfWork` или `EventDispatcher` — так он не связывается с ORM.

## Flush и commit — не одно и то же

`flush()` отправляет накопленные изменения в БД внутри текущей транзакции. Это нужно, например, чтобы получить сгенерированное базой поле. `commit()` делает изменения видимыми другим транзакциям и завершает её.

Базовый `SqlAlchemyRepository.create()` вызывает `flush`, но не `commit`. Это позволяет сохранить несколько агрегатов атомарно. `EventDispatcher` берёт на себя commit в типовом сценарии изменения с событиями.

!!! warning "Один владелец commit"

    Решите в приложении, кто завершает транзакцию: middleware/UoW или `EventDispatcher`. Двойной неявный commit усложняет откат и порядок побочных эффектов.

## Декорирование

`RepositoryDecorator` проксирует базовый контракт, поэтому добавляет инфраструктурное поведение без переписывания SQL-репозитория. `CachedRepository` — пример такого декоратора. Порядок декораторов значим: аудит снаружи кэша увидит cache hit, аудит внутри — нет.
