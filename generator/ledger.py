"""
Batch ledger (README Part 4): what each topic of a batch has reached, on disk, so a killed
batch resumes without re-paying and two copies of the pipeline can share one batch.

    output/_batches/<batch_id>/
        topics.txt            the topic list the batch was started with
        state/<key>.json      one per topic: its stage and what that stage produced
        locks/<key>.lock      flock held while a process works on the topic
        audit.jsonl           one line per stage change: time, pid, topic, from -> to, why

Stages: pending -> generating -> generated -> evaluating -> done, or gen_failed.
State files are replaced atomically (temp file + os.replace), so a kill never leaves half a file.
Locks are flocks: the OS drops them when the holder dies, so a dead copy never blocks a resume.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import tempfile
import time

from config import OUTPUT_DIR

BATCHES_DIR = os.environ.get("BATCHES_DIR", os.path.join(OUTPUT_DIR, "_batches"))


def topic_key(topic: str) -> str:
    return hashlib.sha1(topic.encode("utf-8")).hexdigest()[:10]


def write_json_atomic(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def write_text_atomic(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


@contextlib.contextmanager
def file_lock(path: str):
    """Blocking exclusive flock, for short critical sections (appends, report writes)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def append_jsonl(path: str, row: dict) -> None:
    """Append one JSON line under a lock, so two writers never interleave a line."""
    with file_lock(path + ".lock"):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


def reserve_dir(path: str) -> str:
    """Create `path`, or `path-2`, `path-3`, ... and return the one created. os.mkdir is
    atomic, so two processes can never both get the same directory."""
    candidate, n = path, 1
    while True:
        try:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
            os.mkdir(candidate)
            return candidate
        except FileExistsError:
            n += 1
            candidate = f"{path}-{n}"


class Ledger:
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.dir = os.path.join(BATCHES_DIR, batch_id)
        os.makedirs(os.path.join(self.dir, "state"), exist_ok=True)
        os.makedirs(os.path.join(self.dir, "locks"), exist_ok=True)
        self._held = {}

    # --- topics -------------------------------------------------------------------------
    def save_topics(self, topics: list[str]) -> None:
        path = os.path.join(self.dir, "topics.txt")
        if not os.path.exists(path):
            write_text_atomic(path, "\n".join(topics) + "\n")

    def stored_topics(self) -> list[str]:
        with open(os.path.join(self.dir, "topics.txt"), encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]

    # --- state --------------------------------------------------------------------------
    def _path(self, topic: str) -> str:
        return os.path.join(self.dir, "state", topic_key(topic) + ".json")

    def get(self, topic: str) -> dict:
        try:
            with open(self._path(topic), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"topic": topic, "key": topic_key(topic), "stage": "pending"}

    def all_states(self) -> list[dict]:
        out = []
        for name in sorted(os.listdir(os.path.join(self.dir, "state"))):
            if name.endswith(".json"):
                with open(os.path.join(self.dir, "state", name), encoding="utf-8") as f:
                    out.append(json.load(f))
        return out

    def set(self, topic: str, stage: str, why: str = "", **data) -> dict:
        """Move a topic to `stage`, merging `data` into its state, and audit the change."""
        state = self.get(topic)
        prev = state.get("stage")
        state.update(data, stage=stage, updated=time.strftime("%Y-%m-%dT%H:%M:%S"))
        state.setdefault("started", state["updated"])
        write_json_atomic(self._path(topic), state)
        self.audit("stage", topic=topic, key=state["key"], frm=prev, to=stage, why=why)
        return state

    def update(self, topic: str, **data) -> dict:
        """Merge data without changing the stage (e.g. the pid of a running harbor job)."""
        state = self.get(topic)
        state.update(data)
        write_json_atomic(self._path(topic), state)
        return state

    def audit(self, event: str, **data) -> None:
        append_jsonl(os.path.join(self.dir, "audit.jsonl"),
                     {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(), "event": event, **data})

    # --- per-topic locks ------------------------------------------------------------------
    def try_lock(self, topic: str) -> bool:
        """Non-blocking: True if this process now owns the topic, False if another holds it."""
        f = open(os.path.join(self.dir, "locks", topic_key(topic) + ".lock"), "a")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.close()
            return False
        self._held[topic] = f
        return True

    def unlock(self, topic: str) -> None:
        f = self._held.pop(topic, None)
        if f:
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()
