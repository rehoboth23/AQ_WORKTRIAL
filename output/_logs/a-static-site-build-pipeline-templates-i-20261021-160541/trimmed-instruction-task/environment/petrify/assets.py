"""Asset management for the Petrify static site generator.

Handles content-based asset hashing for cache-busting.  Each asset file
is renamed to include an 8-character SHA-256 prefix of its contents,
e.g. ``main.css`` → ``main.a1b2c3d4.css``.
"""

import os
import shutil

from . import utils


def build_asset_map(assets_dir):
    """Build a mapping from asset relative paths to their hashed equivalents.

    The map *keys* are relative paths within the assets directory
    (e.g. ``'css/main.css'``).  The map *values* are the same paths with
    a content hash inserted before the extension
    (e.g. ``'css/main.a1b2c3d4.css'``).

    Args:
        assets_dir: Path to the assets directory.

    Returns:
        Dict mapping original relative paths to hashed relative paths.
    """
    asset_map = {}
    if not os.path.isdir(assets_dir):
        return asset_map

    for root, _dirs, files in os.walk(assets_dir):
        for filename in sorted(files):
            full_path = os.path.join(root, filename)

            # Relative path within the assets dir — used for the value
            rel_path = os.path.relpath(full_path, assets_dir)

            # Key for the map — should match what templates look up
            key = utils.rel_path_key(full_path, assets_dir)

            # Content hash
            content_hash = utils.compute_hash(full_path)

            # Hashed variant of the relative path
            base, ext = os.path.splitext(rel_path)
            name_part = os.path.basename(base)
            dir_part = os.path.dirname(rel_path)
            hashed_name = f"{name_part}.{content_hash}{ext}"
            hashed_rel_path = os.path.join(dir_part, hashed_name) if dir_part else hashed_name

            # Normalise separators to forward slashes for URL use
            key = key.replace(os.sep, '/')
            hashed_rel_path = hashed_rel_path.replace(os.sep, '/')

            asset_map[key] = hashed_rel_path

    return asset_map


def copy_assets(assets_dir, dist_dir):
    """Copy every asset into the output directory with a hashed filename.

    This function computes relative paths correctly using
    ``os.path.relpath(full_path, assets_dir)``.

    Args:
        assets_dir: Source assets directory.
        dist_dir:   Destination directory (typically ``dist/``).
    """
    if not os.path.isdir(assets_dir):
        return

    for root, _dirs, files in os.walk(assets_dir):
        for filename in sorted(files):
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, assets_dir)
            content_hash = utils.compute_hash(full_path)

            base, ext = os.path.splitext(rel_path)
            name_part = os.path.basename(base)
            dir_part = os.path.dirname(rel_path)
            hashed_name = f"{name_part}.{content_hash}{ext}"
            dest_rel = os.path.join(dir_part, hashed_name) if dir_part else hashed_name

            dest_path = os.path.join(dist_dir, dest_rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(full_path, dest_path)


def asset_url(path, asset_map):
    """Look up the hashed URL for an asset path.

    If *path* is found in *asset_map* the hashed version is returned;
    otherwise the original (unhashed) path is returned as a fallback.

    Args:
        path:      Relative asset path as used in templates
                   (e.g. ``'css/main.css'``).
        asset_map: Map built by :func:`build_asset_map`.

    Returns:
        Hashed asset path, or the original if not found.
    """
    if path in asset_map:
        return asset_map[path]
    return path
