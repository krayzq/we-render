# WE Render 0.1.0b2

Beta release.

Highlights:
- fixes the native bridge helper-process startup bug seen with CEF;
- cleaner startup errors;
- non-interactive installer;
- smaller, cleaner end-user release bundle;
- pre-rendered MPKG extraction remains byte-preserving.

Install the Linux ZIP with `./install.sh`, then run `we-render --doctor`.

Native scene rendering still depends on a compatible `linux-wallpaperengine`, Wallpaper Engine assets, FFmpeg and X11/XWayland. Scene fidelity is not guaranteed for every wallpaper.

No Windows, Wine, Proton, desktop recording, telemetry or proprietary assets are bundled.
