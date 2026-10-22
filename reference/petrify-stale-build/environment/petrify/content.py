"""Content loading.

Reads Markdown files with YAML frontmatter from the content directory and
returns one dict per page.
"""

import os
import re

import markdown
import yaml

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text):
    """Split a document into ``(metadata, body)``."""
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, text[match.end():]


def _coerce_scalars(metadata):
    """Convert non-string scalar values to ``str``.

    Lists and nested mappings are processed recursively and ``None`` and
    booleans are kept.  Pages are fingerprinted as JSON by the build manifest,
    so metadata must contain only JSON types.
    """
    out = {}
    for key, value in metadata.items():
        if isinstance(value, dict):
            out[key] = _coerce_scalars(value)
        elif isinstance(value, list):
            out[key] = [v if isinstance(v, (str, bool)) or v is None else str(v) for v in value]
        elif value is None or isinstance(value, (str, bool)):
            out[key] = value
        else:
            out[key] = str(value)
    return out


def compute_url(rel_path):
    """``blog/hello.md`` -> ``/blog/hello/``; ``docs/api/index.md`` -> ``/docs/api/``."""
    path = os.path.splitext(rel_path)[0].replace(os.sep, "/")
    if os.path.basename(path) == "index":
        path = os.path.dirname(path)
    return "/" + path + "/" if path else "/"


def infer_type(rel_path):
    first = rel_path.split(os.sep)[0]
    return {"blog": "post", "projects": "project"}.get(first, "page")


def load_content(content_dir):
    """Return a list of page dicts, sorted by URL."""
    pages = []
    md = markdown.Markdown(extensions=["extra", "toc"])
    for root, _dirs, files in os.walk(content_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(root, filename)
            with open(filepath, encoding="utf-8") as f:
                text = f.read()
            raw_meta, body = parse_frontmatter(text)
            meta = _coerce_scalars(raw_meta)
            rel_path = os.path.relpath(filepath, content_dir)
            md.reset()
            page = {
                "title": meta.get("title", "Untitled"),
                "date": meta.get("date"),
                "type": meta.get("type", infer_type(rel_path)),
                "url": compute_url(rel_path),
                "layout": meta.get("layout"),
                "excerpt": meta.get("excerpt", ""),
                "author": meta.get("author", ""),
                "tags": meta.get("tags", []),
                "body": md.convert(body),
                "source_path": filepath,
                "source_text": text,
            }
            pages.append(page)
    pages.sort(key=lambda p: p["url"])
    return pages
