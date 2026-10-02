# Third-party components

Our CLI and per-process adapter are MIT-licensed. This is an independent project,
not an official Wallpaper Engine/Valve product. No proprietary textures, shaders,
wallpapers, runtime binaries or font files are redistributed.

The portable app vendors Rich 15.0.0, markdown-it-py 4.2.0, mdurl 0.1.2 and
Pygments 2.20.0 from the preceding WE Export distribution, plus typing-extensions
4.16.0 from the installed Python environment (for Python 3.10 compatibility). Their original notices
are preserved in `licenses/`; exact versions are in `vendor/BUNDLED.json`.
These libraries provide terminal formatting, not wallpaper rendering.

The separately installed [Almamu/linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine)
uses GPL-3.0 terms. [FFmpeg](https://ffmpeg.org/legal.html) and the optional
[DepotDownloader](https://github.com/SteamRE/DepotDownloader) carry their own
licenses. They are external executables, not bundled or relicensed by this archive.
If distributing a combined native-engine binary in a later release, audit and
satisfy its corresponding source, licensing and third-party obligations first.

The README cover is a generated product wordmark, not a screenshot or evidence
of a successful wallpaper export.
