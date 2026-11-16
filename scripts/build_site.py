"""Build the website (docs/landing/) from its sources in docs/landing/_src/.

Every page is the head, nav and footer partials around one page body, with `{{name}}` holes
filled in from the page table below. The output is plain HTML committed next to its assets, so
the site is hosted as is: visitors never run a build. `tests/test_build_site.py` fails when the
committed pages differ from a fresh build, so edit `_src/` and run this, never the built pages.

Beside the pages it writes what a host and a search engine look for: `404.html` (the page a host
shows for an address that does not exist), `robots.txt` and `sitemap.xml`.

    uv run python scripts/build_site.py          # write the pages
    uv run python scripts/build_site.py --check  # exit 1 if a committed page is out of date
"""

from __future__ import annotations

import argparse
import functools
import string
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import site_benchmark
import site_home
import site_method
import site_palette
import site_receipts
import site_talk

SITE = Path(__file__).resolve().parent.parent / "docs" / "landing"
SRC = SITE / "_src"
# Where the site is hosted: the canonical links, the link preview's image and the sitemap.
ORIGIN = "https://tracefix.dev"
# May search engines list the site? Not while it is a private preview (DECISIONS 2026-11-06):
# every page says "noindex" and robots.txt names no sitemap. At release set this to True; the
# tests that pin the preview state (tests/test_build_site.py, tests/test_site_talk.py) then fail
# and are updated with it.
SEARCHABLE = False


_HOLE = r"\{\{(?:(?P<escaped>(?!))|(?P<named>[a-z_]+)\}\}|(?P<braced>(?!))|(?P<invalid>))"


class SiteTemplate(string.Template):
    """`{{name}}` holes: the pages' own text has `$` in it (`$ uv run`, `$0.15`), kept literal."""

    # Template compiles this string itself (verbose mode); typeshed types the attribute as the
    # compiled pattern, hence the ignore. `escaped` and `braced` never match; a `{{` that is not a
    # `{{name}}` hole matches `invalid`, so substitute() raises instead of leaving it in the page.
    pattern = _HOLE  # type: ignore[assignment]


@dataclass(frozen=True)
class Page:
    """One built page: its body in `_src/pages/`, where it is written, and its head fields."""

    body: str
    out: str
    title: str
    description: str
    og_title: str
    og_description: str
    scripts: tuple[str, ...] = ()
    # The page's data-made holes (from docs/landing/_data/), on top of the head fields.
    data: Callable[[], Mapping[str, str]] | None = None
    # The 404 page: the host serves it at any address that does not exist, at any depth, so its
    # links cannot be relative. They start at "/" (the site is hosted at the root of its domain).
    # Search engines never list it and the sitemap leaves it out.
    not_found: bool = False

    @property
    def root(self) -> str:
        """The path from the page back to the site root: "" or "../" per folder, "/" on the 404."""
        return "/" if self.not_found else "../" * self.out.count("/")

    @property
    def path(self) -> str:
        """The URL path in the canonical link: "" for the home page, "x/" for x/index.html."""
        return self.out.removesuffix("index.html")


PAGES: tuple[Page, ...] = (
    Page(
        body="index.html",
        out="index.html",
        title="Tracefix: break your fix before your users do",
        description=(
            "Tracefix runs a bug fix from a coding agent or a person, attacks it with inputs the"
            " tests never tried, and hands back a receipt with the ones that still break it."
        ),
        og_title="Tracefix: your fix passed CI. Now let\u2019s try to break it.",
        og_description=(
            "An open-source fix verifier for Python. It attacks a bug fix with inputs the tests"
            " never tried and hands back a receipt with the ones that still break it."
        ),
        scripts=("home.js",),
        data=site_home.fields,
    ),
    Page(
        body="benchmark.html",
        out="benchmark/index.html",
        title="Benchmark: how often Tracefix is right, and every miss",
        description=(
            "Tracefix measured on real bug fixes from open-source Python projects: the release"
            " gates, the results per slice, and every miss with its receipt."
        ),
        og_title="The Tracefix benchmark: the gates, the results and every miss",
        og_description=(
            "Real bug fixes and real agent mistakes from open-source Python projects. Every"
            " number from the committed runs, every miss linked to its receipt."
        ),
        data=site_benchmark.fields,
    ),
    Page(
        body="receipts.html",
        out="receipts/index.html",
        title="Receipts: what Tracefix hands back, for every fixture",
        description=(
            "Every regression fixture's Fix Receipt: the issue, the fix, the receipt as it reads"
            " in a PR comment, the tests Tracefix wrote and the run in the terminal."
        ),
        og_title="Tracefix receipts: every fixture, every finding",
        og_description=(
            "Small buggy repos with known answers, and the receipt Tracefix wrote for each:"
            " counterexamples, levels and the tests behind them."
        ),
        data=site_receipts.gallery_fields,
    ),
    Page(
        body="method.html",
        out="method/index.html",
        title="Method: how Tracefix decides, and where it stops",
        description=(
            "How Tracefix decides: every stage, the evidence ladder, isolation, what a pull"
            " request gets, fork pull requests and what is sent to Anthropic."
        ),
        og_title="The Tracefix method: a model proposes, our code decides",
        og_description=(
            "Every stage, the full evidence ladder and the strict L4 gate, isolation and the"
            " tamper watch, fork pull requests, and exactly what each model is sent."
        ),
        data=site_method.fields,
    ),
    Page(
        body="talk.html",
        out="talk/index.html",
        title="Talk: tell me how you review AI-written fixes",
        description=(
            "Tracefix is for people who review bug fixes a coding agent wrote. A conversation of"
            " about twenty minutes, before anything ships: how you review fixes today."
        ),
        og_title="Talk to me: how do you review a fix a coding agent wrote?",
        og_description=(
            "Before Tracefix is released: a short conversation about how you review AI-written"
            " fixes, what you trust and what has slipped past."
        ),
        data=site_talk.fields,
    ),
    *(
        Page(
            body="receipt.html",
            out=f"receipts/{case}/index.html",
            title=site_receipts.head_title(case),
            description=site_receipts.head_description(case),
            og_title=site_receipts.head_title(case),
            og_description=site_receipts.head_description(case),
            data=functools.partial(site_receipts.case_fields, case),
        )
        for case in site_receipts.cases()
    ),
)

# Not one of PAGES: nothing links to it, the palette does not list it, the sitemap leaves it out.
NOT_FOUND = Page(
    body="404.html",
    out="404.html",
    title="Not found: no page at this address",
    description="There is no page at this address on the Tracefix site.",
    og_title="Tracefix: no page at this address",
    og_description="There is no page at this address on the Tracefix site.",
    not_found=True,
)


def _fill(name: str, fields: dict[str, str]) -> str:
    """Fill one source file; a hole with no value is an error, never left in the page."""
    text = (SRC / name).read_text(encoding="utf-8")
    return SiteTemplate(text).substitute(fields)


def current(page: Page, section: str) -> str:
    """`aria-current` for the nav link of the page's section: "page" on the section's own page,
    "true" on a page inside it (a receipt under Receipts); nothing elsewhere."""
    if page.out == f"{section}/index.html":
        return ' aria-current="page"'
    return ' aria-current="true"' if page.out.startswith(f"{section}/") else ""


@functools.cache
def _palette() -> str:
    """The command palette's entries: the same JSON on every page (links from the site's root)."""
    return site_palette.data()


def render(page: Page) -> str:
    """The page's full HTML."""
    scripts = "".join(f'<script src="{page.root}assets/{s}"></script>\n' for s in page.scripts)
    fields = {
        "root": page.root,
        "origin": ORIGIN,
        "robots": "index, follow" if SEARCHABLE and not page.not_found else "noindex, nofollow",
        "path": page.path,
        "title": page.title,
        "description": page.description,
        "og_title": page.og_title,
        "og_description": page.og_description,
        "scripts": scripts,
        "cur_benchmark": current(page, "benchmark"),
        "cur_receipts": current(page, "receipts"),
        "cur_method": current(page, "method"),
        "cur_talk": current(page, "talk"),
        "palette_data": _palette(),
        **(page.data() if page.data else {}),
    }
    parts = (
        "partials/head.html",
        "partials/nav.html",
        f"pages/{page.body}",
        "partials/footer.html",
    )
    return "".join(_fill(part, fields) for part in parts)


def robots() -> str:
    """robots.txt. Crawlers may read every page either way: while the site is a preview that is
    how they see each page's "noindex" (a page they may not fetch can still be listed by its
    address). The sitemap is named only once the site is SEARCHABLE."""
    lines = ["User-agent: *", "Allow: /"]
    if SEARCHABLE:
        lines += ["", f"Sitemap: {ORIGIN}/sitemap.xml"]
    return "\n".join(lines) + "\n"


def sitemap() -> str:
    """sitemap.xml: the canonical address of every page in PAGES (so not the 404 page)."""
    urls = "".join(f"<url><loc>{ORIGIN}/{page.path}</loc></url>\n" for page in PAGES)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )


def files() -> dict[str, str]:
    """Everything the build writes, by its path in the site, in the order it is written."""
    out = {page.out: render(page) for page in (*PAGES, NOT_FOUND)}
    return {**out, "robots.txt": robots(), "sitemap.xml": sitemap()}


def build(site: Path | None = None) -> list[Path]:
    """Write every file under `site` (default: the committed site); returns the paths written."""
    site = site or SITE
    written = []
    for name, text in files().items():
        target = site / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def stale(site: Path | None = None) -> list[str]:
    """The files under `site` (default: the committed site) that differ from a fresh build."""
    site = site or SITE
    out = []
    for name, text in files().items():
        target = site / name
        if not target.is_file() or target.read_bytes() != text.encode("utf-8"):
            out.append(name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="only report out-of-date files")
    args = parser.parse_args(argv)
    if args.check:
        bad = stale()
        for name in bad:
            print(f"out of date: docs/landing/{name} (run scripts/build_site.py)")
        return 1 if bad else 0
    for path in build():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
