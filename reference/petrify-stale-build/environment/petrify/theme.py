"""Themes.

A theme is a directory under ``themes/`` with optional ``templates/`` and
``assets/`` subdirectories.  Activating a theme adds those directories after
the site's own, so site templates and assets take precedence.
"""

import os


def activate(builder):
    """Add the configured theme's template and asset directories to *builder*."""
    name = builder.config.get("theme")
    if not name:
        return
    root = os.path.join(builder.config.get("themes_dir", "themes"), name)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"theme '{name}' not found in {root}")
    templates = os.path.join(root, "templates")
    if os.path.isdir(templates) and templates not in builder.template_dirs:
        builder.template_dirs.append(templates)
    assets = os.path.join(root, "assets")
    if os.path.isdir(assets) and assets not in builder.asset_dirs:
        builder.asset_dirs.append(assets)
