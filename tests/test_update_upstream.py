import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("update_upstream", Path(__file__).parents[1] / "scripts/update-upstream.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.recipe = "pkgver=2.63.0\npkgrel=2\nsha256sums_x86_64=('oldx')\nsha256sums_aarch64=('olda')\n"
        (self.root / "PKGBUILD").write_text(self.recipe)
        (self.root / ".SRCINFO").write_text("old metadata")

    def test_newer_release_updates_both_architectures_together(self):
        with patch.object(updater, "ROOT", self.root), patch.object(updater, "release", return_value=("2.75.0", {})), patch.object(updater, "asset_hash", side_effect=["newx", "newa"]), patch.object(updater.subprocess, "check_output", side_effect=["1", b"new metadata"]):
            updater.main()
        self.assertIn("pkgver=2.75.0\npkgrel=1", (self.root / "PKGBUILD").read_text())
        self.assertIn("sha256sums_aarch64=('newa')", (self.root / "PKGBUILD").read_text())
        self.assertEqual((self.root / ".SRCINFO").read_bytes(), b"new metadata")

    def test_missing_architecture_preserves_recipe(self):
        with patch.object(updater, "ROOT", self.root), patch.object(updater, "release", return_value=("2.75.0", {})), patch.object(updater, "asset_hash", side_effect=["newx", ValueError("Missing arm64 asset")]), patch.object(updater.subprocess, "check_output", return_value="1"):
            with self.assertRaisesRegex(ValueError, "Missing arm64"):
                updater.main()
        self.assertEqual((self.root / "PKGBUILD").read_text(), self.recipe)
        self.assertEqual((self.root / ".SRCINFO").read_text(), "old metadata")

    def test_same_or_older_release_preserves_pkgrel(self):
        self.recipe = "pkgver=2.75.0\npkgrel=3\nsha256sums_x86_64=('newx')\nsha256sums_aarch64=('newa')\n"
        (self.root / "PKGBUILD").write_text(self.recipe)
        for version, comparison in [("2.75.0", "0"), ("2.63.0", "-1")]:
            with self.subTest(version=version), patch.object(updater, "ROOT", self.root), patch.object(updater, "release", return_value=(version, {})), patch.object(updater, "asset_hash", side_effect=["newx", "newa"]), patch.object(updater.subprocess, "check_output", return_value=comparison):
                updater.main()
            self.assertEqual((self.root / "PKGBUILD").read_text(), self.recipe)

    def test_missing_asset_and_download_failure(self):
        with self.assertRaisesRegex(ValueError, "Missing archive"):
            updater.asset_hash({}, "2.75.0", "x64", self.root)
        assets = {name: {"browser_download_url": name} for name in ["ocx-2.75.0-bun-linux-x64.tar.gz", "ocx-2.75.0-bun-linux-x64.tar.gz.sha256"]}
        with patch.object(updater, "download", side_effect=OSError("network unavailable")):
            with self.assertRaisesRegex(OSError, "network unavailable"):
                updater.asset_hash(assets, "2.75.0", "x64", self.root)

    def test_checksum_mismatch(self):
        filename = "ocx-2.75.0-bun-linux-x64.tar.gz"
        assets = {name: {"browser_download_url": name} for name in [filename, filename + ".sha256"]}

        def download(url, destination):
            destination.write_bytes(("0" * 64 + "  " + filename).encode() if url.endswith(".sha256") else b"archive")

        with patch.object(updater, "download", side_effect=download):
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                updater.asset_hash(assets, "2.75.0", "x64", self.root)


if __name__ == "__main__":
    unittest.main()
