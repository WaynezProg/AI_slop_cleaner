from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise RuntimeError(f"Refusing to write JSON through symlink: {path}")
        if not path.is_file():
            raise RuntimeError(f"Refusing to overwrite non-file JSON path: {path}")

    temp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    finally:
        if temp_path.exists() or temp_path.is_symlink():
            temp_path.unlink()
