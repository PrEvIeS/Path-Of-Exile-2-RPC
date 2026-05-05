"""Application settings loaded via pydantic-settings.

Source precedence (highest → lowest):
  init kwargs → env (POE2RPC_*) → TOML file → defaults

TOML file location (Behavior Change #5 from ADR):
  Windows : %APPDATA%\\poe2-rpc\\config.toml
  POSIX   : ~/.config/poe2-rpc/config.toml
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import PrivateAttr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


def _default_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "poe2-rpc" / "config.toml"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POE2RPC_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_app_id: str = "1315800372207419504"
    process_name: str = "PathOfExileSteam.exe"
    locations_url: str | None = None
    log_stream_enqueue_deadline_seconds: float = 2.0
    log_stream_queue_maxsize: int = 1000
    throttle_window_seconds: float = 15.0
    connect_retry_attempts: int = 5
    publish_retry_attempts: int = 3
    log_format: Literal["console", "json"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    _toml_file: str = PrivateAttr(default="")

    def __init__(self, _toml_file: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._toml_file = _toml_file
        if _toml_file:
            self._apply_toml(Path(_toml_file))

    def _apply_toml(self, path: Path) -> None:
        if not path.exists():
            return
        with open(path, "rb") as f:
            data = tomllib.load(f)
        for key, value in data.items():
            if key in self.__class__.model_fields:
                object.__setattr__(self, key, value)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # framework signature requires these but we don't consume them
        del dotenv_settings, file_secret_settings
        toml_source = TomlConfigSettingsSource(settings_cls, toml_file=_default_config_path())
        # init → env → default TOML file → defaults
        return (init_settings, env_settings, toml_source)
