"""Render release downloads into the static Pages site (no browser API calls)."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil

REPO = 'https://github.com/oneydef/EarA-linux'


def render(template, release):
    if template.count('<!-- release:start -->') != 1 or template.count('<!-- release:end -->') != 1:
        raise ValueError('Release section markers are missing or duplicated')
    tag = release['tag_name']
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
        raise ValueError('Expected a published stable release')
    url = f'{REPO}/releases/tag/{tag}'
    date = release['published_at'][:10]
    links = []
    formats = (('.flatpak', 'Flatpak'), ('.AppImage', 'AppImage'),
               ('.deb', 'Debian / Ubuntu'), ('.rpm', 'RPM'), ('.tar.gz', 'Source'))
    for suffix, label in formats:
        for asset in release.get('assets', []):
            href = asset.get('browser_download_url', '')
            if asset['name'].endswith(suffix) and href.startswith(f'{REPO}/releases/download/{tag}/'):
                links.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
    if not links:
        raise ValueError('Release has no downloadable packages')
    block = (f'<p class="release-version"><a href="{url}">EarA {tag.lstrip("v")}</a>'
             f' · <time datetime="{html.escape(date)}">{html.escape(date)}</time></p>\n'
             '<nav class="release-downloads" aria-label="Release packages">'
             + ' '.join(links) + '</nav>')
    template = re.sub(r'<!-- release:start -->.*?<!-- release:end -->',
                      lambda _: '<!-- release:start -->\n' + block + '\n<!-- release:end -->',
                      template, flags=re.S)
    def metadata(match):
        data = json.loads(match.group(1))
        data.update(softwareVersion=tag.lstrip('v'), downloadUrl=url)
        return '<script type="application/ld+json">\n' + json.dumps(data, indent=2) + '\n  </script>'
    return re.sub(r'<script type="application/ld\+json">(.*?)</script>', metadata, template, flags=re.S)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('release_json', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / 'docs/demo'
    rendered = render((source / 'index.html').read_text(), json.loads(args.release_json.read_text()))
    shutil.copytree(source, args.output, dirs_exist_ok=True)
    (args.output / 'index.html').write_text(rendered)


if __name__ == '__main__':
    main()
