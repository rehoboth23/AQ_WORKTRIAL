"""Configuration loading for the Petrify static site generator.

Reads ``site.yaml`` and applies sensible defaults for any missing keys.
"""

import os
import yaml


def load_config(config_path='site.yaml'):
    """Load and return site configuration.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Dict of configuration values.
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    config.setdefault('site_name', 'My Site')
    config.setdefault('site_url', '/')
    config.setdefault('output_dir', 'dist')
    config.setdefault('assets_dir', 'assets')
    config.setdefault('content_dir', 'content')
    config.setdefault('templates_dir', 'templates')
    config.setdefault('nav_items', [])
    config.setdefault('nav_depth_offset', 0)
    config.setdefault('cache_bust', True)

    return config
