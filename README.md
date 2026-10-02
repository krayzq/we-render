![we-render](docs/cover.png)

# WE Render

**Your wallpaper, as a file.** Linux CLI for extracting pre-rendered Wallpaper Engine video and exporting supported native scenes without desktop recording.

> **0.1.0b2 · Beta.** Native scene export depends on the installed Linux renderer and may not reproduce every Wallpaper Engine effect yet.

## Install

Download the **Linux ZIP** from Releases, unpack it, then run:

```sh
./install.sh
~/.local/bin/we-render --doctor
```

The installer is non-interactive and never runs `pacman`, `yay`, `apt` or builds third-party packages for you.

## Use

```sh
we-render
we-render ./Knight.mpkg
we-render ./my-wallpaper/
we-render "https://steamcommunity.com/sharedfiles/filedetails/?id=3775394622"
we-render ./my-wallpaper/ --wizard
we-render ./my-wallpaper/ --format png --at 5
```

Scene defaults: **4K fit · 60 FPS · 30 s · H.264**.

Supported outputs: **MP4 · GIF · PNG · JPG**. Pre-rendered `.mpkg` video can be copied without re-encoding.

For scene export you also need Wallpaper Engine assets, FFmpeg and a compatible native `linux-wallpaperengine` installation. The current installer does **not** build that renderer automatically.

[Usage guide](docs/USAGE.md) · [Changelog](CHANGELOG.md) · [License](LICENSE)

Not affiliated with Wallpaper Engine or Valve. No proprietary assets are included.
