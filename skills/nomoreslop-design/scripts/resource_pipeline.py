#!/usr/bin/env python3
"""Inspect public design resources, fetch selected registry files, audit local use.

Dependency-free; never installs, executes downloaded code, logs in, or controls a
browser. Only `fetch` writes: into a new explicit project-relative directory.
Reports establish delivery/static structure, never quality, rights, or behavior.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "references" / "source-adapters.json"
MAX_RESPONSE = 3 * 1024 * 1024
MAX_FILES = 100
MAX_SCAN_FILES = 1500
MAX_SCAN_BYTES = 12 * 1024 * 1024
TIMEOUT = 20
SOURCE_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css", ".html", ".htm", ".vue", ".svelte"}
RESOLVE_SUFFIXES = ("", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css", ".json", ".svg", ".html")
RECEIPT = ".source/receipt.json"
RESPONSE = ".source/response.json"
LIMITATION = "Static delivery/trace audit only. Self-reported observations are not independently verified; no execution, visual evaluation, license clearance, or guarantee of complete dependency analysis."


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path, limit: int = MAX_RESPONSE):
    if path.stat().st_size > limit:
        raise ValueError(f"JSON exceeds {limit} bytes: {path.name}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_relative(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError("Expected a nonempty bounded relative path")
    value = value.replace("\\", "/")
    parts = value.split("/")
    if value.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"Unsafe relative path: {value!r}")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if re.search(r'[<>:"|?*\x00-\x1f]', part) or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved or part.lower() in {".git", "node_modules"}:
            raise ValueError(f"Unsafe path segment: {part!r}")
    return PurePosixPath(value)


def inside(root: Path, relative: str, must_exist: bool = False) -> Path:
    root = root.resolve()
    target = root.joinpath(*safe_relative(relative).parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Path resolves outside the project (possibly a symlink)")
    if must_exist and not target.is_file():
        raise ValueError(f"File does not exist: {relative}")
    return target


def public_url(url: str, resolve_dns: bool = True) -> str:
    if not isinstance(url, str) or len(url) > 2048 or re.search(r"[\x00-\x20]", url):
        raise ValueError("Expected a bounded public HTTPS URL")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Only public HTTPS URLs without credentials or fragments are accepted")
    if parsed.port not in (None, 443):
        raise ValueError("Only standard public HTTPS port is accepted")
    private_keys = {"token", "access_token", "api_key", "apikey", "authorization", "signature", "sig", "key", "password", "x-amz-signature", "x-amz-credential"}
    if any(key.lower() in private_keys for key, _ in parse_qsl(parsed.query)):
        raise ValueError("Credentials/signed URLs are not accepted; use the authorized connector instead")
    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private/local hosts are not supported")
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        addresses = []
        if resolve_dns:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)]
    if any(not address.is_global for address in addresses):
        raise ValueError("Private/nonpublic addresses are not supported")
    return url


class SafeRedirect(HTTPRedirectHandler):
    def __init__(self):
        self.count = 0

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 5:
            raise ValueError("Redirect limit exceeded")
        public_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def retrieve(url: str) -> dict:
    started = time.monotonic()
    public_url(url)
    request = Request(url, headers={"User-Agent": "nomoreslop-resource-pipeline/16 (public read-only research)", "Accept": "application/json,text/html,text/plain;q=0.9", "Accept-Encoding": "identity"})
    try:
        response = build_opener(SafeRedirect()).open(request, timeout=TIMEOUT)
    except HTTPError as error:
        status = error.code
        access = {401: "auth_required", 402: "payment_required", 403: "access_denied", 404: "not_found", 429: "rate_limited"}.get(status, "http_error")
        retry = error.headers.get("Retry-After") if error.headers else None
        error.close()
        return {"requested_url": url, "checked_at": now(), "status": status, "access": access, "retry_after": retry, "body": b"", "error": "No automatic retry or alternate-interface access bypass is performed"}
    except (URLError, TimeoutError, OSError) as error:
        return {"requested_url": url, "checked_at": now(), "status": None, "access": "network_error", "body": b"", "error": type(error).__name__}
    with response:
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_RESPONSE:
            raise ValueError("Response exceeds size limit")
        if response.headers.get("Content-Encoding", "identity").lower() not in {"identity", ""}:
            raise ValueError("Compressed response rejected; decompression is not performed")
        chunks, remaining = [], MAX_RESPONSE + 1
        while remaining:
            if time.monotonic() - started > TIMEOUT:
                raise ValueError("Overall retrieval time budget exceeded")
            chunk = response.read(min(65536, remaining))
            if not chunk: break
            chunks.append(chunk)
            remaining -= len(chunk)
        body = b"".join(chunks)
        if len(body) > MAX_RESPONSE:
            raise ValueError("Response exceeds size limit")
        return {"requested_url": url, "canonical_url": response.geturl(), "checked_at": now(), "status": response.status, "content_type": response.headers.get("Content-Type", ""), "response_sha256": digest(body), "bytes": len(body), "body": body}


def dependencies(value) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def package_name(specifier: str) -> str:
    if specifier.startswith("@"):
        parts = specifier.split("/")
        return parts[0] + "/" + parts[1].split("@")[0] if len(parts) >= 2 else specifier
    return re.split(r"[/@]", specifier, 1)[0]


def registry_data(data) -> dict | None:
    if not isinstance(data, dict) or not isinstance(data.get("files"), list) or not data["files"]:
        return None
    if len(data["files"]) > MAX_FILES:
        raise ValueError("Registry file count exceeds limit")
    files, seen, total = [], set(), 0
    for entry in data["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("content"), str) or not entry["content"].strip():
            raise ValueError("Registry files require nonempty inline content; URL-only records need another authorized retrieval route")
        path = str(safe_relative(entry.get("path")))
        folded = path.casefold()
        if folded == ".source" or folded.startswith(".source/") or any(folded == old or folded.startswith(old + "/") or old.startswith(folded + "/") for old in seen):
            raise ValueError("Duplicate/reserved registry file path")
        seen.add(folded)
        encoded = entry["content"].encode("utf-8")
        total += len(encoded)
        if total > MAX_RESPONSE:
            raise ValueError("Registry content exceeds limit")
        files.append({"path": path, "content": entry["content"], "sha256": digest(encoded), "bytes": len(encoded), "type": entry.get("type"), "target": entry.get("target")})
    return {"name": str(data.get("name", "unnamed"))[:200], "type": data.get("type"), "source_version": data.get("version") if isinstance(data.get("version"), str) else None, "files": files, "dependencies": dependencies(data.get("dependencies")), "dev_dependencies": dependencies(data.get("devDependencies")), "registry_dependencies": dependencies(data.get("registryDependencies")), "license": data.get("license"), "author": data.get("author")}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.text, self.links = [], [], []
        self.title_depth = self.skip = self.code_blocks = self.passwords = 0
        self.main_text = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title": self.title_depth += 1
        if tag in {"script", "style", "noscript"}: self.skip += 1
        if tag in {"pre", "code"}: self.code_blocks += 1
        if tag == "input" and attrs.get("type", "").lower() == "password": self.passwords += 1
        if tag == "a" and attrs.get("href") and len(self.links) < 200: self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "title": self.title_depth = max(0, self.title_depth - 1)
        if tag in {"script", "style", "noscript"}: self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if self.title_depth: self.title.append(data)
        if not self.skip and not self.title_depth and data.strip(): self.text.append(data.strip())


def inspect_response(response: dict) -> tuple[dict, dict | None]:
    output = {key: value for key, value in response.items() if key != "body"}
    output["limitation"] = LIMITATION
    if response.get("access"):
        return output, None
    body = response["body"]
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        output.update(access="unsupported_binary", capabilities=[])
        return output, None
    trimmed = text.lstrip()
    if "json" in response.get("content_type", "") or trimmed.startswith(("{", "[")):
        try:
            data = json.loads(text)
            registry = registry_data(data)
        except json.JSONDecodeError:
            output.update(access="unparseable", capabilities=[])
            return output, None
        if registry:
            output.update(access="source_available", capabilities=["metadata", "source"], **{key: value for key, value in registry.items() if key != "files"})
            output["files"] = [{key: value for key, value in entry.items() if key != "content"} for entry in registry["files"]]
            output["rights"] = "unverified; check publisher and per-asset/dependency terms before use"
            return output, registry
        output.update(access="metadata_only", capabilities=["metadata"], shape="object" if isinstance(data, dict) else "array", keys=list(data)[:40] if isinstance(data, dict) else [], source_version=None)
        return output, None
    if "html" in response.get("content_type", "") or trimmed.lower().startswith(("<!doctype html", "<html")):
        page = Page()
        page.feed(text)
        title, visible = " ".join(page.title).strip(), " ".join(page.text)
        lower = (title + " " + visible[:5000]).lower()
        if any(term in lower for term in ("verify you are human", "checking your browser", "just a moment", "security verification", "captcha")):
            access = "challenge"
        elif page.passwords or re.search(r"^(?:log\s*in|sign\s*in|login|authenticate)(?:\s|[|—-]|$)", title.lower()):
            access = "auth_required"
        elif len(visible) < 180 and re.search(r'<(?:div|main)[^>]+id=[\"\'](?:root|app|__next)[\"\']', text, re.I):
            access = "spa_shell"
        else:
            access = "html_document"
        links = list(dict.fromkeys(urljoin(response.get("canonical_url", response["requested_url"]), link) for link in page.links if link.startswith(("/", "https://"))))
        output.update(access=access, capabilities=["metadata"] if access == "html_document" else [], title=title[:300], text_sample=visible[:1200], code_blocks_observed=page.code_blocks, links=links[:30], links_truncated=len(links) > 30, source_version=None)
        return output, None
    output.update(access="text_document", capabilities=["metadata"], text_sample=text[:1200], source_version=None)
    return output, None


def imports(text: str, suffix: str) -> tuple[list[str], bool]:
    # Deliberately bounded lexical extraction, not an AST or a full module resolver.
    # Strip ordinary comments; template strings/regex and language extensions can
    # still create ambiguity. Missing edges are reported as unknown, never proof.
    cleaned = re.sub(r"/\*.*?\*/|(?m:^\s*//[^\n]*)", "", text, flags=re.S)
    found = []
    # Navigation href is not a module/asset dependency. Keep link resources and
    # literal src/CSS URL references, while router links remain a runtime concern.
    for pattern in (r"\b(?:import|export)\s+(?:[^;\n]*?\s+from\s*)?[\"']([^\"']+)[\"']", r"\b(?:import|require)\s*\(\s*[\"']([^\"']+)[\"']\s*\)", r"@import\s+(?:url\(\s*)?[\"']([^\"']+)[\"']", r"\bsrc\s*=\s*[\"']([^\"']+)[\"']", r"<link\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", r"url\(\s*[\"']?([^\)\"']+)[\"']?\s*\)"):
        found.extend(re.findall(pattern, cleaned))
    dynamic = bool(re.search(r"\b(?:import|require)\s*\(\s*[^\s\"']", cleaned))
    return list(dict.fromkeys(found)), dynamic


def resolve_import(root: Path, origin: Path, specifier: str) -> Path | None:
    specifier = unquote(specifier.split("?", 1)[0].split("#", 1)[0])
    if not specifier or specifier.startswith(("data:", "http:", "https:", "mailto:", "tel:", "#")):
        return None
    candidates = []
    if specifier.startswith("."):
        candidates.append(origin.parent / specifier)
    elif specifier.startswith("/"):
        candidates.append(root / specifier.lstrip("/"))
    elif specifier.startswith(("@/", "~/")):
        candidates.extend((root / specifier[2:], root / "src" / specifier[2:]))
    else:
        return None
    for candidate in candidates:
        for suffix in RESOLVE_SUFFIXES:
            path = Path(str(candidate) + suffix).resolve()
            if path.is_relative_to(root) and path.is_file(): return path
        for suffix in RESOLVE_SUFFIXES[1:]:
            path = (candidate / ("index" + suffix)).resolve()
            if path.is_relative_to(root) and path.is_file(): return path
    return None


def scan(root: Path) -> dict:
    root = root.resolve()
    if not root.is_dir(): raise ValueError("Package root must be an existing directory")
    entries, total, truncated = [], 0, False
    skipped = {".git", "node_modules", ".source", ".cache", ".next", "coverage"}
    visited = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in skipped and not (Path(directory) / name).is_symlink())
        for name in sorted(names):
            visited += 1
            if visited > MAX_SCAN_FILES * 4:
                truncated = True
                break
            path = Path(directory) / name
            if path.is_symlink() or path.suffix.lower() not in SOURCE_SUFFIXES: continue
            size = path.stat().st_size
            if len(entries) >= MAX_SCAN_FILES or total + size > MAX_SCAN_BYTES:
                truncated = True
                break
            total += size
            content = path.read_text(encoding="utf-8", errors="replace")
            specs, dynamic = imports(content, path.suffix.lower())
            entries.append((path, specs, dynamic))
        if truncated: break
    return {"entries": entries, "truncated": truncated, "bytes": total, "limits": {"files": MAX_SCAN_FILES, "bytes": MAX_SCAN_BYTES}, "limitations": ["Lexical static scan, not a parser or bundler", "Custom aliases, generated imports, plugins, CSS/media references and runtime assembly may require manual review", "Assets, fonts, environment variables, client boundaries and license notices require additional project review"]}


def audit_receipt(root: Path) -> tuple[dict, list[dict]]:
    """Check consistency with the cached bytes, not publisher authenticity/rights."""
    receipt_file = root / RECEIPT
    if not receipt_file.is_file():
        return {"status": "missing", "problems": [], "limitation": "No receipt was supplied; this is not proof that source was never obtained"}, []
    problems, integrity = [], []
    try:
        receipt = load_json(inside(root, RECEIPT, True))
        if not isinstance(receipt, dict) or receipt.get("schema_version") != 1:
            raise ValueError("Expected receipt schema_version:1 object")
        raw_file = inside(root, RESPONSE, True)
        if raw_file.stat().st_size > MAX_RESPONSE:
            raise ValueError("Cached response exceeds size limit")
        raw = raw_file.read_bytes()
        if digest(raw) != receipt.get("response_sha256"):
            problems.append("cached_response_hash_mismatch")
        registry = registry_data(json.loads(raw.decode("utf-8-sig")))
        if not registry:
            raise ValueError("Cached response is not an inline registry")
        expected = [{key: value for key, value in item.items() if key != "content"} for item in registry["files"]]
        if receipt.get("files") != expected:
            problems.append("receipt_manifest_differs_from_cached_response")
        fingerprint = digest("\n".join(sorted(item["sha256"] for item in registry["files"])).encode("ascii"))
        if receipt.get("content_fingerprint") != fingerprint:
            problems.append("receipt_content_fingerprint_mismatch")
        for key in ("dependencies", "dev_dependencies", "registry_dependencies", "source_version"):
            if receipt.get(key) != registry[key]: problems.append("receipt_" + key + "_differs_from_cached_response")
        for item in registry["files"]:
            path = inside(root, item["path"])
            integrity.append({"path": item["path"], "status": "missing" if not path.is_file() else "matches_received" if digest(path.read_bytes()) == item["sha256"] else "changed_since_received"})
    except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
        problems.append(str(error))
    return {"status": "inconsistent" if problems else "consistent_received", "problems": problems, "limitation": "Hashes establish consistency/freshness, not publisher authenticity, license, integration or runtime correctness"}, integrity


def check_package(root: Path) -> dict:
    root = root.resolve()
    info = scan(root)
    receipt_integrity, integrity = audit_receipt(root)
    receipt = load_json(root / RECEIPT) if receipt_integrity["status"] == "consistent_received" else {}
    metadata = load_json(root / "package.json") if (root / "package.json").is_file() else {}
    if not isinstance(metadata, dict): raise ValueError("package.json must be an object")
    declared = {package_name(item) for item in receipt.get("dependencies", []) + receipt.get("dev_dependencies", [])}
    declared |= set(dependencies(metadata.get("dependencies"))) | set(dependencies(metadata.get("devDependencies"))) | set(dependencies(metadata.get("peerDependencies")))
    external, external_imports, unresolved, graph, dynamic = set(), [], [], {}, []
    for path, specs, uncertain in info["entries"]:
        relative = path.relative_to(root).as_posix()
        graph[relative] = []
        if uncertain: dynamic.append(relative)
        for specifier in specs:
            target = resolve_import(root, path, specifier)
            if not target and path.suffix.lower() in {".html", ".htm", ".css"} and not re.match(r"^(?:[/@~#]|[a-zA-Z]+:)", specifier):
                target = resolve_import(root, path, "./" + specifier)
            if target:
                graph[relative].append(target.relative_to(root).as_posix())
            elif specifier.startswith((".", "/", "@/", "~/")):
                unresolved.append({"file": relative, "specifier": specifier, "status": "unresolved_static; aliases/custom bundler may resolve in the target project"})
            elif not re.match(r"^(?:https?:|data:|mailto:|tel:|[?#]|node:)", specifier):
                external.add(package_name(specifier))
                external_imports.append({"file": relative, "specifier": specifier, "package": package_name(specifier)})
    status = "gaps" if external - declared or unresolved or receipt_integrity["status"] == "inconsistent" or any(row["status"] == "missing" for row in integrity) or receipt.get("registry_dependencies") else "unknown" if dynamic or info["truncated"] else "no_static_gaps_observed"
    return {"schema_version": 1, "static_status": status, "root": str(root), "scanned_files": len(info["entries"]), "scan_truncated": info["truncated"], "limits": info["limits"], "external_packages_observed": sorted(external), "external_imports": external_imports, "declared_packages": sorted(declared), "dependency_declaration_gaps": sorted(external - declared), "unresolved_local_imports": unresolved, "registry_dependencies_to_resolve": receipt.get("registry_dependencies", []), "dynamic_import_files": dynamic, "receipt_integrity": receipt_integrity, "received_file_integrity": integrity, "graph": graph, "limitations": info["limitations"] + [LIMITATION]}


def fetch_registry(url: str, project: Path, output: str, source_id: str | None = None) -> dict:
    project = project.resolve()
    if not project.is_dir(): raise ValueError("Project root must already exist")
    target = inside(project, output)
    if target.exists(): raise ValueError("Output must be a new directory; existing files/directories are never overwritten")
    response = retrieve(url)
    inspected, registry = inspect_response(response)
    if not registry or inspected.get("access") != "source_available":
        return {**inspected, "written": False, "reason": "fetch supports explicit inline registry JSON only; select an authorized source/export route for other formats"}
    # Validate the entire plan before any writes; downloaded path/target never
    # chooses a destination outside the explicit new package directory.
    for entry in registry["files"]: inside(target, entry["path"])
    target.mkdir(parents=True, exist_ok=False)
    for entry in registry["files"]:
        destination = inside(target, entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream: stream.write(entry["content"].encode("utf-8"))
    cache = target / ".source"
    cache.mkdir()
    (target / RESPONSE).write_bytes(response["body"])
    receipt = {key: value for key, value in inspected.items() if key not in {"text_sample", "links", "limitation"}}
    receipt.update(schema_version=1, publisher_id=source_id, fetched_at=now(), project_relative_output=output, response_cache=RESPONSE, source_version=registry["source_version"], origin_status="received; not integrated", rights="unverified; preserve notices and check publisher, third-party and media terms", content_fingerprint=digest("\n".join(sorted(item["sha256"] for item in registry["files"])).encode("ascii")))
    (target / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    package = check_package(target)
    return {"written": True, "output": str(target), "receipt": str(target / RECEIPT), "files_received": len(registry["files"]), "response_sha256": receipt["response_sha256"], "source_version": registry["source_version"], "package_check": {key: value for key, value in package.items() if key != "graph"}, "limitation": LIMITATION}


def source_list(kind=None, platform=None, source_id=None) -> dict:
    data = load_json(ADAPTERS)
    entries = data["sources"]
    if source_id: entries = [entry for entry in entries if entry["id"] == source_id]
    if kind: entries = [entry for entry in entries if kind in entry["kinds"]]
    if platform: entries = [entry for entry in entries if platform in entry["platforms"]]
    return {"schema_version": data["schema_version"], "count": len(entries), "sources": entries, "note": "Capability map, not a live health check. MCP/documented routes are not connected or executed by this CLI. Choose sources for the current task; the order is not a compulsory crawl."}


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def current_files(files, project: Path) -> bool:
    if not isinstance(files, dict) or not files:
        return False
    for relative, expected in files.items():
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            return False
        try:
            if digest(inside(project, relative, True).read_bytes()) != expected: return False
        except (ValueError, OSError, TypeError):
            return False
    return True


def selection_review(profile, decision: dict, candidate_map: dict) -> dict:
    """Check declared search/comparison structure, never actual relevance or truth.

    A receipt demonstrates delivery. It must not silently become evidence that
    a first result was selected against the project's design direction.
    """
    findings = []
    def issue(code, message): findings.append({"code": code, "message": message})
    def strings(value): return isinstance(value, list) and bool(value) and all(nonempty(x) for x in value)
    research = decision.get("research")
    if not isinstance(research, dict):
        return {"status": "missing", "findings": [{"code": "research_missing", "message": "Selected resource needs actual tag-based discovery, inspected alternatives and closure, or a scoped existing/exact basis"}]}
    closure = research.get("closure", {})
    if not isinstance(closure, dict): closure = {}
    route = closure.get("status")
    if route not in ("compared", "exact_user_reference", "current_project_basis", "unresolved"):
        issue("research_closure_missing", "Use compared/exact_user_reference/current_project_basis/unresolved closure")
    inspections = research.get("inspections", [])
    if not isinstance(inspections, list):
        issue("research_inspections_invalid", "Inspections must be an array"); inspections = []
    inspected = {}
    for item in inspections:
        if not isinstance(item, dict): issue("research_inspection_invalid", "Inspection must be an object"); continue
        cid = item.get("candidate_id")
        if not nonempty(cid) or cid not in candidate_map or cid in inspected:
            issue("research_inspection_origin", "Each inspection needs one unique actual candidate_id"); continue
        inspected[cid] = item
        if not strings(item.get("evidence")):
            issue("research_inspection_evidence", "Candidate detail/code/media inspection needs actual evidence references; a feed title alone is insufficient")
        observations = item.get("observations", {})
        if not isinstance(observations, dict) or any(not nonempty(observations.get(axis)) for axis in ("style", "composition", "ux", "material", "feasibility")):
            issue("research_fit_missing", "Inspect style, composition, UX, actual project material and implementation feasibility separately")
        prior = item.get("prior_use", {})
        if not isinstance(prior, dict) or prior.get("status") not in ("new", "same_project", "other_project", "unknown"):
            issue("research_prior_use_missing", "Record known new/same_project/other_project/unknown use; do not invent history")
        elif prior.get("status") in ("same_project", "other_project") and not nonempty(prior.get("reference")):
            issue("research_prior_use_reference", "Known reuse needs the actual available prior project/component reference")
        if isinstance(prior, dict) and prior.get("status") == "other_project" and not nonempty(prior.get("reason")):
            issue("research_reuse_basis_missing", "Reuse from another project needs a current task-specific requalification; cache familiarity is not a selection basis")
    selected = decision.get("selection", {})
    winner = selected.get("candidate_id") if isinstance(selected, dict) else None
    if not isinstance(winner, str) or winner not in inspected:
        issue("research_winner_not_inspected", "Selected origin must have its own detail/property inspection")
    if route in ("exact_user_reference", "current_project_basis"):
        basis = closure.get("basis", {})
        expected = ("prompt", "answer") if route == "exact_user_reference" else ("project",)
        if not isinstance(basis, dict) or basis.get("type") not in expected or not nonempty(basis.get("reference")) or not nonempty(basis.get("text")):
            issue("research_exception_basis_missing", "Exact user reference/current-product basis needs its actual scoped instruction or current-project evidence")
        if route == "current_project_basis" and isinstance(winner, str) and winner in inspected:
            prior = inspected[winner].get("prior_use", {})
            if not isinstance(prior, dict) or prior.get("status") != "same_project":
                issue("research_current_project_mismatch", "Another brand's cached component is not an approved basis of this current project")
        return {"status": "gaps" if findings else "scoped_basis_recorded", "route": route, "inspected": len(inspected), "findings": findings}
    if route == "unresolved":
        issue("research_unresolved", "Search limitations remain open; a preliminary implementation is not completed selection")
        if not nonempty(closure.get("reason")): issue("research_limit_reason_missing", "Unresolved research needs the actual limitation and next route")
    if not isinstance(profile, dict): profile = {}
    tags = profile.get("tags", {})
    if profile.get("origin") not in ("given", "derived", "mixed") or not nonempty(profile.get("basis")) or not isinstance(tags, dict) or any(not strings(tags.get(axis)) for axis in ("style", "composition", "ux", "platform")):
        issue("research_profile_missing", "Need task-derived or given style/composition/UX/platform tags and their brief basis before ordinary selection")
    normalize = lambda value: " ".join(value.casefold().split())
    project_tags = {normalize(value) for key, values in tags.items() if key != "avoid" and isinstance(values, list) for value in values if nonempty(value)} if isinstance(tags, dict) else set()
    queries = research.get("queries", [])
    if not isinstance(queries, list): issue("research_queries_invalid", "Queries must be an array"); queries = []
    query_ids, discovered, tagged_search = set(), set(), False
    scopes = ("tag", "category", "semantic_search", "targeted_search", "registry_index", "exact_item", "homepage", "featured")
    for query in queries:
        if not isinstance(query, dict): issue("research_query_invalid", "Query must be an object"); continue
        qid = query.get("id")
        if not nonempty(qid) or qid in query_ids:
            issue("research_query_identity", "Queries need unique nonempty IDs"); continue
        refines = query.get("refines")
        if refines is not None and (not isinstance(refines, str) or refines not in query_ids):
            issue("research_query_refinement", "Refinement must refer to an earlier actual query")
        query_ids.add(qid)
        scope, status = query.get("scope"), query.get("status")
        if scope not in scopes or status not in ("results", "empty", "blocked", "planned"):
            issue("research_query_status", "Record actual query scope and results/empty/blocked/planned status")
        if not nonempty(query.get("source_url")) or query.get("channel") not in ("mcp", "api", "cli", "http", "search") or not nonempty(query.get("query")):
            issue("research_query_route", "Query needs actual source, channel and executed query/filter description")
        if status != "planned" and not strings(query.get("evidence")):
            issue("research_query_evidence", "Executed search needs returned material/error evidence; a query plan does not count")
        results = query.get("result_ids", [])
        if not isinstance(results, list) or not all(nonempty(cid) and cid in candidate_map for cid in results):
            issue("research_query_results", "Result IDs must resolve to actual candidate records"); results = []
        if status == "results" and not results:
            issue("research_query_results_missing", "A results claim needs actual candidate IDs")
        if status == "results" and strings(query.get("evidence")):
            discovered.update(results)
            if scope in ("tag", "category", "semantic_search", "targeted_search", "registry_index") and strings(query.get("tags")):
                if {normalize(value) for value in query["tags"]} & project_tags:
                    tagged_search = True
                else:
                    issue("research_query_tags_unlinked", "Discovery tags must refer to the project profile; provider translations belong in the actual query/filter description")
    if not tagged_search:
        issue("research_tag_search_missing", "Home/featured feeds, exact familiar names and planned queries do not replace executed task-tag discovery inside catalogs or targeted programmatic search")
    comparison = research.get("comparison", {})
    if not isinstance(comparison, dict): comparison = {}
    alternatives = comparison.get("alternative_ids", [])
    if not strings(alternatives) or len(set(alternatives)) != len(alternatives):
        issue("research_alternative_missing", "Ordinary selection needs a genuinely different inspected alternative for the same task"); alternatives = []
    for cid in alternatives:
        if cid == winner or cid not in inspected:
            issue("research_alternative_uninspected", "Alternative must be a different actually inspected candidate")
        if cid not in discovered:
            issue("research_alternative_not_discovered", "Alternative needs a recorded discovery path, not a name invented after selection")
        if isinstance(winner, str) and winner in candidate_map and cid in candidate_map:
            # A common layout may have materially different UX. Do not infer
            # equivalence from matching prose; only honor an explicit cosmetic group.
            group = candidate_map[winner].get("cosmetic_variant_of")
            if nonempty(group) and group == candidate_map[cid].get("cosmetic_variant_of"):
                issue("research_structure_not_distinct", "Known purely cosmetic variants of one solution do not establish a materially different alternative")
    if isinstance(winner, str) and winner not in discovered:
        issue("research_winner_not_discovered", "Winner needs an actual discovery path under this task")
    if any(not nonempty(comparison.get(field)) for field in ("choice_reason", "tradeoffs", "structure_difference")):
        issue("research_comparison_missing", "Explain current-project choice, tradeoffs and meaningful structural/UX differences before acceptance")
    return {"status": "gaps" if findings else "comparison_recorded", "route": route, "inspected": len(inspected), "queries": len(queries), "findings": findings}


def structural_coverage(state: dict, project: Path) -> dict:
    if not isinstance(state, dict) or not isinstance(state.get("decisions"), list):
        raise ValueError("State must contain a decisions array")
    project = project.resolve()
    package = check_package(project)
    graph = package["graph"]
    findings, reports = [], []
    seen_ids = set()
    def issue(decision, code, message): findings.append({"decision": decision, "code": code, "message": message})
    if state.get("schema_version") != 1:
        issue("project", "schema_version_invalid", "Expected schema_version:1 state")
    if state.get("mode") not in ("new", "redesign", "local"):
        issue("project", "mode_invalid", "Expected mode new/redesign/local")
    if package["scan_truncated"]:
        issue("project", "scan_truncated", "Scan limits were reached; unscanned application paths remain unknown")
    decisions = state["decisions"]
    scope = state.get("resource_scope", {})
    basis = scope.get("basis", {}) if isinstance(scope, dict) else {}
    explicit_omission = (isinstance(scope, dict) and scope.get("status") == "no_external_research"
                         and nonempty(scope.get("reason")) and isinstance(basis, dict)
                         and basis.get("type") in {"prompt", "answer", "delegation", "project"}
                         and nonempty(basis.get("reference")) and nonempty(basis.get("text")))
    omitted = not decisions and (state.get("mode") == "local" or explicit_omission)
    if not decisions and not omitted:
        issue("project", "decisions_missing", "No resource decisions recorded for this scope; absence is not completed research")
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            issue(str(index), "decision_invalid", "Decision must be an object")
            continue
        identity = decision.get("id")
        if not nonempty(identity): identity = f"(missing id {index})"
        if identity in seen_ids: issue(identity, "duplicate_id", "Decision IDs must be unique")
        seen_ids.add(identity)
        for field in ("id", "section", "intent", "state"):
            if not nonempty(decision.get(field)): issue(identity, "missing_" + field, f"Missing {field}")
        decision_state = decision.get("state")
        if decision_state not in ("open", "selected", "implemented", "verified", "blocked"):
            issue(identity, "invalid_state", "Decision state must be open/selected/implemented/verified/blocked")
        candidates = decision.get("candidates", [])
        if not isinstance(candidates, list):
            issue(identity, "candidates_invalid", "Candidates must be an array"); candidates = []
        candidate_map = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                issue(identity, "candidate_invalid", "Candidate must be an object"); continue
            cid = candidate.get("id")
            if not nonempty(cid) or cid in candidate_map:
                issue(identity, "candidate_identity", "Candidates need unique nonempty string IDs")
                continue
            candidate_map[cid] = candidate
            if not nonempty(candidate.get("url")): issue(identity, "candidate_origin_missing", "Candidate needs the actual material URL; a provider name alone is insufficient")
            if candidate.get("status") not in ("considered", "selected", "rejected", "blocked"):
                issue(identity, "candidate_status_invalid", "Candidate status must be considered/selected/rejected/blocked")
            if candidate.get("status") == "rejected" and not (nonempty(candidate.get("reason")) and nonempty(candidate.get("alternative"))):
                issue(identity, "rejection_incomplete", "Rejected candidate needs a concrete reason and an alternative route/candidate; rejection alone does not close the task")
        selection = decision.get("selection") or {}
        implementation = decision.get("implementation") or {}
        if not isinstance(selection, dict):
            issue(identity, "selection_invalid", "Selection must be an object"); selection = {}
        if not isinstance(implementation, dict):
            issue(identity, "implementation_invalid", "Implementation must be an object"); implementation = {}
        status = selection.get("status")
        final_origin = status in ("integrated", "adapted", "own_implementation", "inspiration_only")
        paths, entrypoints = implementation.get("paths", []), implementation.get("entrypoints", [])
        for label, values in (("paths", paths), ("entrypoints", entrypoints)):
            if not isinstance(values, list) or not all(nonempty(value) for value in values):
                issue(identity, "implementation_" + label + "_invalid", label + " must be an array of relative paths")
        if not isinstance(paths, list) or not all(nonempty(value) for value in paths): paths = []
        if not isinstance(entrypoints, list) or not all(nonempty(value) for value in entrypoints): entrypoints = []
        reachability, provenance_status = "not_claimed", "not_claimed"
        if final_origin:
            cid = selection.get("candidate_id")
            if not isinstance(cid, str) or cid not in candidate_map:
                issue(identity, "selection_origin_missing", "Selected origin must resolve to an actual considered/studied material record")
            elif candidate_map[cid].get("status") == "rejected":
                issue(identity, "selected_rejected", "A rejected candidate cannot simultaneously be the selected origin")
            if not nonempty(selection.get("property")):
                issue(identity, "selected_property_missing", "Describe the observable property, not just a component name")
        elif decision_state in ("selected", "implemented", "verified"):
            issue(identity, "selection_status_missing", "Closed implementation needs integrated/adapted/own_implementation/inspiration_only origin status")
        if status == "own_implementation" and not nonempty(decision.get("reason")):
            issue(identity, "own_basis_missing", "Own implementation needs a task-specific basis after considering ready solutions")
        research_status = "not_selected"
        if final_origin and decision_state in ("selected", "implemented", "verified"):
            review = selection_review(state.get("research_profile"), decision, candidate_map)
            research_status = review["status"]
            for finding in review["findings"]: issue(identity, finding["code"], finding["message"])
        if final_origin and decision_state in ("implemented", "verified"):
            if not paths or not entrypoints:
                issue(identity, "implementation_trace_missing", "Implementation claims need actual paths and application entrypoints")
            pending, reachable = [], set()
            for relative in entrypoints:
                try: pending.append(inside(project, relative, True).relative_to(project).as_posix())
                except (ValueError, OSError) as error: issue(identity, "entrypoint_missing", str(error))
            while pending:
                current = pending.pop()
                if current in reachable: continue
                reachable.add(current)
                pending.extend(graph.get(current, []))
            resolved_paths = []
            for relative in paths:
                try: resolved_paths.append(inside(project, relative, True).relative_to(project).as_posix())
                except (ValueError, OSError) as error: issue(identity, "implementation_missing", str(error))
            reachability = "reachable_static" if resolved_paths and all(relative in reachable for relative in resolved_paths) else "unknown"
            if reachability == "unknown":
                issue(identity, "reachability_unknown", "Static application path was not established; unknown does not mean unused or passed")
            if set(package["dynamic_import_files"]) & reachable:
                reachability = "unknown_edges"
                issue(identity, "dynamic_edges_unknown", "Application branch includes nonliteral imports; runtime/bundler analysis remains required")
            unresolved = [row for row in package["unresolved_local_imports"] if row["file"] in reachable]
            if unresolved:
                issue(identity, "local_imports_unresolved", "Application branch has unresolved helper/media imports; inspect the package report")
            branch_dependencies = {row["package"] for row in package["external_imports"] if row["file"] in reachable}
            if branch_dependencies - set(package["declared_packages"]):
                issue(identity, "dependency_declarations_missing", "Observed application-branch packages have no declaration in the scanned project/receipt; this does not inspect installed packages")
            if status in ("integrated", "adapted"):
                receipt_path = implementation.get("receipt")
                provenance = implementation.get("provenance")
                if receipt_path:
                    try:
                        receipt_file = inside(project, receipt_path, True)
                        if receipt_file.name != "receipt.json" or receipt_file.parent.name != ".source":
                            raise ValueError("A CLI receipt must be .source/receipt.json beside its cached response")
                        audit, received = audit_receipt(receipt_file.parent.parent)
                        provenance_status = audit["status"]
                        if audit["status"] != "consistent_received":
                            issue(identity, "receipt_invalid", "; ".join(audit["problems"]) or "Receipt missing")
                        if any(row["status"] == "missing" for row in received):
                            issue(identity, "received_file_missing", "A received source file is missing; resolve/document the adapted package")
                        source_map = implementation.get("source_map", {})
                        if not isinstance(source_map, dict):
                            issue(identity, "source_map_invalid", "source_map must map received relative paths to current project-relative implementation paths"); source_map = {}
                        received_names = {row["path"] for row in received}
                        mapped = set()
                        for original in received_names:
                            original_path = inside(receipt_file.parent.parent, original).relative_to(project).as_posix()
                            mapped.add(original_path)
                        for original, adapted in source_map.items():
                            try:
                                if original not in received_names: raise ValueError("source_map origin is absent from this receipt")
                                mapped.add(inside(project, adapted, True).relative_to(project).as_posix())
                            except (ValueError, OSError, TypeError) as error: issue(identity, "source_map_invalid", str(error))
                        if not set(resolved_paths).issubset(mapped):
                            issue(identity, "source_map_missing", "Current paths must be received files or explicitly mapped adaptations; an unrelated valid receipt is insufficient")
                    except (ValueError, OSError, TypeError) as error:
                        issue(identity, "receipt_invalid", str(error))
                elif isinstance(provenance, dict):
                    provenance_status = "external_self_reported"
                    if provenance.get("kind") not in ("mcp", "authorized_export", "author_repo") or not nonempty(provenance.get("source_url")):
                        issue(identity, "provenance_invalid", "External provenance needs kind mcp/authorized_export/author_repo and actual source_url")
                    evidence = provenance.get("evidence")
                    if not isinstance(evidence, list) or not evidence or not all(nonempty(value) for value in evidence):
                        issue(identity, "provenance_evidence_missing", "External provenance needs locally captured evidence artifact paths")
                    else:
                        for relative in evidence:
                            try: inside(project, relative, True)
                            except (ValueError, OSError) as error: issue(identity, "provenance_evidence_invalid", str(error))
                    if not current_files(provenance.get("files"), project) or not set(resolved_paths).issubset(provenance.get("files", {})):
                        issue(identity, "provenance_files_stale", "External provenance needs matching current SHA256 hashes for implementation files")
                    if provenance.get("source_version") is not None and not nonempty(provenance.get("source_version")):
                        issue(identity, "provenance_version_invalid", "Version is a known release/commit string, or null/omitted when unavailable")
                else:
                    issue(identity, "provenance_missing", "Integrated/adapted claims need a consistent CLI receipt or captured authorized MCP/export/repository provenance")
        checks = decision.get("checks", [])
        if not isinstance(checks, list):
            issue(identity, "checks_invalid", "Checks must be an array"); checks = []
        property_checks = []
        for check in checks:
            if not isinstance(check, dict):
                issue(identity, "check_invalid", "Check must be an object"); continue
            if not isinstance(check.get("required", True), bool):
                issue(identity, "check_required_invalid", "Check required must be boolean")
            check_status = check.get("status")
            if check_status not in ("required", "passed", "failed", "unverified", "not_applicable"):
                issue(identity, "check_status_invalid", "Unknown check status")
            if check_status == "failed" or (check.get("required", True) and check_status in ("required", "unverified")):
                issue(identity, "check_pending", "Required/failed check remains unresolved")
            if check_status in ("unverified", "not_applicable") and not nonempty(check.get("reason")):
                issue(identity, "check_reason_missing", "Unverified/not_applicable needs a concrete reason")
            evidence = check.get("evidence")
            observed = (check_status == "passed" and nonempty(check.get("action")) and nonempty(check.get("observation"))
                        and isinstance(evidence, list) and evidence and all(nonempty(value) for value in evidence)
                        and isinstance(check.get("environment"), dict) and check["environment"]
                        and current_files(check.get("files"), project))
            if check_status == "passed" and not observed:
                issue(identity, "passed_check_incomplete", "Passed is self-reported and requires action, observation, evidence[], environment and matching current file hashes")
            if observed and check.get("kind") in ("source_property", "property") and set(paths).issubset(check["files"]):
                property_checks.append(check)
        if final_origin and decision_state in ("implemented", "verified") and not property_checks:
            issue(identity, "property_review_missing", "Current implementation needs a source-property observation; an import/receipt alone does not show the property survived")
        if decision_state in ("open", "selected", "blocked"):
            issue(identity, "decision_open", "Decision remains open/selected/blocked; preserve the limitation and next route")
        reports.append({"id": identity, "state": decision_state, "origin_status": status,
                        "research_status": research_status,
                        "static_reachability": reachability, "provenance_status": provenance_status,
                        "candidate_count": len(candidates), "reported_current_property_checks": len(property_checks),
                        "evidence_status": "self_reported; hashes check freshness only, never observation truth"})
    return {"schema_version": 1, "structural_status": "gaps" if findings else "not_applicable" if omitted else "structurally_recorded",
            "decisions": reports, "findings": findings, "project_scan_truncated": package["scan_truncated"],
            "static_scan_limits": package["limits"], "limitation": LIMITATION + " Coverage does not assert all project decisions were listed, chosen entrypoints actually render, branches execute, provenance is authentic or a self-reported passed check is true."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sources = sub.add_parser("sources", help="Filter the saved entries + Awwwards + Colorsinspo capability map (no network)")
    sources.add_argument("--kind"); sources.add_argument("--platform"); sources.add_argument("--id")
    inspect = sub.add_parser("inspect", help="Bounded public HTTPS read; summarize registry/metadata/HTML honestly")
    inspect.add_argument("url")
    fetch = sub.add_parser("fetch", help="Receive selected inline registry files; no install or overwrite")
    fetch.add_argument("url"); fetch.add_argument("--project", required=True, type=Path); fetch.add_argument("--output", required=True); fetch.add_argument("--source")
    check = sub.add_parser("check-package", help="Static imports/helpers and received-file audit; never executes code")
    check.add_argument("path", type=Path)
    coverage = sub.add_parser("coverage", help="Check structural trace of the explicit design-state decisions")
    coverage.add_argument("state", type=Path); coverage.add_argument("--project", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "sources": result = source_list(args.kind, args.platform, args.id)
        elif args.command == "inspect": result = inspect_response(retrieve(args.url))[0]
        elif args.command == "fetch":
            if args.source and not source_list(source_id=args.source)["sources"]: raise ValueError("Unknown source ID")
            result = fetch_registry(args.url, args.project, args.output, args.source)
        elif args.command == "check-package":
            result = check_package(args.path); result.pop("graph")
        else: result = structural_coverage(load_json(args.state), args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "coverage" and result["findings"]: return 1
        if args.command == "check-package" and result["static_status"] in {"gaps", "unknown"}: return 1
        if args.command in {"inspect", "fetch"} and result.get("access") in {"auth_required", "payment_required", "access_denied", "challenge", "not_found", "rate_limited", "network_error", "http_error", "unparseable"}: return 1
        if args.command == "fetch" and result.get("written") is False: return 1
        return 0
    except (ValueError, OSError, UnicodeError, TypeError) as error:
        print(json.dumps({"error": str(error), "command": args.command}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
