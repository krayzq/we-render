# Usage

## Requirements

For pre-rendered `.mpkg` extraction: Linux and Python 3.10+.

For scene export: FFmpeg/ffprobe, a C compiler, X11/XWayland, Wallpaper Engine assets from Steam, and a compatible `linux-wallpaperengine` installation.

The WE Render installer does not install system packages, run AUR helpers, or compile third-party projects.

## Install

```sh
./install.sh
~/.local/bin/we-render --doctor
```

For fish:

```fish
fish_add_path ~/.local/bin
```

## Examples

```sh
we-render ./Knight.mpkg
we-render ./my-wallpaper/ --resolution 4k --fps 60 --duration 30
we-render ./my-wallpaper/ --codec hevc --crf 20
we-render ./my-wallpaper/ --encoder nvenc --bitrate 12M
we-render ./my-wallpaper/ --format png --at 5
we-render ./my-wallpaper/ --format gif --resolution 720p --fps 25 --duration 5
```

A Workshop URL first checks your local Steam libraries. If the item is missing, download it through Steam. The optional DepotDownloader path is available with `--download --steam-user YOUR_LOGIN`.

`original`, `720p`, `1080p`, `1440p`, `4k` and `WIDTHxHEIGHT` are valid resolution choices. Aspect ratio is preserved. Upscaling requires `--upscale`.

Pre-rendered MPKG/video inputs default to copying the original bytes. Explicit conversion can change resolution, FPS, duration and codec.

Scene exports are silent SDR. Live mouse/audio interaction cannot remain interactive in a video. Random particles may not loop seamlessly.

## Troubleshooting

```sh
we-render --doctor
we-render ./my-wallpaper/ --inspect
we-render ./my-wallpaper/ --startup-timeout 300
```

Use `--assets /path/to/wallpaper_engine/assets` to override asset discovery.

Renderer logs are written beside failed exports. Bridge startup failures are reported separately from missing assets or unsupported scene effects.

Uninstall:

```sh
python3 install.py --uninstall
```

Your exports, Steam files and cache are kept.
