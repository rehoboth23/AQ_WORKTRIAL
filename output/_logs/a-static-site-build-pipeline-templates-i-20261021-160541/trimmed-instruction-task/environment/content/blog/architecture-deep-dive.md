---
title: Architecture Deep Dive
date: 20 March 2024
type: post
author: Sarah Chen
tags: [architecture, technical]
excerpt: Understanding the internal architecture of the Petrify build pipeline.
---

# Architecture Deep Dive

The Petrify build pipeline consists of several stages: content loading,
asset processing, template rendering, and site generation.

## Content Loading

Content files are parsed from Markdown with YAML frontmatter. The parser
extracts metadata and renders the Markdown body to HTML.

## Asset Processing

The asset pipeline scans the assets directory, computes SHA-256 hashes of
each file, and builds a lookup map for template rendering.

## Template Rendering

Jinja2 templates receive page data, navigation links, and asset URLs.
Each page is rendered to its final HTML form.
