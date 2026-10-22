---
title: Configuration
type: page
---

# Configuration

Petrify uses a `site.yaml` file for site-wide configuration.

## Site Settings

| Key | Description | Default |
|-----|-------------|---------|
| `site_name` | Display name | My Site |
| `output_dir` | Build output | dist |
| `assets_dir` | Asset source | assets |
| `content_dir` | Content source | content |
| `nav_depth_offset` | Nav link adjustment | 0 |

## Navigation

Define navigation items under the `nav_items` key with `title` and
`url` entries.
