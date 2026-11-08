# Restored bundled resources

The extracted source archive omitted binary images, launcher foregrounds, and
fonts still referenced by its Android XML and Kotlin code. These are required
source assets, not APK/build outputs.

## Upstream images and fonts

Missing UI images, legacy/custom launcher foregrounds (xxxhdpi), and the BBH
Bartle, Outfit, and Plus Jakarta Sans fonts were recovered from
[EchoMusicApp/Echo-Music](https://github.com/EchoMusicApp/Echo-Music) at commit
`ee10c5c8c924c676429b9e04d282c5adef7db410`. The base project is GPL-3.0; retain
its existing `LICENSE` and upstream credits. The fonts retain their SIL OFL
licenses separately.

`restored-assets.json` records the exact source commit, source paths, Git blob
SHA-1, SHA-256, and byte length for every restored binary. No upstream source
code, manifest, theme, package identity, or primary Echo logo was substituted
for Vybora's existing code/branding.

## Open-licensed Google Sans Flex

The upstream `google_sans_flex.ttf` contains a restricted, non-open-source font
license and is **not included**. Instead, the font comes from the official
[Google Fonts](https://github.com/google/fonts) SIL OFL release at commit
`86aced91de05cd4f96a06838124cca45be337b2b`, file
`ofl/googlesansflex/GoogleSansFlex[ROND,opsz,slnt,wdth,wght].ttf`.

The existing `sans_flex` resource name aliases this same font, avoiding duplicate
font binaries. OFL texts for all four font families and the Google Sans Flex
trademark notice are included in `app/src/main/assets/licenses/fonts/`, so they
are packaged with the APK as well as preserved in source.

## Vybora primary identity

Primary launcher/notification/share branding stays Vybora. `icon.png` and
`ic_launcher_nobg.png` are raster renditions of the existing
`drawable/ic_vybora_mark.xml`, not copied Echo logos. They remain PNGs because
existing `BitmapDrawable` and bitmap-decoding callers need bitmap resources.
Regenerate them using `scripts/render_branding_assets.py` with Pillow installed.
Resource aliases in `values/branding_aliases.xml` preserve the original drawable,
mipmap, and font identifiers without changing Kotlin call sites.

Run `python3 -B scripts/check_android_resources.py` before building to detect
missing project-owned resources; `scripts/tests/` also verifies the restored
asset hashes and packaged font licenses.
