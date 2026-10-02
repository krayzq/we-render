# WE Render 0.1.0b1

**Beta — native scene integration has not yet been validated with a real
linux-wallpaperengine build.** This is not a universal scene converter.

Download the **linux.zip**, unpack, run `./install.sh`, then `we-render`.
The source archive is for contributors. The `.pyz` is the standalone Python app;
Python and system/native dependencies are not inside it.

Original pre-rendered MPKG video extraction and standard media conversion are
implemented and tested. Native rendering uses a separate engine's hidden OpenGL
buffer and a fixed GLFW clock. The synthetic GLX-to-FFmpeg pipeline is tested,
including six 4K60 frames; real scene effects, Hyprland and NVENC are not yet verified.

Needs: Linux, Python 3.10+, FFmpeg for conversion. Scene path additionally needs
Almamu/linux-wallpaperengine, owned Wallpaper Engine assets, `cc`, X11/XWayland.
No Windows/Wine/Proton, desktop recording, telemetry or bundled proprietary assets.
See `docs/TESTING.md` for the exact verification boundary.
