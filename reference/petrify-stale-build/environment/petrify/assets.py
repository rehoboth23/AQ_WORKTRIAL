"""Static assets.

Every asset is published under a content-hashed name (``main.css`` ->
``main.a1b2c3d4.css``).  Assets can come from several directories (the site's
own and the theme's); a path such as ``css/main.css`` is looked up in each
directory in order.
"""

import os
import shutil

from . import utils


def _walk(asset_dirs):
    """Yield ``(relative_path, full_path)`` for every file, first directory wins."""
    seen = set()
    for directory in asset_dirs:
        if not os.path.isdir(directory):
            continue
        for root, _dirs, files in os.walk(directory):
            for filename in sorted(files):
                full = os.path.join(root, filename)
                rel = utils.rel_path_key(full, directory)
                if rel not in seen:
                    seen.add(rel)
                    yield rel, full


def hashed_name(rel_path, full_path):
    base, ext = os.path.splitext(rel_path)
    return f"{base}.{utils.compute_hash(full_path)}{ext}"


def build_asset_map(asset_dirs):
    """Map each asset path (``css/main.css``) to its published name."""
    return {rel: hashed_name(rel, full) for rel, full in _walk(asset_dirs)}


def copy_assets(asset_dirs, output_dir):
    """Publish every asset under its hashed name.  Existing files are left as they are."""
    count = 0
    for rel, full in _walk(asset_dirs):
        dest = os.path.join(output_dir, hashed_name(rel, full))
        if os.path.exists(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(full, dest)
        count += 1
    return count


def asset_url(path, asset_map):
    """Published name for *path*, or *path* itself when it is not in the map."""
    return asset_map.get(path, path)
