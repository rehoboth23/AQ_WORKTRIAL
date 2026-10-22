"""On-disk cache for rendered reports.

The cache stores rendered HTML output alongside a manifest of dependency
file hashes.  On lookup, current file hashes are compared against the
manifest to decide whether the cached output is still valid.

Cache entries live under ``CACHE_DIR`` in sub-directories named by a
truncated SHA-256 digest of the report parameters (type, data path,
date range).  Each entry contains:

  - ``manifest.json``  — map of dependency path → SHA-256 hex digest
  - ``output.html``    — the rendered HTML
"""

import hashlib
import json
import os
from pathlib import Path


CACHE_DIR = "/app/cache"


class Cache:
    """File-based report cache with dependency-hash validation."""

    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(report_type, data_path, from_date, to_date):
        """Deterministic cache key derived from report parameters."""
        key_str = f"{report_type}|{data_path}|{from_date}|{to_date}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    @staticmethod
    def _hash_file(filepath):
        """SHA-256 hex digest of a file's contents."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, report_type, data_path, from_date, to_date, dep_paths):
        """Return cached output if still valid, otherwise ``None``.

        A cache entry is considered valid when every dependency file that
        appears in *both* the current set and the stored manifest has the
        same hash.  Files that are absent from either side are silently
        ignored — they cannot cause a mismatch.
        """
        key = self._cache_key(report_type, data_path, from_date, to_date)
        entry_dir = self.cache_dir / key
        manifest_path = entry_dir / "manifest.json"
        output_path = entry_dir / "output.html"

        if not manifest_path.exists() or not output_path.exists():
            return None

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Compute current hashes for dependency files that currently exist
        current_hashes = {}
        for dep_path in dep_paths:
            if os.path.exists(dep_path):
                current_hashes[dep_path] = self._hash_file(dep_path)

        # Compare only files present in both the current set and manifest
        for dep_path in set(current_hashes) & set(manifest):
            if current_hashes[dep_path] != manifest[dep_path]:
                return None

        # All compared hashes match — cache hit
        with open(output_path) as f:
            return f.read()

    def store(self, report_type, data_path, from_date, to_date, dep_paths, output):
        """Persist rendered output together with a dependency manifest."""
        key = self._cache_key(report_type, data_path, from_date, to_date)
        entry_dir = self.cache_dir / key
        entry_dir.mkdir(parents=True, exist_ok=True)

        # Build manifest: hash each dependency that exists on disk
        manifest = {}
        for dep_path in dep_paths:
            if os.path.exists(dep_path):
                manifest[dep_path] = self._hash_file(dep_path)

        with open(entry_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        with open(entry_dir / "output.html", "w") as f:
            f.write(output)

    def invalidate(self, report_type, data_path, from_date, to_date):
        """Remove a single cache entry."""
        key = self._cache_key(report_type, data_path, from_date, to_date)
        entry_dir = self.cache_dir / key
        if entry_dir.exists():
            for f in entry_dir.iterdir():
                f.unlink()
            entry_dir.rmdir()

    def clear(self):
        """Remove all cache entries."""
        if self.cache_dir.exists():
            for entry in self.cache_dir.iterdir():
                if entry.is_dir():
                    for f in entry.iterdir():
                        f.unlink()
                    entry.rmdir()
