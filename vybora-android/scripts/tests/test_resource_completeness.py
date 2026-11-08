import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_android_resources import PROJECT, declared_resources, missing_resources


class ResourceCompletenessTest(unittest.TestCase):
    def test_all_project_resource_references_resolve(self):
        self.assertEqual(dict(missing_resources()), {})

    def test_resource_aliases_are_indexed(self):
        resources = declared_resources()
        self.assertIn(("mipmap", "ic_launcher_foreground"), resources)
        self.assertIn(("drawable", "ic_launcher_foreground"), resources)
        self.assertIn(("font", "sans_flex"), resources)

    def test_audit_detects_missing_xml_and_kotlin_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "app/src/main"
            drawable = source / "res/drawable"
            drawable.mkdir(parents=True)
            (drawable / "existing.xml").write_text('<bitmap src="@drawable/missing_image"/>')
            (source / "Example.kt").write_text("val icon = R.drawable.missing_icon; val system = android.R.drawable.ic_delete")
            missing = missing_resources(project)
            self.assertIn(("drawable", "missing_image"), missing)
            self.assertIn(("drawable", "missing_icon"), missing)
            self.assertNotIn(("drawable", "ic_delete"), missing)

    def test_restored_assets_match_recorded_upstream_hashes(self):
        manifest = json.loads((PROJECT / "third_party/restored-assets.json").read_text())
        self.assertEqual(len(manifest["files"]), 29)
        for item in manifest["files"]:
            with self.subTest(asset=item["path"]):
                data = (PROJECT / item["path"]).read_bytes()
                self.assertEqual(len(data), item["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
                blob = b"blob " + str(len(data)).encode() + b"\0" + data
                self.assertEqual(hashlib.sha1(blob).hexdigest(), item["git_blob_sha1"])

    def test_bitmap_callers_have_real_png_resources(self):
        for name in ("icon", "ic_launcher_nobg"):
            data = (PROJECT / f"app/src/main/res/drawable/{name}.png").read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (512, 512))

    def test_font_licenses_are_packaged_with_the_apk(self):
        directory = PROJECT / "app/src/main/assets/licenses/fonts"
        for family in ("bbhbartle", "googlesansflex", "outfit", "plusjakartasans"):
            license_text = (directory / f"{family}-OFL.txt").read_text()
            self.assertIn("SIL OPEN FONT LICENSE", license_text)
        self.assertTrue((directory / "googlesansflex-TRADEMARKS.md").is_file())


if __name__ == "__main__":
    unittest.main()
