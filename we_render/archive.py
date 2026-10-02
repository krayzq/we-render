"""Independent PKGV (relative offsets) and PKGM (sequential) reader."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from .errors import ExportError
from .storage import MIB, Reader, Span, clean

IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tga', '.dds'}
VIDEO_EXT = {'.mp4', '.m4v', '.webm', '.mov', '.mkv', '.avi'}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT | {'.gif', '.tex'}

def norm(s):
    return s.replace('\\', '/').removeprefix('./')

@dataclass
class Resource:
    name: str
    span: Span
    role: str = 'resource'
    texture: object = None
    problem: str | None = None
    @property
    def suffix(self):
        return Path(norm(self.name)).suffix.lower()
    @property
    def preview(self):
        return bool(re.match(r'^(preview|thumbnail|thumb)([._-]|$)', norm(self.name).split('/')[-1], re.I))
    @property
    def kind(self):
        if self.problem:
            return 'unsupported'
        if self.texture:
            return self.texture.kind
        if self.suffix in VIDEO_EXT:
            return 'video'
        if self.suffix == '.gif':
            return 'animation'
        return 'image'

@dataclass
class Package:
    path: Path
    version: str
    resources: list[Resource]
    metadata: dict = field(default_factory=dict)
    notices: list[str] = field(default_factory=list)
    @property
    def title(self):
        value = self.metadata.get('title')
        return clean(value) if isinstance(value, str) and value.strip() else self.path.stem
    @property
    def scene(self):
        return self.version.startswith('PKGV') or str(self.metadata.get('type', '')).lower() == 'scene'


def read_json(span: Span):
    if span.size > MIB:
        return {}
    try:
        value = json.loads(span.read(MIB).decode('utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (UnicodeError, ValueError, RecursionError):
        return {}


def open_package(path: Path) -> Package:
    span = Span.whole(path)
    entries = []
    with Reader(span, max_header=16 * MIB) as r:
        version = r.string(64)
        if not re.fullmatch(r'PKG[VM][0-9]{4}', version):
            raise ExportError('Not a supported Wallpaper Engine PKG/MPKG signature.')
        count = r.u32()
        if not 1 <= count <= 100000 or count * 13 > span.size:
            raise ExportError('Invalid number of resources.')
        names = set()
        for _ in range(count):
            name = r.string()
            key = norm(name).casefold()
            if key in names:
                raise ExportError('Duplicate resource names are ambiguous.')
            names.add(key)
            offset_or_index, size = r.u32(), r.u32()
            entries.append((name, offset_or_index, size))
        start = r.pos
    pos = 0
    resources = []
    ranges = []
    metadata = {}
    for name, value, size in entries:
        offset = value if version.startswith('PKGV') else pos
        part = span.sub(start + offset, size)
        ranges.append((offset, offset + size))
        if norm(name).casefold() == 'project.json':
            metadata = read_json(part)
        if Path(norm(name)).suffix.lower() in MEDIA_EXT:
            resources.append(Resource(name, part))
        pos += size
    # Reject overlapping payloads, but permit padding and offset-sorted PKGV tables.
    end = 0
    for a, b in sorted(ranges):
        if a < end and b > a:
            raise ExportError('Overlapping resource ranges are not supported.')
        end = max(end, b)
    if not metadata:
        sidecar = path.parent / 'project.json'
        if sidecar.is_file():
            metadata = read_json(Span.whole(sidecar))
    package = Package(span.path, version, resources, metadata)
    project_file = norm(str(metadata.get('file', ''))).casefold()
    for resource in resources:
        if resource.preview:
            resource.role = 'preview'
        elif resource.suffix in VIDEO_EXT:
            if str(metadata.get('type', '')).lower() == 'video' and norm(resource.name).casefold() == project_file:
                resource.role = 'main video'
            elif version.startswith('PKGM') and norm(resource.name).casefold() in {'wallpaper.mp4', 'wallpaper.webm'}:
                resource.role = 'pre-rendered video candidate'
    if package.scene:
        package.notices.append('Scene resources are separate layers. Extraction does not composite the scene or render its effects.')
    if version.startswith('PKGM') and any('candidate' in x.role for x in resources):
        package.notices.append('A pre-rendered video candidate was found. Scene metadata can remain after mobile export; inspect playback.')
    return package
