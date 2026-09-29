from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

REQUIRED = {
    'static/icons/icon-192.png': (192, 192),
    'static/icons/icon-512.png': (512, 512),
    'static/icons/icon-maskable-512.png': (512, 512),
    'static/icons/apple-touch-icon.png': (180, 180),
    'static/icons/favicon-32.png': (32, 32),
    'static/social-card.png': (1200, 630),
}


class BrandAssetTest(unittest.TestCase):
    def test_favicon_contains_the_radar_target_mark(self):
        root = ET.parse('static/favicon.svg').getroot()
        namespace = {'svg': 'http://www.w3.org/2000/svg'}

        self.assertGreaterEqual(len(root.findall('.//svg:circle', namespace)), 6)

    def test_clean_and_outlined_transparent_logo_lockups_are_available(self):
        namespace = {'svg': 'http://www.w3.org/2000/svg'}
        for path, expected_fill in (
            ('static/branding/soccer-radar-logo.svg', {'#f2f2f2', '#7cff00'}),
            ('static/branding/soccer-radar-logo-outlined.svg', {'none'}),
        ):
            with self.subTest(path=path):
                root = ET.parse(path).getroot()
                self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')
                self.assertFalse(root.findall('svg:rect', namespace), 'logo must have a transparent background')
                self.assertIn('Soccer Radar', root.find('svg:title', namespace).text)
                text = root.findall('.//svg:text', namespace)
                self.assertEqual(len(text), 2)
                self.assertEqual([''.join(node.itertext()) for node in text], ['SOCCER', 'RADAR'])
                self.assertEqual({node.get('fill') for node in text}, expected_fill)
                if 'outlined' in path:
                    self.assertEqual({node.get('stroke') for node in text}, {'#f2f2f2', '#7cff00'})

    def test_pwa_and_ios_icons_have_a_white_radar_beacon_at_the_center(self):
        from PIL import Image

        assets = (
            ('static/icons/icon-512.png', (256, 256)),
            (
                'clients/ios/SoccerScanner/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png',
                (512, 512),
            ),
        )
        for path, center in assets:
            with self.subTest(path=path), Image.open(path) as image:
                red, green, blue = image.convert('RGB').getpixel(center)
                self.assertGreater(min(red, green, blue), 200)

    def test_social_card_places_the_wordmark_to_the_right_of_the_radar(self):
        from PIL import Image

        with Image.open('static/social-card.png') as image:
            wordmark_region = image.convert('RGB').crop((850, 190, 1160, 440))
            self.assertIsNotNone(wordmark_region.getbbox())

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
