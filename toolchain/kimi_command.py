from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_kimi_command() -> str:
    explicit = (os.getenv("KIMI_CLI_EXECUTABLE") or "").strip()
    if explicit and Path(explicit).exists():
        return explicit

    for candidate in ("kimi", "kimi.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    home = Path.home()
    fallback_paths = [
        home / ".local" / "bin" / "kimi.exe",
        home / ".local" / "bin" / "kimi-cli.exe",
        home / "AppData" / "Roaming" / "npm" / "kimi.cmd",
        home / "AppData" / "Roaming" / "npm" / "kimi.exe",
    ]
    for path in fallback_paths:
        if path.exists():
            return str(path)

    return "kimi"
