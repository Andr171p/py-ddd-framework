from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class ConcurrencyPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: PositiveInt = Field(description="Максимальное кол-во одновременно занятых слотов")
    lease_ttl: timedelta = Field(default=timedelta(seconds=60), description="TTL аренды слота")


__all__ = ["ConcurrencyPolicy"]
