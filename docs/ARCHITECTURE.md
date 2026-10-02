# Architecture

```text
Workshop URL/ID ──► local Steam library / optional authenticated downloader
local path ──────► project inspection
                         │
              ┌──────────┴──────────┐
       MPKG / video               Scene project
              │                     │
       selected video          separate Linux engine
              │                     │
      original / FFmpeg        child-only GLFW adapter
              │                fixed GLFW time steps
              │                hidden OpenGL back buffer
              │                     │
              │                 RGB pipe → FFmpeg
              └──────────┬──────────┘
                    validation
                         │
                unique named output
```

## Native adapter

`we_render/native/frame_bridge.c` is compiled on first use using the local `cc`.
It is loaded with `LD_PRELOAD` only into the owned renderer child. It hides that
child's first GLFW window, controls its GLFW clock, reads the GL back buffer before
swap and writes bounded RGB frames through an inherited pipe. The descriptor is
marked close-on-exec within the renderer so subprocesses do not keep it alive.
The child's real OpenGL implementation is used; the adapter is not a renderer.
FFmpeg receives raw frames directly. No image sequence or raw movie is written to disk.

The bridge depends on **interposable GLFW symbols**, X11/XWayland and a functioning
hidden default framebuffer. Static GLFW linkage, a different renderer backend,
internal clocks or code paths that do not swap that buffer may be incompatible.
Clock control is not a guarantee of deterministic RNG, video playback, audio or
all asynchronous scripts. Startup/total timeouts and explicit protocol/frame-count
checks fail rather than publishing truncated files. Pixel/scene fidelity still
requires visual comparison; a successful file-level check does not prove it.

This is deliberately a beta adapter, not a fully integrated/pinned engine fork.
No successful real-engine or hardware compatibility matrix is claimed yet. A
future robust native build should use an explicit offscreen FBO/time/export API
in a pinned renderer version instead of relying on symbol interposition.
The exploratory `next-v2` embedding API is not implemented or bundled here.

## Files and shutdown

Inputs are read-only. Writes occur in output/cache/temp locations. A completed file
is published under a unique name, with a hard-link atomic commit where supported;
on filesystems without links, exclusive creation avoids overwriting existing files.
Ctrl+C and failure terminate child process groups and remove unfinished output.
Logs are kept. MPKG original extraction is streaming and does not require FFmpeg.
Explicit MPKG conversion temporarily stores its compressed video, not raw frames.
