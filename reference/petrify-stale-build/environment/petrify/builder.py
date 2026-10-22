"""Site builder.

A build publishes assets, renders every content page plus the home page and
the RSS feed, and writes redirect stubs.  Builds are incremental: an output
whose manifest key is unchanged and whose file exists is not rendered again.
``build(clean=True)`` deletes the output directory first.
"""

import os
import shutil

import jinja2

from . import assets, config as config_mod, content, dates, links, manifest, permalinks, redirects, theme, urls, utils


class SiteBuilder:
    def __init__(self, config_path="site.yaml"):
        self.config_path = config_path
        self.config = config_mod.load_config(config_path)
        self.output_dir = self.config["output_dir"]
        self.asset_dirs = [self.config["assets_dir"]]
        self.template_dirs = [self.config["templates_dir"]]

        self.pages = content.load_content(self.config["content_dir"])
        self.posts = sorted(
            (p for p in self.pages if p["type"] == "post"),
            key=lambda p: dates.parse(p["date"]),
            reverse=True,
        )
        self.asset_map = assets.build_asset_map(self.asset_dirs)

    # ------------------------------------------------------------------ setup

    def _environment(self):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dirs),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            keep_trailing_newline=True,
        )
        env.filters["display_date"] = dates.display
        env.filters["iso_date"] = dates.iso
        env.filters["rfc822_date"] = dates.rfc822
        env.globals["asset_url"] = lambda path: assets.asset_url(path, self.asset_map)
        env.globals["site_name"] = self.config["site_name"]
        env.globals["site_url"] = self.config["site_url"].rstrip("/")
        return env

    # ------------------------------------------------------------------ build

    def build(self, clean=False):
        if clean and os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        theme.activate(self)
        self.env = self._environment()
        assets.copy_assets(self.asset_dirs, self.output_dir)

        state = manifest.Manifest.load(self.output_dir)
        site_key = manifest.file_digest(self.config_path)
        page_keys = {p["url"]: manifest.page_key(p, site_key) for p in self.pages}

        rendered = 0
        for page in self.pages:
            key = page_keys[page["url"]]
            out = urls.output_path(page["url"], self.output_dir)
            if state.is_current(page["url"], key, out):
                continue
            self._write_page(page, out)
            state.record(page["url"], key)
            rendered += 1

        listing_key = manifest.digest(site_key, *(page_keys[p["url"]] for p in self.posts))
        for url, render in (("/", self._render_home), ("/feed.xml", self._render_feed)):
            key = manifest.digest(url, listing_key)
            out = urls.output_path(url, self.output_dir)
            if state.is_current(url, key, out):
                continue
            utils.write_if_changed(out, render())
            state.record(url, key)
            rendered += 1

        redirect_map = redirects.load(self.config["redirects_file"])
        redirects.write_stubs(redirect_map, self.output_dir, utils.write_if_changed)

        state.save()
        total = len(self.pages) + 2
        print(f"rendered {rendered} of {total} pages")
        return rendered

    # ------------------------------------------------------------------ pages

    def _context(self, url):
        return {
            "nav": links.nav_links(self.config["nav_items"], url),
            "breadcrumbs": links.breadcrumb_links(url, self.config["section_titles"]),
            "asset_prefix": "../" * urls.depth(url),
        }

    def _write_page(self, page, out):
        if page.get("layout"):
            template_name = page["layout"]
        elif page["type"] == "post":
            template_name = "post.html"
        else:
            template_name = "page.html"
        html = self.env.get_template(template_name).render(page=page, **self._context(page["url"]))
        html = permalinks.normalize_links(html, page["url"])
        utils.write_if_changed(out, html)

    def _render_home(self):
        page = {"title": self.config["site_name"], "url": "/"}
        html = self.env.get_template("index.html").render(page=page, posts=self.posts, **self._context("/"))
        return permalinks.normalize_links(html, "/")

    def _render_feed(self):
        return self.env.get_template("feed.xml").render(posts=self.posts)
