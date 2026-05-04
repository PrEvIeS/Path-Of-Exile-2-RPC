"""Domain port Protocols — all runtime_checkable, stdlib + domain imports only."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

from poe2_rpc.domain.events import DomainEvent
from poe2_rpc.domain.locations import Location
from poe2_rpc.domain.models import InstanceInfo, LevelInfo


@runtime_checkable
class GameDetector(Protocol):
    def is_running(self) -> bool: ...
    def log_path(self) -> Path: ...


@runtime_checkable
class LogStream(Protocol):
    def lines(self) -> Iterator[str]: ...


@runtime_checkable
class LogParser(Protocol):
    def parse_level(self, line: str) -> LevelInfo | None: ...
    def parse_instance(self, line: str) -> InstanceInfo | None: ...


@runtime_checkable
class PresencePublisher(Protocol):
    def publish(self, level_info: LevelInfo | None, instance_info: InstanceInfo | None) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class EventBus(Protocol):
    def emit(self, event: DomainEvent) -> None: ...
    def subscribe(self, handler: object) -> None: ...


@runtime_checkable
class LocationCatalogPort(Protocol):
    def resolve(self, area_code: str) -> Location: ...
