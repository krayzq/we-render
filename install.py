#!/usr/bin/env python3
"""Install/uninstall only owned WE Render files; no root needed for the app."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
TAG='we-render-install-v1'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,data,mode):
    fd,name=tempfile.mkstemp(prefix='.we-render-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(data)
        os.chmod(name,mode);os.replace(name,path)
    finally:
        try:os.unlink(name)
        except FileNotFoundError:pass

def main(argv=None):
    ap=argparse.ArgumentParser(description='Install WE Render under your user prefix.')
    ap.add_argument('--prefix',type=Path,default=Path.home()/'.local')
    ap.add_argument('--uninstall',action='store_true')
    args=ap.parse_args(argv)
    prefix=args.prefix.expanduser().resolve();folder=prefix/'share/we-render';launcher=prefix/'bin/we-render'
    manifest=folder/'install.json';app=folder/'we-render.pyz'
    try:
        old={}
        if manifest.exists():
            old=json.loads(manifest.read_text())
            if old.get('type')!=TAG:raise RuntimeError('Unrecognized installation manifest; no files changed.')
        for p in (manifest,app,launcher):
            if p.is_symlink():raise RuntimeError(f'Refusing to replace a symlink: {p}')
        for p in (app,launcher):
            if p.exists() and old.get('hashes',{}).get(str(p))!=digest(p):
                raise RuntimeError(f'Unowned or modified file: {p}. Move it aside before installing/uninstalling.')
        if args.uninstall:
            if not old:raise RuntimeError('No managed installation was found.')
            for p in (app,launcher,manifest):p.unlink(missing_ok=True)
            try:folder.rmdir()
            except OSError:pass
            print('Uninstalled. Your exports, Steam files and cache were kept.');return 0
        if sys.version_info<(3,10):raise RuntimeError('Python 3.10 or newer is required.')
        folder.mkdir(parents=True,exist_ok=True);launcher.parent.mkdir(parents=True,exist_ok=True)
        source=ROOT/'we-render.pyz'
        if not source.is_file():
            spec=importlib.util.spec_from_file_location('we_render_build',ROOT/'tools/build.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory(prefix='we-render-install-') as td:
                source=module.build_app(Path(td)/'we-render.pyz')
                app_bytes=source.read_bytes()
        else:app_bytes=source.read_bytes()
        script=('#!/bin/sh\n# '+TAG+'\nexec python3 '+shlex.quote(str(app))+' "$@"\n').encode()
        atomic(app,app_bytes,0o755);atomic(launcher,script,0o755)
        data={'type':TAG,'hashes':{str(p):digest(p) for p in (app,launcher)}}
        atomic(manifest,(json.dumps(data,indent=2)+'\n').encode(),0o644)
        print(f'Installed: {launcher}\nRun: {launcher} --doctor\nThen: {launcher}')
        if str(launcher.parent) not in os.environ.get('PATH','').split(os.pathsep):
            print(f'Add {launcher.parent} to PATH. For fish: fish_add_path {shlex.quote(str(launcher.parent))}')
        print('The CLI is installed; scene export also needs the native renderer and your Wallpaper Engine assets.')
        return 0
    except (OSError,ValueError,RuntimeError,KeyboardInterrupt,EOFError) as exc:
        print('Install stopped: '+str(exc),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
