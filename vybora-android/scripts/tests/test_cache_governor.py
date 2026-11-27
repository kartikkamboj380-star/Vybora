"""Guards for the app's cache ceilings.

The app promises to stay small: the audio stream cache, the artwork cache and the
database's write-ahead log all have ceilings, and "lite mode" lowers the two that
grow on their own. These tests read the sources that decide those ceilings so a
later change cannot quietly undo the promise.
"""

from pathlib import Path
import re
import unittest

PROJECT = Path(__file__).resolve().parents[2]
APP = PROJECT / "app/src/main/kotlin/com/music/echo"
CACHE_GOVERNOR = APP / "utils/CacheGovernor.kt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class CacheCeilingTest(unittest.TestCase):
    def test_defaults_and_lite_ceilings_are_the_documented_ones(self):
        source = read(CACHE_GOVERNOR)
        expected = {
            "DEFAULT_SONG_CACHE_MB": 256,
            "DEFAULT_IMAGE_CACHE_MB": 96,
            "LITE_SONG_CACHE_MB": 64,
            "LITE_IMAGE_CACHE_MB": 32,
        }
        for name, value in expected.items():
            with self.subTest(constant=name):
                match = re.search(rf"const val {name}\s*=\s*(\d+)", source)
                self.assertIsNotNone(match, f"{name} is missing")
                self.assertEqual(int(match.group(1)), value)

    def test_lite_mode_lowers_both_ceilings(self):
        source = read(CACHE_GOVERNOR)
        for function, lite_constant in (
            ("effectiveSongCacheMb", "LITE_SONG_CACHE_MB"),
            ("effectiveImageCacheMb", "LITE_IMAGE_CACHE_MB"),
        ):
            with self.subTest(function=function):
                body = re.search(rf"fun {function}\([^)]*\): Int \{{(.*?)\n  \}}", source, re.S)
                self.assertIsNotNone(body, f"{function} is missing")
                body = body.group(1)
                self.assertIn("if (!liteMode) return configuredMb", body)
                self.assertIn(f"minOf(configuredMb, {lite_constant})", body)

    def test_a_zero_or_unlimited_setting_is_the_user_s_own_choice(self):
        source = read(CACHE_GOVERNOR)
        for function in ("effectiveSongCacheMb", "effectiveImageCacheMb"):
            with self.subTest(function=function):
                body = re.search(rf"fun {function}\([^)]*\): Int \{{(.*?)\n  \}}", source, re.S)
                self.assertIsNotNone(body)
                self.assertIn("if (configuredMb <= 0) return configuredMb", body.group(1))

    def test_the_song_cache_provider_reads_the_effective_ceiling(self):
        source = read(APP / "di/AppModule.kt")
        self.assertIn("CacheGovernor.songCacheLimitMb(context)", source)

    def test_coil_disk_cache_uses_the_effective_ceiling_not_the_raw_setting(self):
        source = read(APP / "App.kt")
        self.assertIn("CacheGovernor.imageCacheLimitMb(this@App)", source)
        # Reading the raw preference here would ignore lite mode entirely.
        self.assertNotIn("it[MaxImageCacheSizeKey]", source)
        self.assertIn("maxSizeBytes(cacheSize * 1024 * 1024L)", source)

    def test_the_image_memory_cache_is_a_tenth_of_the_heap(self):
        source = read(APP / "App.kt")
        self.assertIn("maxSizePercent(context, 0.10)", source)

    def test_lite_mode_trims_what_is_already_on_disk(self):
        source = read(APP / "ui/screens/settings/StorageSettings.kt")
        self.assertIn("CacheGovernor.trimAll(context, playerCache, database)", source)
        self.assertIn("CacheGovernor.effectiveSongCacheMb(maxSongCacheSize, liteMode)", source)
        self.assertIn("CacheGovernor.effectiveImageCacheMb(maxImageCacheSize, liteMode)", source)


class CacheTrimTest(unittest.TestCase):
    def test_the_startup_trim_runs_in_the_application(self):
        source = read(APP / "App.kt")
        self.assertIn("CacheGovernor.trimAll(this@App)", source)

    def test_the_music_service_trims_the_database_on_start(self):
        source = read(APP / "playback/MusicService.kt")
        self.assertIn("CacheGovernor", source)

    def test_the_trim_drops_the_least_recently_played_streams_first(self):
        source = read(CACHE_GOVERNOR)
        self.assertIn("lastTouchTimestamp", source)
        self.assertIn("removeResource(key)", source)

    def test_the_write_ahead_log_is_truncated(self):
        source = read(CACHE_GOVERNOR)
        self.assertIn("PRAGMA wal_checkpoint(TRUNCATE)", source)


if __name__ == "__main__":
    unittest.main()
