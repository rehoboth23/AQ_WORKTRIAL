"""Navigation and breadcrumb links.

Links are relative, so the site works from any base path.
"""

from . import urls


def nav_links(nav_items, current_url):
    """Navigation entries with hrefs relative to the page at *current_url*."""
    prefix = "../" * urls.depth(current_url)
    result = []
    for item in nav_items:
        href = prefix + item["url"].lstrip("/")
        result.append({
            "title": item["title"],
            "href": href or "./",
            "active": item["url"] == current_url,
        })
    return result


def breadcrumb_links(current_url, titles):
    """Trail from the site root to the page's parent.

    *titles* maps directory URLs to display titles; unknown directories use
    their last path segment.
    """
    trail = []
    url = current_url
    while url != "/":
        url = urls.parent(url)
        label = titles.get(url) or (url.strip("/").rsplit("/", 1)[-1].replace("-", " ").title() or "Home")
        trail.append({"title": label, "href": urls.relativize(url, current_url)})
    trail.reverse()
    return trail
