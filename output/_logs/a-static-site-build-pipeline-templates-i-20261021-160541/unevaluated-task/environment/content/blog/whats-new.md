---
title: What's New in v2.0
date: 15 December 2024
type: post
author: Sarah Chen
tags: [release, update]
excerpt: The latest release brings major improvements to the build system.
---

# What's New in v2.0

The latest release brings major improvements to the build system including
faster incremental builds and improved asset management.

## Performance Improvements

Build times are now 40% faster thanks to a new caching layer that tracks
file changes between runs.

## Asset Hashing

Assets are now automatically fingerprinted with content hashes, making
cache-busting trivial and eliminating manual version strings.
