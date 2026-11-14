# E2E: Realtime / WebSocket

Сценарии сгруппированы по доменам — новые тесты кладём в нужный пакет,
а не плоским списком `test_*.py` в корне.

```
tests/e2e/
  harness.py              # compose / readiness
  conftest.py             # session stack
  docker/                 # один файл на сервис
  delivery/               # cross-instance messaging
  limits/                 # distributed admission
  resilience/             # stop/kill/restart (marker: destructive)
  acceptance/             # business-like vertical
```

## Запуск

```sh
make e2e-up      # один раз: build + up
make test-e2e    # без --build (быстрый повтор)
make e2e-down
```

`E2E_BUILD=1` заставляет pytest пересобрать образы. По умолчанию build нет —
это основная экономия на старте.

Destructive-тесты (`resilience/`) помечены `@pytest.mark.destructive` и
восстанавливают инстансы только после себя, а не перед каждым тестом.

## DSL

Отдельный стенд, не входит в `make test-e2e`:

```text
tests/e2e/dsl/docker/compose.yaml
tests/e2e/dsl/docker/postgres.docker-compose.yml
tests/e2e/dsl/docker/api.docker-compose.yml
```

```sh
make e2e-dsl-up
make test-e2e-dsl
make e2e-dsl-down
```
