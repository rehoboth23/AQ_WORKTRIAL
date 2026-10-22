The Petrify static site generator builds but the generated site in `dist/` is not correct. Fix it so the output meets these requirements:

- Blog posts on the homepage and in `dist/feed.xml` must be in reverse-chronological order by publication date (format: `DD Month YYYY`)
- Every `<link href>` and `<script src>` for CSS/JS in every HTML file must reference a hashed filename (8-char hex, e.g. `main.abc12345.css`), and each referenced file must actually exist in `dist/`
- Navigation links in `<nav>` must resolve to the correct destination from every page regardless of depth, including a working link to the site root from every page
- The build must complete without errors
