"""Main builder for the Petrify static site generator.

Orchestrates content loading, asset processing, template rendering,
and site output generation.
"""

import os
import shutil

import jinja2

from . import assets as assets_mod
from . import config as config_mod
from . import content as content_mod
from . import links as links_mod
from . import utils


class SiteBuilder:
    """Builds a complete static site from content, templates, and assets."""

    def __init__(self, config_path='site.yaml'):
        self.config = config_mod.load_config(config_path)
        self.output_dir = self.config['output_dir']
        self.assets_dir = self.config['assets_dir']
        self.content_dir = self.config['content_dir']
        self.templates_dir = self.config['templates_dir']

        # Jinja2 template environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
        )

        # Build the asset map (keys → hashed paths)
        self.asset_map = assets_mod.build_asset_map(self.assets_dir)

        # Load all content pages
        self.pages = content_mod.load_content(self.content_dir)

        # Separate blog posts and sort them
        self.posts = [p for p in self.pages if p['type'] == 'post']
        self.posts_sorted = self._sort_posts(self.posts)

        # Register template globals
        self._setup_template_globals()

    # ------------------------------------------------------------------ #
    #  Post sorting
    # ------------------------------------------------------------------ #

    def _sort_posts(self, posts):
        """Sort posts for display."""
        return sorted(posts, key=lambda p: p['date'], reverse=True)

    # ------------------------------------------------------------------ #
    #  Template setup
    # ------------------------------------------------------------------ #

    def _setup_template_globals(self):
        """Register functions and variables available in all templates."""
        self.env.globals['asset_url'] = lambda path: assets_mod.asset_url(
            path, self.asset_map
        )
        self.env.globals['site_name'] = self.config['site_name']
        self.env.globals['site_url'] = self.config.get('site_url', '/')

    # ------------------------------------------------------------------ #
    #  Build entry point
    # ------------------------------------------------------------------ #

    def build(self):
        """Build the entire site into the output directory."""
        # Wipe and recreate the output directory
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # Copy assets with content-hashed filenames
        assets_mod.copy_assets(self.assets_dir, self.output_dir)

        # Render each content page
        for page in self.pages:
            self._render_page(page)

        # Render the blog index (homepage)
        self._render_blog_index()

        # Render the RSS feed
        self._render_feed()

        print(f"Site built successfully in {self.output_dir}/")

    # ------------------------------------------------------------------ #
    #  Page rendering
    # ------------------------------------------------------------------ #

    def _get_nav_links(self, current_url):
        """Compute navigation links relative to *current_url*."""
        nav_items = self.config.get('nav_items', [])
        depth_offset = self.config.get('nav_depth_offset', 0)
        return links_mod.nav_links(nav_items, current_url, depth_offset=depth_offset)

    def _render_page(self, page):
        """Render a single content page to disk."""
        current_url = page['url']
        nav = self._get_nav_links(current_url)
        depth = utils.url_depth(current_url)
        asset_prefix = '../' * depth

        # Choose template by content type
        if page['type'] == 'post':
            template_name = 'post.html'
        elif page.get('layout'):
            template_name = page['layout']
        else:
            template_name = 'page.html'

        template = self.env.get_template(template_name)
        context = {
            'page': page,
            'nav': nav,
            'site_name': self.config['site_name'],
            'asset_prefix': asset_prefix,
        }
        html = template.render(**context)

        output_path = self._url_to_filepath(current_url)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html)

    def _render_blog_index(self):
        """Render the homepage showing the most recent blog posts."""
        nav = self._get_nav_links('/')
        template = self.env.get_template('index.html')
        context = {
            'page': {'title': self.config['site_name'], 'url': '/'},
            'posts': self.posts_sorted,
            'nav': nav,
            'site_name': self.config['site_name'],
            'asset_prefix': '',
        }
        html = template.render(**context)
        output_path = os.path.join(self.output_dir, 'index.html')
        with open(output_path, 'w') as f:
            f.write(html)

    def _render_feed(self):
        """Render an RSS 2.0 feed of blog posts."""
        template = self.env.get_template('feed.xml')
        context = {
            'posts': self.posts_sorted,
            'site_name': self.config['site_name'],
            'site_url': self.config.get('site_url', '/'),
        }
        xml = template.render(**context)
        output_path = os.path.join(self.output_dir, 'feed.xml')
        with open(output_path, 'w') as f:
            f.write(xml)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _url_to_filepath(self, url):
        """Map a URL to its output file path.

        '/'        → dist/index.html
        '/about/'  → dist/about/index.html
        """
        url = url.strip('/')
        if not url:
            return os.path.join(self.output_dir, 'index.html')
        return os.path.join(self.output_dir, url, 'index.html')
