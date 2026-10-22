"""Redirect stubs for moved pages.

``redirects.yaml`` maps old URLs to new ones::

    /guide/: /docs/getting-started/

For each entry an HTML stub is written at the old URL that sends visitors to
the new one with a meta refresh.
"""

import os

import yaml

from . import urls

STUB = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={href}">
<link rel="canonical" href="{href}">
<title>Moved</title>
</head>
<body><p>This page has moved to <a href="{href}">{href}</a>.</p></body>
</html>
"""


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {str(k): str(v) for k, v in data.items()}


def write_stubs(redirects, output_dir, write):
    """Write a stub for each redirect with *write(path, text)*; return the count."""
    for source, target in sorted(redirects.items()):
        href = urls.relativize(target, source) if target.startswith("/") else target
        write(urls.output_path(source, output_dir), STUB.format(href=href))
    return len(redirects)
