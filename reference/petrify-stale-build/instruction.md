Our documentation site in `/app` is built with Petrify (`python3 build.py` builds incrementally into `dist/`, `python3 build.py --clean` rebuilds from scratch). Since the last round of changes the generated site has problems: some pages reference stylesheets that don't exist, the blog order isn't right everywhere, some links go to the wrong place, and rebuilding after an edit doesn't always reflect the edit. Fix the generator so the site meets these requirements:

- Every stylesheet and script referenced by any page must be a content-hashed file (`name.<8 hex>.ext`) that exists in `dist/`. The site must render with the theme named in `site.yaml`.
- Every link in the rendered HTML (navigation and page bodies) must resolve, from the page it appears on, to an existing page or file in `dist/`.
- A post's frontmatter `date` may be written as `DD Month YYYY` or as an unquoted ISO `YYYY-MM-DD`. Dates are displayed as `DD Month YYYY`, and posts on the home page and in `dist/feed.xml` are listed newest first.
- An entry in `redirects.yaml` must never replace a page generated from `content/`; redirect stubs are only for URLs that have no content page.
- An incremental build after any edit to `content/`, `templates/`, `themes/`, `site.yaml`, `redirects.yaml` or the assets (adding, changing, renaming or deleting files) must produce exactly the same `dist/` as a clean build. The build prints `rendered N of M pages`; a rebuild with no edits must render 0 pages.

Keep the source layout and the build commands as they are.
