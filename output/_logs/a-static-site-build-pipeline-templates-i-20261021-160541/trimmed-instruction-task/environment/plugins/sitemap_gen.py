"""Sitemap generator plugin for Petrify.

This plugin is **disabled** by default and is not called during the
build.  To enable it, add ``sitemap`` to the ``plugins`` list in
``site.yaml`` and import this module in ``builder.py``.

Uses :func:`petrify.links.absolute_url` for URL construction.
"""

import os
from petrify.links import absolute_url


def generate_sitemap(pages, output_dir, base_url=''):
    """Write a ``sitemap.xml`` into *output_dir*.

    Args:
        pages:      List of page dicts (each needs a ``'url'`` key).
        output_dir: Directory to write ``sitemap.xml`` into.
        base_url:   Base URL for constructing absolute loc values.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in pages:
        url = absolute_url(page['url'], base_url)
        lines.append(f'  <url><loc>{url}</loc></url>')

    lines.append('</urlset>')

    output_path = os.path.join(output_dir, 'sitemap.xml')
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
