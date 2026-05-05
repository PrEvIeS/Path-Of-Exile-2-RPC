"""Frozen pydantic v2 domain event hierarchy."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from poe2_rpc.domain.models import InstanceInfo, LevelInfo


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)


class GameStarted(DomainEvent):
    log_path: Path


class GameStopped(DomainEvent):
    pass


class CharacterLevelChanged(DomainEvent):
    level_info: LevelInfo


class AreaEntered(DomainEvent):
    instance_info: InstanceInfo
