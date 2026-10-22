"""URL helpers.

Site URLs are absolute paths with a leading slash.  Directory URLs end with a
slash (``'/docs/api/'``); the site root is ``'/'``.  Document URLs name a file
(``'/docs/api/index.html'``, ``'/feed.xml'``).
"""

import os
import posixpath
from urllib.parse import urljoin, urlsplit


def depth(url):
    """Number of directory segments: ``depth('/') == 0``, ``depth('/docs/api/') == 2``."""
    stripped = url.strip("/")
    return len(stripped.split("/")) if stripped else 0


def parent(url):
    """Directory that contains *url*.

    ``parent('/docs/api/index.html') == '/docs/api/'``
    ``parent('/docs/api/') == '/docs/'``
    ``parent('/') == '/'``
    """
    parts = [p for p in url.strip("/").split("/")[:-1] if p]
    return "/" + "/".join(parts) + "/" if parts else "/"


_ORIGIN = "http://site.invalid"


def join(base, href):
    """Resolve *href* against *base* (RFC 3986) and return the path part."""
    return urlsplit(urljoin(_ORIGIN + base, href)).path or "/"


def relativize(target, base_dir):
    """Express *target* relative to the directory URL *base_dir*.

    ``relativize('/about/', '/docs/') == '../about/'``
    """
    rel = posixpath.relpath(target, base_dir)
    if target.endswith("/"):
        rel = "./" if rel == "." else rel + "/"
    return rel


def is_internal(href):
    """True for links into the site: no scheme, no host, not a bare fragment."""
    if not href or href.startswith(("#", "//", "mailto:", "tel:", "data:")):
        return False
    return not urlsplit(href).scheme


def directory_form(url):
    """Add a trailing slash to a URL whose last segment has no extension."""
    last = url.rstrip("/").rsplit("/", 1)[-1]
    if url.endswith("/") or "." in last:
        return url
    return url + "/"


def output_path(url, output_dir):
    """Output file for a URL: ``'/'`` -> ``<out>/index.html``, ``'/a/'`` -> ``<out>/a/index.html``."""
    path = url.strip("/")
    if not path:
        return os.path.join(output_dir, "index.html")
    if url.endswith("/"):
        return os.path.join(output_dir, *path.split("/"), "index.html")
    return os.path.join(output_dir, *path.split("/"))
