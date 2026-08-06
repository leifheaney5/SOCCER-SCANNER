from pathlib import Path
import unittest

REQUIRED = {
    'static/icons/icon-192.png': (192, 192),
    'static/icons/icon-512.png': (512, 512),
    'static/icons/icon-maskable-512.png': (512, 512),
    'static/icons/apple-touch-icon.png': (180, 180),
    'static/icons/favicon-32.png': (32, 32),
    'static/social-card.png': (1200, 630),
}


class BrandAssetTest(unittest.TestCase):
    def test_every_required_icon_exists_at_the_right_size(self):
        from PIL import Image

        for path, expected in REQUIRED.items():
            with self.subTest(path=path):
                asset = Path(path)
                self.assertTrue(asset.exists(), f'{path} is missing')
                with Image.open(asset) as image:
                    self.assertEqual(image.size, expected)

    def test_icons_are_opaque(self):
        from PIL import Image

        # An alpha channel on an iOS/PWA icon renders as a black box.
        for path in ('static/icons/icon-512.png', 'static/icons/apple-touch-icon.png'):
            with self.subTest(path=path), Image.open(path) as image:
                self.assertEqual(image.mode, 'RGB')

    def test_the_manifest_declares_the_png_icons(self):
        import json

        manifest = json.loads(Path('static/manifest.webmanifest').read_text())
        sources = {icon['src'] for icon in manifest['icons']}

        self.assertIn('/static/icons/icon-192.png', sources)
        self.assertIn('/static/icons/icon-512.png', sources)
        maskable = [i for i in manifest['icons'] if 'maskable' in i.get('purpose', '')]
        self.assertTrue(maskable, 'a maskable icon is required for Android')
        # An SVG must not be the maskable icon — Android will not mask it.
        for icon in maskable:
            self.assertTrue(icon['src'].endswith('.png'))


if __name__ == '__main__':
    unittest.main()
