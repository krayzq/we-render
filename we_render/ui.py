"""Small dependency-free terminal UI."""
from __future__ import annotations
from contextlib import contextmanager
import os
import shutil
import sys
import time
from . import __version__
from .errors import ExportError
from .storage import clean

RESET="\x1b[0m"
GREEN="\x1b[32m"
YELLOW="\x1b[33m"
RED="\x1b[31m"
BOLD="\x1b[1m"
DIM="\x1b[2m"

class UI:
    def __init__(self,quiet=False,no_color=False,console=None):
        self.quiet=quiet
        self.stream=getattr(console,"file",None) or sys.stderr
        self.color=bool(getattr(self.stream,"isatty",lambda:False)()) and not no_color and "NO_COLOR" not in os.environ

    def _style(self,text,*codes):
        text=clean(str(text))
        return "".join(codes)+text+RESET if self.color and codes else text

    def _print(self,text=""):
        print(text,file=self.stream,flush=True)

    def header(self):
        if self.quiet:return
        self._print()
        self._print("  "+self._style("we-",BOLD)+self._style("render",BOLD,GREEN)+self._style(f"  {__version__}",DIM))
        self._print(self._style("  Scene to motion. On Linux.",DIM))
        self._print()

    def note(self,message):
        if not self.quiet:self._print(self._style("  "+clean(message),YELLOW))

    def line(self,label,value):
        if not self.quiet:self._print(f"  {self._style(label,DIM):<24} {clean(str(value))}")

    def error(self,message):
        msg=clean(message)
        self._print(self._style("  Export stopped",RED,BOLD))
        for line in msg.splitlines() or [""]:
            self._print("  "+line)

    def ask(self,prompt,default=None):
        if not sys.stdin.isatty():raise ExportError("Pass a file/URL on the command line, or run this command in a terminal.")
        suffix=f" [{default}]" if default is not None else ""
        self.stream.write(f"  {clean(prompt)}{suffix}: ");self.stream.flush()
        value=sys.stdin.readline()
        if value=="":raise EOFError()
        value=value.rstrip("\r\n")
        return value if value else (default if default is not None else "")

    def menu(self,title,choices,default=0):
        self._print()
        self._print("  "+self._style(clean(title),BOLD))
        for i,(label,_) in enumerate(choices,1):
            marker=self._style(str(i),GREEN)
            self._print(f"    {marker}  {clean(label)}")
        while True:
            raw=self.ask("Choose",str(default+1))
            if raw.isdigit() and 1<=int(raw)<=len(choices):return choices[int(raw)-1][1]
            self.note("Enter one of the numbers above.")

    def plan(self,source,opts,output):
        if self.quiet:return
        self._print()
        self._print("  "+self._style("Export",BOLD,GREEN))
        rows=[("Wallpaper",source.title),("Source",source.kind),("Output",opts.format.upper()),("Folder",str(output))]
        if opts.format!="original":
            rows += [("Resolution",opts.resolution+" · keep aspect"),("FPS",str(opts.fps))]
            if opts.format not in {"png","jpg"}:rows.append(("Duration",f"{opts.duration:g} s"))
            if source.kind=="scene" and source.width and source.height:
                w,h=opts.size(source.width,source.height);rows.append(("Render canvas",f"{w} × {h}"))
            if opts.format in {"png","jpg"}:rows.append(("Snapshot time",f"{opts.at:g} s"))
            if opts.format=="mp4":rows.append(("Quality",f"{opts.codec.upper()} · {opts.encoder} · "+(opts.bitrate or f"CRF {opts.crf}")))
        width=max(len(k) for k,_ in rows)
        for key,value in rows:self._print(f"    {self._style(key,DIM):<{width+8}} {clean(str(value))}")
        self._print()

    @contextmanager
    def progress(self):
        if self.quiet:
            yield lambda *args:None
            return
        terminal=bool(getattr(self.stream,"isatty",lambda:False)())
        state={"stage":None,"start":time.monotonic(),"last_len":0,"active":False}
        glyphs="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        def update(current,total,stage):
            stage=clean(stage)
            if not terminal:
                if stage!=state["stage"]:
                    self._print(f"  {stage} ...")
                    state["stage"]=stage
                return
            state["stage"]=stage
            elapsed=max(time.monotonic()-state["start"],1e-6)
            cols=shutil.get_terminal_size((100,24)).columns
            barw=max(10,min(34,cols-58))
            if total:
                ratio=max(0.0,min(1.0,current/total))
                filled=int(barw*ratio)
                bar="█"*filled+"░"*(barw-filled)
                pct=f"{ratio*100:5.1f}%"
                eta=(elapsed/current*(total-current)) if current else 0
                tail=f"{pct}  ETA {int(eta//60):02d}:{int(eta%60):02d}"
            else:
                bar="─"*barw
                tail=""
            spin=glyphs[int(elapsed*8)%len(glyphs)]
            line=f"  {spin} {stage[:24]:24} {bar} {tail}".rstrip()
            pad=max(0,state["last_len"]-len(line))
            self.stream.write("\r"+line+" "*pad);self.stream.flush()
            state["last_len"]=len(line);state["active"]=True

        try:
            yield update
        finally:
            if terminal and state["active"]:self.stream.write("\n");self.stream.flush()

    def done(self,result):
        if self.quiet:return
        self._print("  "+self._style("✓",GREEN)+" "+self._style("Saved",BOLD)+" "+clean(result["path"]))
        self.line("Size",f'{result["size"]/1048576:.2f} MiB')
        self.line("Method",result["method"])
        if result.get("compatibility"):self.note(result["compatibility"])
