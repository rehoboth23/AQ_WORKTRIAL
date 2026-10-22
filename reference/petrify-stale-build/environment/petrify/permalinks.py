"""Link normalisation for rendered pages.

Every internal ``<a href>`` is rewritten to its canonical relative form: the
link is resolved, given directory form (``about`` -> ``about/``) and written
relative to the directory of the document it appears in.  External links,
fragments and links with a query string are left alone.
"""

import re

from . import urls

_HREF = re.compile(r'(<a\b[^>]*?\bhref=")([^"]*)(")', re.IGNORECASE)


def normalize_links(html, document_url):
    """Rewrite internal links in *html*.

    *document_url* is the URL of the rendered document; links are resolved
    against, and written relative to, the directory that contains it.
    """
    base = urls.parent(document_url)

    def fix(match):
        href = match.group(2)
        if not urls.is_internal(href) or "?" in href:
            return match.group(0)
        path, _, fragment = href.partition("#")
        target = urls.directory_form(urls.join(base, path)) if path else None
        new = urls.relativize(target, base) if target else ""
        if fragment:
            new += "#" + fragment
        return match.group(1) + new + match.group(3)

    return _HREF.sub(fix, html)
