"""Ghi trace.jsonl: moi luot handoff giua cac agent la mot dong JSON.

Khong append giua cac lan chay: file duoc mo lai o che do ghi de moi lan
chay pipeline, dung yeu cau "chi can luot chay moi nhat".
"""

import json
import time
from datetime import datetime, timezone

from . import config


class TraceWriter:
    def __init__(self, path=None):
        self.path = path or config.TRACE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")
        self._seq = 0

    def emit(self, case_id: str, agent: str, event: str, payload: dict) -> None:
        self._seq += 1
        record = {
            "seq": self._seq,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "case_id": case_id,
            "agent": agent,
            "event": event,
            "payload": payload,
        }
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Timer:
    """Do thoi gian mot buoc agent de ghi vao trace."""

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed_ms = round((time.perf_counter() - self.started) * 1000, 2)
