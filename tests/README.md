# Тесты DDF

## Быстрые тесты без внешних сервисов

```sh
make test-unit
```

## Интеграционные тесты

```sh
make test-integration
make test-integration-realtime   # Docker + testcontainers
```

## E2E

Сценарии по пакетам: `delivery/`, `limits/`, `resilience/`, `acceptance/`.

```sh
make e2e-up    # build образов один раз
make test-e2e  # без --build
make e2e-down
```

## Load (Locust)

```sh
make test-load
make test-load-headless
```

Подробности: `tests/apps/realtime_tickets/README.md`,
`tests/integration/realtime/README.md`, `tests/e2e/README.md`,
`tests/load/README.md`, план — `tests/TEST_PLAN.md`.
