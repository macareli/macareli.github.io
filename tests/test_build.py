"""Regression tests for the release mirror's trust and publication boundaries."""

from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from scripts import build


PAYLOAD = b"PK\x03\x04an official APK test payload"


def metadata():
    return {
        "draft": False,
        "prerelease": False,
        "tag_name": "v1.19.4",
        "name": "MaiChat 1.19.4",
        "html_url": "https://github.com/macareli/Maichat/releases/tag/v1.19.4",
        "published_at": "2026-11-05T05:02:29Z",
        "body": "A public stable release.",
        "assets": [{
            "name": "MaiChat-1.19.4.apk",
            "state": "uploaded",
            "size": len(PAYLOAD),
            "digest": "sha256:" + hashlib.sha256(PAYLOAD).hexdigest(),
            "browser_download_url": "https://github.com/macareli/Maichat/releases/download/v1.19.4/MaiChat-1.19.4.apk",
        }],
    }


def response(payload, *, content_length=None):
    result = io.BytesIO(payload)
    result.headers = {} if content_length is None else {"Content-Length": str(content_length)}
    return result


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.release = build.validate_release(metadata())

    def test_rejects_untrusted_or_unfinished_release_metadata(self):
        changes = [
            {"draft": True},
            {"prerelease": True},
            {"tag_name": "v1.19.4-beta"},
            {"html_url": "https://github.com/another/Maichat/releases/tag/v1.19.4"},
            {"published_at": "2026-11-05"},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(build.BuildError):
                build.validate_release(metadata() | change)

    def test_rejects_unsafe_apk_urls_missing_digests_and_ambiguous_assets(self):
        changes = [
            {"browser_download_url": "https://evil.example/MaiChat-1.19.4.apk"},
            {"browser_download_url": "https://github.com/another/Maichat/releases/download/v1.19.4/MaiChat-1.19.4.apk"},
            {"name": "../MaiChat-1.19.4.apk"},
            {"digest": None},
            {"digest": "md5:" + "f" * 32},
            {"size": 0},
            {"size": build.MAX_APK_SIZE + 1},
            {"state": "new"},
        ]
        for change in changes:
            data = metadata()
            data["assets"][0].update(change)
            with self.subTest(change=change), self.assertRaises(build.BuildError):
                build.validate_release(data)
        data = metadata()
        data["assets"].append(deepcopy(data["assets"][0]))
        with self.assertRaises(build.BuildError):
            build.validate_release(data)

    def test_verified_cache_is_reused_without_network(self):
        cached = self.directory / f"{self.release.sha256}.apk"
        cached.write_bytes(PAYLOAD)
        with patch.object(build, "open_url", side_effect=AssertionError("unexpected network")):
            self.assertEqual(build.ensure_apk(self.release, self.directory), cached)

    def test_modified_cache_is_detected_and_replaced(self):
        cached = self.directory / f"{self.release.sha256}.apk"
        cached.write_bytes(b"!" * len(PAYLOAD))
        with patch.object(build, "open_url", return_value=response(PAYLOAD)) as network:
            self.assertEqual(build.ensure_apk(self.release, self.directory).read_bytes(), PAYLOAD)
            network.assert_called_once_with(self.release.source_asset_url)

    def test_bad_or_incomplete_download_never_enters_cache(self):
        bad_responses = [
            response(PAYLOAD[:-1]),
            response(b"!" * len(PAYLOAD)),
            response(PAYLOAD + b"extra"),
            response(PAYLOAD, content_length=len(PAYLOAD) + 1),
        ]
        for index, downloaded in enumerate(bad_responses):
            cache = self.directory / str(index)
            with self.subTest(index=index), patch.object(build, "open_url", return_value=downloaded):
                with self.assertRaises(build.BuildError):
                    build.ensure_apk(self.release, cache)
                self.assertEqual(list(cache.iterdir()), [])

    def test_redirects_cannot_leak_credentials_or_fetch_other_hosts(self):
        handler = build.SafeRedirectHandler(build.DOWNLOAD_HOSTS)
        request = urllib.request.Request(self.release.source_asset_url)
        for url in (
            "http://github.com/macareli/Maichat",
            "https://github.com.evil.example/file.apk",
            "https://evil.example/file.apk",
            "https://user:password@github.com/file.apk",
        ):
            with self.subTest(url=url), self.assertRaises(build.BuildError):
                handler.redirect_request(request, None, 302, "Found", {}, url)
        api_handler = build.SafeRedirectHandler(frozenset({"api.github.com"}))
        with self.assertRaises(build.BuildError):
            api_handler.redirect_request(request, None, 302, "Found", {}, self.release.source_asset_url)

    def test_api_token_is_not_added_to_apk_requests(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-secret-token"}), patch.object(
            urllib.request, "build_opener"
        ) as factory:
            build.open_url(self.release.source_asset_url)
            apk_request = factory.return_value.open.call_args.args[0]
            self.assertIsNone(apk_request.get_header("Authorization"))
            build.open_url(build.API_URL, api=True)
            api_request = factory.return_value.open.call_args.args[0]
            self.assertEqual(api_request.get_header("Authorization"), "Bearer test-secret-token")


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "source"
        for folder in ("src/pages", "src/layouts", "src/styles", "assets"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "CNAME").write_text("maichat.me\n")
        (self.root / "src/styles/site.css").write_text("body{margin:0}")
        (self.root / "src/layouts/shell.css").write_text("header{display:flex}")
        (self.root / "assets/mark.svg").write_text("<svg></svg>")
        (self.root / "src/layouts/header.html").write_text('<header>{{release_version}}</header>')
        (self.root / "src/layouts/footer.html").write_text('<footer>{{release_name}}</footer>')
        template = '<!doctype html><html><body>{{header}}<a download="{{release_filename}}" href="{{release_url}}">Download</a>{{release_notes}}{{footer}}</body></html>'
        for name in ("index", "release"):
            (self.root / f"src/pages/{name}.html").write_text(template)
        self.release = build.validate_release(metadata())
        self.apk = self.directory / "verified.apk"
        self.apk.write_bytes(PAYLOAD)
        self.output = self.directory / "_site"

    def test_site_contains_identical_same_origin_apk_and_manifest(self):
        build.build_site(self.root, self.output, self.release, self.apk)
        self.assertEqual((self.output / self.release.url.lstrip("/")).read_bytes(), PAYLOAD)
        manifest = json.loads((self.output / "release/manifest.json").read_text())
        self.assertEqual(manifest["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(manifest["url"], "/release/files/MaiChat-1.19.4.apk")
        self.assertEqual(manifest["repository"], "macareli/Maichat")
        self.assertEqual((self.output / "CNAME").read_text(), "maichat.me\n")
        for page in ("index.html", "release/index.html"):
            rendered = (self.output / page).read_text()
            self.assertNotIn("{{", rendered)
            self.assertIn('href="/release/files/MaiChat-1.19.4.apk"', rendered)
        for path in ("src/styles/site.css", "src/layouts/shell.css", "assets/mark.svg", "404.html", "manifest.webmanifest", "robots.txt", "sitemap.xml", ".nojekyll"):
            self.assertTrue((self.output / path).is_file(), path)
        self.assertFalse((self.output / "src/pages").exists())
        self.assertFalse((self.output / "src/layouts/header.html").exists())

    def test_release_text_is_escaped_even_inside_shared_partials(self):
        data = metadata() | {"name": '<script>alert("name")</script>', "body": '<script>alert("notes")</script>\n\nSecond & paragraph\n\nDownload **MaiChat-1.19.4.apk**. **<img onerror=alert(1)>**'}
        release = build.validate_release(data)
        build.build_site(self.root, self.output, release, self.apk)
        page = (self.output / "release/index.html").read_text()
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("<p>Second &amp; paragraph</p>", page)
        self.assertIn("<strong>MaiChat-1.19.4.apk</strong>", page)
        self.assertIn("<strong>&lt;img onerror=alert(1)&gt;</strong>", page)
        self.assertNotIn("<img onerror", page)

    def test_bad_template_keeps_previous_build_intact(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("previous working site")
        (self.root / "src/pages/release.html").write_text("{{missing_value}}")
        with self.assertRaisesRegex(build.BuildError, "Unresolved"):
            build.build_site(self.root, self.output, self.release, self.apk)
        self.assertEqual((self.output / "index.html").read_text(), "previous working site")
        self.assertEqual(list(self.directory.glob("._site-build-*")), [])

    def test_modified_apk_cannot_replace_existing_site(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("previous working site")
        self.apk.write_bytes(b"!" * len(PAYLOAD))
        with self.assertRaisesRegex(build.BuildError, "APK changed"):
            build.build_site(self.root, self.output, self.release, self.apk)
        self.assertEqual((self.output / "index.html").read_text(), "previous working site")

    def test_failed_output_swap_restores_previous_build(self):
        self.output.mkdir()
        (self.output / "index.html").write_text("previous working site")
        original_replace = os.replace

        def replace(source, destination):
            if "-build-" in Path(source).name:
                raise OSError("simulated output filesystem error")
            return original_replace(source, destination)

        with patch.object(build.os, "replace", side_effect=replace), self.assertRaises(OSError):
            build.build_site(self.root, self.output, self.release, self.apk)
        self.assertEqual((self.output / "index.html").read_text(), "previous working site")

    def test_build_cannot_overwrite_source_or_publish_symlinks(self):
        for output in (self.root, self.root.parent, self.root / "src", self.root / "assets"):
            with self.subTest(output=output), self.assertRaises(build.BuildError):
                build.build_site(self.root, output, self.release, self.apk)
        (self.root / "assets/leak").symlink_to(self.root / "CNAME")
        with self.assertRaisesRegex(build.BuildError, "symbolic links"):
            build.build_site(self.root, self.output, self.release, self.apk)


if __name__ == "__main__":
    unittest.main()
