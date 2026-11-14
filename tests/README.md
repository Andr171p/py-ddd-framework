# Тесты DDF

## Unit и integration

```sh
make test-unit
make test-integration
```

`make test-unit` не поднимает сервисы. `make test-integration` включает DSL на PostgreSQL и MongoDB через testcontainers и поэтому требует Docker. Realtime по-прежнему отдельно: `make test-integration-realtime`.

## DSL

Общая оснастка: `tests/helpers/dsl/`. Тесты: `tests/unit/dsl/`, `tests/integration/dsl/`, `tests/e2e/dsl/`, `tests/load/dsl/`.

```sh
make test-e2e-dsl
make e2e-dsl-up
make e2e-dsl-down
make test-load-dsl
```

Повторный e2e без пересборки образа: `DSL_E2E_BUILD=0`. Уже поднятый стенд: `DSL_E2E_MANAGE=0`.

Пустая группа в PostgreSQL отклоняется, в MongoDB совпадает со всеми документами. `Search` есть только при переданном callback. `$isNull` в MongoDB — BSON null, не отсутствующее поле. `$ne` в SQL не включает NULL, в MongoDB включает null и отсутствующее поле. Репозитории сами не добавляют организацию и soft-delete.

## E2E realtime

Сценарии по пакетам: `delivery/`, `limits/`, `resilience/`, `acceptance/`. DSL в этот прогон не входит.

```sh
make e2e-up    # build образов один раз
make test-e2e  # без --build
make e2e-down
```

## Load (Locust)

```sh
make test-load
make test-load-headless
make test-load-dsl
```

Подробности: `tests/apps/realtime_tickets/README.md`,
`tests/integration/realtime/README.md`, `tests/e2e/README.md`,
`tests/load/README.md`, план — `tests/TEST_PLAN.md`.
