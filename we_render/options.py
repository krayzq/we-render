"""Explicit export settings; no silent quality/resolution fallback."""
from __future__ import annotations
from dataclasses import dataclass
import math
import re
from .errors import ExportError

PRESETS = {'720p':(1280,720), '1080p':(1920,1080), '1440p':(2560,1440), '4k':(3840,2160)}

@dataclass
class Options:
    format: str = 'mp4'
    resolution: str = '4k'
    fps: int = 60
    duration: float = 30.0
    warmup: float = 2.0
    at: float = 0.0
    codec: str = 'h264'
    encoder: str = 'cpu'
    crf: int = 18
    bitrate: str | None = None
    upscale: bool = False
    flip: bool = False
    startup_timeout: int = 120
    timeout: int = 7200

    def validate(self):
        if self.format not in {'mp4','gif','png','jpg','original'}:
            raise ExportError('Format must be mp4, gif, png, jpg or original.')
        if self.codec not in {'h264','hevc'} or self.encoder not in {'cpu','nvenc'}:
            raise ExportError('Unsupported codec or encoder.')
        if not 1 <= self.fps <= 240:
            raise ExportError('FPS must be between 1 and 240.')
        for key, lo, hi in [('duration',0.01,3600),('warmup',0,60),('at',0,3600)]:
            value = getattr(self,key)
            if not math.isfinite(value) or not lo <= value <= hi:
                raise ExportError(f'{key} must be between {lo} and {hi} seconds.')
        if not 0 <= self.crf <= 51:
            raise ExportError('CRF must be between 0 and 51.')
        if self.bitrate and not re.fullmatch(r'[1-9][0-9]{0,5}(?:\.[0-9]{1,2})?[kKmM]?', self.bitrate):
            raise ExportError('Bitrate must look like 12M or 8000k.')
        if not 1 <= self.startup_timeout <= 600 or not 1 <= self.timeout <= 86400:
            raise ExportError('Timeouts are out of range.')
        self.size(1920,1080)
        return self

    @property
    def frames(self):
        return 1 if self.format in {'png','jpg'} else max(1, round(self.duration*self.fps))

    @property
    def skipped_frames(self):
        # Snapshots start at their exact requested timeline position, not after warmup.
        return round((self.at if self.format in {'png','jpg'} else self.warmup)*self.fps)

    def size(self, width:int, height:int):
        if not 2 <= width <= 32768 or not 2 <= height <= 32768:
            raise ExportError('Source dimensions are missing or out of range.')
        if self.resolution == 'original':
            mw,mh=width,height
        elif self.resolution in PRESETS:
            mw,mh=PRESETS[self.resolution]
        else:
            match=re.fullmatch(r'([0-9]{1,5})[xX]([0-9]{1,5})',self.resolution)
            if not match:
                raise ExportError('Resolution: original, 720p, 1080p, 1440p, 4k or WIDTHxHEIGHT.')
            mw,mh=map(int,match.groups())
        if not 2 <= mw <= 16384 or not 2 <= mh <= 16384 or mw*mh>67108864:
            raise ExportError('Requested resolution exceeds the 64-megapixel safety limit.')
        ratio=min(mw/width,mh/height)
        if not self.upscale:ratio=min(ratio,1.0)
        w,h=max(2,int(width*ratio)//2*2),max(2,int(height*ratio)//2*2)
        if self.format=='gif' and w*h > 1920*1080:
            raise ExportError('GIF export is limited to 1080p. Use --resolution 720p or MP4 for 4K.')
        return w,h

    def codec_args(self):
        if self.format=='gif':return ['-loop','0']
        if self.format=='png':return ['-c:v','png','-frames:v','1','-update','1']
        if self.format=='jpg':return ['-q:v','2','-frames:v','1','-update','1']
        codec={'cpu':{'h264':'libx264','hevc':'libx265'},'nvenc':{'h264':'h264_nvenc','hevc':'hevc_nvenc'}}[self.encoder][self.codec]
        args=['-c:v',codec,'-preset','medium' if self.encoder=='cpu' else 'p5']
        if self.bitrate:args+=['-b:v',self.bitrate]
        elif self.encoder=='cpu':args+=['-crf',str(self.crf)]
        else:args+=['-rc','vbr','-cq',str(self.crf),'-b:v','0']
        args+=['-pix_fmt','yuv420p','-movflags','+faststart']
        if self.codec=='hevc':args+=['-tag:v','hvc1']
        return args

    def filter(self, width=None,height=None,*,gl=False):
        chain=[]
        if bool(gl)^self.flip:chain.append('vflip')
        if width and height:chain.append(f'scale={width}:{height}:flags=lanczos')
        chain.append('setsar=1')
        if self.format=='gif':
            # A per-frame palette prevents buffering an entire 4K animation in RAM.
            return ','.join(chain)+',split[palin][vin];[palin]palettegen=stats_mode=single[pal];[vin][pal]paletteuse=new=1:dither=sierra2_4a'
        return ','.join(chain)
