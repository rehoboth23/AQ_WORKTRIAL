---
title: Q3 Performance Report
date: 2024-11-03
author: Priya Raman
tags: [performance, metrics]
excerpt: Build times, cache hit rates and what we changed this quarter.
---

# Q3 Performance Report

Build times, cache hit rates and what we changed this quarter.

## Background

This post walks through the details, with links to the [documentation](../../docs/) and the [project list](../../projects/).

## Details

- Builds are incremental: only pages whose inputs changed are rendered again.
- Assets are published under content-hashed names.
- Every page links back to the [home page](../../).
