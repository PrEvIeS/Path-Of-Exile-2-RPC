"""Frozen pydantic v2 value objects for the domain layer."""
from pydantic import BaseModel, ConfigDict


class LevelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    base_class: str
    ascension_class: str | None  # None when player not yet ascended
    level: int


class InstanceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    area_code: str
    area_display_name: str
    level: int
    seed: int
