import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_pages', ROOT / 'scripts/build-pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


class PagesReleaseTests(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / 'docs/demo/index.html').read_text()
        self.release = {
            'tag_name': 'v0.6.2', 'published_at': '2026-11-10T12:00:00Z',
            'draft': False, 'prerelease': False,
            'assets': [{'name': 'EarA.flatpak', 'browser_download_url':
                        pages.REPO + '/releases/download/v0.6.2/EarA.flatpak'}],
        }

    def test_release_version_and_links_are_rendered_without_browser_fetch(self):
        output = pages.render(self.template, self.release)
        data = json.loads(re.search(r'application/ld\+json">(.*?)</script>', output, re.S)[1])
        self.assertEqual(data['softwareVersion'], '0.6.2')
        self.assertIn('EarA 0.6.2</a>', output)
        self.assertIn('2026-11-10</time>', output)
        self.assertIn(self.release['assets'][0]['browser_download_url'], output)
        self.assertNotIn('>RPM</a>', output)
        self.assertNotIn('fetch(', output)

    def test_unpublished_or_prerelease_or_empty_release_cannot_replace_site(self):
        for change in ({'draft': True}, {'prerelease': True}, {'assets': []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                pages.render(self.template, {**self.release, **change})

    def test_unrelated_downloads_and_invalid_tags_are_rejected(self):
        self.release['assets'][0]['browser_download_url'] = 'https://example.org/EarA.flatpak'
        with self.assertRaises(ValueError):
            pages.render(self.template, self.release)
        self.release['tag_name'] = '<script>alert(1)</script>'
        with self.assertRaises(ValueError):
            pages.render(self.template, self.release)
