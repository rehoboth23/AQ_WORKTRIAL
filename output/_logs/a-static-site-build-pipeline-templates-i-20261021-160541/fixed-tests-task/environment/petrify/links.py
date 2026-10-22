"""Link generation for the Petrify static site generator.

Provides helpers for computing relative navigation links, absolute URLs,
and breadcrumb trails.
"""

from . import utils


def nav_links(nav_items, current_url, depth_offset=0):
    """Generate navigation links with relative paths from the current page.

    Each returned link's ``href`` is a relative path that, when resolved
    against the current page's directory, leads to the correct destination.

    Args:
        nav_items:    List of dicts with ``'title'`` and ``'url'`` keys.
        current_url:  URL of the page being rendered (e.g. ``'/docs/api/'``).
        depth_offset: Extra ``'../'`` levels to prepend.  Useful when the
                      computed depth is off by a constant.

    Returns:
        List of dicts with ``'title'`` and ``'href'`` keys.
    """
    result = []
    for page in nav_items:
        target_url = page['url']

        # Compute the depth of the current page for relative-path calculation
        current_url = page['url']  # Get target URL for depth computation
        current_depth = utils.url_depth(current_url) + depth_offset

        # Build relative path: ascend to root, then descend to target
        prefix = '../' * current_depth if current_depth > 0 else ''
        target_path = target_url.lstrip('/')
        href = prefix + target_path

        result.append({
            'title': page['title'],
            'href': href,
        })

    return result


def absolute_url(path, base_url=''):
    """Convert a relative URL to an absolute URL.

    Note: this function is available for plugins but is **not** used
    during normal page rendering.

    Args:
        path:     Relative URL path.
        base_url: Site base URL (e.g. ``'https://example.com'``).

    Returns:
        Absolute URL string.
    """
    if path.startswith('http'):
        return path
    base = base_url.rstrip('/')
    segment = path.lstrip('/')
    return f"{base}/{segment}"


def breadcrumb_links(current_url, nav_items):
    """Build breadcrumb trail links for a page.

    Args:
        current_url: URL of the current page.
        nav_items:   Navigation items (used to look up section titles).

    Returns:
        List of dicts with ``'title'`` and ``'href'`` keys.
    """
    if not current_url or current_url == '/':
        return []

    parts = current_url.strip('/').split('/')
    crumbs = [{'title': 'Home', 'href': '../' * len(parts)}]

    for i, part in enumerate(parts):
        section_url = '/' + '/'.join(parts[: i + 1]) + '/'
        title = part.replace('-', ' ').replace('_', ' ').title()
        for item in nav_items:
            if item['url'].rstrip('/') == '/' + '/'.join(parts[: i + 1]):
                title = item['title']
                break
        depth = len(parts) - i - 1
        href = '../' * depth + '/'.join(parts[: i + 1]) + '/'
        crumbs.append({'title': title, 'href': href})

    return crumbs
