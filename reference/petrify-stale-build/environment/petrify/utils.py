"""Small helpers shared by the build."""

import hashlib
import os


def compute_hash(filepath):
    """First 8 hex characters of the SHA-256 of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def rel_path_key(full_path, base_dir):
    """Path of *full_path* relative to *base_dir*, with forward slashes."""
    return os.path.relpath(full_path, base_dir).replace(os.sep, "/")


def write_if_changed(path, text):
    """Write *text* to *path* unless the file already has exactly that content.

    Returns ``True`` when the file was written.
    """
    data = text.encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True
