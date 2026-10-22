"""Content loading and parsing for the Petrify static site generator.

Reads Markdown files with YAML frontmatter from the content directory,
extracts metadata, renders Markdown to HTML, and computes page URLs.
"""

import os
import re

import markdown
import yaml


def parse_frontmatter(text):
    """Split a Markdown document into YAML frontmatter and body.

    Returns:
        Tuple ``(metadata_dict, body_text)``.
    """
    pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    match = pattern.match(text)
    if not match:
        return {}, text
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = text[match.end():]
    return frontmatter, body


def load_content(content_dir):
    """Walk the content tree and return a list of parsed page dicts.

    Each dict contains at least ``title``, ``date``, ``type``, ``url``,
    ``body``, and ``source_path`` keys.
    """
    pages = []
    for root, _dirs, files in os.walk(content_dir):
        for filename in sorted(files):
            if not filename.endswith('.md'):
                continue
            filepath = os.path.join(root, filename)
            with open(filepath, 'r') as f:
                text = f.read()
            metadata, body = parse_frontmatter(text)
            rel_path = os.path.relpath(filepath, content_dir)
            url = compute_url(rel_path)
            content_type = metadata.get('type', infer_type(rel_path))
            html_body = markdown.markdown(body, extensions=['extra', 'codehilite'])

            page = {
                'title': metadata.get('title', 'Untitled'),
                'date': metadata.get('date', None),
                'type': content_type,
                'url': url,
                'body': html_body,
                'excerpt': metadata.get('excerpt', ''),
                'layout': metadata.get('layout', None),
                'source_path': filepath,
            }
            if content_type == 'post':
                page['author'] = metadata.get('author', 'Staff')
                page['tags'] = metadata.get('tags', [])
            pages.append(page)
    return pages


def compute_url(rel_path):
    """Derive a URL from a content file's relative path.

    ``blog/hello.md``   → ``/blog/hello/``
    ``docs/api/index.md`` → ``/docs/api/``
    """
    path = os.path.splitext(rel_path)[0]
    if os.path.basename(path) == 'index':
        path = os.path.dirname(path)
    if path:
        url = '/' + path.replace(os.sep, '/') + '/'
    else:
        url = '/'
    return url


def infer_type(rel_path):
    """Guess the content type from the file's location in the tree."""
    first = rel_path.split(os.sep)[0]
    if first == 'blog':
        return 'post'
    if first == 'projects':
        return 'project'
    return 'page'
