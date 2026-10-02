"""Local-only Workshop resolution; no credentials, HTTP or shell execution."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
import struct
from urllib.parse import parse_qs, urlparse
from dataclasses import dataclass
from .errors import ExportError as UnpackError
from .storage import safe_name as safe_filename

APP_ID = '431960'
MAX_JSON = 8 * 1024 * 1024

@dataclass(frozen=True)
class Source:
    path: Path
    kind: str
    title: str
    root: Path | None = None
    width: int | None = None
    height: int | None = None
    workshop_id: str | None = None


def workshop_id(value: str) -> str | None:
    value = value.strip()
    if re.fullmatch(r'[0-9]{1,20}', value):
        return str(int(value)) if 0 < int(value) < 2**64 else None
    try:
        p = urlparse(value)
        port = p.port
    except ValueError as exc:
        raise UnpackError('Invalid Workshop URL.') from exc
    if p.scheme in ('https', 'http') and p.hostname in ('steamcommunity.com', 'www.steamcommunity.com'):
        if p.username or p.password or port or p.path.rstrip('/') not in ('/sharedfiles/filedetails', '/workshop/filedetails'):
            raise UnpackError('Expected a Steam Workshop item URL, not a collection or profile.')
        ids = parse_qs(p.query).get('id', [])
        if len(ids) == 1 and re.fullmatch(r'[0-9]{1,20}', ids[0]) and 0 < int(ids[0]) < 2**64:
            return str(int(ids[0]))
        raise UnpackError('The Workshop URL has no valid numeric id.')
    if p.scheme and p.scheme != 'file':
        raise UnpackError('Only Steam Workshop item URLs and local paths are supported.')
    return None


def _json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_JSON:
        raise UnpackError(f'Missing or oversized JSON file: {path}')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise UnpackError(f'Invalid JSON: {path.name}') from exc
    if not isinstance(data, dict):
        raise UnpackError(f'{path.name} must contain a JSON object.')
    return data


def _decode_vdf_string(s: str) -> str:
    return re.sub(r'\\([\\"])', r'\1', s)


def steam_libraries(extra: list[Path] | None = None) -> list[Path]:
    home = Path.home()
    roots = list(extra or [])
    if os.environ.get('WE_STEAM_ROOT'):
        roots.insert(0, Path(os.environ['WE_STEAM_ROOT']))
    roots += [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root',
              home / '.var/app/com.valvesoftware.Steam/data/Steam',
              home / '.var/app/com.valvesoftware.Steam/.local/share/Steam',
              home / 'snap/steam/common/.local/share/Steam', home / '.steam/steamcmd',
              home / '.local/share/Steam/steamcmd', home / 'Steam', home / '.local/share/we-render/steamcmd']
    found: list[Path] = []
    for root in roots:
        root = root.expanduser().resolve()
        if root.name == 'steamapps':
            root = root.parent
        if root not in found and root.is_dir():
            found.append(root)
    for root in list(found):
        for vf in (root / 'steamapps/libraryfolders.vdf', root / 'config/libraryfolders.vdf'):
            if not vf.is_file() or vf.stat().st_size > 4 * 1024 * 1024:
                continue
            text = vf.read_text(encoding='utf-8', errors='replace')
            for match in re.finditer(r'"(?:path|[0-9]+)"\s*"((?:\\.|[^"\\])*)"', text):
                candidate = Path(_decode_vdf_string(match.group(1))).expanduser()
                if candidate.is_absolute() and candidate.is_dir():
                    candidate = candidate.resolve()
                    if candidate not in found:
                        found.append(candidate)
    return found


def locate_item(item_id: str, roots: list[Path]) -> Path | None:
    for root in roots:
        p = root / 'steamapps/workshop/content' / APP_ID / item_id
        if (p / 'project.json').is_file():
            return p
    return None


def locate_assets(roots: list[Path], explicit: Path | None = None) -> Path | None:
    candidates = ([explicit] if explicit else [])
    if os.environ.get('WE_ASSETS'):
        candidates += [Path(os.environ['WE_ASSETS'])]
    candidates += [root / 'steamapps/common/wallpaper_engine/assets' for root in roots]
    for p in candidates:
        p = p.expanduser().resolve()
        if p.is_dir() and (p / 'shaders').is_dir():
            return p
    return None


def _read_scene_pkg(path: Path, name: str) -> dict:
    """Read a bounded scene JSON in PKGV without extracting textures to disk."""
    size = path.stat().st_size
    with path.open('rb') as f:
        def get(n: int) -> bytes:
            if n < 0 or f.tell() + n > min(size, 16 * 1024 * 1024):
                raise UnpackError('Truncated or oversized PKG table.')
            data = f.read(n)
            if len(data) != n:
                raise UnpackError('Truncated PKG.')
            return data
        def u32():
            return struct.unpack('<I', get(4))[0]
        n = u32()
        if n != 8 or not re.fullmatch(rb'PKGV[0-9]{4}', get(n)):
            raise UnpackError('Unsupported scene PKG signature.')
        count = u32()
        if not 0 < count <= 100000:
            raise UnpackError('Invalid PKG resource count.')
        selected = None
        for _ in range(count):
            length = u32()
            if not 0 < length <= 4096:
                raise UnpackError('Invalid PKG resource name length.')
            resource = get(length).decode('utf-8', 'strict').replace('\\', '/')
            offset, length = u32(), u32()
            if resource.casefold() == name.replace('\\', '/').casefold():
                if selected:
                    raise UnpackError('Ambiguous duplicate scene resource.')
                selected = offset, length
        data_start = f.tell()
        if selected is None:
            raise UnpackError(f'{name} was not found in {path.name}.')
        offset, length = selected
        if length > MAX_JSON or data_start + offset + length > size:
            raise UnpackError('Invalid scene JSON range in PKG.')
        f.seek(data_start + offset)
        try:
            data = json.loads(f.read(length).decode('utf-8-sig'))
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise UnpackError('Invalid scene JSON in PKG.') from exc
        if not isinstance(data, dict):
            raise UnpackError('Scene JSON is not an object.')
        return data


def contained(root: Path, name: str) -> Path:
    p = (root / name.replace('\\', '/')).resolve()
    if not p.is_relative_to(root.resolve()):
        raise UnpackError('Project refers to a file outside its directory.')
    return p


def dimensions(scene: dict) -> tuple[int, int]:
    general = scene.get('general', {})
    ortho = general.get('orthogonalprojection', {}) if isinstance(general, dict) else {}
    if isinstance(ortho, dict):
        for block in (ortho, general):
            w, h = block.get('width'), block.get('height')
            if isinstance(w, (int, float)) and isinstance(h, (int, float)):
                if math.isfinite(w) and math.isfinite(h) and 2 <= w <= 32768 and 2 <= h <= 32768:
                    return int(w), int(h)
    raise UnpackError('Cannot determine the authored scene resolution. Specify --size WIDTHxHEIGHT explicitly.')


def inspect_path(path: Path, item_id: str | None = None, explicit_size: tuple[int, int] | None = None) -> Source:
    path = path.expanduser().resolve(strict=True)
    if path.is_file() and path.suffix.lower()=='.pkg' and not (path.parent/'project.json').is_file():
        scene=_read_scene_pkg(path,'scene.json')
        w,h=explicit_size or dimensions(scene)
        return Source(path,'scene',safe_filename(path.stem),None,w,h,item_id)
    if path.is_dir() or path.name in ('project.json', 'scene.pkg', 'scene.json') or path.suffix.lower()=='.pkg':
        root = path if path.is_dir() else path.parent
        project = _json(root / 'project.json')
        kind = str(project.get('type', '')).lower()
        title = safe_filename(str(project.get('title') or root.name), 160)
        target = str(project.get('file', ''))
        if kind == 'video':
            media = contained(root, target)
            if not media.is_file():
                raise UnpackError('The project video is missing.')
            return Source(media, 'video', title, root, workshop_id=item_id)
        if kind != 'scene':
            raise UnpackError(f'Wallpaper type {kind!r} is not supported. Web/application wallpapers are not executed.')
        if explicit_size:
            w, h = explicit_size
        else:
            scene_path = contained(root, target)
            scene = _json(scene_path) if scene_path.is_file() else _read_scene_pkg(root / 'scene.pkg', target)
            w, h = dimensions(scene)
        return Source(root, 'scene', title, root, w, h, item_id)
    if not path.is_file():
        raise UnpackError('Input must be a regular file or wallpaper project directory.')
    if path.suffix.lower() == '.mpkg':
        return Source(path, 'mpkg', safe_filename(path.stem), workshop_id=item_id)
    if path.suffix.lower() in ('.mp4', '.webm', '.mkv', '.m4v', '.mov'):
        return Source(path, 'video', safe_filename(path.stem), workshop_id=item_id)
    raise UnpackError('Use a Workshop URL/ID, project directory, project.json, scene.pkg, pre-rendered .mpkg or video file.')


def fit_size(width: int, height: int, maximum: tuple[int, int] = (3840, 2160)) -> tuple[int, int]:
    """Fit inside UHD, never upscale. Even dimensions suit yuv420p encoders."""
    factor = min(1.0, maximum[0] / width, maximum[1] / height)
    return max(2, int(width * factor) // 2 * 2), max(2, int(height * factor) // 2 * 2)
