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

### Assets Not Loading

### Build Errors on Dates

