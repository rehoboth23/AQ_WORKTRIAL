# Petrify

A small static site generator: Markdown with YAML frontmatter, Jinja2 templates,
content-hashed assets, themes and incremental builds.

## Usage

```bash
python3 build.py           # incremental build into dist/
python3 build.py --clean   # full rebuild
python3 -m http.server 8000 -d dist   # preview
```

## Layout

```
content/         Markdown pages; content/blog/ holds posts
templates/       Jinja2 templates (override theme templates of the same name)
themes/<name>/   theme templates and assets; the active theme is set in site.yaml
assets/          site assets (override theme assets of the same path)
redirects.yaml   old URL -> new URL; a stub page is written at each old URL
site.yaml        site configuration
```

## Frontmatter

```yaml
title: Release Notes
date: 15 December 2024
author: Jane Doe
tags: [release]
excerpt: One-line summary shown on the home page and in the feed.
```
