---
title: Migration Guide
date: 10 Februray 2024
type: post
author: Alex Kim
tags: [guide, migration]
excerpt: How to migrate your existing site to the new build system.
---

# Migration Guide

This guide covers migrating from Petrify v1.x to v2.0. The new build
system introduces several breaking changes that you should be aware of.

## Step 1: Update Configuration

Rename your `config.yaml` to `site.yaml` and update the key names to
match the new format.

## Step 2: Move Assets

Move your static files from `static/` to `assets/`. The new asset
pipeline will automatically hash them for cache-busting.

## Step 3: Update Templates

Template globals have changed. Replace any calls to `static_url()` with
`asset_url()`.
