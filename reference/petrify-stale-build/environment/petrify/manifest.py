"""Build manifest for incremental builds.

The manifest is ``<output_dir>/.petrify-manifest.json``::

    {"version": 1, "entries": {"/about/": "<key>", "/feed.xml": "<key>", ...}}

Each entry maps an output URL to the key it was last rendered with.  The
builder re-renders an output when its current key differs from the stored one
or when the output file is missing.
"""

import hashlib
import json
import os

FILENAME = ".petrify-manifest.json"


def digest(*parts):
    """SHA-256 hex digest of the given strings, in order."""
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def file_digest(path):
    """Digest of a file's bytes; empty string if the file does not exist."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def page_key(page, site_key):
    """Key for a content page: its source text, its metadata and *site_key*."""
    meta = {k: v for k, v in page.items() if k not in ("body", "source_path")}
    return digest(page["source_text"], json.dumps(meta, sort_keys=True), site_key)


class Manifest:
    def __init__(self, output_dir, entries=None):
        self.path = os.path.join(output_dir, FILENAME)
        self.entries = entries or {}

    @classmethod
    def load(cls, output_dir):
        path = os.path.join(output_dir, FILENAME)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return cls(output_dir)
        if data.get("version") != 1:
            return cls(output_dir)
        return cls(output_dir, data.get("entries", {}))

    def is_current(self, url, key, output_file):
        return self.entries.get(url) == key and os.path.exists(output_file)

    def record(self, url, key):
        self.entries[url] = key

    def save(self):
        text = json.dumps({"version": 1, "entries": self.entries}, indent=1, sort_keys=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
