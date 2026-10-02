# Changelog

## 0.1.0b2

- Fixed native bridge startup when CEF/helper subprocesses inherit `LD_PRELOAD` without the frame pipe.
- Added regression coverage for helper-process bridge activation.
- Improved renderer/bridge startup error messages.
- Removed the obsolete first-publish helper and its CI-only test.
- Made the installer non-interactive; it no longer invokes package managers or AUR helpers.
- Simplified the README and Linux release bundle.

Native scene fidelity still depends on the external Linux renderer and remains beta.

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
