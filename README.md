![we-render](docs/cover.png)

# WE Render

Linux CLI for turning Wallpaper Engine media and supported native scenes into normal files.

> **0.1.0b3 · Beta.** Pre-rendered MPKG extraction is reliable. Native scene export depends on the installed Linux renderer and may not reproduce every effect yet.

## Install

Download the **Linux ZIP** from Releases, unpack it, then:

```sh
./install.sh
~/.local/bin/we-render --doctor
```

The installer is non-interactive. It never runs `pacman`, `yay`, `apt` or builds third-party packages.

## Use

```sh
we-render
we-render ./Knight.mpkg
we-render ./my-wallpaper/
we-render "https://steamcommunity.com/sharedfiles/filedetails/?id=3775394622"
we-render ./my-wallpaper/ --wizard
we-render ./my-wallpaper/ --format png --at 5
```

Default scene export: **4K fit · 60 FPS · 30 s · H.264**.

Outputs: **MP4 · GIF · PNG · JPG**. A pre-rendered `.mpkg` can be extracted without re-encoding.

Scene export additionally needs FFmpeg, a C compiler, X11/XWayland, Wallpaper Engine assets from Steam, and a compatible native `linux-wallpaperengine` installation.

No Windows, Wine, Proton, desktop recording or proprietary Wallpaper Engine assets are bundled.

MIT licensed. See [CHANGELOG.md](CHANGELOG.md).
