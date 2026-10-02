"""One task: wallpaper source → a video or a fully composed rendered frame."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import unquote,urlparse
from . import __version__
from .errors import ExportError
from .options import Options
from .source import steam_libraries as steam_roots,locate_item,locate_assets,inspect_path,workshop_id
from .archive import open_package
from .storage import Span,safe_name
from .ui import UI


def parser():
    p=argparse.ArgumentParser(prog='we-render',description='Export Wallpaper Engine media or render supported scenes on Linux. Scene backend is beta.',epilog='MPKG/video defaults to original bytes. Scenes default to 4K fit, 60 FPS, 30 s, MP4. No Windows, Wine or desktop recording.')
    p.add_argument('source',nargs='?',help='Workshop URL/ID, scene project, scene.pkg, .mpkg or video')
    p.add_argument('-o','--output',type=Path,default=Path('./exports'),help='Output directory (default: ./exports)')
    p.add_argument('-f','--format',choices=['original','mp4','gif','png','jpg'])
    p.add_argument('--resolution',help='original, 720p, 1080p, 1440p, 4k or WIDTHxHEIGHT; keep aspect')
    p.add_argument('--fps',type=int)
    p.add_argument('--duration',type=float,help='Video duration in seconds; shorter inputs are repeated')
    p.add_argument('--at',type=float,help='Timestamp for PNG/JPG')
    p.add_argument('--warmup',type=float,default=2,help='Scene simulation warm-up (default: 2 s)')
    p.add_argument('--codec',choices=['h264','hevc'],default='h264')
    p.add_argument('--encoder',choices=['cpu','nvenc'],default='cpu')
    p.add_argument('--crf',type=int,default=18)
    p.add_argument('--bitrate',help='Target video bitrate, e.g. 12M (instead of CRF)')
    p.add_argument('--upscale',action='store_true',help='Explicitly allow enlargement; does not restore detail')
    p.add_argument('--flip',action='store_true',help='Reverse the default vertical orientation')
    p.add_argument('--assets',type=Path,help='Original Wallpaper Engine assets directory')
    p.add_argument('--renderer',default='linux-wallpaperengine',help='Native Almamu-compatible renderer executable')
    p.add_argument('--steam-library',type=Path,action='append',default=[])
    p.add_argument('--scene-size',help='Override unknown authored canvas: WIDTHxHEIGHT')
    p.add_argument('--download',action='store_true',help='Allow download using separately installed DepotDownloader')
    p.add_argument('--steam-user',help='Steam login; DepotDownloader asks for password/Steam Guard itself')
    p.add_argument('--downloader',help='DepotDownloader executable')
    p.add_argument('--offline',action='store_true',help='Never invoke a downloader')
    p.add_argument('--entry',help='Exact video entry in an MPKG when ambiguous')
    p.add_argument('--wizard',action='store_true',help='Choose export settings interactively')
    p.add_argument('--inspect',action='store_true',help='Inspect input, without rendering')
    p.add_argument('--doctor',action='store_true',help='Check installed dependencies (not a scene compatibility test)')
    p.add_argument('--startup-timeout',type=int,default=120)
    p.add_argument('--timeout',type=int,default=7200)
    p.add_argument('--json',action='store_true',help='Machine-readable results on stdout')
    p.add_argument('--quiet',action='store_true')
    p.add_argument('--no-color',action='store_true')
    p.add_argument('--version',action='version',version=__version__)
    return p


def doctor(args,ui):
    roots=steam_roots(args.steam_library);assets=locate_assets(roots,args.assets)
    info={'version':__version__,'platform':sys.platform,'ffmpeg':shutil.which('ffmpeg'),
          'ffprobe':shutil.which('ffprobe'),'compiler':shutil.which('cc'),
          'renderer':shutil.which(args.renderer),'assets':str(assets) if assets else None,
          'display':os.environ.get('DISPLAY'),
          'depotdownloader':shutil.which(args.downloader or 'DepotDownloader') or shutil.which('depotdownloader'),
          'scene_compatibility':'Not established by dependency checks; inspect your rendered scene.'}
    info['scene_dependencies_present']=all(info[x] for x in ('ffmpeg','ffprobe','compiler','renderer','assets','display'))
    for key,value in info.items():ui.line(key,str(value) if value is not None else 'Not found')
    if args.json:print(json.dumps(info,ensure_ascii=False))
    else:
        ui.note('Scene dependencies present.' if info['scene_dependencies_present'] else 'Scene runtime is incomplete. See docs/USAGE.md. MPKG original extraction only needs Python.')
    return 0 if info['scene_dependencies_present'] else 3


def resolve(value,args,ui):
    value=value.strip()
    if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":value=value[1:-1]
    if value.startswith('file://'):
        parsed=urlparse(value)
        if parsed.netloc not in ('','localhost'):raise ExportError('Only local file:// paths are allowed.')
        value=unquote(parsed.path)
    roots=steam_roots(args.steam_library)
    item=workshop_id(value)
    if item:
        path=locate_item(item,roots)
        cache=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'we-render/workshop'/item
        if not path and (cache/'project.json').is_file():path=cache
        if not path:
            if not args.download or args.offline or args.inspect:
                raise ExportError('This Workshop item is not downloaded. Subscribe in Steam and wait for the files, or use --download --steam-user YOUR_LOGIN with DepotDownloader. A Workshop URL is not a ready-made MPKG.')
            from .download import download_item
            path=download_item(item,args.steam_user,args.downloader,ui.line)
    else:path=Path(value)
    override=None
    if args.scene_size:
        m=re.fullmatch(r'([0-9]{1,5})x([0-9]{1,5})',args.scene_size)
        if not m:raise ExportError('--scene-size must be WIDTHxHEIGHT.')
        override=tuple(map(int,m.groups()))
        if min(override)<2 or max(override)>32768:raise ExportError('Invalid authored scene dimensions.')
    return inspect_path(path,item,override),roots


def pick_video(package,entry,ui):
    videos=[r for r in package.resources if r.kind=='video' and not r.preview]
    if entry:
        selected=[r for r in videos if r.name==entry]
        if len(selected)!=1:raise ExportError('--entry must name exactly one non-preview video in the package.')
        return selected[0]
    preferred=[r for r in videos if r.role in {'main video','pre-rendered video candidate'}]
    if len(preferred)==1:return preferred[0]
    if not videos:raise ExportError('This MPKG contains no rendered video. It is a dynamic package, not a Pre-rendered export. Use its original scene project instead.')
    if len(videos)==1:
        ui.note('One embedded video found. Check that it is the full scene, not a video layer.')
        return videos[0]
    raise ExportError('Several videos found. Use --inspect, then --entry with the exact main-video filename.')


def make_options(args,source):
    modified=any(x is not None for x in (args.resolution,args.fps,args.duration,args.at,args.bitrate)) or args.upscale or args.flip or args.codec!='h264' or args.encoder!='cpu' or args.crf!=18
    fmt=args.format or ('mp4' if source.kind=='scene' or modified else 'original')
    if fmt=='original' and source.kind=='scene':raise ExportError('A scene must be rendered. Choose mp4, gif, png or jpg.')
    if fmt=='original' and modified:raise ExportError('Original copies bytes; it cannot change FPS, size or quality. Choose --format mp4 to convert.')
    opts=Options(format=fmt,resolution=args.resolution or ('720p' if fmt=='gif' else '4k'),
                 fps=args.fps or (25 if fmt=='gif' else 60),duration=args.duration if args.duration is not None else (5 if fmt=='gif' else 30),
                 at=args.at or 0,warmup=args.warmup,codec=args.codec,encoder=args.encoder,crf=args.crf,bitrate=args.bitrate,
                 upscale=args.upscale,flip=args.flip,startup_timeout=args.startup_timeout,timeout=args.timeout)
    # Do not turn invalid zero values into defaults.
    if args.fps is not None:opts.fps=args.fps
    return opts.validate()


def wizard(ui,opts,source):
    formats=[('MP4 video','mp4'),('GIF animation (smaller output recommended)','gif'),('PNG rendered frame','png'),('JPG rendered frame','jpg')]
    if source.kind!='scene':formats.insert(0,('Original video · no re-encoding','original'))
    opts.format=ui.menu('Output format',formats)
    if opts.format=='original':return opts
    res=[('4K UHD · fit within 3840 × 2160','4k'),('Original canvas','original'),('1440p','1440p'),('1080p','1080p'),('720p','720p'),('Custom bounding box','custom')]
    opts.resolution=ui.menu('Resolution · original proportions',res,4 if opts.format=='gif' else 0)
    if opts.resolution=='custom':opts.resolution=ui.ask('WIDTHxHEIGHT')
    if opts.format in {'png','jpg'}:opts.at=float(ui.ask('Scene time in seconds','0'))
    else:
        opts.fps=int(ui.ask('FPS','25' if opts.format=='gif' else '60'))
        opts.duration=float(ui.ask('Duration in seconds','5' if opts.format=='gif' else '30'))
    if opts.format=='mp4':
        opts.codec=ui.menu('Codec',[('H.264 · widest compatibility','h264'),('HEVC / H.265','hevc')])
        opts.encoder=ui.menu('Encoder',[('CPU · no specific GPU required','cpu'),('NVIDIA NVENC · needs driver support','nvenc')])
        mode=ui.menu('Quality',[('High quality · CRF 18','18'),('Balanced · CRF 23','23'),('Target bitrate','bitrate')])
        if mode=='bitrate':opts.bitrate=ui.ask('Target bitrate','12M')
        else:opts.crf=int(mode);opts.bitrate=None
    return opts.validate()


def main(argv=None):
    args=parser().parse_args(argv);ui=UI(args.quiet or args.json,args.no_color)
    try:
        if sys.platform!='linux':raise ExportError('WE Render is a Linux application.')
        ui.header()
        if args.doctor:return doctor(args,ui)
        interactive=args.source is None
        source,roots=resolve(args.source or ui.ask('Wallpaper file, folder or Steam Workshop URL'),args,ui)
        package=open_package(source.path) if source.kind=='mpkg' else None
        if args.inspect:
            report={**asdict(source),'path':str(source.path),'root':str(source.root) if source.root else None}
            if package:report['videos']=[{'name':r.name,'size':r.span.size,'role':r.role} for r in package.resources if r.kind=='video']
            if args.json:print(json.dumps(report,ensure_ascii=False))
            else:
                for k,v in report.items():ui.line(k,str(v))
            return 0
        opts=make_options(args,source)
        if args.wizard:opts=wizard(ui,opts,source)
        if interactive and not args.wizard:
            action=ui.menu('Ready to export',[('Use recommended settings','export'),('Choose settings','settings'),('Cancel','cancel')])
            if action=='cancel':return 130
            if action=='settings':opts=wizard(ui,opts,source)
        ui.plan(source,opts,args.output)
        if source.kind=='scene':ui.note('Native scene backend: BETA. It exports what the Linux engine renders; effects compatibility is not guaranteed.')
        if opts.format=='gif':ui.note('GIF timing is quantized to hundredths of a second; it cannot preserve every requested FPS exactly.')
        if opts.format!='original':ui.note('Converted/rendered outputs are silent SDR. Original video extraction keeps its original audio and metadata.')
        from .media import copy_media,convert
        with ui.progress() as progress:
            if source.kind=='scene':
                from .renderer import render
                result=render(source,args.output,locate_assets(roots,args.assets),opts,args.renderer,progress)
            elif package:
                resource=pick_video(package,args.entry,ui)
                title=safe_name(package.metadata.get('title') or source.title)
                ext=resource.suffix.lstrip('.')
                if opts.format=='original':result=copy_media(resource.span,args.output,title,ext,progress)
                else:
                    with tempfile.TemporaryDirectory(prefix='we-render-media-') as td:
                        media=Path(td)/('source.'+ext);resource.span.copy(media,progress)
                        result=convert(media,args.output,title,opts,progress)
            elif opts.format=='original':result=copy_media(Span.whole(source.path),args.output,source.title,source.path.suffix.lstrip('.'),progress)
            else:result=convert(source.path,args.output,source.title,opts,progress)
        ui.done(result)
        print(json.dumps({'ok':True,**result},ensure_ascii=False) if args.json else result['path'])
        return 0
    except KeyboardInterrupt:
        if args.json:print(json.dumps({'ok':False,'error':'Cancelled'}))
        else:ui.note('Cancelled. Incomplete exports were removed; your source is unchanged.')
        return 130
    except (ExportError,OSError,ValueError,EOFError) as exc:
        if args.json:print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False))
        else:ui.error(str(exc))
        return 1
