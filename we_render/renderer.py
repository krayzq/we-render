"""Native engine frame-buffer export. This backend is beta, not universal.

The child engine owns its scene, OpenGL context and render buffers. Our small
per-process GLFW adapter supplies a fixed simulation clock and reads its hidden
back buffer. It never reads desktop pixels and never uses Wine/Proton.
"""
from __future__ import annotations
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
from .errors import ExportError
from .media import executable, stop, track, ffmpeg_command, validate_render
from .storage import publish


def build_bridge():
    source=files('we_render').joinpath('native/frame_bridge.c').read_bytes()
    key=hashlib.sha256(source+os.uname().machine.encode()).hexdigest()[:24]
    base=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'we-render/native'
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Do not accept native code from a writable-by-others cache.
    if base.is_symlink() or base.stat().st_uid!=os.getuid() or base.stat().st_mode & 0o022:
        raise ExportError('Native cache must be owned by you and not writable by other users.')
    target=base/f'frames-{key}.so'
    if target.exists():
        if target.is_symlink() or not target.is_file() or target.stat().st_uid!=os.getuid() or target.stat().st_mode&0o022:
            raise ExportError('Unsafe native adapter cache file.')
        return target
    with tempfile.TemporaryDirectory(prefix='compile-',dir=base) as td:
        src=Path(td)/'adapter.c';binary=Path(td)/'adapter.so';src.write_bytes(source)
        cmd=[executable('cc'),'-std=c11','-O2','-fPIC','-shared','-Wall','-Wextra','-Werror',
             str(src),'-o',str(binary),'-ldl','-pthread']
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise ExportError('Native adapter compilation timed out after 120 seconds.') from exc
        if p.returncode:raise ExportError('Cannot compile native frame adapter:\n'+p.stderr[-4000:])
        binary.chmod(0o700);os.replace(binary,target)
    return target


def header(fd,proc,timeout):
    end=time.monotonic()+timeout; data=bytearray()
    while time.monotonic()<end:
        if len(data)>128:raise ExportError('Invalid renderer protocol header.')
        if select.select([fd],[],[],0.2)[0]:
            c=os.read(fd,1)
            if not c:
                code=proc.poll()
                if code==71:
                    raise ExportError('Native frame bridge stopped during startup (exit 71). Inspect the log for bridge compatibility or configuration details.')
                if code is not None:
                    raise ExportError(f'Renderer exited before frame handoff (exit {code}). Inspect the log for renderer/bridge startup details.')
                raise ExportError('Renderer closed the frame pipe before producing frames. Inspect the log for renderer/bridge startup details.')
            if c==b'\n':
                try:
                    sig,w,h,fps=data.decode('ascii').split()
                    if sig!='WERRGB1':raise ValueError()
                    return int(w),int(h),int(fps)
                except (ValueError,UnicodeError) as exc:raise ExportError('Invalid renderer frame protocol.') from exc
            data+=c
        if proc.poll() is not None:
            code=proc.returncode
            if code==71:
                raise ExportError('Native frame bridge stopped during startup (exit 71). Inspect the log for bridge compatibility or configuration details.')
            raise ExportError(f'Renderer stopped before producing a frame (exit {code}); no video was published.')
    raise ExportError('Renderer startup timed out before frame handoff. This build may be incompatible with the GLFW bridge, or the scene may need more warm-up time. Inspect the log; --startup-timeout can be increased.')


def render(source,output,assets,opts,renderer,callback):
    executable('ffprobe');executable('ffmpeg');binary=executable(renderer)
    if not os.environ.get('DISPLAY'):
        raise ExportError('Scene export currently needs an X11/XWayland session (DISPLAY). On Hyprland enable XWayland. No desktop capture is used. EGL-only/headless mode is not implemented.')
    if assets is None:raise ExportError('Wallpaper Engine assets were not found. Install it through Steam, or pass --assets /path/to/wallpaper_engine/assets.')
    bridge=build_bridge()
    if any(c.isspace() or c==':' for c in str(bridge)):
        raise ExportError('XDG_CACHE_HOME must not contain whitespace or colons for the native adapter.')
    w,h=opts.size(source.width,source.height)
    output=output.expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    log=output/f'we-render-{time.time_ns()}.log'
    read_fd,write_fd=os.pipe();engine=encoder=None
    with tempfile.TemporaryDirectory(prefix='.we-render-',dir=output) as td, log.open('w') as lf:
        temp=Path(td)/('result.'+opts.format)
        project=source.root
        if project is None:
            project=Path(td)/'project';project.mkdir()
            (project/'scene.pkg').symlink_to(source.path)
            (project/'project.json').write_text(json.dumps({'title':source.title,'type':'Scene','file':'scene.json'}))
        env=os.environ.copy()
        for key in ('WAYLAND_DISPLAY','WE_RENDER_OWNER'):env.pop(key,None)
        env.update(XDG_SESSION_TYPE='x11',SDL_AUDIODRIVER='dummy',
                   LD_PRELOAD=str(bridge), WE_RENDER_ACTIVE='1',WE_RENDER_FD=str(write_fd),
                   WE_RENDER_WIDTH=str(w),WE_RENDER_HEIGHT=str(h),WE_RENDER_FPS=str(opts.fps),
                   WE_RENDER_WARMUP=str(opts.skipped_frames),WE_RENDER_FRAMES=str(opts.frames))
        cmd=[binary,'--window',f'0x0x{w}x{h}','--fps',str(opts.fps),'--silent','--noautomute',
             '--no-audio-processing','--disable-mouse','--no-fullscreen-pause','--scaling','fit',
             '--assets-dir',str(assets),str(project)]
        lf.write('WE Render beta. Native child framebuffer export, not desktop capture.\n')
        lf.write('Scene visual compatibility is limited by the installed renderer.\n')
        lf.write('Command: '+json.dumps(cmd)+'\n');lf.flush()
        try:
            callback(0,None,'Loading scene / warming up')
            engine=subprocess.Popen(cmd,env=env,pass_fds=(write_fd,),stdin=subprocess.DEVNULL,
                                    stdout=lf,stderr=lf,start_new_session=True,cwd=td)
            os.close(write_fd);write_fd=-1
            actual=header(read_fd,engine,opts.startup_timeout)
            if actual!=(w,h,opts.fps):raise ExportError('Renderer dimensions/FPS do not match the request.')
            input_args=['-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{h}',
                        '-framerate',str(opts.fps),'-i','pipe:0']
            command=ffmpeg_command(input_args,temp,opts,opts.filter(gl=True))
            encoder=subprocess.Popen(command,stdin=read_fd,stdout=subprocess.PIPE,stderr=lf,start_new_session=True)
            os.close(read_fd);read_fd=-1
            track(encoder,opts.frames,callback,opts.timeout)
            try:code=engine.wait(timeout=15)
            except subprocess.TimeoutExpired as exc:raise ExportError('Renderer did not shut down cleanly; incomplete export rejected.') from exc
            if code:raise ExportError(f'Renderer failed with exit code {code}.')
            meta=validate_render(temp,w,h,opts)
            target=publish(temp,output,source.title+'.'+opts.format)
            return dict(path=str(target),size=target.stat().st_size,media=meta,log=str(log),
                        method='Native scene → hidden OpenGL buffer → FFmpeg',
                        compatibility='Beta: inspect visuals against the original wallpaper')
        except ExportError as exc:raise ExportError(f'{exc}\nLog: {log}') from exc
        finally:
            stop(engine);stop(encoder)
            for fd in (read_fd,write_fd):
                if fd>=0:
                    try:os.close(fd)
                    except OSError:pass
