#!/usr/bin/env python3
"""First publication to the authenticated user's GitHub account.

Creates a NEW public repository after an explicit confirmation. Never force
pushes, edits an existing remote repository, or asks for a password/token itself.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from we_render import __version__


def run(args,**kwargs):
    return subprocess.run(args,cwd=ROOT,text=True,check=True,**kwargs)

def main(argv=None):
    ap=argparse.ArgumentParser(description='Publish this project to a new public GitHub repository.')
    ap.add_argument('--name',default='we-render',help='New repository name, without owner')
    ap.add_argument('--dry-run',action='store_true',help='Print the plan; do not contact GitHub or modify Git')
    args=ap.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}',args.name):ap.error('Invalid repository name')
    if args.dry_run:
        print(f'Plan: build → gh login → identify owner → new PUBLIC {args.name} → first commit → push main → tag v{__version__}.\nGitHub Actions will test/build and create a DRAFT prerelease; publish it after checking your real scene.');return 0
    try:
        if not shutil.which('git') or not shutil.which('gh'):
            raise RuntimeError('Install Git and GitHub CLI first. Arch: sudo pacman -S --needed git github-cli')
        if (ROOT/'.git').exists():
            raise RuntimeError('This directory already has Git history. Use the manual/resume instructions in docs/PUBLISHING.ru.md; no existing history was changed.')
        status=subprocess.run(['gh','auth','status','--hostname','github.com'],cwd=ROOT,capture_output=True)
        if status.returncode:run(['gh','auth','login','--hostname','github.com','--git-protocol','https','--web','--scopes','workflow'])
        run(['gh','auth','setup-git'])
        user=json.loads(run(['gh','api','user'],capture_output=True).stdout)
        login=user['login'];uid=int(user['id']);repo=f'{login}/{args.name}'
        existing=subprocess.run(['gh','repo','view',repo,'--json','name'],cwd=ROOT,capture_output=True)
        if existing.returncode==0:raise RuntimeError(f'{repo} already exists. Choose another --name. No remote repository was changed.')
        run([sys.executable,'tools/build.py'])
        print(f'\nThis will publish the source, README, cover and tests PUBLICLY as {repo}.')
        print('The scene backend is beta and has not been validated against a real upstream scene here.')
        print('Do not include your wallpapers, passwords, tokens or proprietary assets in the project.')
        if input('Type PUBLISH to continue: ')!='PUBLISH':print('Cancelled.');return 130
        run(['git','init','-b','main'])
        run(['git','config','user.name',login])
        run(['git','config','user.email',f'{uid}+{login}@users.noreply.github.com'])
        names=['we_render','vendor','licenses','tests','tools','docs','.github','README.md','LICENSE','THIRD_PARTY.md','CHANGELOG.md',
               'SECURITY.md','CONTRIBUTING.md','pyproject.toml','.gitignore','run.py','install.py','install.sh','MANIFEST.in']
        run(['git','add','--',*names]);run(['git','diff','--cached','--stat'])
        if input('Review the list above. Upload these files? [y/N] ').lower()!='y':
            print('Stopped before commit/upload. Local Git index remains for review.');return 130
        run(['git','commit','-m',f'Initial WE Render {__version__} beta'])
        run(['gh','repo','create',repo,'--public','--source','.','--remote','origin','--push',
             '--description','Linux wallpaper video exporter · original extraction and beta native scene rendering'])
        run(['gh','repo','edit',repo,'--add-topic','wallpaper-engine','--add-topic','linux','--add-topic','cli','--add-topic','ffmpeg'])
        run(['git','tag','-a','v'+__version__,'-m','WE Render '+__version__])
        run(['git','push','origin','v'+__version__])
        print('\nSource uploaded. Open Actions and wait for the release build. Check and publish its draft prerelease in Releases.\nThis script does not claim the remote workflow has already passed.')
        run(['gh','repo','view',repo,'--web']);return 0
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.CalledProcessError,EOFError,KeyboardInterrupt) as exc:
        print('Publication stopped: '+str(exc),file=sys.stderr)
        print('Any steps that already succeeded are kept. There is no destructive rollback or force-push. See docs/PUBLISHING.ru.md.',file=sys.stderr)
        return 1
if __name__=='__main__':raise SystemExit(main())
