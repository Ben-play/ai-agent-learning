#!/usr/bin/env python3
"""Build and validate a strict allowlisted GitHub Pages staging directory."""

from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import shutil
import stat
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT_FILES = (
    "index.html",
    "404.html",
    "offline.html",
    "manifest.webmanifest",
    "service-worker.js",
    ".nojekyll",
)
HTML_DIRECTORIES = ("lessons", "qa", "reference", "best-practices")
ASSET_FILES = (
    "assets/back-to-top.js",
    "assets/bottom-nav.js",
    "assets/content-tools.js",
    "assets/course-bar.js",
    "assets/course-catalog.js",
    "assets/lesson-times.json",
    "assets/overview-toggle.js",
    "assets/pwa.js",
    "assets/quiz.js",
    "assets/style.css",
    "assets/theme-toggle.js",
    "assets/toc.js",
    "assets/icons/icon-192.png",
    "assets/icons/icon-512.png",
    "assets/icons/icon-maskable-512.png",
)
README_FILES = (
    "code/phase1-python/phase1-practices-capstone/README.md",
    "code/phase2-model-selection/phase2-practices-capstone/README.md",
)
GENERATED_README_FILES = tuple(name.removesuffix(".md") + ".html" for name in README_FILES)
BUILD_VERSION_PLACEHOLDER = "__BUILD_VERSION__"
PWA_BUILD_PLACEHOLDER = "__PWA_BUILT__"
SITE_ROOT_PLACEHOLDER = "__SITE_ROOT__"
BUILD_MARKER = ".pages-artifact"
SENSITIVE_PARTS = frozenset(
    {
        ".aws",
        ".azure",
        ".claude",
        ".env",
        ".git",
        ".github",
        ".gnupg",
        ".ssh",
        ".venv",
        "credentials",
        "credential",
        "private",
        "secrets",
        "secret",
        "tokens",
        "token",
    }
)
SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".npmrc",
        ".pypirc",
        "authorized_keys",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "known_hosts",
        "netrc",
        "service-account.json",
    }
)
SENSITIVE_SUFFIXES = (".key", ".pem", ".p12", ".pfx", ".jks", ".keystore")
IGNORED_SCHEMES = frozenset({"http", "https", "mailto", "javascript", "data"})


class BuildError(RuntimeError):
    """A safe, user-facing build failure."""


class LinkParser(HTMLParser):
    """Collect local href and src attributes from HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str, int, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._collect(attrs)

    def _collect(self, attrs: list[tuple[str, str | None]]) -> None:
        line, column = self.getpos()
        for name, value in attrs:
            if name.lower() in {"href", "src"} and value is not None:
                self.links.append((name.lower(), value.strip(), line, column + 1))


def is_sensitive(relative: PurePosixPath) -> bool:
    """Reject common secret-bearing paths even if a whitelist is edited badly."""
    lowered = tuple(part.casefold() for part in relative.parts)
    name = lowered[-1] if lowered else ""
    return (
        any(part in SENSITIVE_PARTS for part in lowered)
        or name in SENSITIVE_NAMES
        or name.startswith(".env.")
        or name.endswith(SENSITIVE_SUFFIXES)
    )


def reject_symlink_chain(root: Path, relative: PurePosixPath) -> Path:
    """Resolve a source path without ever following a symlink."""
    current = root
    if current.is_symlink():
        raise BuildError(f"source root is a symlink: {root}")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BuildError(f"symlink is not allowed: {current}")
    return current


def exact_child(parent: Path, requested: str) -> Path:
    """Look up one path component with Linux-style exact casing."""
    if not parent.is_dir():
        raise BuildError(f"missing directory: {parent}")
    matches = [child for child in parent.iterdir() if child.name.casefold() == requested.casefold()]
    if not matches:
        raise BuildError(f"missing path: {parent / requested}")
    if len(matches) != 1 or matches[0].name != requested:
        found = ", ".join(sorted(child.name for child in matches))
        raise BuildError(
            f"case mismatch or collision: requested {parent / requested}; found {found}"
        )
    return matches[0]


def exact_source(root: Path, relative: PurePosixPath, *, kind: str = "file") -> Path:
    """Require an exact-cased, non-symlink source path of the expected kind."""
    if relative.is_absolute() or ".." in relative.parts:
        raise BuildError(f"unsafe source path: {relative}")
    if is_sensitive(relative):
        raise BuildError(f"sensitive path is forbidden: {relative}")

    current = root
    if current.is_symlink():
        raise BuildError(f"source root is a symlink: {root}")
    for index, part in enumerate(relative.parts):
        current = exact_child(current, part)
        mode = current.stat(follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            raise BuildError(f"symlink is not allowed: {current}")
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(mode):
            raise BuildError(f"expected directory: {current}")

    final_mode = current.stat(follow_symlinks=False).st_mode
    if kind == "file" and not stat.S_ISREG(final_mode):
        raise BuildError(f"expected regular file: {current}")
    if kind == "directory" and not stat.S_ISDIR(final_mode):
        raise BuildError(f"expected directory: {current}")
    return current


def collect_sources(root: Path) -> dict[PurePosixPath, Path]:
    """Build the complete copy manifest and reject unexpected whitelist contents."""
    sources: dict[PurePosixPath, Path] = {}

    for name in ROOT_FILES:
        relative = PurePosixPath(name)
        sources[relative] = exact_source(root, relative)

    assets = exact_source(root, PurePosixPath("assets"), kind="directory")
    expected_assets = {PurePosixPath(name) for name in ASSET_FILES}
    discovered_assets: set[PurePosixPath] = set()
    for entry in sorted(assets.rglob("*"), key=lambda item: item.as_posix()):
        relative = PurePosixPath(entry.relative_to(root).as_posix())
        reject_symlink_chain(root, relative)
        if is_sensitive(relative):
            raise BuildError(f"sensitive asset is forbidden: {relative}")
        mode = entry.stat(follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise BuildError(f"special asset entry is not allowed: {relative}")
        discovered_assets.add(relative)
    missing_assets = expected_assets - discovered_assets
    unexpected_assets = discovered_assets - expected_assets
    if missing_assets or unexpected_assets:
        details = []
        if missing_assets:
            details.append("missing: " + ", ".join(sorted(map(str, missing_assets))))
        if unexpected_assets:
            details.append("unexpected: " + ", ".join(sorted(map(str, unexpected_assets))))
        raise BuildError("asset allowlist mismatch (" + "; ".join(details) + ")")
    for relative in sorted(expected_assets, key=str):
        sources[relative] = exact_source(root, relative)

    for directory_name in HTML_DIRECTORIES:
        directory_relative = PurePosixPath(directory_name)
        directory = exact_source(root, directory_relative, kind="directory")
        html_count = 0
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = directory_relative / entry.name
            reject_symlink_chain(root, relative)
            if is_sensitive(relative):
                raise BuildError(f"sensitive path is forbidden: {relative}")
            mode = entry.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode) or entry.suffix != ".html":
                raise BuildError(
                    f"unexpected entry in {directory_name} (only first-level .html files are allowed): "
                    f"{relative}"
                )
            sources[relative] = entry
            html_count += 1
        if html_count == 0:
            raise BuildError(f"no HTML files found in required directory: {directory_name}")

    for name in README_FILES:
        relative = PurePosixPath(name)
        sources[relative] = exact_source(root, relative)

    return sources


def ensure_safe_output(root: Path, output: Path) -> Path:
    """Validate the destination before destructive staging operations."""
    root = root.resolve(strict=True)
    output = output.expanduser().absolute()

    probe = output
    while True:
        if os.path.lexists(probe):
            if probe.is_symlink():
                raise BuildError(f"output path must not contain a symlink: {probe}")
            resolved_probe = probe.resolve(strict=True)
            remainder = output.relative_to(probe)
            resolved = resolved_probe.joinpath(*remainder.parts)
            break
        parent = probe.parent
        if parent == probe:
            resolved = output.resolve(strict=False)
            break
        probe = parent

    try:
        resolved.relative_to(root)
    except ValueError:
        pass
    else:
        raise BuildError(f"output must be outside the source tree: {resolved}")

    if resolved == root or resolved == root.parent or resolved == Path(resolved.anchor):
        raise BuildError(f"unsafe output directory: {resolved}")
    return resolved


def inline_markdown(text: str) -> str:
    """Render a deliberately small, escaped Markdown inline subset."""
    placeholders: list[str] = []

    def hold(value: str) -> str:
        token = f"\x00{len(placeholders)}\x00"
        placeholders.append(value)
        return token

    protected = re.sub(
        r"`([^`]+)`",
        lambda match: hold(f"<code>{html.escape(match.group(1))}</code>"),
        text,
    )
    protected = re.sub(
        r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
        lambda match: hold(
            f'<a href="{html.escape(match.group(2), quote=True)}" rel="noopener noreferrer">'
            f"{html.escape(match.group(1))}</a>"
        ),
        protected,
    )
    escaped = html.escape(protected, quote=True)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    for index, value in enumerate(placeholders):
        escaped = escaped.replace(f"\x00{index}\x00", value)
    return escaped


def render_markdown_document(source: Path) -> str:
    """Render the README subset used by the published capstone guides."""
    lines = source.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    code_lines: list[str] = []
    code_language = ""
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{inline_markdown(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"</{list_tag}>")
            list_tag = None

    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                language_class = (
                    f' class="language-{html.escape(code_language, quote=True)}"'
                    if code_language
                    else ""
                )
                output.append(
                    f"<pre><code{language_class}>{html.escape(chr(10).join(code_lines))}</code></pre>"
                )
                code_lines.clear()
                code_language = ""
                in_code = False
            else:
                code_language = stripped[3:].strip()
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            output.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
            continue
        item = re.match(r"^[-*+]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if item or ordered:
            flush_paragraph()
            wanted = "ul" if item else "ol"
            if list_tag != wanted:
                close_list()
                output.append(f"<{wanted}>")
                list_tag = wanted
            value = (item or ordered).group(1)
            output.append(f"<li>{inline_markdown(value)}</li>")
            continue
        flush_paragraph() if list_tag else None
        close_list()
        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            output.append("<hr>")
        elif stripped.startswith("> "):
            flush_paragraph()
            output.append(f"<blockquote>{inline_markdown(stripped[2:])}</blockquote>")
        else:
            paragraph.append(stripped)

    if in_code:
        raise BuildError(f"unclosed fenced code block in {source}")
    flush_paragraph()
    close_list()
    title = next((re.sub(r"^#\s+", "", line).strip() for line in lines if line.startswith("# ")), source.parent.name)
    body = "\n    ".join(output)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#F8F6F1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="../../../assets/style.css">
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ width: min(100% - 2rem, 52rem); margin: 0 auto; padding: 2rem 0 4rem; line-height: 1.75; }}
    h1, h2, h3 {{ line-height: 1.25; color: #1A3A2A; }}
    a {{ color: #A65F00; }}
    code {{ font-family: ui-monospace, monospace; overflow-wrap: anywhere; }}
    pre {{ overflow-x: auto; padding: 1rem; border-radius: .75rem; background: #181C1A; color: #E8EEE9; }}
    blockquote {{ margin-left: 0; padding-left: 1rem; border-left: 3px solid #D97706; }}
    @media (prefers-color-scheme: dark) {{ body {{ background: #1A1A1E; color: #DDD8CE; }} h1, h2, h3 {{ color: #83D5A7; }} }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
  <script src="../../../assets/course-catalog.js"></script>
  <script src="../../../assets/theme-toggle.js"></script>
  <script src="../../../assets/pwa.js"></script>
</body>
</html>
'''


def rewrite_readme_links(stage: Path) -> None:
    """Point staged local course links at the rendered README documents."""
    pattern = re.compile(r'(?P<prefix>href=["\'])(?P<url>[^"\']*README)\.md(?P<tail>[?#][^"\']*)?(?P<quote>["\'])')

    def rewrite(match: re.Match[str]) -> str:
        url = match.group("url")
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or url.startswith("//"):
            return match.group(0)
        return (
            match.group("prefix")
            + url
            + ".html"
            + (match.group("tail") or "")
            + match.group("quote")
        )

    for path in stage.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub(rewrite, text)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="")


def normalize_site_root(value: str) -> str:
    """Normalize the configured Pages base path to a root-relative directory URL."""
    value = value.strip()
    if not value or value == "/":
        return "/"
    if not value.startswith("/") or ".." in value.split("/"):
        raise BuildError(f"invalid site base path: {value!r}")
    return value.rstrip("/") + "/"


def finalize_generated_files(stage: Path, site_root: str) -> None:
    """Render web documents and inject deployment-specific metadata."""
    site_root = normalize_site_root(site_root)
    fallback = stage / "404.html"
    fallback_text = fallback.read_text(encoding="utf-8")
    if fallback_text.count(SITE_ROOT_PLACEHOLDER) < 1:
        raise BuildError("404.html must contain a site-root placeholder")
    fallback.write_text(
        fallback_text.replace(SITE_ROOT_PLACEHOLDER, site_root),
        encoding="utf-8",
        newline="",
    )
    offline = stage / "offline.html"
    offline_text = offline.read_text(encoding="utf-8")
    if offline_text.count(SITE_ROOT_PLACEHOLDER) < 1:
        raise BuildError("offline.html must contain a site-root placeholder")
    offline.write_text(
        offline_text.replace(SITE_ROOT_PLACEHOLDER, site_root),
        encoding="utf-8",
        newline="",
    )

    pwa = stage / "assets" / "pwa.js"
    pwa_text = pwa.read_text(encoding="utf-8")
    if pwa_text.count(PWA_BUILD_PLACEHOLDER) != 1:
        raise BuildError("assets/pwa.js must contain exactly one build marker placeholder")
    pwa.write_text(
        pwa_text.replace(PWA_BUILD_PLACEHOLDER, "true"),
        encoding="utf-8",
        newline="",
    )

    for source_name, generated_name in zip(README_FILES, GENERATED_README_FILES, strict=True):
        source = stage.joinpath(*PurePosixPath(source_name).parts)
        target = stage.joinpath(*PurePosixPath(generated_name).parts)
        target.write_text(render_markdown_document(source), encoding="utf-8", newline="")
        source.unlink()
    rewrite_readme_links(stage)
    (stage / BUILD_MARKER).write_text(
        "allowlisted-pages-artifact\n", encoding="utf-8", newline=""
    )

    worker = stage / "service-worker.js"
    worker_text = worker.read_text(encoding="utf-8")
    if worker_text.count(BUILD_VERSION_PLACEHOLDER) != 1:
        raise BuildError("service-worker.js must contain exactly one build-version placeholder")
    digest = hashlib.sha256()
    for path in sorted(stage.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative_bytes = path.relative_to(stage).as_posix().encode("utf-8")
        payload = (
            worker_text.replace(BUILD_VERSION_PLACEHOLDER, "").encode("utf-8")
            if path == worker
            else path.read_bytes()
        )
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    worker.write_text(
        worker_text.replace(BUILD_VERSION_PLACEHOLDER, digest.hexdigest()),
        encoding="utf-8",
        newline="",
    )


TEXT_SUFFIXES = frozenset({".css", ".html", ".js", ".json", ".md", ".txt", ".webmanifest", ".xml"})


def copy_manifest(
    sources: dict[PurePosixPath, Path], stage: Path, site_root: str
) -> None:
    """Copy regular files into a fresh private staging directory."""
    for relative, source in sorted(sources.items(), key=lambda item: str(item[0])):
        target = stage.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() in TEXT_SUFFIXES:
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="")
        else:
            shutil.copyfile(source, target, follow_symlinks=False)
    finalize_generated_files(stage, site_root)


def list_output_files(stage: Path) -> set[PurePosixPath]:
    """Inventory staged files while rejecting symlinks and special files."""
    found: set[PurePosixPath] = set()
    for path in stage.rglob("*"):
        relative = PurePosixPath(path.relative_to(stage).as_posix())
        mode = path.stat(follow_symlinks=False).st_mode
        if stat.S_ISLNK(mode):
            raise BuildError(f"symlink found in output: {relative}")
        if stat.S_ISREG(mode):
            if is_sensitive(relative):
                raise BuildError(f"sensitive file found in output: {relative}")
            found.add(relative)
        elif not stat.S_ISDIR(mode):
            raise BuildError(f"special file found in output: {relative}")
    return found


def normalize_local_link(
    raw: str, source: PurePosixPath, site_root: str = "/"
) -> PurePosixPath | None:
    """Map a local URL to its expected artifact path."""
    if not raw or raw.startswith("#"):
        return None
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() in IGNORED_SCHEMES:
        return None
    if parsed.scheme or parsed.netloc:
        raise BuildError(f"unsupported URL in {source}: {raw!r}")

    try:
        decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise BuildError(f"invalid percent-encoding in {source}: {raw!r}") from error
    decoded = decoded.replace("\\", "/")
    if "\x00" in decoded:
        raise BuildError(f"NUL byte in URL in {source}: {raw!r}")
    if decoded.startswith("//"):
        raise BuildError(f"protocol-relative URL is not an allowed local URL in {source}: {raw!r}")
    if not decoded:
        target_text = source.as_posix()
    elif decoded.startswith("/"):
        site_root = normalize_site_root(site_root)
        if site_root == "/":
            target_text = decoded.lstrip("/")
        elif decoded == site_root.rstrip("/") or decoded.startswith(site_root):
            target_text = decoded[len(site_root):]
        else:
            raise BuildError(
                f"root-relative URL escapes the configured Pages root in {source}: {raw!r}"
            )
    else:
        target_text = (source.parent / decoded).as_posix()

    stack: list[str] = []
    for part in target_text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not stack:
                raise BuildError(f"local URL escapes the artifact root in {source}: {raw!r}")
            stack.pop()
        else:
            stack.append(part)
    final_segment = decoded.rstrip("/").rsplit("/", 1)[-1]
    if decoded.endswith("/") or final_segment in {".", ".."} or not stack:
        stack.append("index.html")

    target = PurePosixPath(*stack)
    if is_sensitive(target):
        raise BuildError(f"local URL targets a sensitive path in {source}: {raw!r}")
    return target


def exact_artifact_target(
    target: PurePosixPath,
    files: set[PurePosixPath],
    casefolded: dict[str, list[PurePosixPath]],
) -> None:
    """Require a generated target and report case-only mismatches clearly."""
    if target in files:
        return
    matches = casefolded.get(target.as_posix().casefold(), [])
    if matches:
        found = ", ".join(sorted(item.as_posix() for item in matches))
        raise BuildError(f"local URL case mismatch: requested {target}; found {found}")
    raise BuildError(f"local URL target is not in the artifact: {target}")


def validate_output(
    stage: Path, expected: set[PurePosixPath], site_root: str
) -> tuple[dict[PurePosixPath, set[PurePosixPath]], set[PurePosixPath]]:
    """Validate artifact inventory and every local HTML href/src."""
    site_root = normalize_site_root(site_root)
    files = list_output_files(stage)
    expected = (
        expected - {PurePosixPath(name) for name in README_FILES}
    ) | {PurePosixPath(name) for name in GENERATED_README_FILES} | {
        PurePosixPath(BUILD_MARKER)
    }
    missing = expected - files
    unexpected = files - expected
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing: " + ", ".join(sorted(map(str, missing))))
        if unexpected:
            details.append("unexpected: " + ", ".join(sorted(map(str, unexpected))))
        raise BuildError("artifact whitelist mismatch (" + "; ".join(details) + ")")

    casefolded: dict[str, list[PurePosixPath]] = {}
    for item in files:
        casefolded.setdefault(item.as_posix().casefold(), []).append(item)
    collisions = [items for items in casefolded.values() if len(items) > 1]
    if collisions:
        formatted = "; ".join(
            ", ".join(sorted(item.as_posix() for item in items)) for items in collisions
        )
        raise BuildError(f"case-insensitive artifact path collision: {formatted}")

    readme_links: dict[PurePosixPath, set[PurePosixPath]] = {
        PurePosixPath(name): set() for name in GENERATED_README_FILES
    }
    linked_readmes: set[PurePosixPath] = set()
    for source in sorted((item for item in files if item.suffix == ".html"), key=str):
        parser = LinkParser()
        html_path = stage.joinpath(*source.parts)
        try:
            parser.feed(html_path.read_text(encoding="utf-8"))
            parser.close()
        except (UnicodeError, OSError) as error:
            raise BuildError(f"cannot parse UTF-8 HTML {source}: {error}") from error

        for attribute, raw, line, column in parser.links:
            try:
                target = normalize_local_link(raw, source, site_root)
                if target is None:
                    continue
                exact_artifact_target(target, files, casefolded)
            except BuildError as error:
                raise BuildError(
                    f"{source}:{line}:{column} {attribute}={raw!r}: {error}"
                ) from error
            if target in readme_links:
                readme_links[target].add(source)
                linked_readmes.add(target)

    return readme_links, linked_readmes


def install_stage(stage: Path, output: Path) -> None:
    """Replace the destination only after the staged artifact passes validation."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(output):
        if output.is_symlink():
            raise BuildError(f"output became a symlink during the build: {output}")
        if not output.is_dir() or not (output / BUILD_MARKER).is_file():
            raise BuildError(
                f"refusing to replace an output not owned by this builder: {output}"
            )
        shutil.rmtree(output)
    shutil.copytree(stage, output, copy_function=shutil.copyfile)


def print_summary(
    output: Path,
    file_count: int,
    readme_links: dict[PurePosixPath, set[PurePosixPath]],
    linked_readmes: set[PurePosixPath],
) -> None:
    """Distinguish copied README allowlist entries from actual HTML link targets."""
    print(f"Built {file_count} allowlisted files at {output}")
    print(f"Allowlisted README files ({len(README_FILES)}):")
    for name in README_FILES:
        print(f"  - {name}")
    print(f"README files actually linked by artifact HTML ({len(linked_readmes)} unique):")
    if not linked_readmes:
        print("  - (none)")
    for readme in sorted(linked_readmes, key=str):
        sources = ", ".join(sorted(source.as_posix() for source in readme_links[readme]))
        print(f"  - {readme.as_posix()} <- {sources}")


def remove_tree(path: Path) -> None:
    """Remove a temporary tree, retrying transient Windows file locks."""
    last_error: OSError | None = None
    for _ in range(3):
        try:
            shutil.rmtree(path)
            return
        except OSError as error:
            last_error = error
            time.sleep(0.1)
    if last_error is not None:
        raise last_error


def build(root: Path, output: Path, site_root: str) -> None:
    """Build, validate, and publish one staging artifact."""
    sources = collect_sources(root)
    output = ensure_safe_output(root, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage_path = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        copy_manifest(sources, stage_path, site_root)
        readme_links, linked_readmes = validate_output(
            stage_path, set(sources), site_root
        )
        install_stage(stage_path, output)
        print_summary(
            output,
            len(sources) - len(README_FILES) + len(GENERATED_README_FILES) + 1,
            readme_links,
            linked_readmes,
        )
    finally:
        if os.path.lexists(stage_path):
            remove_tree(stage_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="destination directory, which must be outside the repository",
    )
    parser.add_argument(
        "--site-root",
        default="/",
        help="deployed Pages base path, for example /ai-agent-learning/",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    try:
        build(root, args.output, args.site_root)
    except (BuildError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
