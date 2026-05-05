"""Typer CLI + composition root.

The only module allowed to import infrastructure adapters AND application code
together. Everything below this layer sees Protocols only (Principle 4).

Commands:
    run             Continuous monitor loop (default).
    once            Process one log-stream pass and exit.
    validate-config Load settings + bundled assets without running the loop.
                    Pass --no-discord to skip Discord IPC contact.
    --version       Print version and exit.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterator

import structlog
import typer

from poe2_rpc.__version__ import __version__
from poe2_rpc.application.bus import AsyncioEventBus
from poe2_rpc.application.handlers import MutableState
from poe2_rpc.application.orchestrator import Orchestrator
from poe2_rpc.application.throttle import PresenceThrottle
from poe2_rpc.domain.ports import LogStream
from poe2_rpc.infrastructure.catalog import load_bundled_catalog
from poe2_rpc.infrastructure.detection import PsutilGameDetector
from poe2_rpc.infrastructure.log_stream import WatchdogLogStream
from poe2_rpc.infrastructure.logging import configure_logging
from poe2_rpc.infrastructure.parsing import RegexLogParser
from poe2_rpc.infrastructure.presence import PypresencePublisher
from poe2_rpc.infrastructure.settings import AppSettings

_log = structlog.get_logger(__name__)

app = typer.Typer(
    name="poe2-rpc",
    help="Discord Rich Presence integration for Path of Exile 2.",
    no_args_is_help=False,
)


class _SyncLineIterator:
    """Adapter: drains WatchdogLogStream's async queue into a sync Iterator[str].

    Lives in the composition root because LogStream is a sync Protocol but the
    Watchdog adapter speaks asyncio. Owns the start/stop of the observer.
    """

    def __init__(self, stream: WatchdogLogStream, loop: asyncio.AbstractEventLoop) -> None:
        self._stream = stream
        self._loop = loop
        stream.start()

    def lines(self) -> Iterator[str]:
        try:
            while True:
                line = self._loop.run_until_complete(self._stream._queue.get())
                yield line
        finally:
            self._stream.stop()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"poe2-rpc {__version__}")
        raise typer.Exit()


def build_orchestrator(settings: AppSettings) -> Orchestrator:
    """Assemble all adapters and return a runnable Orchestrator.

    Extracted as a public function so CLI tests can patch it in isolation.
    """
    detector = PsutilGameDetector(settings)
    parser = RegexLogParser()
    catalog = load_bundled_catalog()
    publisher = PypresencePublisher(settings)
    bus = AsyncioEventBus()

    def factory(path: Path, loop: asyncio.AbstractEventLoop) -> LogStream:
        watchdog_stream = WatchdogLogStream(path, settings, loop)
        return _SyncLineIterator(watchdog_stream, loop)

    return Orchestrator(
        detector=detector,
        parser=parser,
        publisher=publisher,
        catalog=catalog,
        bus=bus,
        log_stream_factory=factory,
        throttle=PresenceThrottle(interval=settings.throttle_window_seconds),
        current_state=MutableState(),
        settings=settings,
    )


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
) -> None:
    """Discord Rich Presence integration for Path of Exile 2."""


@app.command()
def run() -> None:
    """Run the continuous monitor loop until cancelled."""
    settings = AppSettings()
    configure_logging(settings)
    orch = build_orchestrator(settings)
    orch.run()


@app.command()
def once() -> None:
    """Run a single log-stream pass and exit."""
    settings = AppSettings()
    configure_logging(settings)
    orch = build_orchestrator(settings)
    orch.run_once()


@app.command(name="validate-config")
def validate_config(
    no_discord: bool = typer.Option(
        False,
        "--no-discord",
        help="Skip Discord IPC contact; validate config + bundled assets only.",
    ),
) -> None:
    """Validate config + bundled assets without running the monitor loop.

    With ``--no-discord``: loads settings, configures structlog, loads bundled
    locations.json, prints settings JSON, and exits 0. Used as the deep-smoke
    step in F-3 to prove the pydantic-settings + TOML + structlog + watchdog
    import chain initializes end-to-end without contacting Discord.
    """
    settings = AppSettings()
    configure_logging(settings)
    load_bundled_catalog()

    if not no_discord:
        publisher = PypresencePublisher(settings)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(publisher.connect())
        finally:
            publisher.close()
            loop.close()
            asyncio.set_event_loop(None)

    typer.echo(settings.model_dump_json(indent=2))
    raise typer.Exit(0)
