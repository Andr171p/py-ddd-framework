UV_TEST = uv run --group test
UV_REALTIME = $(UV_TEST) --extra redis --extra rabbit
COMPOSE_E2E = tests/e2e/docker/compose.yaml
export TESTCONTAINERS_RYUK_DISABLED ?= true
export NO_PROXY ?= 127.0.0.1,localhost

.PHONY: test-unit test-integration test-integration-realtime test-e2e test-e2e-rabbit test-load test-load-headless e2e-up e2e-down load-up load-down

test-unit:
	$(UV_TEST) pytest tests/unit -q

test-integration:
	$(UV_TEST) --extra sqlalchemy pytest tests/integration -v --ignore=tests/integration/realtime

test-integration-realtime:
	$(UV_REALTIME) pytest tests/integration/realtime -v

e2e-up:
	docker compose -f $(COMPOSE_E2E) up -d --build --wait

e2e-down:
	docker compose -f $(COMPOSE_E2E) down -v

test-e2e:
	$(UV_REALTIME) pytest tests/e2e -v

test-e2e-rabbit:
	REALTIME_BACKEND=rabbit $(UV_REALTIME) pytest tests/e2e -v

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
