# Security

Render only wallpapers you trust. A native renderer can execute shaders and scene
scripts; this tool is not an isolation sandbox. It does not run Windows executables
or Web wallpapers. The frame adapter is loaded only into the newly started native
renderer, never injected into an unrelated/running desktop process.

MPKG tables and payloads are bounded, extraction uses selected file spans, and
existing export files/symlinks are not overwritten. Do not run the application as
root. The installer needs no root privileges unless you explicitly approve system
package installation with `--deps`.

Do not post passwords, tokens, copyrighted asset archives or unredacted local paths
in Issues. Report malformed-input problems with a small synthetic reproducer.
The publication helper authenticates through the official `gh` CLI; it never asks
for a token itself. No telemetry, automatic update downloads or website uploads.
