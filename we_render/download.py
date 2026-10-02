"""Optional authorized Steam Workshop download via a separate DepotDownloader.

No password arguments, anonymous-access promises, private APIs or .mpkg service.
The downloader receives a terminal for its own Steam authentication prompts.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from .errors import ExportError as UnpackError


def download_item(item_id: str, username: str | None, downloader: str | None, info) -> Path:
    base = Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'we-render/workshop'
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    target = base/item_id
    if (target/'project.json').is_file():
        info('Cached',str(target))
        return target
    binary = shutil.which(downloader) if downloader else (shutil.which('DepotDownloader') or shutil.which('depotdownloader'))
    if not binary:
        raise UnpackError('Wallpaper is not installed locally. Subscribe in Steam and wait for its download, or install DepotDownloader and retry with --steam-user YOUR_LOGIN. This tool does not download pre-rendered MPKGs from a hidden service.')
    if not username:
        raise UnpackError('Downloading requires --steam-user YOUR_LOGIN. DepotDownloader will handle the password / Steam Guard itself. Alternatively download through Steam first.')
    if username.startswith('-') or any(not c.isprintable() for c in username):
        raise UnpackError('Invalid Steam login name.')
    if target.exists():
        raise UnpackError(f'Incomplete cache already exists: {target}. Inspect it before retrying.')
    with tempfile.TemporaryDirectory(prefix=f'.{item_id}-',dir=base) as temp:
        destination=Path(temp)/'content'
        cmd=[binary,'-app','431960','-pubfile',item_id,'-username',username,
             '-dir',str(destination),'-validate']
        info('Downloading','DepotDownloader will prompt directly; WE Render does not receive or store your password.')
        # No shell. Authentication stays in the external program's terminal.
        try:
            from .media import stop
            proc=subprocess.Popen(cmd,cwd=temp,start_new_session=True)
            try:
                returncode=proc.wait(timeout=7200)
            finally:
                stop(proc)
        except subprocess.TimeoutExpired as exc:
            raise UnpackError('Steam download timed out. No completed cache was published.') from exc
        if returncode:
            raise UnpackError(f'DepotDownloader failed (exit {returncode}). Ownership, Steam authentication and Workshop availability still apply.')
        if not (destination/'project.json').is_file():
            raise UnpackError('Downloaded item has no root project.json. Collections/non-wallpaper items are unsupported; no render was attempted.')
        if target.exists():
            raise UnpackError('Another download created this cache entry. Retry to use it.')
        destination.rename(target)
    return target
