package echo.music.iad1tya.ui.player

import android.view.TextureView
import android.view.ViewGroup
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import androidx.annotation.OptIn
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.VideoSize
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import androidx.media3.ui.AspectRatioFrameLayout
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import timber.log.Timber

/**
 * The song's music video, playing behind the player while the audio keeps playing.
 *
 * The video carries no sound of its own — the track the listener chose is the sound, and the
 * picture follows it. That is why it is muted, and why it is kept in step with the audio player
 * rather than run on its own clock: a music video that drifts out of sync with the song it
 * belongs to is worse than no video at all.
 *
 * The video is a separate player from the audio on purpose. The audio belongs to
 * [echo.music.iad1tya.playback.MusicService] and has to survive the player being closed, the
 * screen being locked and the notification being used; a picture that stops when the screen does
 * is exactly what should happen.
 */
@OptIn(UnstableApi::class)
@Composable
fun MusicVideoBackground(
  url: String,
  isPlaying: Boolean,
  audioPositionMs: Long,
  modifier: Modifier = Modifier,
) {
  val context = LocalContext.current
  var isVideoReady by remember(url) { mutableStateOf(false) }

  val trackSelector =
    remember {
      DefaultTrackSelector(context).apply {
        parameters = buildUponParameters().setMaxVideoSize(MAX_WIDTH, MAX_HEIGHT).build()
      }
    }

  val exoPlayer =
    remember {
      ExoPlayer.Builder(context)
        .setTrackSelector(trackSelector)
        .setLoadControl(
          DefaultLoadControl.Builder()
            // A video buffer is big: a couple of seconds of 720p is already several megabytes.
            // Keeping it small is what stops the video from eating the memory the app keeps
            // free for everything else.
            .setTargetBufferBytes(TARGET_BUFFER_BYTES)
            .setBufferDurationsMs(MIN_BUFFER_MS, MAX_BUFFER_MS, BUFFER_FOR_PLAYBACK_MS, 1_000)
            .build()
        )
        .build()
        .apply {
          // The music is the audio track's job; this player only draws.
          setAudioAttributes(
            AudioAttributes.Builder()
              .setUsage(C.USAGE_MEDIA)
              .setContentType(C.AUDIO_CONTENT_TYPE_MOVIE)
              .build(),
            false,
          )
          volume = 0f
          repeatMode = Player.REPEAT_MODE_ONE
          videoScalingMode = C.VIDEO_SCALING_MODE_SCALE_TO_FIT_WITH_CROPPING
          playWhenReady = false
        }
    }

  val aspectRatioFrameLayout =
    remember {
      AspectRatioFrameLayout(context).apply {
        resizeMode = AspectRatioFrameLayout.RESIZE_MODE_ZOOM
        setBackgroundColor(android.graphics.Color.TRANSPARENT)
      }
    }

  DisposableEffect(exoPlayer) {
    val listener =
      object : Player.Listener {
        override fun onRenderedFirstFrame() {
          isVideoReady = true
        }

        override fun onVideoSizeChanged(videoSize: VideoSize) {
          if (videoSize.width > 0 && videoSize.height > 0) {
            aspectRatioFrameLayout.setAspectRatio(videoSize.width.toFloat() / videoSize.height)
          }
        }

        override fun onPlayerError(error: androidx.media3.common.PlaybackException) {
          Timber.tag(TAG).w(error, "The music video could not be played")
          isVideoReady = false
        }
      }
    exoPlayer.addListener(listener)
    onDispose { exoPlayer.removeListener(listener) }
  }

  LaunchedEffect(url) {
    isVideoReady = false
    val mediaItem =
      MediaItem.Builder()
        .setUri(url)
        .setMimeType(
          if (url.contains("m3u8", ignoreCase = true)) MimeTypes.APPLICATION_M3U8
          else MimeTypes.VIDEO_MP4
        )
        .build()
    exoPlayer.setMediaItem(mediaItem)
    exoPlayer.prepare()
  }

  LaunchedEffect(isPlaying) { exoPlayer.playWhenReady = isPlaying }

  // The music keeps playing in the background; the picture must not. A video that nobody is
  // watching is data and battery spent for nothing.
  val latestIsPlaying by rememberUpdatedState(isPlaying)
  val lifecycleOwner = LocalLifecycleOwner.current
  DisposableEffect(lifecycleOwner, exoPlayer) {
    val observer =
      LifecycleEventObserver { _, event ->
        when (event) {
          Lifecycle.Event.ON_STOP -> exoPlayer.pause()
          Lifecycle.Event.ON_START -> exoPlayer.playWhenReady = latestIsPlaying
          else -> Unit
        }
      }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
  }

  // Keep the picture with the song. The audio position is read through a remembered state so
  // that this loop is not restarted every time the position changes.
  val latestAudioPosition by rememberUpdatedState(audioPositionMs)
  LaunchedEffect(url) {
    while (isActive) {
      delay(SYNC_INTERVAL_MS)
      val target = latestAudioPosition
      if (target <= 0L) continue
      val videoPosition = exoPlayer.currentPosition
      if (videoPosition > 0L && kotlin.math.abs(videoPosition - target) > SYNC_THRESHOLD_MS) {
        exoPlayer.seekTo(target)
      }
    }
  }

  DisposableEffect(exoPlayer) { onDispose { exoPlayer.release() } }

  val alpha by
    animateFloatAsState(
      targetValue = if (isVideoReady) 1f else 0f,
      animationSpec = tween(durationMillis = 600),
      label = "musicVideoAlpha",
    )

  AndroidView(
    factory = { _ ->
      aspectRatioFrameLayout.apply {
        isEnabled = false
        isClickable = false
        isFocusable = false

        if (childCount == 0) {
          val textureView =
            TextureView(context).apply {
              layoutParams = ViewGroup.LayoutParams(MATCH_PARENT, MATCH_PARENT)
            }
          addView(textureView)
          exoPlayer.setVideoTextureView(textureView)
        }
      }
    },
    modifier = modifier.alpha(alpha),
  )
}

private const val TAG = "MusicVideoBackground"

/** The tallest rendition the player will ask for. */
private const val MAX_WIDTH = 1280
private const val MAX_HEIGHT = 720

/** Four megabytes of video buffer: enough to ride over a hiccup, small enough to stay cheap. */
private const val TARGET_BUFFER_BYTES = 4 * 1024 * 1024

private const val MIN_BUFFER_MS = 2_500
private const val MAX_BUFFER_MS = 15_000
private const val BUFFER_FOR_PLAYBACK_MS = 500

/** How often the picture is checked against the song. */
private const val SYNC_INTERVAL_MS = 500L

/** How far the picture may drift from the song before it is pulled back into line. */
private const val SYNC_THRESHOLD_MS = 1_200L
