# Changelog

## 0.1.0b1

First WE Render beta, building on the preceding WE Export experiments.

- English interactive CLI, real progress, media settings and JSON results.
- Byte-preserving extraction of pre-rendered MPKG video.
- Native GLFW child-renderer → raw-frame pipe → MP4/GIF/PNG/JPG adapter.
- Fixed GLFW simulation steps, warm-up, snapshots, exact MP4 frame/FPS checks.
- Original-aspect fitting, explicit upscaling, H.264/HEVC and optional NVENC.
- Local Steam resolution and optional DepotDownloader adapter.
- User-prefix install, offline portable app, short README, cover and publication helper.

Native integration with an actual linux-wallpaperengine build remains unverified.
Read `docs/TESTING.md` before describing this as stable or universally compatible.
