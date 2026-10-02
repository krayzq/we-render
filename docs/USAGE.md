# Quick guide

## Requirements

Linux, Python 3.10+. The download includes the Python terminal libraries.
Original MPKG/video extraction does not need FFmpeg or the scene renderer.

For scene export: a compatible [Almamu/linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine),
owned Wallpaper Engine files installed through Steam, FFmpeg/ffprobe,
`cc` and an X11/XWayland `DISPLAY`. No Windows runtime is launched.
The GLFW adapter's compatibility with a real renderer build is not yet established
in this release; this limitation is separate from package dependencies being present.

Arch:

```sh
sudo pacman -S --needed python ffmpeg gcc xorg-xwayland
# With an already installed AUR helper; inspect its build files:
yay -S linux-wallpaperengine-git
```

Debian/Ubuntu: install `python3 ffmpeg gcc xwayland`, then follow the native
renderer's upstream build instructions. This project does not bundle that renderer.

```sh
./install.sh
~/.local/bin/we-render --doctor
```

`--doctor` checks dependencies, not scene correctness. Exit 3 means the scene
runtime is incomplete; original video extraction can still work.
For fish: `fish_add_path ~/.local/bin`. Without installation: `python3 we-render.pyz`.

## Export

```sh
we-render ./my-wallpaper/ --resolution 4k --fps 60 --duration 30
we-render ./my-wallpaper/ --codec hevc --crf 20
we-render ./my-wallpaper/ --encoder nvenc --bitrate 12M
we-render ./my-wallpaper/ --format png --at 5
we-render ./my-wallpaper/ --format gif --resolution 720p --fps 25 --duration 5
we-render ./Knight.mpkg --format original
we-render ./Knight.mpkg --format mp4 --resolution 1080p --fps 30
```

`original`, `720p`, `1080p`, `1440p`, `4k` and `WIDTHxHEIGHT` are resolution choices.
They preserve aspect without cropping. Upscaling requires `--upscale`; it does not
restore lost detail. Sizes may be rounded to even pixels. GIF is limited to 1080p
and uses per-frame palettes to bound memory; its timing is quantized to 10 ms.

MPKG and video inputs default to copying the original, including audio. Explicit
conversion repeats a shorter input to the requested duration, drops audio and
may lose quality. FPS conversion repeats/drops frames, not AI interpolation.
An original non-MP4 file retains its true extension; it is never just renamed MP4.

A scene starts with 2 seconds of simulation warm-up for video; change `--warmup`.
For PNG/JPG, `--at` is the simulation position, rounded to the selected frame step.
Only animations supported by the native engine can be included. Async video layers,
audio-reactive behavior and some scripts may not follow the fixed simulation clock.
SDR only; no HDR-preservation claim. Random particles can create a visible loop seam.

## Workshop downloads

A URL/ID first checks Steam libraries and the local cache. If missing, subscribe
through Steam and wait for the download. Alternatively, install
[DepotDownloader](https://github.com/SteamRE/DepotDownloader) yourself and run:

```sh
we-render "STEAM_WORKSHOP_URL" --download --steam-user YOUR_LOGIN
```

DepotDownloader handles its own login/Steam Guard prompts. Never put your password
in the command. Ownership/access rules still apply. This optional network path has
not been tested against a real logged-in Steam account here. `--offline` disables it.
There is no service that this program uses to download pre-rendered MPKGs.

## Troubleshooting

`--assets /path/to/wallpaper_engine/assets` overrides asset discovery.
`--steam-library /games/SteamLibrary` adds a Steam library.
`--scene-size 3840x2160` overrides missing canvas metadata.
`--startup-timeout 300` allows longer scene loading/warm-up.
`--inspect` lists metadata and MPKG video entries. Use `--entry "wallpaper.mp4"`
when multiple videos make selection ambiguous.

Renderer errors are logged beside exports. Inspect the output visually; dimensions
and FPS alone do not prove that all effects rendered correctly. `--flip` reverses
orientation when diagnosing renderer differences. There is no desktop-capture fallback.
Render only wallpapers you trust: this is not a sandbox for untrusted shaders/scripts.
Ctrl+C removes unfinished exports. Logs and already finished files are retained.

Uninstall: `python3 install.py --uninstall`. Your exports, Steam data and cache remain.
Cache: `${XDG_CACHE_HOME:-~/.cache}/we-render`. It can be deleted manually when not exporting.
