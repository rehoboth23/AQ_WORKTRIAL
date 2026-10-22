---
title: API Details
type: page
---

# API Details

Detailed API documentation for all public modules and functions.

## builder module

The `SiteBuilder` class is the main entry point for building a site.

### SiteBuilder.\_\_init\_\_(config_path)

Load configuration and prepare the build environment.

### SiteBuilder.build()

Execute the full build pipeline and write output to disk.

## assets module

### build_asset_map(assets_dir)

Scan assets and return a dict mapping original paths to hashed paths.

### copy_assets(assets_dir, dist_dir)

Copy all assets to the output directory with hashed filenames.
