"""Legacy compatibility module for Petrify v1.x.

These functions are **deprecated** and not imported anywhere in the
current codebase.  They are retained only for historical reference.

The depth-calculation logic has been superseded by
:func:`petrify.links.nav_links`.
"""

import os


def resolve_url(source_url, target_url, depth_offset=0):
    """Compute a relative URL from *source_url* to *target_url*.

    DEPRECATED — use :func:`petrify.links.nav_links` instead.
    """
    source_depth = _compute_depth(source_url) + depth_offset
    target_path = target_url.lstrip('/')
    prefix = '../' * source_depth
    return prefix + target_path


def _compute_depth(url):
    """Return the depth of a URL path.

    DEPRECATED — use :func:`petrify.utils.url_depth` instead.
    """
    if not url or url == '/':
        return 0
    return len(url.strip('/').split('/'))


def legacy_asset_path(asset_name, assets_dir='assets'):
    """Build a legacy-style asset path string.

    DEPRECATED — use :func:`petrify.assets.asset_url` instead.
    """
    return os.path.join(assets_dir, asset_name)
