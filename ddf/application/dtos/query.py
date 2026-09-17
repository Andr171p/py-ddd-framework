from typing import Annotated

from pydantic import Field

from ddf.application.dsl import Expression

QueryDTO = Annotated[Expression, Field(description="DTO для построения фильтров через DSL")]
