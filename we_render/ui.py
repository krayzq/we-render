"""English-only terminal UI. Escape wallpaper metadata, not user terminals."""
from __future__ import annotations
from contextlib import contextmanager
import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from . import __version__
from .errors import ExportError
from .storage import clean

class UI:
    def __init__(self,quiet=False,no_color=False,console=None):
        self.console=console or Console(stderr=True,no_color=no_color or "NO_COLOR" in os.environ,highlight=False)
        self.quiet=quiet
    def header(self):
        if self.quiet:return
        self.console.print()
        self.console.print(Text.assemble(('  we-', 'bold'),('render','bold green'),(f'  {__version__}','dim')))
        self.console.print('  Scene to motion. On Linux.\n',style='dim')
    def note(self,message):
        if not self.quiet:self.console.print(Text('  '+clean(message),style='yellow'))
    def line(self,label,value):
        if not self.quiet:self.console.print(Text.assemble(('  '+label+'  ','dim'),(clean(value),'')))
    def error(self,message):
        self.console.print(Panel(Text(clean(message)),title='Export stopped',title_align='left',border_style='red'))
    def ask(self,prompt,default=None):
        if not sys.stdin.isatty():raise ExportError('Pass a file/URL on the command line, or run this command in a terminal.')
        return Prompt.ask(Text(prompt),default=default,console=self.console)
    def menu(self,title,choices,default=0):
        table=Table.grid(padding=(0,2))
        for i,(label,_) in enumerate(choices,1):table.add_row(Text(str(i),style='green'),Text(label))
        self.console.print(Panel(table,title=title,title_align='left',border_style='bright_black',padding=(1,2)))
        while True:
            raw=self.ask('Choose',str(default+1))
            if raw.isdigit() and 1<=int(raw)<=len(choices):return choices[int(raw)-1][1]
            self.note('Enter one of the numbers above.')
    def plan(self,source,opts,output):
        if self.quiet:return
        table=Table.grid(padding=(0,3));table.add_column(style='dim');table.add_column()
        rows=[('Wallpaper',source.title),('Source',source.kind),('Output',opts.format.upper()),('Folder',str(output))]
        if opts.format!='original':
            rows+= [('Resolution',opts.resolution+' · keep aspect'),('FPS',str(opts.fps))]
            if opts.format not in {'png','jpg'}:rows.append(('Duration',f'{opts.duration:g} s'))
            if source.kind=='scene' and source.width and source.height:
                w,h=opts.size(source.width,source.height);rows.append(('Render canvas',f'{w} × {h}'))
            if opts.format in {'png','jpg'}:rows.append(('Snapshot time',f'{opts.at:g} s'))
            if opts.format=='mp4':rows.append(('Quality',f'{opts.codec.upper()} · {opts.encoder} · '+(opts.bitrate or f'CRF {opts.crf}')))
        for key,value in rows:table.add_row(Text(key),Text(clean(value)))
        self.console.print(Panel(table,title='Export',title_align='left',border_style='green',padding=(1,2)))
    @contextmanager
    def progress(self):
        if self.quiet or not self.console.is_terminal:
            last=['']
            def update(current,total,stage):
                if not self.quiet and stage!=last[0]:
                    self.line(stage,'…');last[0]=stage
            yield update;return
        with Progress(SpinnerColumn(style='green'),TextColumn('{task.description}',markup=False),
                      BarColumn(complete_style='green',finished_style='green',bar_width=None),
                      TaskProgressColumn(),TimeRemainingColumn(),console=self.console,expand=True,refresh_per_second=6) as progress:
            task=progress.add_task('Preparing',total=None);stage_seen=['']
            def update(current,total,stage):
                if stage!=stage_seen[0]:
                    progress.reset(task,total=total,description=stage);stage_seen[0]=stage
                progress.update(task,total=total,completed=min(current,total) if total else current)
            yield update
    def done(self,result):
        if self.quiet:return
        self.console.print(Text.assemble(('  ✓ ', 'green'),('Saved ', 'bold'),(clean(result['path']),'')))
        self.line('Size',f'{result["size"]/1048576:.2f} MiB')
        self.line('Method',result['method'])
        if result.get('compatibility'):self.note(result['compatibility'])
