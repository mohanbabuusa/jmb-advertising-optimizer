"""One JSON snapshot per transaction: state and audit cannot partially commit."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from filelock import FileLock


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(path) + ".lock", timeout=10)

    def initialize(self, state: dict) -> None:
        with self.lock:
            if not self.path.exists():
                self._write(state)

    def _write(self, state: dict) -> None:
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                    suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump(state, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def read(self) -> dict:
        with self.lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    @contextmanager
    def transaction(self):
        with self.lock:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            original = deepcopy(state)
            yield state
            if state["audit"][:len(original["audit"])] != original["audit"]:
                raise ValueError("Existing audit history is immutable.")
            if state != original:
                self._write(state)
