"""Psutil-based game process detector."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psutil

from poe2_rpc.infrastructure.settings import AppSettings


class PsutilGameDetector:
    def __init__(
        self,
        settings: AppSettings,
        process_iter_factory: Callable[[list[str]], Iterator[Any]] | None = None,
    ) -> None:
        self._settings = settings
        self._process_iter = process_iter_factory or psutil.process_iter

    def find_log_path(self) -> Path | None:
        for proc in self._iter_processes_safely():
            if proc is None:
                continue
            return proc
        return None

    def _iter_processes_safely(self) -> Iterator[Path | None]:
        for proc in self._process_iter(["name", "exe"]):
            try:
                info = proc.info
                if info.get("name") == self._settings.process_name:
                    exe = info.get("exe")
                    if exe:
                        yield Path(exe).parent / "logs" / "Client.txt"
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
