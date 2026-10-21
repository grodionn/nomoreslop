#!/usr/bin/env python3
"""Read-only inventory of UI text candidates; never executes or fetches project code.

Static candidates, observed browser text and editorial judgments are separate evidence.
Run --help for the browser snapshot JSON format and coverage limits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys

VERSION = 1
EXTENSIONS = {".html", ".htm", ".svg", ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".css"}
SKIP_DIRS = {".git", "node_modules", ".next", ".nuxt", ".cache", "__pycache__", ".local"}
ATTR_ROLES = {"alt": "image-alternative", "title": "tooltip-or-title", "aria-label": "accessible-name",
              "aria-description": "accessible-description", "placeholder": "placeholder",
              "label": "control-label", "value": "control-value"}
BLOCKS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "button", "a", "li", "label", "figcaption", "text", "title", "desc"}
DYNAMIC = "[dynamic expression]"


def normalize(value):
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def js_unescape(value):
    def replace(match):
        token = match.group(1)
        if token.startswith("u{"):
            number = token[2:-1]
        elif token.startswith(("u", "x")):
            number = token[1:]
        else:
            return {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}.get(token, token)
        try:
            return chr(int(number, 16))
        except (ValueError, OverflowError):
            return match.group(0)
    return re.sub(r"\\(u\{[\da-fA-F]+\}|u[\da-fA-F]{4}|x[\da-fA-F]{2}|\r?\n|.)", replace, value)


def literals(code):
    """Conservative lexical scan: strings/comments/templates, not a JS/TS AST."""
    found = []

    def literal(pos):
        quote, start = code[pos], pos
        pos += 1
        parts, dynamic = [], False
        while pos < len(code):
            if code[pos] == "\\":
                parts.append(code[pos:pos + 2])
                pos += 2
            elif code[pos] == quote:
                value = js_unescape("".join(parts))
                found.append((start, value, "js-template" if quote == "`" else "js-string", dynamic, pos + 1))
                return pos + 1
            elif quote == "`" and code.startswith("${", pos):
                dynamic = True
                parts.append(DYNAMIC)
                pos = expression(pos + 2)
            else:
                parts.append(code[pos])
                pos += 1
        found.append((start, js_unescape("".join(parts)), "unterminated-string", True, pos))
        return pos

    def expression(pos):
        depth = 1
        while pos < len(code):
            if code.startswith("//", pos):
                end = code.find("\n", pos)
                pos = len(code) if end < 0 else end + 1
            elif code.startswith("/*", pos):
                end = code.find("*/", pos + 2)
                pos = len(code) if end < 0 else end + 2
            elif code[pos] in "\"'`":
                pos = literal(pos)
            elif code[pos] == "{":
                depth += 1
                pos += 1
            elif code[pos] == "}":
                depth -= 1
                pos += 1
                if depth == 0:
                    return pos
            else:
                pos += 1
        return pos

    pos = 0
    while pos < len(code):
        if code.startswith("//", pos):
            end = code.find("\n", pos)
            pos = len(code) if end < 0 else end + 1
        elif code.startswith("/*", pos):
            end = code.find("*/", pos + 2)
            pos = len(code) if end < 0 else end + 2
        elif code[pos] in "\"'`":
            pos = literal(pos)
        else:
            pos += 1
    return sorted(found)


class Inventory:
    def __init__(self):
        self.entries, self.gaps, self.files = [], [], []

    def add(self, text, source, line=1, column=1, role="text", origin="static-markup", visibility="unverified", context="", state=None, dynamic=False, location_accuracy="exact"):
        text = normalize(text)
        if not text:
            return
        item = dict(text=text, source=source, line=line, column=column, role=role, origin=origin,
                    visibility=visibility, context=context, dynamic=dynamic, location_accuracy=location_accuracy)
        if state is not None:
            item["state"] = state
        item["id"] = hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        self.entries.append(item)

    def gap(self, source, reason, **extra):
        self.gaps.append(dict(source=source, reason=reason, **extra))


class Markup(HTMLParser):
    def __init__(self, inventory, source, origin="static-markup", base_line=1, approximate=False, dynamic=False):
        super().__init__(convert_charrefs=True)
        self.inventory, self.source, self.origin = inventory, source, origin
        self.base_line, self.approximate, self.dynamic = base_line, approximate, dynamic
        self.stack, self.buffers = [], []
        self.special = None
        self.special_text = []

    def add(self, value, role="text", position=None, context=None):
        line, col = position or self.getpos()
        hidden = any(frame[1] for frame in self.stack)
        self.inventory.add(value, self.source, self.base_line + line - 1, col + 1, role, self.origin,
                           "declared-hidden" if hidden else "unverified", context or "/".join(frame[0] for frame in self.stack),
                           dynamic=self.dynamic or DYNAMIC in value,
                           location_accuracy="template-approximate" if self.approximate else "exact")

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        hidden = "hidden" in data or bool(re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", data.get("style", ""), re.I))
        # aria-hidden affects accessibility exposure, not visual visibility.
        self.stack.append((tag, hidden))
        for key, value in attrs:
            if value and key in ATTR_ROLES and (key != "value" or tag in {"input", "option", "button"}):
                self.add(value, ATTR_ROLES[key], context=f"{tag}[{key}]")
        if tag in BLOCKS:
            self.buffers.append((tag, self.getpos(), [], len(self.stack)))
        if tag in {"script", "style"}:
            self.special = tag
            self.special_text = []
        if tag == "br":
            for _, _, parts, _ in self.buffers:
                parts.append(" ")
        if tag in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.special == tag:
            code = "".join(self.special_text)
            line = self.base_line + self.getpos()[0] - code.count("\n") - 1
            if tag == "script":
                scan_js(code, self.inventory, self.source, max(1, line))
            else:
                scan_css(code, self.inventory, self.source, max(1, line))
            self.special = None
        for index in range(len(self.buffers) - 1, -1, -1):
            name, position, parts, depth = self.buffers[index]
            if name == tag:
                role = "heading" if re.fullmatch(r"h[1-6]", tag) else "document-or-svg-title" if tag == "title" else "text-block"
                self.add("".join(parts), role, position)
                self.buffers.pop(index)
                break
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        if self.special:
            self.special_text.append(data)
            return
        if self.buffers:
            for _, _, parts, _ in self.buffers:
                parts.append(data)
        else:
            self.add(data)

    def finish(self):
        self.close()
        for tag, position, parts, _ in self.buffers:
            self.add("".join(parts), "incomplete-text-block", position)


def scan_css(code, inventory, source, base_line=1):
    clean = re.sub(r"/\*[\s\S]*?\*/", lambda m: "\n" * m.group().count("\n"), code)
    for match in re.finditer(r"\bcontent\s*:\s*([^;}]+)", clean, re.I):
        value = match.group(1)
        for offset, text, _, dynamic, _end in literals(value):
            inventory.add(text, source, base_line + clean.count("\n", 0, match.start()), role="generated-content", origin="css-content", context="content property", dynamic=dynamic, location_accuracy="line-only")
        if re.search(r"\b(?:attr|var|counter|counters)\s*\(", value):
            inventory.gap(source, "CSS content depends on attributes, variables or counters; inspect the rendered state.", line=base_line + clean.count("\n", 0, match.start()))


def scan_js(code, inventory, source, base_line=1):
    tokens = literals(code)
    for offset, value, kind, dynamic, _end in tokens:
        line = base_line + code.count("\n", 0, offset)
        if re.search(r"<[A-Za-z][\w:.-]*(?:\s|>|/)", value):
            parser = Markup(inventory, source, kind, line, approximate=True, dynamic=dynamic)
            parser.feed(value)
            parser.finish()
        else:
            inventory.add(value, source, line, offset - code.rfind("\n", 0, offset), "unclassified-string", kind, context="Static string candidate; may be a class, key, path, data or UI text.", dynamic=dynamic)
    # JSX/TSX is not HTML. Extract direct child text conservatively; expressions remain a stated gap.
    masked = list(code)
    for offset, value, kind, dynamic, end in tokens:
        masked[offset:end] = [" " if char != "\n" else "\n" for char in code[offset:end]]
    jsx_code = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", lambda m: "".join("\n" if char == "\n" else " " for char in m.group()), "".join(masked))
    for match in re.finditer(r">([^<>{}]+)<", jsx_code):
        candidate = normalize(match.group(1))
        if candidate and re.search(r"[^\W\d_]", candidate, re.UNICODE) and not re.search(r"[;=]", candidate):
            inventory.add(candidate, source, base_line + code.count("\n", 0, match.start(1)), role="jsx-child-candidate", origin="jsx-static-candidate", context="Conservative JSX child text; verify AST/rendered output.")
    inventory.gap(source, "JS/TS scan is lexical, not an AST or execution: import graphs, regex ambiguity, concatenation, JSX expressions, localization, network and runtime state text require review/rendered snapshots.")


def rendered_snapshot(path, inventory):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("Rendered snapshot must be an object with an entries array.")
    state = data.get("state")
    if not isinstance(state, str) or not state.strip():
        raise ValueError("Rendered snapshot requires a non-empty state description.")
    meta = {key: data.get(key) for key in ("url", "version", "viewport", "captured_at", "coverage")}
    for entry in data["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            raise ValueError("Each rendered entry requires a text string.")
        inventory.add(entry["text"], str(path), role=entry.get("role", "observed-text"), origin="rendered-snapshot",
                      visibility=entry.get("visibility", "observed-unspecified"), context=entry.get("selector", ""), state=state, location_accuracy="snapshot-selector")
    inventory.files.append(dict(path=str(path), kind="rendered-snapshot", metadata=meta, state=state))
    inventory.gap(str(path), "Imported user/agent browser evidence; script does not authenticate capture, execute actions or cover unlisted states.", state=state)
    if not all(meta.get(key) for key in ("version", "viewport", "captured_at")):
        inventory.gap(str(path), "Snapshot metadata incomplete: supply version, viewport and captured_at for reproducible comparison.")


def project_files(root, inventory):
    def walk_error(error):
        inventory.gap(str(error.filename or root), f"Directory traversal failed: {error}")
    for directory, dirs, names in os.walk(root, topdown=True, onerror=walk_error, followlinks=False):
        # Prune before descent: dependency/cache trees must not be enumerated at all.
        dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS)
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix.lower() in EXTENSIONS:
                yield path


def collect(args):
    root = args.root.resolve()
    if not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root}")
    if args.max_file_bytes <= 0:
        raise ValueError("max-file-bytes must be positive.")
    inventory = Inventory()
    for path in project_files(root, inventory):
        relative = path.relative_to(root).as_posix()
        if args.include and not any(fnmatch.fnmatch(relative, pattern) for pattern in args.include):
            continue
        if any(fnmatch.fnmatch(relative, pattern) for pattern in args.exclude):
            continue
        try:
            if path.stat().st_size > args.max_file_bytes:
                inventory.gap(relative, f"Skipped: exceeds max-file-bytes={args.max_file_bytes}.")
                continue
            payload = path.read_bytes()
            if len(payload) > args.max_file_bytes:
                inventory.gap(relative, f"Skipped: exceeds max-file-bytes={args.max_file_bytes} after read.")
                continue
            code = payload.decode("utf-8-sig")
        except (OSError, UnicodeError) as error:
            inventory.gap(relative, f"Cannot stat/read/decode UTF-8 file: {error}")
            continue
        inventory.files.append(dict(path=relative, kind="static", sha256=hashlib.sha256(payload).hexdigest()))
        if path.suffix.lower() in {".html", ".htm", ".svg"}:
            parser = Markup(inventory, relative)
            parser.feed(code)
            parser.finish()
        elif path.suffix.lower() == ".css":
            scan_css(code, inventory, relative)
        else:
            scan_js(code, inventory, relative)
    for path in args.rendered:
        rendered_snapshot(path.resolve(), inventory)
    canonical = None
    canonical_sha256 = None
    if args.canonical:
        canonical_payload = args.canonical.read_bytes()
        canonical_text = normalize(canonical_payload.decode("utf-8-sig"))
        canonical = str(args.canonical.resolve())
        canonical_sha256 = hashlib.sha256(canonical_payload).hexdigest()
        for entry in inventory.entries:
            # Candidate reconciliation aid; not approval or a statement of editorial quality.
            entry["canonical_match"] = entry["text"] in canonical_text
    inventory.gap("project", "Static candidates do not establish visibility. CSS, responsive composition, image/canvas/video text, external data, unreachable templates and unvisited runtime states are not fully evaluated. Default excludes: " + ", ".join(sorted(SKIP_DIRS)))
    result = dict(schema_version=VERSION, collected_at=datetime.now(timezone.utc).isoformat(), root=str(root),
                  canonical=canonical, canonical_sha256=canonical_sha256,
                  scan_options=dict(include=args.include, exclude=args.exclude, max_file_bytes=args.max_file_bytes),
                  files=inventory.files, entries=inventory.entries, gaps=inventory.gaps,
                  summary=dict(files=len(inventory.files), candidates=len(inventory.entries), gaps=len(inventory.gaps),
                               unmatched_candidates=sum(not entry.get("canonical_match", True) for entry in inventory.entries)))
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        # Project files are never modified. Output is the only write, explicitly requested.
        target = args.output.resolve()
        protected_inputs = [path.resolve() for path in args.rendered]
        protected_inputs.extend((root / item["path"]).resolve() for item in inventory.files if item["kind"] == "static")
        if args.canonical:
            protected_inputs.append(args.canonical.resolve())
        if target in protected_inputs or (target.exists() and (target.is_relative_to(root) or args.output.absolute().is_relative_to(root))):
            raise ValueError("Output must not overwrite an existing project file.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
        print(json.dumps(dict(output=str(target), **result["summary"]), ensure_ascii=False))
    else:
        print(output, end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Rendered snapshot JSON: {state: description, version: commit-or-hash, viewport: {width: 1440, height: 900}, captured_at: ISO-time, url: own-site-url, coverage: checked actions, entries: [{text: exact text, role: heading|accessible-name|..., selector: locator, visibility: visible|accessibility-only|hidden}]} . Supply actual browser observations, not static source relabeled as rendered.")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("collect-text", help="Inventory static candidates plus optional already-captured browser snapshots.")
    command.add_argument("root", type=Path)
    command.add_argument("--include", action="append", default=[], help="Repeatable project-relative glob; otherwise all supported source extensions.")
    command.add_argument("--exclude", action="append", default=[], help="Repeatable glob, e.g. vendor/* or *.min.js; omissions remain a review responsibility.")
    command.add_argument("--rendered", type=Path, action="append", default=[], help="Existing browser-exported JSON snapshot; never launches a browser.")
    command.add_argument("--canonical", type=Path, help="Exact approved content file; substring match is a reconciliation aid, not editorial approval.")
    command.add_argument("--output", type=Path, help="Write a JSON inventory. Default: stdout. Does not overwrite an existing project file.")
    command.add_argument("--max-file-bytes", type=int, default=2_000_000)
    args = parser.parse_args()
    try:
        collect(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"audit_project: {error}\n")


if __name__ == "__main__":
    main()
