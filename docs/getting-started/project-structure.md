# Структура проекта

DDF не требует единственного верного дерева каталогов. Граница важнее расположения: бизнес-правила не должны знать, что запрос пришёл из FastAPI и что данные лежат в PostgreSQL.

Практичная отправная точка для сервиса заказов:

```text
src/orders/
├── domain/
│   ├── models.py          # Order, OrderLine, события, инварианты
│   └── value_objects.py   # Money, OrderNumber
├── application/
│   ├── commands.py        # use case и DTO команды
│   ├── repositories.py    # узкие Protocol, если нужны предметные методы
│   └── services.py
├── infrastructure/
│   ├── sqlalchemy/        # ORM-модели, Data Mapper, реализации repo/UoW
│   ├── cache.py
│   └── messaging.py
└── presentation/
    └── http.py            # FastAPI routers, dependency injection, схемы HTTP
```

## Как распределять код

| Слой | Отвечает за | Не должен знать о |
| --- | --- | --- |
| `domain` | правила, состояние, инварианты, события | HTTP, ORM, Redis, брокере |
| `application` | сценарии, транзакционная граница, оркестрация | SQL-выражениях и маршрутах |
| `infrastructure` | SQLAlchemy, Redis, RabbitMQ, внешние API | бизнес-решениях |
| `presentation` | разбор запроса, авторизация, перевод ошибок | внутренностях БД |

Небольшие DTO, нужные только HTTP API, держите у `presentation`. DTO команды, описывающие намерение пользователя (`CreateOrder`), — у `application`. Сам `Order` не обязан быть Pydantic-моделью: это снижает связность с transport-слоем.

!!! tip "Один bounded context — один пакет"

    Когда контексты независимы, лучше `billing/`, `catalog/`, `identity/` с собственными слоями, чем общие гигантские папки `domain/` и `repositories/` на весь монолит. Так проще увидеть границу языка и зависимостей.

## Где располагается DDF

`ddf` — библиотека общих абстракций. Код конкретного бизнеса не следует добавлять в неё: `OrderRepository` или правила расчёта скидки остаются в приложении. От DDF достаточно наследовать общие модели и использовать его контракты.
