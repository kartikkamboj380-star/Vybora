package echo.music.iad1tya.utils

import android.content.Context
import androidx.annotation.OptIn
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.cache.Cache
import coil3.imageLoader
import echo.music.iad1tya.constants.LiteModeKey
import echo.music.iad1tya.constants.MaxImageCacheSizeKey
import echo.music.iad1tya.constants.MaxSongCacheSizeKey
import echo.music.iad1tya.db.MusicDatabase
import java.io.File
import timber.log.Timber

/**
 * The app's caches, and the rules that keep them small.
 *
 * Three things in a music app grow without a ceiling:
 *
 * - the **audio stream cache** — a few megabytes per track, and a queue of a hundred tracks adds
 *   up to a gigabyte nobody asked for;
 * - the **artwork cache** (Coil) — the app shows a lot of thumbnails, and each one is cached to
 *   disk as well as to memory;
 * - the **SQLite write-ahead log**, which is rewritten on every checkpoint and can be left sitting
 *   at tens of megabytes between checkpoints.
 *
 * This object is the one place that decides how big each of them is allowed to get:
 *
 * - [songCacheLimitMb] and [imageCacheLimitMb] are the ceilings the cache providers read, so a
 *   fresh install never grows past them;
 * - [trimAll] brings an install that has already grown back under them, which is what makes the
 *   ceiling bite for people who upgraded rather than installed fresh;
 * - **lite mode** lowers both ceilings and trims on every start.
 *
 * The user's own choice always wins over a default: a ceiling the user raised is never lowered
 * behind their back, and only lite mode — which the user switched on deliberately — overrides it.
 */
@OptIn(UnstableApi::class)
object CacheGovernor {

  private const val TAG = "CacheGovernor"

  /** Default ceiling for the audio stream cache. */
  const val DEFAULT_SONG_CACHE_MB = 256

  /** Default ceiling for the artwork cache. */
  const val DEFAULT_IMAGE_CACHE_MB = 96

  /** Lite mode's ceiling for the audio stream cache. */
  const val LITE_SONG_CACHE_MB = 64

  /** Lite mode's ceiling for the artwork cache. */
  const val LITE_IMAGE_CACHE_MB = 32

  /** How much was reclaimed by a trim. */
  data class TrimReport(
    val songCacheFreedBytes: Long = 0,
    val imageCacheFreedBytes: Long = 0,
    val databaseFreedBytes: Long = 0,
  ) {
    val totalFreedBytes: Long
      get() = songCacheFreedBytes + imageCacheFreedBytes + databaseFreedBytes
  }

  /** Whether lite mode is switched on. */
  fun isLiteMode(context: Context): Boolean = context.dataStore[LiteModeKey] ?: false

  /**
   * The audio stream cache's ceiling, in megabytes.
   *
   * `-1` means "keep everything" and `0` means "cache nothing"; both are the user's explicit
   * choice and are passed through untouched.
   */
  fun songCacheLimitMb(context: Context): Int =
    effectiveSongCacheMb(
      configuredMb = context.dataStore[MaxSongCacheSizeKey] ?: DEFAULT_SONG_CACHE_MB,
      liteMode = isLiteMode(context),
    )

  /** The artwork cache's ceiling, in megabytes. `0` means "cache nothing". */
  fun imageCacheLimitMb(context: Context): Int =
    effectiveImageCacheMb(
      configuredMb = context.dataStore[MaxImageCacheSizeKey] ?: DEFAULT_IMAGE_CACHE_MB,
      liteMode = isLiteMode(context),
    )

  /**
   * The audio stream cache's ceiling for a given setting and lite-mode state.
   *
   * Kept separate from [songCacheLimitMb] so the settings screen can show the ceiling it is
   * actually enforcing without reading the preferences on every recomposition.
   */
  fun effectiveSongCacheMb(configuredMb: Int, liteMode: Boolean): Int {
    if (configuredMb <= 0) return configuredMb
    if (!liteMode) return configuredMb
    return minOf(configuredMb, LITE_SONG_CACHE_MB)
  }

  /** The artwork cache's ceiling for a given setting and lite-mode state. */
  fun effectiveImageCacheMb(configuredMb: Int, liteMode: Boolean): Int {
    if (configuredMb <= 0) return configuredMb
    if (!liteMode) return configuredMb
    return minOf(configuredMb, LITE_IMAGE_CACHE_MB)
  }

  /**
   * Brings every cache back under its ceiling.
   *
   * Safe to call at any time: nothing here is required for playback, and a cache that is already
   * under its ceiling is left exactly as it is.
   */
  fun trimAll(
    context: Context,
    playerCache: Cache? = null,
    database: MusicDatabase? = null,
  ): TrimReport {
    val songFreed = trimSongCache(playerCache, songCacheLimitMb(context))
    val imageFreed = trimImageCache(context, imageCacheLimitMb(context))
    val dbFreed = trimDatabase(database)
    val report = TrimReport(songFreed, imageFreed, dbFreed)
    if (report.totalFreedBytes > 0) {
      Timber.tag(TAG)
        .d(
          "Trimmed ${report.totalFreedBytes / 1024} KiB " +
            "(songs ${report.songCacheFreedBytes / 1024} KiB, " +
            "images ${report.imageCacheFreedBytes / 1024} KiB, " +
            "db ${report.databaseFreedBytes / 1024} KiB)"
        )
    }
    return report
  }

  /**
   * Drops the least recently played stream cache entries until the cache fits its ceiling.
   *
   * The order is the cache's own: every span knows when it was last touched, and a track's most
   * recently touched span says when the listener last had it on.
   */
  fun trimSongCache(cache: Cache?, limitMb: Int): Long {
    if (cache == null || limitMb < 0) return 0
    val limitBytes = limitMb.toLong() * 1024 * 1024
    val before = runCatching { cache.cacheSpace }.getOrDefault(0L)
    if (before <= limitBytes) return 0

    val oldestFirst =
      runCatching {
          cache.keys
            .mapNotNull { key ->
              val spans = cache.getCachedSpans(key)
              if (spans.isEmpty()) null else key to spans.maxOf { it.lastTouchTimestamp }
            }
            .sortedBy { it.second }
        }
        .getOrDefault(emptyList())

    for ((key, _) in oldestFirst) {
      if (runCatching { cache.cacheSpace }.getOrDefault(0L) <= limitBytes) break
      runCatching { cache.removeResource(key) }
        .onFailure { Timber.tag(TAG).w(it, "Could not remove $key from the stream cache") }
    }

    val after = runCatching { cache.cacheSpace }.getOrDefault(before)
    return (before - after).coerceAtLeast(0)
  }

  /**
   * Drops the oldest artwork files until Coil's disk cache fits its ceiling.
   *
   * Coil's own index is left alone: it already tolerates files that are no longer there, and
   * deleting the journal would only make it re-index what is left.
   */
  fun trimImageCache(context: Context, limitMb: Int): Long {
    if (limitMb < 0) return 0
    val limitBytes = limitMb.toLong() * 1024 * 1024
    val diskCache = runCatching { context.imageLoader.diskCache }.getOrNull() ?: return 0
    val directory = runCatching { diskCache.directory.toFile() }.getOrNull() ?: return 0
    if (!directory.exists() || !directory.isDirectory) return 0

    val files =
      directory.listFiles()?.filter { it.isFile && !it.name.startsWith("journal") } ?: return 0
    val before = files.sumOf { it.length() }
    if (before <= limitBytes) return 0

    var freed = 0L
    for (file in files.sortedBy { it.lastModified() }) {
      if (before - freed <= limitBytes) break
      val size = file.length()
      if (file.delete()) {
        freed += size
      }
    }
    return freed
  }

  /**
   * Truncates the database's write-ahead log.
   *
   * The log holds every page written since the last checkpoint; truncating it hands those pages
   * back to the database file and leaves the log empty.
   */
  fun trimDatabase(database: MusicDatabase?): Long {
    if (database == null) return 0
    return runCatching {
        val helper = database.openHelper
        val db = helper.writableDatabase
        val walFile = File(db.path + "-wal")
        val before = if (walFile.exists()) walFile.length() else 0L
        db.query("PRAGMA wal_checkpoint(TRUNCATE)").close()
        val after = if (walFile.exists()) walFile.length() else 0L
        (before - after).coerceAtLeast(0)
      }
      .getOrElse {
        Timber.tag(TAG).w(it, "Could not truncate the database write-ahead log")
        0L
      }
  }
}
