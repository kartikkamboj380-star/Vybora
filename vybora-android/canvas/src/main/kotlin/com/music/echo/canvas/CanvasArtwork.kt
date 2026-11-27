package echo.music.iad1tya.canvas

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CanvasArtwork(
  val name: String? = null,
  val artist: String? = null,
  @SerialName("albumId") val albumId: String? = null,
  val albumName: String? = null,
  val static: String? = null,
  val animated: String? = null,
  val videoUrl: String? = null,
  val clipStartMs: Long? = null,
  val clipEndMs: Long? = null,
  /** The YouTube video the artwork was resolved from, when it came from one. */
  val videoId: String? = null,
) {
  val preferredAnimationUrl: String?
    get() = animated ?: videoUrl
}
