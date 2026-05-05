"""Tests for AsyncioEventBus — dispatch and exception isolation."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

import pytest

from poe2_rpc.domain.events import DomainEvent, GameStarted


def _make_event() -> GameStarted:
    return GameStarted(log_path=Path("/tmp/Client.txt"))


@pytest.mark.asyncio
async def test_bus_dispatches_to_multiple_handlers() -> None:
    from poe2_rpc.application.bus import AsyncioEventBus

    received_a: list[DomainEvent] = []
    received_b: list[DomainEvent] = []

    async def handler_a(event: DomainEvent) -> None:
        received_a.append(event)

    async def handler_b(event: DomainEvent) -> None:
        received_b.append(event)

    bus = AsyncioEventBus()
    bus.subscribe(GameStarted, handler_a)
    bus.subscribe(GameStarted, handler_b)

    event = _make_event()
    await bus.publish(event)

    assert received_a == [event]
    assert received_b == [event]


@pytest.mark.asyncio
async def test_bus_isolates_handler_exceptions() -> None:
    from poe2_rpc.application.bus import AsyncioEventBus

    received_b: list[DomainEvent] = []

    async def handler_a(event: DomainEvent) -> None:
        raise RuntimeError("boom")

    async def handler_b(event: DomainEvent) -> None:
        received_b.append(event)

    bus = AsyncioEventBus()
    bus.subscribe(GameStarted, handler_a)
    bus.subscribe(GameStarted, handler_b)

    event = _make_event()
    await bus.publish(event)  # must NOT raise

    assert received_b == [event]
