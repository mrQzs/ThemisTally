"""Deterministic offline Markdown checks for builtin docs plugins.

The checker consumes an immutable in-memory snapshot supplied by its caller. It
never follows a URL, reads arbitrary paths, or claims semantic content review.
"""
from __future__ import annotations

import copy
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any, Mapping, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit

from .builtin_artifacts import ArtifactError, digest, resource_ref, validate_artifact

try:  # markdown-it-py is available only in the WSL verification environment.
    from markdown_it import MarkdownIt  # type: ignore
except ImportError:  # pragma: no cover - exercised on Windows Python 3.9
    MarkdownIt = None  # type: ignore

MAX_BYTES = 1_048_576
MAX_FILES = 4096
MAX_TOTAL_BYTES = 16 * 1_048_576
_PROFILE = "commonmark-explicit-anchors-v1"
_EXTERNAL_STATUSES = {"NOT_CHECKED_EXTERNAL", "NOT_CHECKED_NONFILE"}
_OK_STATUSES = {"LOCAL_OK"}
_FINDING_STATUSES = {
    "BROKEN_FRAGMENT", "BROKEN_LOCAL_LINK", "DIRECTORY_TARGET_UNSUPPORTED",
    "DUPLICATE_ANCHOR", "FORBIDDEN_PATH", "FORBIDDEN_SCHEME", "INVALID_URL",
    "LOCAL_OK", "NOT_CHECKED_EXTERNAL", "NOT_CHECKED_NONFILE",
    "UNSUPPORTED_FRAGMENT_TARGET", "UNSUPPORTED_HTML", "UNSUPPORTED_QUERY",
}
_PARSER_PROFILES = {"markdown-it-py", "fallback-commonmark-subset"}


def _repo_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ArtifactError("E_DOC_PATH", "/path", "non-empty repository-relative path required")
    if value.startswith("/") or "\\" in value or ":" in value:
        raise ArtifactError("E_DOC_PATH", "/path", "absolute or platform path forbidden")
    parts = value.split("/")
    if any(x in {"", ".", ".."} for x in parts):
        raise ArtifactError("E_DOC_PATH", "/path", "empty, dot and traversal segments forbidden")
    if any(ord(ch) < 32 or 0x7F <= ord(ch) <= 0x9F for ch in value):
        raise ArtifactError("E_DOC_PATH", "/path", "control character forbidden")
    return value


class Snapshot(object):
    """Immutable-by-copy fixture file map; regular files only."""
    def __init__(self, files: Mapping[str, bytes]):
        if not isinstance(files, Mapping) or len(files) > MAX_FILES:
            raise ArtifactError("E_DOC_SNAPSHOT", "/", "bounded file mapping required")
        result = {}
        folded = set()
        total_bytes = 0
        for raw_path, raw_data in files.items():
            path = _repo_path(raw_path)
            if not isinstance(raw_data, bytes) or len(raw_data) > MAX_BYTES:
                raise ArtifactError("E_DOC_RESOURCE", path, "UTF-8 bytes within size limit required")
            total_bytes += len(raw_data)
            if total_bytes > MAX_TOTAL_BYTES:
                raise ArtifactError("E_DOC_LIMIT", "/", "snapshot exceeds total byte limit")
            key = path.casefold()
            if key in folded:
                raise ArtifactError("E_DOC_PATH_COLLISION", path, "portable path collision")
            folded.add(key)
            result[path] = bytes(raw_data)
        self._files = result

    def read(self, path: str) -> bytes:
        path = _repo_path(path)
        try:
            return self._files[path]
        except KeyError:
            raise ArtifactError("E_DOC_RESOURCE_MISSING", path, "snapshot resource missing")

    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._files))

    def ref(self, path: str, kind: str = "file", ident: str = "snapshot") -> dict:
        return {"kind": kind, "id": ident, "path": _repo_path(path), "sha256": digest(self.read(path))}

    def verify(self, ref: Mapping[str, Any]) -> bytes:
        resource_ref(ref, "/resource_ref")
        data = self.read(ref["path"])
        if digest(data) != ref["sha256"]:
            raise ArtifactError("E_DOC_RESOURCE_DRIFT", ref["path"], "snapshot bytes do not match reference")
        return data


def _html_facts(content: str) -> Tuple[list, list, list]:
    class Facts(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self, convert_charrefs=True)
            self.links, self.anchors, self.unsupported = [], [], []
        def handle_starttag(self, tag, attrs):
            if tag not in {"a", "img", "br"}:
                self.unsupported.append(tag)
            attr = dict(attrs)
            if attr.get("id"):
                self.anchors.append(attr["id"])
            if tag == "a" and attr.get("name"):
                self.anchors.append(attr["name"])
            for key in ("href", "src"):
                if attr.get(key) is not None:
                    self.links.append(attr[key])
        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
    parser = Facts()
    try:
        parser.feed(content); parser.close()
    except Exception as exc:
        raise ArtifactError("E_DOC_HTML", "/", "invalid inline HTML") from exc
    return parser.links, parser.anchors, parser.unsupported


def _fallback_facts(text: str) -> Tuple[list, list, list]:
    """Small CommonMark-compatible subset used when markdown-it-py is absent.

    Fenced code, indented code and code spans are masked before links are
    extracted. Reference definitions are resolved from their literal targets.
    Unknown constructs remain unclaimed rather than being treated as links.
    """
    links, anchors, unsupported = [], [], []
    lines = text.splitlines()
    masked = []
    fenced = False; fence = ""
    definitions = {}
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not fenced:
                fenced, fence = True, marker
            elif marker == fence:
                fenced = False
            masked.append("")
            continue
        if fenced or line.startswith("    "):
            masked.append("")
            continue
        m = re.match(r"^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))(?:\s+.*)?$", line)
        if m:
            key = m.group(1).strip().casefold()
            # CommonMark uses the first definition when a label is repeated.
            definitions.setdefault(key, m.group(2) or m.group(3))
            masked.append("")
        else:
            masked.append(line)
    source = "\n".join(masked)
    # Remove inline code spans while preserving positions enough for matching.
    source = re.sub(r"(`+)(?:.|\n)*?\1", "", source)
    # Inline and reference links/images. Nested label parsing is intentionally
    # conservative: malformed labels produce no finding and are left UNKNOWN.
    pattern = re.compile(r"(!?)\[([^\]\n]+)\](?:\((?:<([^>\n]*)>|([^\s)]+))(?:\s+[^)]*)?\)|\[([^\]\n]*)\])")
    for match in pattern.finditer(source):
        target = match.group(3) or match.group(4)
        if target is None:
            key = (match.group(5) or match.group(2)).strip().casefold()
            target = definitions.get(key)
            if target is None:
                continue
        links.append(target)
    # CommonMark shortcut reference links use a definition without a second
    # bracket pair, e.g. ``[guide]`` with ``[guide]: guide.md`` below.
    shortcut = re.compile(r"(?<![!A-Za-z0-9_])\[([^\]\n]+)\](?!\s*(?:\(|\[))")
    for match in shortcut.finditer(source):
        target = definitions.get(match.group(1).strip().casefold())
        if target is not None:
            links.append(target)
    # Explicit HTML is parsed independently from markdown links.
    for html in re.findall(r"<(?:(?:a|img|br)\b[^>]*|[A-Za-z][^>]*)>", source):
        hlinks, hanchors, hunsupported = _html_facts(html)
        links.extend(hlinks); anchors.extend(hanchors); unsupported.extend(hunsupported)
    return links, anchors, unsupported


def markdown_facts(data: bytes) -> Tuple[list, list, list]:
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ArtifactError("E_DOC_LIMIT", "/", "document exceeds byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError("E_DOC_ENCODING", "/", "UTF-8 Markdown required") from exc
    if text.startswith("\ufeff"):
        raise ArtifactError("E_DOC_ENCODING", "/", "BOM is not accepted")
    if MarkdownIt is None:
        return _fallback_facts(text)
    parser = MarkdownIt("commonmark", {"maxNesting": 64})
    parser.validateLink = lambda url: True
    try:
        tokens = parser.parse(text)
    except Exception as exc:
        raise ArtifactError("E_DOC_PARSE", "/", "CommonMark parse failed") from exc
    links, anchors, unsupported = [], [], []
    stack = list(reversed(tokens)); count = 0
    while stack:
        token = stack.pop(); count += 1
        if count > 100000:
            raise ArtifactError("E_DOC_LIMIT", "/", "AST token limit exceeded")
        if token.type in {"link_open", "image"}:
            links.append(token.attrGet("href") or token.attrGet("src") or "")
        elif token.type in {"html_inline", "html_block"}:
            hlinks, hanchors, hunsupported = _html_facts(token.content)
            links.extend(hlinks); anchors.extend(hanchors); unsupported.extend(hunsupported)
        if token.children:
            stack.extend(reversed(token.children))
    return links, anchors, unsupported


def local_target(source: str, url: str) -> Tuple[str, str, str]:
    """Classify a link without reading or contacting its target."""
    _repo_path(source)
    if not isinstance(url, str) or any(ord(ch) < 32 or 0x7F <= ord(ch) <= 0x9F for ch in url) or "\\" in url:
        return "FORBIDDEN_PATH", "", ""
    try:
        split = urlsplit(url)
    except ValueError:
        return "INVALID_URL", "", ""
    scheme = split.scheme.lower()
    if scheme in {"http", "https"} or (not scheme and split.netloc):
        return "NOT_CHECKED_EXTERNAL", "", ""
    if scheme in {"mailto", "tel"}:
        return "NOT_CHECKED_NONFILE", "", ""
    if scheme:
        return "FORBIDDEN_SCHEME", "", ""
    if split.query:
        return "UNSUPPORTED_QUERY", "", ""
    raw = split.path + split.fragment
    if re.search(r"%(?![0-9a-fA-F]{2})", raw):
        return "INVALID_URL", "", ""
    try:
        path, fragment = unquote(split.path, encoding="utf-8", errors="strict"), unquote(split.fragment, encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return "INVALID_URL", "", ""
    if any(ord(ch) < 32 or 0x7F <= ord(ch) <= 0x9F for ch in path + fragment) or "\\" in path or ":" in path:
        return "FORBIDDEN_PATH", "", ""
    if not path:
        return "LOCAL", source, fragment
    parts = source.split("/")[:-1] if not path.startswith("/") else []
    for segment in path.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if not parts:
                return "FORBIDDEN_PATH", "", ""
            parts.pop()
        else:
            parts.append(segment)
    if not parts:
        return "DIRECTORY_TARGET_UNSUPPORTED", "", ""
    return "LOCAL", "/".join(parts), fragment


def docs_check(snapshot: Snapshot, source_paths: Sequence[str]) -> dict:
    if isinstance(source_paths, (str, bytes)) or not isinstance(source_paths, Sequence):
        raise ArtifactError("E_DOC_SOURCE", "/source_paths", "a sequence of repository paths is required")
    findings = []
    cache = {}
    def facts(path):
        if path not in cache:
            cache[path] = markdown_facts(snapshot.read(path))
        return cache[path]
    normalized_paths = [_repo_path(p) for p in source_paths]
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ArtifactError("E_DOC_SOURCE", "/source_paths", "duplicate source path is ambiguous")
    paths = sorted(normalized_paths)
    for path in paths:
        links, anchors, unsupported = facts(path)
        if len(anchors) != len(set(anchors)):
            findings.append({"source": path, "target": "", "status": "DUPLICATE_ANCHOR"})
        for tag in sorted(set(unsupported)):
            findings.append({"source": path, "target": tag, "status": "UNSUPPORTED_HTML"})
        for href in links:
            state, target, fragment = local_target(path, href)
            if state == "LOCAL":
                if target not in snapshot.names():
                    state = "BROKEN_LOCAL_LINK"
                elif fragment:
                    if not target.endswith((".md", ".markdown")):
                        state = "UNSUPPORTED_FRAGMENT_TARGET"
                    else:
                        _, ids, bad = facts(target)
                        if bad:
                            state = "UNSUPPORTED_HTML"
                        elif len(ids) != len(set(ids)):
                            state = "DUPLICATE_ANCHOR"
                        else:
                            state = "LOCAL_OK" if fragment in ids else "BROKEN_FRAGMENT"
                else:
                    state = "LOCAL_OK"
            findings.append({"source": path, "target": href, "status": state})
    excluded = {"NOT_CHECKED_EXTERNAL", "NOT_CHECKED_NONFILE"}
    errors = [f for f in findings if f["status"] not in excluded | {"LOCAL_OK"}]
    return {"profile": _PROFILE, "findings": findings, "local_status": "SATISFIED" if not errors else "FAILED_OR_INCOMPLETE", "unchecked": sum(f["status"] in excluded for f in findings), "semantic_review": "NOT_PERFORMED", "parser": "markdown-it-py" if MarkdownIt is not None else "fallback-commonmark-subset"}


def _validate_docs_payload(payload: Any) -> dict:
    if not isinstance(payload, Mapping) or set(payload) != {"profile", "findings", "local_status", "unchecked", "semantic_review", "parser"}:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload", "closed docs-check payload required")
    if payload["profile"] != _PROFILE:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/profile", "unsupported docs-check profile")
    if type(payload["parser"]) is not str or payload["parser"] not in _PARSER_PROFILES:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/parser", "unsupported parser profile")
    if payload["semantic_review"] != "NOT_PERFORMED":
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/semantic_review", "semantic review is not performed by this plugin")
    if type(payload["unchecked"]) is not int or payload["unchecked"] < 0:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/unchecked", "non-negative integer required")
    findings = payload["findings"]
    if not isinstance(findings, list):
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/findings", "finding list required")
    normalized = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, Mapping) or set(finding) != {"source", "target", "status"}:
            raise ArtifactError("E_DOC_FINDING", f"/payload/findings/{index}", "closed finding required")
        if not isinstance(finding["source"], str) or not finding["source"]:
            raise ArtifactError("E_DOC_FINDING", f"/payload/findings/{index}/source", "source path required")
        if not isinstance(finding["target"], str):
            raise ArtifactError("E_DOC_FINDING", f"/payload/findings/{index}/target", "target must be text")
        if type(finding["status"]) is not str or finding["status"] not in _FINDING_STATUSES:
            raise ArtifactError("E_DOC_FINDING", f"/payload/findings/{index}/status", "unknown finding status")
        normalized.append({"source": finding["source"], "target": finding["target"], "status": finding["status"]})
    expected_unchecked = sum(row["status"] in _EXTERNAL_STATUSES for row in normalized)
    expected_status = "SATISFIED" if all(row["status"] in _OK_STATUSES | _EXTERNAL_STATUSES for row in normalized) else "FAILED_OR_INCOMPLETE"
    if payload["unchecked"] != expected_unchecked:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/unchecked", "unchecked count does not match findings")
    if payload["local_status"] != expected_status:
        raise ArtifactError("E_DOC_PAYLOAD", "/payload/local_status", "local status does not match findings")
    return {"profile": payload["profile"], "findings": normalized, "local_status": payload["local_status"], "unchecked": payload["unchecked"], "semantic_review": payload["semantic_review"], "parser": payload["parser"]}


def validate_docs_check(record: Mapping[str, Any]) -> dict:
    normalized = validate_artifact(record)
    if normalized["record_type"] != "docs-check":
        raise ArtifactError("E_DOC_PAYLOAD", "/record_type", "docs-check artifact required")
    if normalized["status"] == "PASS":
        raise ArtifactError("E_DOC_PRODUCTION_GATE", "/status", "PASS requires a trusted dispatcher receipt")
    normalized["payload"] = _validate_docs_payload(normalized["payload"])
    local_status = normalized["payload"]["local_status"]
    if normalized["status"] in {"READY", "PASS"}:
        raise ArtifactError("E_DOC_PRODUCTION_GATE", "/status", "docs-check cannot grant readiness or PASS")
    if local_status == "SATISFIED" and normalized["status"] == "FAIL":
        raise ArtifactError("E_DOC_PAYLOAD", "/status", "FAIL status contradicts satisfied local checks")
    if local_status == "FAILED_OR_INCOMPLETE" and normalized["status"] == "REFERENCE_ONLY":
        raise ArtifactError("E_DOC_PAYLOAD", "/status", "reference-only status requires satisfied local checks")
    declared = {ref["path"] for ref in normalized["source_refs"]}
    for index, finding in enumerate(normalized["payload"]["findings"]):
        if finding["source"] not in declared:
            raise ArtifactError("E_DOC_PROVENANCE", f"/payload/findings/{index}/source", "finding source is not declared in source_refs")
    return normalized


def build_docs_check(snapshot: Snapshot, source_paths: Sequence[str], *, source_refs: Sequence[Mapping[str, str]] = (), candidate_ref: Optional[Mapping[str, str]] = None, environment_ref: Optional[Mapping[str, str]] = None, artifact_id: str = "docs-check", producer_version: str = "1.0.0", status: Optional[str] = None) -> dict:
    if not isinstance(snapshot, Snapshot):
        raise ArtifactError("E_DOC_SNAPSHOT", "/snapshot", "Snapshot required")
    if isinstance(source_refs, (str, bytes)) or not isinstance(source_refs, Sequence):
        raise ArtifactError("E_DOC_PROVENANCE", "/source_refs", "a sequence of ResourceRef values is required")
    if isinstance(source_paths, (str, bytes)) or not isinstance(source_paths, Sequence):
        raise ArtifactError("E_DOC_SOURCE", "/source_paths", "a sequence of repository paths is required")
    normalized_paths = [_repo_path(p) for p in source_paths]
    if len(set(normalized_paths)) != len(normalized_paths):
        raise ArtifactError("E_DOC_SOURCE", "/source_paths", "duplicate source path is ambiguous")
    payload = docs_check(snapshot, source_paths)
    if len(source_refs) != len(normalized_paths):
        raise ArtifactError("E_DOC_PROVENANCE", "/source_refs", "one source reference is required for each source path")
    seen = set()
    normalized_refs = []
    for index, ref in enumerate(source_refs):
        if not isinstance(ref, Mapping):
            raise ArtifactError("E_DOC_PROVENANCE", f"/source_refs/{index}", "ResourceRef required")
        verified = snapshot.verify(ref)
        del verified
        path = resource_ref(ref, f"/source_refs/{index}")["path"]
        if path not in normalized_paths or path in seen:
            raise ArtifactError("E_DOC_PROVENANCE", f"/source_refs/{index}", "source reference does not match source paths")
        seen.add(path)
        normalized_refs.append(dict(ref))
    if seen != set(normalized_paths):
        raise ArtifactError("E_DOC_PROVENANCE", "/source_refs", "source reference coverage is incomplete")
    if status is None:
        status = "REFERENCE_ONLY" if payload["local_status"] == "SATISFIED" else "FAIL"
    if status is not None and type(status) is not str:
        raise ArtifactError("E_DOC_PRODUCTION_GATE", "/status", "status must be text or null")
    if status == "PASS":
        raise ArtifactError("E_DOC_PRODUCTION_GATE", "/status", "PASS requires a trusted dispatcher receipt")
    record = {"record_type": "docs-check", "schema_version": 1, "artifact_id": artifact_id, "producer": {"kind": "builtin-plugin", "id": "docs-checks", "version": producer_version}, "status": status, "source_refs": normalized_refs, "candidate_ref": None if candidate_ref is None else dict(candidate_ref), "environment_ref": None if environment_ref is None else dict(environment_ref), "payload": payload}
    return validate_docs_check(record)


__all__ = ["Snapshot", "markdown_facts", "local_target", "docs_check", "build_docs_check", "validate_docs_check"]
