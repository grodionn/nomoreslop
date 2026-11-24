"""Bounded public palette-card extraction and opaque sRGB contrast. Python 3.10+."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

BASE = "https://colorsinspo.com"
AGENT = "nomoreslop-color/1.0"
MAX_BYTES = 2_000_000
MAX_ITEMS = 64


def allowed_url(value: str) -> str:
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.netloc != "colorsinspo.com"
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Use a public HTTPS Colorsinspo path without query, credentials or fragment")
    if not re.fullmatch(r"/(?:color-palettes|gradients|solid-color)(?:/[a-z0-9-]+){0,3}/?|/color/[0-9a-fA-F]{6}/?|/robots\.txt", parsed.path):
        raise ValueError("Only palette/gradient/solid-color page paths, color details and robots.txt are supported")
    return value


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str) -> tuple[bytes, str]:
    allowed_url(url)
    request = Request(url, headers={"User-Agent": AGENT, "Accept": "text/html,text/plain"})
    with build_opener(PublicRedirects()).open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP status: " + str(response.status))
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "text/plain"):
            raise ValueError("Expected public HTML/text, received " + content_type)
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Response exceeds byte limit")
        return data, response.url


def fetch_page(url: str) -> tuple[bytes, str]:
    allowed_url(url)
    if urlparse(url).path == "/robots.txt":
        raise ValueError("Extract expects a palette/gradient/solid-color page")
    robots, _ = download(BASE + "/robots.txt")
    rules = RobotFileParser()
    rules.parse(robots.decode("utf-8", errors="replace").splitlines())
    if not rules.can_fetch(AGENT, url):
        raise ValueError("robots.txt does not allow this route for the tool")
    return download(url)


def item_kind(href: str) -> str | None:
    path = urlparse(href).path
    if re.fullmatch(r"/color/[0-9a-fA-F]{6}/?", path):
        return "solid-color"
    m = re.fullmatch(r"/(color-palettes|gradients)/([a-z][a-z0-9-]*)/?", path)
    if not m or m[2] in ("hue", "temperature", "harmony", "type"):
        return None
    return "palette" if m[1] == "color-palettes" else "gradient"


def gradient_value(style: str) -> str | None:
    for declaration in style.split(";"):
        key, separator, value = declaration.partition(":")
        if separator and key.strip().lower() in ("background", "background-image"):
            value = value.strip()
            if (len(value) <= 4096 and re.match(r"(?:repeating-)?(?:linear|radial|conic)-gradient\(", value, re.I)
                    and not re.search(r"url\s*\(|expression\s*\(", value, re.I)):
                return value
    return None


class Cards(HTMLParser):
    def __init__(self, source_url: str):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.items: list[dict] = []
        self.links: list[str] = []
        self.current: dict | None = None
        self.anchor = False
        self.anchor_text: list[str] = []
        self.article_depth = 0
        self.solid_link: tuple[str, str] | None = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "article":
            if self.article_depth == 0:
                self.current = {"url": None, "kind": None, "name": "", "colors": [], "gradient_css": None}
                if self.solid_link:
                    self.current.update(url=self.solid_link[0], kind="solid-color", name=self.solid_link[1])
            self.article_depth += 1
        if tag == "a":
            href = data.get("href", "")
            absolute = urljoin(self.source_url, href)
            try:
                allowed_url(absolute)
            except ValueError:
                pass
            else:
                if absolute not in self.links and len(self.links) < 200:
                    self.links.append(absolute)
                if item_kind(absolute) == "solid-color":
                    self.solid_link = (absolute, data.get("aria-label", "").removeprefix("Open "))
                if self.current is not None and item_kind(absolute):
                    self.current["url"] = absolute
                    self.current["kind"] = item_kind(absolute)
                    title = re.fullmatch(r"Inspect (.+) gradient", data.get("title", ""))
                    if title:
                        self.current["name"] = title[1]
                    self.anchor = True
                    self.anchor_text = []
        if self.current is None:
            return
        if tag == "button":
            match = re.fullmatch(r"Copy #?([0-9a-fA-F]{6})", data.get("aria-label", ""))
            if match:
                self.current["colors"].append("#" + match[1].upper())
        if self.current["gradient_css"] is None:
            self.current["gradient_css"] = gradient_value(data.get("style", ""))

    def handle_data(self, data):
        if self.anchor:
            self.anchor_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.solid_link = None
        if tag == "a" and self.anchor:
            if self.current is not None:
                title = " ".join("".join(self.anchor_text).split())
                if title:
                    self.current["name"] = title
            self.anchor = False
            self.anchor_text = []
        if tag == "article" and self.article_depth:
            self.article_depth -= 1
            if self.article_depth == 0 and self.current is not None:
                item = self.current
                valid = (item["kind"] == "palette" and 2 <= len(item["colors"]) <= 16) or (
                    item["kind"] == "gradient" and item["gradient_css"] is not None) or (
                    item["kind"] == "solid-color" and len(item["colors"]) == 1)
                if item["url"] and valid and len(self.items) < MAX_ITEMS:
                    signature = (item["url"], tuple(item["colors"]), item["gradient_css"])
                    if not any((p["url"], tuple(p["colors"]), p["gradient_css"]) == signature for p in self.items):
                        self.items.append(item)
                self.current = None


def extract(data: bytes, source_url: str, channel: str) -> dict:
    allowed_url(source_url)
    if len(data) > MAX_BYTES:
        raise ValueError("HTML exceeds byte limit")
    text = data.decode("utf-8", errors="strict")
    if "<html" not in text.lower() and "<article" not in text.lower():
        raise ValueError("Expected HTML; no page/card structure found")
    collector = Cards(source_url)
    collector.feed(text)
    signature = [(x["url"], x["colors"], x["gradient_css"]) for x in collector.items]
    fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    warnings = ["Article cards only; related cards on a detail page are not its primary export. No design ranking or live render validation."]
    if not collector.items:
        warnings.append("No supported cards found. A category hub, changed markup, shell or challenge is not evidence that the catalog is empty.")
    return {"source_url": source_url, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "channel": channel, "content_sha256": hashlib.sha256(data).hexdigest(),
            "item_count": len(collector.items), "items_fingerprint": fingerprint,
            "items": collector.items, "discovered_links": collector.links, "warnings": warnings}


def rgb(value: str) -> tuple[float, float, float]:
    if not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        raise ValueError("Use opaque sRGB #RGB or #RRGGBB; alpha/OKLCH/P3 require explicit composition/conversion")
    value = value[1:]
    if len(value) == 3:
        value = "".join(x * 2 for x in value)
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(value: str) -> float:
    components = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb(value)]
    return sum(x * coefficient for x, coefficient in zip(components, (0.2126, 0.7152, 0.0722)))


def contrast(foreground: str, background: str) -> dict:
    low, high = sorted((luminance(foreground), luminance(background)))
    ratio = (high + 0.05) / (low + 0.05)
    return {"foreground": foreground, "background": background, "ratio": ratio,
            "meets_3_to_1": ratio >= 3, "meets_4_5_to_1": ratio >= 4.5, "meets_7_to_1": ratio >= 7,
            "scope": "Opaque sRGB pair only. Caller determines applicable criterion, font size/weight, neighbors and exceptions. Not WCAG conformance."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("extract", help="One palette/gradient/solid-color page (plus robots) or saved HTML; no JavaScript")
    group = inspect.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--html", type=Path)
    inspect.add_argument("--source-url", help="Required provenance URL with saved HTML")
    pair = sub.add_parser("contrast", help="WCAG relative luminance ratio for an opaque sRGB pair")
    pair.add_argument("foreground")
    pair.add_argument("background")
    args = parser.parse_args(argv)
    try:
        if args.command == "contrast":
            result = contrast(args.foreground, args.background)
        elif args.url:
            if args.source_url:
                raise ValueError("--source-url is only for saved HTML")
            data, final_url = fetch_page(args.url)
            result = extract(data, final_url, "live-public-http")
        else:
            if not args.source_url:
                raise ValueError("Saved HTML requires --source-url")
            with args.html.open("rb") as saved:
                data = saved.read(MAX_BYTES + 1)
            result = extract(data, args.source_url, "saved-html-not-live-request")
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error), "status": "unavailable-or-invalid-not-empty-catalog"}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
