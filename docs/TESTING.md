# Validation — 0.1.0b2

## What was actually run

Linux x86-64, Python 3.13.5, FFmpeg/ffprobe, local C compiler, Mesa GLX and Xvfb.
No upstream engine binary, genuine complete asset set, or authenticated Steam/GitHub
account was available for execution. Direct network access from the build container
failed, including source/dependency fetch attempts.

```sh
xvfb-run -a python -m pytest -q
```

**74 tests passed, none skipped** in the recorded run. One Python 3.13 `forkpty`
deprecation warning was emitted by the terminal-test harness, not by the app.

The test suite covers input/URL validation, Steam-library discovery, source bounds,
MPKG selection, refusal to substitute a preview for a scene, collisions/symlinks,
source changes, original-byte extraction, real FFmpeg conversion, resolution/FPS,
malformed input and cancellation. Distribution tests also exercised isolated `python -I -S` startup, reproducible
zipapp builds, installation/removal, protecting modified files, workflow YAML parsing and the real interactive terminal menu.

**Native tests use a small GLFW-shaped ABI fixture over real X11/GLX/OpenGL.**
It draws a synthetic red/blue animation. It is not GLFW itself and does not parse
Wallpaper Engine scenes. MP4, GIF, PNG and JPG traverse the actual C adapter and
FFmpeg. Tests verify no mapped window, frame counts, pixel orientation, warm-up,
rejection of wrong framebuffer size, child cancellation and **6 frames at 3840×2160
and 60 FPS**. This is a short smoke test, not a sustained 4K performance benchmark.

A provided real Knight package was inspected for its scene metadata (3840×2160).
That scene was **not rendered** here. It is not distributed as a fixture.
The generated wordmark contains no renderer screenshot or claimed export result.

## Not verified

- **An actual linux-wallpaperengine build with this adapter; all real-scene fidelity.**
- Real Hyprland, AMD/Intel/NVIDIA hardware, NVENC, ARM, HDR, async scene video or scripts.
- Authenticated Workshop download or publication to a real GitHub account.
- The prepared GitHub Actions matrix (until it runs in the owner's repository).

Passing frame/codec checks does not prove that leaves, rain, shaders or every layer
are correct. A dependency `--doctor` result likewise is not a compatibility test.
Do not remove the beta label on the basis of synthetic tests alone.

## First real acceptance test

Run a short export of a trusted scene whose original appearance is known:

```sh
we-render ./my-wallpaper/ --duration 2 --fps 60 --resolution 4k
```

Compare its colors, composition, effects and motion with the original renderer.
Random particle positions need not match frame-for-frame. Check a full 30-second
export, multiple wallpapers, cancel/restart and user installation on target hardware.
Record renderer commit, driver, OS and missing effects before claiming support.

Release checksums are provided for file integrity; they are not cryptographic signatures.

## Additional installation check

The source installer, launcher and uninstaller were also run successfully as the
unprivileged `nobody` account in a temporary prefix. The application source was
read-only to that account. This did not install system dependencies or test Hyprland.

## 0.1.0b2 regression

Adds a regression test for renderer helper processes that inherit the bridge environment. Helper processes must stay passive when the export pipe is unavailable, while the intended renderer process still rejects incomplete bridge configuration.
