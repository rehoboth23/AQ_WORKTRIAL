"""Site configuration (``site.yaml``) with defaults."""

import yaml

DEFAULTS = {
    "site_name": "My Site",
    "site_url": "/",
    "output_dir": "dist",
    "assets_dir": "assets",
    "content_dir": "content",
    "templates_dir": "templates",
    "themes_dir": "themes",
    "theme": None,
    "redirects_file": "redirects.yaml",
    "nav_items": [],
    "section_titles": {},
}


def load_config(path="site.yaml"):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    config = dict(DEFAULTS)
    config.update(data)
    return config
