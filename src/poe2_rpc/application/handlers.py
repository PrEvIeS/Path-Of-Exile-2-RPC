"""Application-layer event handlers — pure application code, no infrastructure imports."""
from __future__ import annotations

import structlog
import structlog.contextvars

from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.events import AreaEntered, CharacterLevelChanged
from poe2_rpc.domain.models import InstanceInfo, LevelInfo
from poe2_rpc.domain.ports import PresencePublisher

_log = structlog.get_logger(__name__)


class MutableState:
    """Shared mutable state threaded through handlers so each can see the other's last value."""

    def __init__(self) -> None:
        self.level_info: LevelInfo | None = None
        self.instance_info: InstanceInfo | None = None


def _format_details(level_info: LevelInfo) -> str:
    details = f"{level_info.username} ({level_info.base_class}"
    if level_info.ascension_class is not None:
        details += f" | {level_info.ascension_class}"
    details += f" - Lvl {level_info.level})"
    return details


async def on_level_changed(
    event: CharacterLevelChanged,
    *,
    publisher: PresencePublisher,
    throttle: PresenceThrottle,
    current_state: MutableState,
) -> None:
    li = event.level_info
    current_state.level_info = li

    structlog.contextvars.bind_contextvars(
        username=li.username,
        character_class=li.base_class,
        area=current_state.instance_info.area_display_name if current_state.instance_info else "",
    )

    if not throttle.should_update():
        return

    area = current_state.instance_info.area_display_name if current_state.instance_info else ""
    _log.info(
        "level_changed",
        username=li.username,
        character_class=li.base_class,
        area=area,
        level=li.level,
        details=_format_details(li),
    )
    await publisher.publish(li, current_state.instance_info)


async def on_area_entered(
    event: AreaEntered,
    *,
    publisher: PresencePublisher,
    throttle: PresenceThrottle,
    current_state: MutableState,
) -> None:
    ii = event.instance_info
    current_state.instance_info = ii

    structlog.contextvars.bind_contextvars(
        username=current_state.level_info.username if current_state.level_info else "",
        character_class=current_state.level_info.base_class if current_state.level_info else "",
        area=ii.area_display_name,
    )

    if not throttle.should_update():
        return

    username = current_state.level_info.username if current_state.level_info else ""
    character_class = current_state.level_info.base_class if current_state.level_info else ""
    _log.info(
        "area_entered",
        username=username,
        character_class=character_class,
        area=ii.area_display_name,
        area_level=ii.level,
    )
    await publisher.publish(current_state.level_info, ii)
