"""Bounded file spans and collision-safe publishing. No source writes."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
import errno
import hashlib
import os
import re
import shutil
import stat
import struct
import tempfile
from .errors import ExportError

MIB = 1024 * 1024

def clean(text: object) -> str:
    return ''.join(c if c.isprintable() else ' ' for c in str(text))

def safe_name(text: str, limit: int = 160) -> str:
    text = clean(text).replace('\\', '/').split('/')[-1]
    text = re.sub(r'[<>:"/\\|?*]', '_', text).strip(' .') or 'wallpaper'
    if re.match(r'^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', text, re.I):
        text = '_' + text
    return text.encode('utf-8')[:limit].decode('utf-8', 'ignore') or 'wallpaper'

def identity(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns

@dataclass(frozen=True)
class Span:
    path: Path
    offset: int
    size: int
    stamp: tuple

    @classmethod
    def whole(cls, path: Path):
        path = path.expanduser().resolve(strict=True)
        st = path.stat()
        if not stat.S_ISREG(st.st_mode):
            raise ExportError('Input must be a regular file, not a device or named pipe.')
        return cls(path, 0, st.st_size, identity(st))

    @contextmanager
    def opened(self):
        flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(self.path, flags)
        with os.fdopen(fd, 'rb') as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode) or identity(os.fstat(f.fileno())) != self.stamp:
                raise ExportError('Source changed after inspection. Inspect it again.')
            f.seek(self.offset)
            yield f
            if identity(os.fstat(f.fileno())) != self.stamp:
                raise ExportError('Source changed during export; the output was not published.')

    def sub(self, offset: int, size: int):
        if offset < 0 or size < 0 or offset + size > self.size:
            raise ExportError('A resource points outside its container.')
        return Span(self.path, self.offset + offset, size, self.stamp)

    def read(self, limit: int = 256 * MIB) -> bytes:
        if self.size > limit:
            raise ExportError(f'Resource exceeds the {limit // MIB} MiB decode safety limit.')
        with self.opened() as f:
            result = f.read(self.size)
            if len(result) != self.size:
                raise ExportError('Source is truncated.')
            return result

    def head(self, size=32):
        return self.sub(0, min(size, self.size)).read()

    def copy(self, output: Path, progress=None):
        done = 0
        with self.opened() as source, output.open('wb') as dest:
            while done < self.size:
                chunk = source.read(min(MIB, self.size - done))
                if not chunk:
                    raise ExportError('Source is truncated.')
                dest.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, self.size, 'Copying')
        return done

class Reader:
    def __init__(self, span: Span, *, max_header=None):
        self.span = span
        self.pos = 0
        self.max_header = max_header
        self._ctx = None
        self.stream = None
    def __enter__(self):
        self._ctx = self.span.opened()
        self.stream = self._ctx.__enter__()
        return self
    def __exit__(self, *args):
        return self._ctx.__exit__(*args)
    def read(self, n):
        if n < 0 or self.pos + n > self.span.size:
            raise ExportError('Truncated or invalid resource header.')
        if self.max_header and self.pos + n > self.max_header:
            raise ExportError('Resource table exceeds the safety limit.')
        self.stream.seek(self.span.offset + self.pos)
        b = self.stream.read(n)
        if len(b) != n:
            raise ExportError('Source is truncated.')
        self.pos += n
        return b
    def skip(self, n):
        if n < 0 or self.pos + n > self.span.size:
            raise ExportError('Payload exceeds its container.')
        self.pos += n
    def u32(self):
        return struct.unpack('<I', self.read(4))[0]
    def i32(self):
        return struct.unpack('<i', self.read(4))[0]
    def f32(self):
        return struct.unpack('<f', self.read(4))[0]
    def string(self, limit=4096):
        n = self.u32()
        if not 1 <= n <= limit:
            raise ExportError('Invalid string length in the package.')
        try:
            result = self.read(n).decode('utf-8')
        except UnicodeError as e:
            raise ExportError('Invalid UTF-8 resource name.') from e
        if '\0' in result:
            raise ExportError('A resource name contains a NUL byte.')
        return result
    def cstring(self, limit=64):
        buf = bytearray()
        for _ in range(limit):
            c = self.read(1)
            if c == b'\0':
                try:
                    return buf.decode('utf-8')
                except UnicodeError as e:
                    raise ExportError('Invalid UTF-8 in a TEX header.') from e
            buf.extend(c)
        raise ExportError('Unterminated TEX header string.')

@contextmanager
def temporary_output(directory: Path, extension: str):
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='.we-render-', suffix='.' + extension, dir=directory)
    os.close(fd)
    path = Path(filename)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)

def publish(temp: Path, directory: Path, name: str) -> Path:
    """Publish only completed files, without replacing existing files/symlinks."""
    directory = directory.expanduser().resolve()
    name = safe_name(name, 220)
    stem, ext = Path(name).stem, Path(name).suffix
    for n in range(10000):
        dest = directory / (name if not n else f'{stem} ({n}){ext}')
        try:
            os.link(temp, dest)
            return dest
        except FileExistsError:
            continue
        except OSError as exc:
            if exc.errno not in (errno.EXDEV, errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP):
                raise
            try:
                fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            except FileExistsError:
                continue
            try:
                with os.fdopen(fd, 'wb') as out, temp.open('rb') as src:
                    shutil.copyfileobj(src, out, MIB)
            except BaseException:
                dest.unlink(missing_ok=True)
                raise
            return dest
    raise ExportError('Too many output files with the same name.')

def checksum(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(MIB), b''):
            h.update(block)
    return h.hexdigest()
