from http import HTTPStatus

from locust import HttpUser, between, tag, task
from scenarios import NEAR_LIMIT, OVERSIZED, invalid_expression, typical_expression

SEARCH = "/tickets/search"


class TypicalUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task
    def search(self) -> None:
        with self.client.post(
            SEARCH,
            json=typical_expression(),
            name="typical search",
            catch_response=True,
        ) as response:
            if response.status_code == HTTPStatus.OK:
                response.success()
            else:
                response.failure(f"status {response.status_code}")


class InvalidUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @tag("security")
    @task
    def flood(self) -> None:
        with self.client.post(
            SEARCH,
            json=invalid_expression(),
            name="invalid search",
            catch_response=True,
        ) as response:
            if response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT:
                response.success()
            else:
                response.failure(f"status {response.status_code}")


class NearLimitUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @tag("security")
    @task
    def wide_tree(self) -> None:
        with self.client.post(
            SEARCH,
            json=NEAR_LIMIT,
            name="near-limit search",
            catch_response=True,
        ) as response:
            if response.status_code == HTTPStatus.OK:
                response.success()
            else:
                response.failure(f"status {response.status_code}")


class OversizedUser(HttpUser):
    wait_time = between(0.2, 0.5)
    weight = 1

    @tag("security")
    @task
    def oversized(self) -> None:
        with self.client.post(
            SEARCH,
            json=OVERSIZED,
            name="oversized search",
            catch_response=True,
        ) as response:
            if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
                response.failure(f"status {response.status_code}")
            else:
                response.success()
