# Сущности и Value Object

Сущность отвечает на вопрос «что это за конкретный объект?», а Value Object — «каким значением он обладает?». Это различие определяет равенство, изменяемость и место бизнес-проверок.

## Entity и AggregateRoot

`Entity` — базовый `dataclass` с полями:

- `id` — UUIDv7, создаётся автоматически;
- `created_at` и `updated_at` — время в UTC;
- `deleted_at` и свойство `is_deleted` для soft delete;
- скрытая очередь доменных событий.

Равенство сущностей определяется только `id`, поэтому две загрузки одного заказа будут равны, даже если их снимки состояния отличаются.

```python
from dataclasses import dataclass
from decimal import Decimal

from ddf.domain.exceptions import InvariantViolationError
from ddf.domain.models import AggregateRoot


@dataclass
class Invoice(AggregateRoot):
    amount: Decimal = Decimal("0")
    is_paid: bool = False

    def pay(self, received: Decimal) -> None:
        if self.is_paid:
            raise InvariantViolationError("Счёт уже оплачен")
        if received != self.amount:
            raise InvariantViolationError("Неверная сумма оплаты")
        self.is_paid = True
```

`AggregateRoot` пока является семантическим расширением `Entity`: он обозначает публичную точку входа в агрегат. Репозиторий обычно выдаёт и сохраняет именно корни агрегатов, а не вложенные объекты.

!!! tip "Меняйте через поведение"

    Поля dataclass остаются открытыми — это нормальный Python. Но если изменение связано с правилом, создайте метод (`pay`, `cancel`, `add_line`), чтобы правило не разъехалось по контроллерам и воркерам.

## Value Object

Value Object не имеет собственной идентичности: два одинаковых значения взаимозаменяемы. В DDF их удобно писать как неизменяемые (`frozen=True`) dataclass.

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Сумма не может быть отрицательной")
        if len(self.currency) != 3:
            raise ValueError("Нужен ISO-код валюты")
```

В пакете есть готовый `Email`: он валидирует и нормализует адрес при создании. Благодаря неизменяемости `Email` безопасно использовать как значение и ключ.

```python
from ddf.domain.vo.email import Email

email = Email("dev@example.com")
assert email.domain == "example.com"
```

## Ошибки предметной области

Для нарушения правил используйте `DomainError` или его специализации `InvariantViolationError` и `InvalidStateError`. У них есть машиночитаемый `error_code`, HTTP-статус и опциональные `details`; presentation-слой может централизованно преобразовать их в ответ API.

Не используйте доменные исключения для ошибки инфраструктуры вроде недоступного Redis. Это разные причины и для них нужны разные политика повтора и наблюдаемость.

## Soft delete

`deleted_at` — лишь общее поле, а не готовая политика удаления. Если сущность «удалена», репозиторий и все выборки должны последовательно исключать её сами. До появления такого правила `SqlAlchemyRepository.delete()` выполняет физический `DELETE`.

!!! warning "Не смешивайте две стратегии"

    Для одного агрегата выберите soft delete или физическое удаление. Одновременное использование приведёт к неожиданным дублям, утечкам данных в списках и неверным уникальным ограничениям.
