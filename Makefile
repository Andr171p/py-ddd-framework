UV_TEST = uv run --group test
UV_REALTIME = $(UV_TEST) --extra redis --extra rabbit
COMPOSE_E2E = tests/e2e/docker/compose.yaml
export TESTCONTAINERS_RYUK_DISABLED ?= true
export NO_PROXY ?= 127.0.0.1,localhost

.PHONY: lint format-check typecheck audit package-smoke test-unit test-integration test-integration-realtime test-e2e test-e2e-smoke test-e2e-rabbit test-e2e-dsl e2e-dsl-up e2e-dsl-down test-load test-load-headless test-load-dsl e2e-up e2e-down load-up load-down

DSL_COMPOSE = tests/e2e/dsl/docker/compose.yaml
UV_DSL = $(UV_TEST) --extra sqlalchemy --extra mongo

lint:
	uv run --group dev ruff check .

format-check:
	uv run --group dev ruff format --check .

typecheck:
	uv run --group dev mypy ddf

audit:
	uv export --frozen --all-extras --all-groups --no-emit-project -o requirements-audit.txt
	uvx pip-audit --disable-pip --requirement requirements-audit.txt --progress-spinner off
	uv run --no-project python -c "from pathlib import Path; Path('requirements-audit.txt').unlink(missing_ok=True)"

package-smoke:
	uv build
	uvx twine check dist/*
	uv run --no-project --python 3.14 python scripts/package_smoke.py

test-unit:
	$(UV_TEST) pytest tests/unit -q

test-integration:
	$(UV_DSL) pytest tests/integration -v --ignore=tests/integration/realtime

test-integration-realtime:
	$(UV_REALTIME) pytest tests/integration/realtime -v

e2e-up:
	docker compose -f $(COMPOSE_E2E) up -d --build --wait

e2e-down:
	docker compose -f $(COMPOSE_E2E) down -v

test-e2e:
	$(UV_REALTIME) pytest tests/e2e -v --ignore=tests/e2e/dsl

test-e2e-smoke:
	$(UV_REALTIME) pytest tests/e2e -v --ignore=tests/e2e/dsl -m "not destructive"

test-e2e-rabbit:
	REALTIME_BACKEND=rabbit $(UV_REALTIME) pytest tests/e2e -v --ignore=tests/e2e/dsl

load-up:
	REALTIME_BACKEND=redis docker compose -f tests/load/compose.yaml up -d --build --wait

load-down:
	docker compose -f tests/load/compose.yaml down -v

test-load: load-up
	@echo Locust UI: http://127.0.0.1:8089
	@powershell -NoProfile -Command "Start-Process powershell -ArgumentList '-NoProfile','-File','scripts/open-locust-ui.ps1' -WindowStyle Hidden"
	$(UV_TEST) locust -f tests/load/locustfile.py --host http://127.0.0.1:18001 --web-host 0.0.0.0 --web-port 8089

test-load-headless: load-up
	$(UV_TEST) locust -f tests/load/locustfile.py --host http://127.0.0.1:18001 \
		--headless -u 100 -r 10 -t 5m --html reports/load-baseline.html
	$(MAKE) load-down

e2e-dsl-up:
	docker compose -f $(DSL_COMPOSE) up -d --build --wait

e2e-dsl-down:
	docker compose -f $(DSL_COMPOSE) down -v

test-e2e-dsl:
	$(UV_TEST) --extra sqlalchemy pytest tests/e2e/dsl -v

test-load-dsl: e2e-dsl-up
	$(UV_TEST) locust -f tests/load/dsl/locustfile.py --host http://127.0.0.1:18121 \
		--headless -u 15 -r 5 -t 20s --only-summary
	$(MAKE) e2e-dsl-down
