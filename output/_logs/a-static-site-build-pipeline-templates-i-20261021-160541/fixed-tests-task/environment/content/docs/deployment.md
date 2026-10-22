---
title: Deployment
type: page
---

# Deployment

Deploy your generated site to any static hosting provider.

## GitHub Pages

The simplest option is to deploy to GitHub Pages using a workflow that
runs `python3 build.py` and publishes the `dist/` directory.

## Netlify

Add a `netlify.toml` that specifies the build command and publish
directory.

## Self-Hosted

Copy the `dist/` directory to your web server's document root.
