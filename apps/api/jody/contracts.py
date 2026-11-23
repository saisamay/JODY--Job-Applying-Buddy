from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=512)


class SessionToken(BaseModel):
    token: str
    max_age: int


class ManualJob(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    description: str = Field(min_length=1, max_length=12000)
    source_url: HttpUrl | None = None

    @field_validator("source_url")
    @classmethod
    def public_link(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value and (value.username or value.password):
            raise ValueError("Remove embedded credentials")
        return value


class Job(BaseModel):
    id: UUID
    description: str
    source_url: str | None
    created_at: datetime


class Live(BaseModel):
    status: Literal["live"] = "live"


class Ready(BaseModel):
    status: Literal["ready", "unavailable"]
    postgres: bool
    redis: bool


class Error(BaseModel):
    detail: str
