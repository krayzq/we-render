# Contributing

```sh
python -m pip install pytest pexpect
xvfb-run -a python -m pytest -q
python tools/build.py
```

Native fixture tests need X11 development headers, libGL, a C compiler and FFmpeg.
They are **not** actual linux-wallpaperengine compatibility tests. For a real-scene
report include engine commit/version, GPU driver, public Workshop ID, all missing
effects, command and a redacted log. Never commit proprietary Wallpaper Engine assets.
Keep extraction, scene rendering and media conversion as distinct operations.
Do not hide unsupported scene features behind a preview-image fallback.
