"""Cross-platform local runtime paths; never default to the repository."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "OpenSAT"
DATA_DIR_ENV_VAR = "OPENSAT_DATA_DIR"
LEGACY_DATA_DIR_ENV_VAR = "SAT_PRECISION_LAB_DATA_DIR"


@dataclass(frozen=True)
class DataPaths:
    root: Path
    database: Path
    exports: Path
    temporary: Path
    backups: Path
    logs: Path


def default_data_root() -> Path:
    # Keep the former override readable so existing local scripts do not lose
    # access to their data during the product rename.
    override = os.environ.get(DATA_DIR_ENV_VAR) or os.environ.get(LEGACY_DATA_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Application Support" / APP_DIR_NAME
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        return Path(local_app_data) / APP_DIR_NAME if local_app_data else home / APP_DIR_NAME
    if system == "Linux":
        data_home = os.environ.get("XDG_DATA_HOME")
        return Path(data_home) / "opensat" if data_home else home / ".local" / "share" / "opensat"
    return home / ".opensat"


def ensure_data_layout(root: Path | None = None) -> DataPaths:
    root = (root or default_data_root()).expanduser().resolve()
    paths = DataPaths(
        root=root,
        database=root / "opensat.sqlite3",
        exports=root / "exports",
        temporary=root / "temporary",
        backups=root / "backups",
        logs=root / "logs",
    )
    for directory in (paths.root, paths.exports, paths.temporary, paths.backups, paths.logs):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass
    return paths
