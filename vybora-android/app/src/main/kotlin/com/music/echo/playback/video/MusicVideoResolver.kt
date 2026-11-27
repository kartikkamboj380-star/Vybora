package echo.music.iad1tya.playback.video

import echo.music.iad1tya.canvas.YouTubeVideoCanvasProvider
import timber.log.Timber

/**
 * A music video that can play alongside the audio.
 */
data class MusicVideoSource(
  /** The YouTube video the stream came from. */
  val videoId: String,
  /** The stream to play. */
  val url: String,
  val title: String? = null,
  val artist: String? = null,
)

/**
 * Finds the music video for a song.
 *
 * A YouTube Music track is usually an audio upload with no picture at all, so the video has to be
 * looked for: the track's own id is tried first — some tracks *are* the video — and when that
 * has nothing to play, the official video for the song is searched for.
 *
 * The resolution itself is shared with the canvas, which needs a video for the same reason; the
 * difference is the ceiling on the quality. The canvas shows a five-second loop and does not
 * care, while this plays the whole thing and asks for a height a phone can actually show.
 */
object MusicVideoResolver {
  private const val TAG = "MusicVideoResolver"

  /**
   * The tallest rendition to ask for.
   *
   * 720p is what a phone screen shows, and it costs a fraction of what 1080p does.
   */
  const val MAX_HEIGHT = 720

  /**
   * The music video for [songId], or null when there is none to be found.
   *
   * This does network work — a search when the track itself has no video — so it belongs off the
   * main thread.
   */
  suspend fun resolve(
    songId: String,
    title: String? = null,
    artist: String? = null,
    durationSec: Long? = null,
  ): MusicVideoSource? {
    if (songId.isBlank()) return null
    return try {
      val artwork =
        YouTubeVideoCanvasProvider.getCanvasForVideo(
          videoId = songId,
          title = title?.takeIf { it.isNotBlank() },
          artist = artist?.takeIf { it.isNotBlank() },
          durationSec = durationSec,
          maxHeight = MAX_HEIGHT,
        )

      val url = artwork?.videoUrl?.takeIf { it.isNotBlank() }
      if (url == null) {
        Timber.tag(TAG).d("No music video found for $songId")
        return null
      }

      MusicVideoSource(
        videoId = artwork.videoId ?: songId,
        url = url,
        title = title,
        artist = artist,
      )
    } catch (e: Exception) {
      Timber.tag(TAG).w(e, "Could not resolve a music video for $songId")
      null
    }
  }
}
