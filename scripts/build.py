#!/usr/bin/env python3
"""Build the static site with an integrity-checked copy of the official APK."""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "macareli/Maichat"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ORIGIN = "https://maichat.me"
MAX_APK_SIZE = 512 * 1024 * 1024
MAX_METADATA_SIZE = 2 * 1024 * 1024
PLACEHOLDER = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
DOWNLOAD_HOSTS = frozenset(
    {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}
)


class BuildError(Exception):
    """An incomplete or untrusted release must never be published."""


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]):
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (
            target.scheme != "https"
            or target.netloc not in self.allowed_hosts
            or target.username
            or target.password
        ):
            raise BuildError("Release download redirected outside GitHub's HTTPS hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url: str, *, api: bool = False):
    headers = {"User-Agent": "MaiChat-static-release-builder/1.0"}
    if api:
        headers.update(
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
        # Credentials are only sent to the API, never to release download hosts.
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    allowed_hosts = frozenset({"api.github.com"}) if api else DOWNLOAD_HOSTS
    opener = urllib.request.build_opener(SafeRedirectHandler(allowed_hosts))
    return opener.open(urllib.request.Request(url, headers=headers), timeout=90)


def fetch_release() -> dict:
    with closing(open_url(API_URL, api=True)) as response:
        raw = response.read(MAX_METADATA_SIZE + 1)
    if len(raw) > MAX_METADATA_SIZE:
        raise BuildError("Release metadata exceeds the size limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("GitHub returned invalid release metadata") from error


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    name: str
    published_at: str
    filename: str
    size: int
    sha256: str
    source_url: str
    source_asset_url: str
    notes: str

    @property
    def url(self) -> str:
        return f"/release/files/{self.filename}"

    def manifest(self) -> dict:
        return {
            "repository": REPOSITORY,
            "version": self.version,
            "tag": self.tag,
            "name": self.name,
            "published_at": self.published_at,
            "filename": self.filename,
            "size": self.size,
            "sha256": self.sha256,
            "url": self.url,
            "source_url": self.source_url,
            "source_asset_url": self.source_asset_url,
            "notes": self.notes,
        }

    def substitutions(self) -> dict[str, str]:
        published = datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))
        readable_date = f"{published:%B} {published.day}, {published.year}"
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", self.notes) if part.strip()]
        notes = "\n".join(
            "<p>" + re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html.escape(part)).replace("\n", "<br>\n") + "</p>"
            for part in paragraphs
        ) or "<p>No release notes were provided.</p>"
        values = {
            "release_version": self.version,
            "release_name": self.name,
            "release_date": readable_date,
            "release_size": f"{self.size / 1_000_000:.1f} MB",
            "release_filename": self.filename,
            "release_url": self.url,
            "release_sha256": self.sha256,
            "release_source": self.source_url,
        }
        return {key: html.escape(value, quote=True) for key, value in values.items()} | {
            "release_notes": notes
        }


def validate_release(data: dict) -> Release:
    if not isinstance(data, dict) or data.get("draft") is not False or data.get("prerelease") is not False:
        raise BuildError("Only a published stable release can be mirrored")
    tag = data.get("tag_name", "")
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag) if isinstance(tag, str) else None
    if not match:
        raise BuildError("The stable release must have a numeric version tag")
    version = match.group(1)
    source_url = f"https://github.com/{REPOSITORY}/releases/tag/{tag}"
    if data.get("html_url") != source_url:
        raise BuildError("Release metadata does not belong to the official repository")
    published_at = data.get("published_at")
    try:
        if not isinstance(published_at, str):
            raise ValueError
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if published.tzinfo is None:
            raise ValueError
    except ValueError as error:
        raise BuildError("The release publication date is missing or invalid") from error
    filename = f"MaiChat-{version}.apk"
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise BuildError("Release assets are missing")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == filename]
    if len(matches) != 1:
        raise BuildError(f"Expected exactly one official {filename} asset")
    asset = matches[0]
    if asset.get("state") != "uploaded":
        raise BuildError("The official APK is not completely uploaded")
    asset_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}"
    if asset.get("browser_download_url") != asset_url:
        raise BuildError("The APK download URL does not match the official release")
    size = asset.get("size")
    if type(size) is not int or not 0 < size <= MAX_APK_SIZE:
        raise BuildError("The APK size is missing or exceeds the mirror limit")
    digest = asset.get("digest", "")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise BuildError("GitHub must supply a SHA-256 digest for the APK")
    name = data.get("name") or f"MaiChat {version}"
    notes = data.get("body") or ""
    if not isinstance(name, str) or len(name) > 500 or not isinstance(notes, str) or len(notes) > 100_000:
        raise BuildError("Invalid release title or notes")
    return Release(version, tag, name, published_at, filename, size, digest[7:], source_url, asset_url, notes)


def file_matches(path: Path, release: Release) -> bool:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != release.size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == release.sha256


def ensure_apk(release: Release, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{release.sha256}.apk"
    if file_matches(destination, release):
        print(f"Verified cached {release.filename} ({release.size:,} bytes)")
        return destination
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    descriptor, temporary = tempfile.mkstemp(prefix=f"{release.sha256}-", suffix=".part", dir=cache_dir)
    temporary_path = Path(temporary)
    try:
        digest = hashlib.sha256()
        count = 0
        with os.fdopen(descriptor, "wb") as output, closing(open_url(release.source_asset_url)) as response:
            header_size = response.headers.get("Content-Length")
            if header_size is not None and header_size != str(release.size):
                raise BuildError("The download Content-Length does not match GitHub's asset size")
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > release.size:
                    raise BuildError("The APK download exceeds GitHub's declared asset size")
                digest.update(chunk)
                output.write(chunk)
        if count != release.size or digest.hexdigest() != release.sha256:
            raise BuildError("APK size or SHA-256 verification failed; refusing to publish")
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"Downloaded and verified {release.filename} ({release.size:,} bytes)")
    return destination


def render(template: str, substitutions: dict[str, str], partials: dict[str, str]) -> str:
    # Expand partials first so their metadata uses exactly the page's release values.
    expanded = PLACEHOLDER.sub(lambda match: partials.get(match[1], match[0]), template)
    result = PLACEHOLDER.sub(lambda match: substitutions.get(match[1], match[0]), expanded)
    unresolved = PLACEHOLDER.findall(result)
    if unresolved:
        raise BuildError(f"Unresolved template placeholders: {', '.join(sorted(set(unresolved)))}")
    return result


def copy_static(source: Path, target: Path, *, exclude_suffixes: frozenset[str] = frozenset()) -> None:
    if not source.is_dir():
        raise BuildError(f"Missing static source directory: {source}")
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.suffix.lower() in exclude_suffixes:
            continue
        if path.is_symlink():
            raise BuildError(f"Static sources must not contain symbolic links: {relative}")
        if path.is_file():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def build_site(root: Path, output: Path, release: Release, apk: Path) -> None:
    if output.is_symlink():
        raise BuildError("The output must not be a symbolic link")
    root, output = root.resolve(), output.resolve()
    if output == root or output in root.parents:
        raise BuildError("The output must be a separate build directory")
    for source_name in ("src", "assets", "scripts", "tests", ".github", ".git", ".cache", "node_modules"):
        source = root / source_name
        if output == source or source in output.parents:
            raise BuildError("The output cannot replace a source directory")
    if not file_matches(apk, release):
        raise BuildError("The APK changed before site generation")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}-build-", dir=output.parent))
    stage.chmod(0o755)
    try:
        copy_static(root / "assets", stage / "assets")
        copy_static(root / "src", stage / "src", exclude_suffixes=frozenset({".html"}))
        partials = {
            part: (root / "src" / "layouts" / f"{part}.html").read_text(encoding="utf-8")
            for part in ("header", "footer")
        }
        substitutions = release.substitutions()
        pages = [("index", "index.html"), ("release", "release/index.html")]
        if (root / "src/pages/404.html").is_file():
            pages.append(("404", "404.html"))
        for name, destination in pages:
            template = (root / "src" / "pages" / f"{name}.html").read_text(encoding="utf-8")
            rendered = render(template, substitutions, partials)
            page = stage / destination
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(rendered, encoding="utf-8")
        release_dir = stage / "release"
        (release_dir / "files").mkdir()
        mirrored_apk = stage / release.url.lstrip("/")
        shutil.copyfile(apk, mirrored_apk)
        if not file_matches(mirrored_apk, release):
            raise BuildError("The staged APK failed verification")
        (release_dir / "manifest.json").write_text(
            json.dumps(release.manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        cname = (root / "CNAME").read_text(encoding="utf-8").strip()
        if cname != "maichat.me":
            raise BuildError("CNAME must preserve the maichat.me custom domain")
        (stage / "CNAME").write_text(cname + "\n", encoding="utf-8")
        (stage / ".nojekyll").touch()
        (stage / "manifest.webmanifest").write_text(json.dumps({
            "name": "MaiChat", "short_name": "MaiChat", "start_url": "/", "scope": "/",
            "display": "browser", "theme_color": "#fff7fc", "background_color": "#fff7fc",
            "icons": [{"src": "/assets/images/maichat-mark.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
        }, indent=2) + "\n", encoding="utf-8")
        (stage / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n", encoding="utf-8")
        (stage / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{ORIGIN}/</loc></url>\n"
            f"  <url><loc>{ORIGIN}/release/</loc></url>\n"
            "</urlset>\n", encoding="utf-8"
        )
        if not (stage / "404.html").exists():
            (stage / "404.html").write_text(
                '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<meta name="robots" content="noindex"><title>Page not found · MaiChat</title>'
                '<link rel="stylesheet" href="/src/tokens/material-tokens.css">'
                '<link rel="stylesheet" href="/src/tokens/generated-scheme.css">'
                '<link rel="stylesheet" href="/src/tokens/theme.css">'
                '<link rel="stylesheet" href="/src/layouts/shell.css"></head>'
                '<body><main id="main" class="wrap"><p>MaiChat · 404</p><h1>This page could not be found.</h1>'
                '<p>You can <a href="/">return to the homepage</a> or '
                '<a href="/release/">download the latest release</a>.</p></main></body></html>\n',
                encoding="utf-8"
            )
        backup = None
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-previous-", dir=output.parent))
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(stage, output)
        except OSError:
            if backup is not None:
                os.replace(backup, output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-json", type=Path, help="Use pre-fetched official GitHub API metadata")
    parser.add_argument("--metadata-only", action="store_true", help="Validate release metadata without downloading or building")
    parser.add_argument("--metadata-output", type=Path, help="Save the validated API metadata for a later build")
    parser.add_argument("--github-output", type=Path, help="Append the validated version and digest to GitHub Actions outputs")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache" / "releases")
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.release_json.read_text(encoding="utf-8")) if args.release_json else fetch_release()
        release = validate_release(data)
        if args.metadata_output:
            args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
            args.metadata_output.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as stream:
                stream.write(f"version={release.version}\nsha256={release.sha256}\n")
        if args.metadata_only:
            print(f"Official stable release: {release.version}; SHA-256: {release.sha256}")
            return 0
        output = args.output.resolve()
        cache = args.cache_dir.resolve()
        if cache == output or output in cache.parents:
            raise BuildError("The APK cache must be outside the build output")
        apk = ensure_apk(release, cache)
        build_site(ROOT, output, release, apk)
        print(f"Built {output} with {release.url}")
        return 0
    except (BuildError, OSError, ValueError, urllib.error.URLError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
