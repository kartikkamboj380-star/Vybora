from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[2]
RES = PROJECT / "app/src/main/res"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class BrandingResourcesTest(unittest.TestCase):
    def test_manifest_drawables_and_mipmaps_exist(self):
        resources = set()
        for module in PROJECT.iterdir():
            resource_root = module / "src/main/res"
            if not resource_root.is_dir():
                continue
            for directory in resource_root.iterdir():
                if directory.is_dir():
                    kind = directory.name.split("-", 1)[0]
                    resources.update((kind, path.stem) for path in directory.iterdir() if path.is_file())
        manifest = ET.parse(PROJECT / "app/src/main/AndroidManifest.xml")
        for node in manifest.iter():
            for value in node.attrib.values():
                match = re.fullmatch(r"@(drawable|mipmap)/([a-z0-9_]+)", value)
                if match:
                    with self.subTest(resource=value):
                        self.assertIn(match.groups(), resources)

    def test_quick_settings_icon_reuses_the_monochrome_brand_silhouette(self):
        original = ET.parse(RES / "drawable/ic_vybora_mark.xml").getroot()
        icon = ET.parse(RES / "drawable/ic_qs_vybora_logo.xml").getroot()
        self.assertEqual(icon.attrib[ANDROID + "width"], "24dp")
        self.assertEqual(icon.find("path").attrib[ANDROID + "strokeColor"], "@android:color/white")
        self.assertEqual(icon.find("path").attrib[ANDROID + "pathData"],
                         original.find("path").attrib[ANDROID + "pathData"])

    def test_tv_banner_has_landscape_dimensions_and_brand_colors(self):
        banner = ET.parse(RES / "mipmap-anydpi/tv_banner.xml").getroot()
        self.assertEqual(banner.attrib[ANDROID + "viewportWidth"], "320")
        self.assertEqual(banner.attrib[ANDROID + "viewportHeight"], "180")
        self.assertEqual(banner.find("path").attrib[ANDROID + "fillColor"], "@color/vybora_splash_background")
        self.assertEqual(len(banner.find("group").findall("path")), 2)


if __name__ == "__main__":
    unittest.main()
