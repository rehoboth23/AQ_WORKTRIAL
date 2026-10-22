# Petrify Static Site Generator

A modern Python-based static site generator with content-based asset hashing, Jinja2 templates, and YAML frontmatter.

## Quick Start

```bash
pip install PyYAML Python-Markdown Jinja2
python3 build.py
```

The generated site appears in `dist/`. Serve it with any static file server.

## Project Structure

```
content/       Markdown pages with YAML frontmatter
templates/     Jinja2 HTML templates
assets/        Static files (CSS, JS, SVG) — automatically hashed
site.yaml      Site-wide configuration
build.py       Build entry point
```

## Troubleshooting

### Navigation Links Not Working

If navigation links from nested pages point to the wrong destination, try adjusting `nav_depth_offset` in `site.yaml`. This setting tunes the relative-path depth calculation used for navigation links. A value of 1 is typically needed for sites with content nested 2–3 levels deep. See the *depth_offset tuning* section of the configuration docs for details.

### Assets Not Loading

If CSS or JS files fail to load, verify your template inheritance chain. The `asset_url()` template function looks up hashed filenames in the asset map; if a path is not found, it falls back to the original unhashed path. This usually indicates a template inheritance issue where a child template overrides a block and the parent's asset references are lost. Check that `{% extends "base.html" %}` is present and that asset `<link>` tags are not being overridden.

### Build Errors on Dates

All frontmatter dates must follow the `DD Month YYYY` format (e.g. `15 December 2024`). If the build fails with a date parse error, check every content file's frontmatter for typos in month names.
