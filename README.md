![we-render](docs/cover.png)

**Your wallpaper, as a file.** An English Linux CLI for original video extraction
and native scene export. No Windows, Wine or desktop recording.

> **0.1.0b1 · Beta.** The frame-export pipeline is tested; integration with a real
> `linux-wallpaperengine` build and its effects is **not yet validated here**.
> This is not a guaranteed converter for every Workshop scene. [Test record](docs/TESTING.md).

## Install

Download and unpack the **Linux ZIP** from this repository's Releases, then:

```sh
cd we-render
./install.sh
~/.local/bin/we-render
```

Python **3.10+** is required. Video encoding needs **FFmpeg**.
Scene export additionally needs **Almamu/linux-wallpaperengine**, your installed
Wallpaper Engine **assets**, a **C compiler** and **X11/XWayland**. These are not
bundled. `./install.sh --deps` offers dependency setup on Arch/Debian;
[full prerequisites](docs/USAGE.md#requirements).

## Use

```sh
we-render                                      # interactive terminal menu
we-render ./Knight.mpkg                         # original video, unchanged
we-render ./my-wallpaper/                       # beta scene → MP4
we-render "https://steamcommunity.com/sharedfiles/filedetails/?id=3775394622"
we-render ./my-wallpaper/ --wizard              # choose export settings
we-render ./my-wallpaper/ --format png --at 5    # rendered frame at 5 seconds
```

Scenes default to **4K fit · 60 FPS · 30 s · H.264**. Original proportions are kept;
no automatic upscaling. Outputs go to `./exports/`; existing files are never replaced.
A URL first finds local Steam files. Missing items require Steam download or the
optional authenticated [DepotDownloader path](docs/USAGE.md#workshop-downloads).

**MP4 · GIF · PNG · JPG**, resolution, duration, FPS, CRF/bitrate, H.264/HEVC and
optional NVENC. `--format original` keeps an embedded video's bytes, sound and FPS.
Rendered/converted files are silent; live interaction cannot remain interactive in a video.

## Notes

A `.mpkg` with a pre-rendered video is extracted, not re-rendered. A `scene.pkg`
uses the separate Linux renderer; missing scene support is **not** replaced with a
static texture. Effects depend on that renderer. Loops are not guaranteed seamless.

[User guide](docs/USAGE.md) · [Publish on GitHub / RU](docs/PUBLISHING.ru.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Testing](docs/TESTING.md)

MIT for our code. [Third-party notices](THIRD_PARTY.md).
Not affiliated with Wallpaper Engine or Valve. No proprietary assets are included.
