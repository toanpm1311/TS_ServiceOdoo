from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field


class OrderBy(str, Enum):
    asc = 'asc'
    desc = 'desc'


class BaseModel(PydanticBaseModel):
    def model_post_init(self, *args, **kwargs):
        super().model_post_init(*args, **kwargs)
        for field in self:
            value = field[1]
            if isinstance(value, datetime):
                # convert naive datetime to aware datetime to show on mobile
                value = value.replace(tzinfo=timezone.utc)
                setattr(self, field[0], value)


class BaseORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MasterData(BaseModel):
    key: str
    value: Any


# money
class Currency(BaseModel):
    name:  Optional[str | bool] = Field(default=None)
    symbol:  Optional[str | bool] = Field(default=None)
