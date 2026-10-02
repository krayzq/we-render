"""FFmpeg operations and verifiable output; all subprocesses avoid shell=True."""
from __future__ import annotations
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time
from fractions import Fraction
from .errors import ExportError
from .storage import Span, publish, temporary_output, checksum


def executable(name):
    import shutil
    result=shutil.which(str(name))
    if not result:raise ExportError(f'{name} is not installed. Run we-render --doctor.')
    return result


def stop(proc):
    if proc is None:return
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        proc.wait(timeout=3)


def probe(path, count=False):
    args=[executable('ffprobe'),'-v','error']
    if count:args+=['-count_frames']
    args+=['-show_streams','-show_format','-of','json',str(path)]
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=120)
        if result.returncode:raise ValueError(result.stderr[-2000:])
        data=json.loads(result.stdout)
        v=next(s for s in data['streams'] if s.get('codec_type')=='video')
        rate=v.get('avg_frame_rate','0/1')
        try:fps=float(Fraction(rate))
        except (ValueError,ZeroDivisionError):fps=0.0
        n=v.get('nb_frames',v.get('nb_read_frames'))
        return dict(width=int(v['width']),height=int(v['height']),fps=fps,rate=rate,
                    frames=int(n) if str(n).isdigit() else None,
                    duration=float(data.get('format',{}).get('duration',0)),
                    codec=v.get('codec_name'),audio=any(s.get('codec_type')=='audio' for s in data['streams']))
    except (ValueError,KeyError,StopIteration,subprocess.TimeoutExpired) as exc:
        raise ExportError('Cannot validate media: '+str(exc)) from exc


def track(proc,total,callback,timeout):
    assert proc.stdout is not None
    end=time.monotonic()+timeout; pending=b''
    while True:
        if time.monotonic()>end:raise ExportError('Processing timed out. Partial output was removed.')
        if select.select([proc.stdout],[],[],0.2)[0]:
            chunk=os.read(proc.stdout.fileno(),65536)
            if chunk:
                pending+=chunk
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    if line.startswith(b'frame='):
                        try:callback(int(line[6:].strip()),total,'Rendering / encoding')
                        except ValueError:pass
            elif proc.poll() is not None:break
        elif proc.poll() is not None:break
    if proc.wait()!=0:raise ExportError('FFmpeg failed. Check the diagnostic log. No output was published.')


def ffmpeg_command(input_args,output,opts,filters):
    return [executable('ffmpeg'),'-hide_banner','-v','warning','-nostdin','-y',
            *input_args,'-an','-vf',filters,*opts.codec_args(),'-progress','pipe:1',str(output)]


def validate_render(path,w,h,opts):
    meta=probe(path, count=opts.format=='gif')
    if (meta['width'],meta['height'])!=(w,h):raise ExportError('Output dimensions do not match the request.')
    if opts.format=='mp4':
        if meta['frames']!=opts.frames:raise ExportError(f'Expected {opts.frames} frames, received {meta["frames"]}.')
        if abs(meta['fps']-opts.fps)>0.001:raise ExportError('Output FPS does not match the request.')
    return meta


def copy_media(span:Span,output:Path,title:str,extension:str,callback):
    with temporary_output(output,extension) as temp:
        span.copy(temp,callback)
        # Copy does not require a codec decoder. Hash the exact extracted file for provenance.
        sha=checksum(temp)
        target=publish(temp,output,title+'.'+extension)
        return dict(path=str(target),size=target.stat().st_size,sha256=sha,method='Original bytes · no re-encoding')


def convert(path:Path,output:Path,title:str,opts,callback):
    source=probe(path);w,h=opts.size(source['width'],source['height'])
    output.mkdir(parents=True,exist_ok=True)
    with temporary_output(output,opts.format) as temp:
        log=output/f'we-render-{time.time_ns()}.log'
        args=[]
        if opts.format not in {'png','jpg'}:args+=['-stream_loop','-1']
        args+=['-i',str(path)]
        if opts.format in {'png','jpg'}:args+=['-ss',str(opts.at)]
        else:args+=['-t',str(opts.frames/opts.fps),'-r',str(opts.fps)]
        cmd=ffmpeg_command(args,temp,opts,opts.filter(w,h))
        proc=None
        with log.open('w') as out:
            try:
                proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=out,start_new_session=True)
                track(proc,opts.frames,callback,opts.timeout)
            except ExportError as exc:raise ExportError(f'{exc}\nLog: {log}') from exc
            finally:stop(proc)
        meta=validate_render(temp,w,h,opts)
        target=publish(temp,output,title+'.'+opts.format)
        return dict(path=str(target),size=target.stat().st_size,media=meta,log=str(log),method='FFmpeg conversion · audio removed')
