"""
MkDocs hook:
- Finds the latest blog post URL from generated files (after the blog plugin runs).
- Counts blog posts and injects the count into the about page via <!--ARTICLE_COUNT-->.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_post_count: int = 0


def on_nav(nav, config, files, **kwargs):
    global _post_count
    latest_date: date | None = None
    latest_url: str | None = None
    latest_title: str | None = None
    post_count = 0

    for f in files:
        # Blog plugin generates files at: blog/YYYY/MM/DD/<slug>/index.html
        m = re.match(r"blog/(\d{4})/(\d{2})/(\d{2})/([^/]+)/index\.html$", f.dest_path)
        if not m:
            continue
        post_count += 1
        try:
            post_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue

        if latest_date is None or post_date > latest_date:
            latest_date = post_date
            # Strip trailing index.html to get the clean directory URL
            latest_url = f.dest_path[: -len("index.html")]

            # Read title from source file if available, else derive from slug
            if f.src_path:
                src = Path(config["docs_dir"]) / f.src_path
                if src.exists():
                    content = src.read_text(encoding="utf-8")
                    title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
                    latest_title = title_m.group(1).strip() if title_m else m.group(4)
                else:
                    latest_title = m.group(4).replace("-", " ").title()
            else:
                latest_title = m.group(4).replace("-", " ").title()

    _post_count = post_count
    config["extra"]["latest_post"] = (
        {"title": latest_title, "url": latest_url} if latest_url else None
    )


def on_page_markdown(markdown, page, config, files, **kwargs):
    if "<!--ARTICLE_COUNT-->" in markdown:
        return markdown.replace("<!--ARTICLE_COUNT-->", str(_post_count))
    return markdown
