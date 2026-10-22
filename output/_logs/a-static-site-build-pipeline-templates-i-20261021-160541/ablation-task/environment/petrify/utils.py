"""Utility functions for the Petrify static site generator.

Contains hashing, path-key computation, URL-depth calculation,
date formatting, and slugification helpers.
"""

import hashlib
import os
import re


def compute_hash(filepath):
    """Return the first 8 hex characters of the SHA-256 of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()[:8]


def rel_path_key(full_path, assets_dir):
    """Return the map key for an asset file.

    Args:
        full_path:   Absolute or relative path to the asset file.
        assets_dir:  Path to the root of the assets directory.
    """
    return os.path.relpath(full_path)


def url_depth(url):
    """Return the directory depth of a URL path.

    ``url_depth('')              → 0``
    ``url_depth('/')             → 0``
    ``url_depth('/about/')       → 1``
    ``url_depth('/docs/api/')    → 2``
    ``url_depth('/a/b/c/')       → 3``
    """
    if not url or url == '/':
        return 0
    return len(url.strip('/').split('/'))


def format_date(date_str, fmt='%B %d, %Y'):
    """Re-format a ``'DD Month YYYY'`` date string."""
    from datetime import datetime
    dt = datetime.strptime(date_str, '%d %B %Y')
    return dt.strftime(fmt)


def slugify(text):
    """Convert arbitrary text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')
