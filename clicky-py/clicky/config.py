"""Config loader for ClickyWin.

Reads config.toml from the OS-appropriate per-user config directory via
platformdirs. Validates required fields and detects the unconfigured placeholder
worker URL (so the panel can surface a clear first-run warning).
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER_WORKER_URL = "https://clicky-win-proxy.your-subdomain.workers.dev"

# v1 supports the two listen-only-hook-friendly bindings. caps_lock is
# deferred to v2 because it requires a suppressing hook to swallow the
# lock-toggle side effect, which contradicts our "never swallow keys" rule.
ALLOWED_HOTKEYS = {"ctrl+alt", "right_ctrl"}
ALLOWED_MODELS = {"claude-sonnet-4-6", "claude-opus-4-6"}
ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class ConfigError(Exception):
    """Raised when the config file cannot be loaded or fails validation."""


@dataclass(frozen=True)
class Config:
    worker_url: str
    hotkey: str
    default_model: str
    log_level: str
    knowledge_dir: Path | None

    @classmethod
    def from_path(cls, path: Path) -> Config:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ConfigError(f"cannot read config file at {path}: {exc}") from exc
        try:
            data = tomllib.loads(raw.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise ConfigError(f"cannot parse TOML at {path}: {exc}") from exc

        worker_url = data.get("worker_url")
        if not isinstance(worker_url, str) or not worker_url:
            raise ConfigError("worker_url is required and must be a non-empty string")
        if worker_url == PLACEHOLDER_WORKER_URL:
            raise ConfigError(
                f"worker_url is still the placeholder value. Edit {path} and set it to "
                "your deployed Cloudflare Worker URL."
            )

        hotkey = data.get("hotkey", "ctrl+alt")
        if hotkey not in ALLOWED_HOTKEYS:
            raise ConfigError(
                f"hotkey must be one of {sorted(ALLOWED_HOTKEYS)}, got {hotkey!r}"
            )

        default_model = data.get("default_model", "claude-sonnet-4-6")
        if default_model not in ALLOWED_MODELS:
            raise ConfigError(
                f"default_model must be one of {sorted(ALLOWED_MODELS)}, got {default_model!r}"
            )

        log_level = data.get("log_level", "INFO")
        if log_level not in ALLOWED_LOG_LEVELS:
            raise ConfigError(
                f"log_level must be one of {sorted(ALLOWED_LOG_LEVELS)}, got {log_level!r}"
            )

        knowledge_dir_raw = data.get("knowledge_dir")
        if isinstance(knowledge_dir_raw, str) and knowledge_dir_raw.strip():
            knowledge_dir = Path(knowledge_dir_raw)
        else:
            # Default: %APPDATA%/ClickyWin/knowledge/
            # Use the same config dir parent (path.parent = %APPDATA%/ClickyWin/)
            knowledge_dir = path.parent / "knowledge"

        # None if directory doesn't exist — no error
        if not knowledge_dir.is_dir():
            knowledge_dir = None

        return cls(
            worker_url=worker_url,
            hotkey=hotkey,
            default_model=default_model,
            log_level=log_level,
            knowledge_dir=knowledge_dir,
        )

    @staticmethod
    def ensure_exists(target_path: Path, example_path: Path) -> bool:
        """Copy example to target if target does not exist. Returns True if created."""
        if target_path.exists():
            return False
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example_path, target_path)
        return True
