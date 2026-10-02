from __future__ import annotations
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import pytest
from we_render.archive import open_package
from we_render.storage import Span,publish,safe_name,temporary_output
from we_render.source import workshop_id,steam_libraries,locate_item,inspect_path,dimensions,Source
from we_render.options import Options
from we_render.errors import ExportError
from we_render.cli import parser,make_options,pick_video,main
from we_render.ui import UI
ROOT=Path(__file__).resolve().parents[1]


def pack(items,version=b'PKGM0014'):
    s=lambda t:struct.pack('<I',len(t))+t
    body=b'';table=b''
    for i,(name,data) in enumerate(items):
        table+=s(name.encode())+struct.pack('<II',len(body) if version.startswith(b'PKGV') else i,len(data));body+=data
    return s(version)+struct.pack('<I',len(items))+table+body

@pytest.mark.parametrize('value,expected',[
    ('3775394622','3775394622'),('https://steamcommunity.com/sharedfiles/filedetails/?id=3775394622','3775394622'),
    ('http://www.steamcommunity.com/workshop/filedetails/?id=123&searchtext=x','123'),('/tmp/a b.mpkg',None)])
def test_id(value,expected):assert workshop_id(value)==expected

@pytest.mark.parametrize('value',[
    'https://steamcommunity.com.evil.test/sharedfiles/filedetails/?id=42','https://example.com/a',
    'https://steamcommunity.com:bad/sharedfiles/filedetails/?id=4',
    'https://steamcommunity.com/sharedfiles/filedetails/?id=4&id=5',
    'https://user:pass@steamcommunity.com/sharedfiles/filedetails/?id=4',
    'https://steamcommunity.com/profiles/?id=4'])
def test_bad_urls(value):
    with pytest.raises(ExportError):workshop_id(value)

@pytest.mark.parametrize('values',[
    {'fps':0},{'fps':241},{'duration':float('nan')},{'duration':float('inf')},
    {'duration':-1},{'at':-1},{'warmup':70},{'crf':80},{'resolution':'1x1'},
    {'resolution':'fake'},{'bitrate':'2M;rm x'},{'timeout':0},{'startup_timeout':999}])
def test_bad_options(values):
    with pytest.raises(ExportError):Options(**values).validate()

@pytest.mark.parametrize('size,expected',[
    ((3840,2160),(3840,2160)),((1920,1080),(1920,1080)),((7680,4320),(3840,2160)),
    ((3440,1440),(3440,1440)),((2160,3840),(1214,2160))])
def test_fit(size,expected):assert Options().size(*size)==expected

def test_upscale():assert Options(upscale=True).size(1920,1080)==(3840,2160)
def test_gif_limit():
    with pytest.raises(ExportError):Options(format='gif').size(3840,2160)
def test_snapshot():
    o=Options(format='png',at=1.5,fps=60,warmup=2)
    assert o.frames==1 and o.skipped_frames==90

def test_source_scene(tmp_path):
    (tmp_path/'project.json').write_text(json.dumps({'type':'Scene','file':'scene.json','title':'Synthetic scene'}))
    (tmp_path/'scene.pkg').write_bytes(pack([('scene.json',json.dumps({'general':{'orthogonalprojection':{'width':3840,'height':2160}}}).encode())],b'PKGV0022'))
    s=inspect_path(tmp_path);assert s.kind=='scene' and (s.width,s.height)==(3840,2160)
    (tmp_path/'project.json').unlink();s=inspect_path(tmp_path/'scene.pkg');assert s.root is None and s.width==3840

def test_project_escape(tmp_path):
    (tmp_path/'project.json').write_text(json.dumps({'type':'video','file':'../secret.mp4'}))
    with pytest.raises(ExportError):inspect_path(tmp_path)

def test_unsupported_web(tmp_path):
    (tmp_path/'project.json').write_text(json.dumps({'type':'Web','file':'x.html'}))
    with pytest.raises(ExportError):inspect_path(tmp_path)

def test_library(tmp_path,monkeypatch):
    a=tmp_path/'steam';b=tmp_path/'more';a.mkdir();b.mkdir();(a/'steamapps').mkdir()
    (a/'steamapps/libraryfolders.vdf').write_text(f'"libraryfolders" {{ "2" {{ "path" "{b}" }} }}')
    item=b/'steamapps/workshop/content/431960/42';item.mkdir(parents=True);(item/'project.json').write_text('{}')
    roots=steam_libraries([a]);assert b in roots and locate_item('42',roots)==item

def test_package(tmp_path):
    f=tmp_path/'x.mpkg';f.write_bytes(pack([('project.json',b'{"type":"Scene","title":"Test"}'),('wallpaper.mp4',b'video'),('preview.gif',b'gif')]))
    p=open_package(f);r=pick_video(p,None,UI(quiet=True));assert r.name=='wallpaper.mp4' and r.span.read()==b'video'
    assert r.role=='pre-rendered video candidate'

@pytest.mark.parametrize('bad',[b'',b'xxx',struct.pack('<I',9999),pack([('a.mp4',b'foo'),('a.mp4',b'bar')]),pack([('a.mp4',b'foo')])[:-1]])
def test_bad_packages(tmp_path,bad):
    f=tmp_path/'bad.mpkg';f.write_bytes(bad)
    with pytest.raises(ExportError):open_package(f)

def test_dynamic_not_static_fallback(tmp_path):
    f=tmp_path/'x.mpkg';f.write_bytes(pack([('preview.gif',b'gif')]))
    with pytest.raises(ExportError):pick_video(open_package(f),None,UI(quiet=True))

def test_ambiguous(tmp_path):
    f=tmp_path/'x.mpkg';f.write_bytes(pack([('a.mp4',b'x'),('b.mp4',b'y')]))
    p=open_package(f)
    with pytest.raises(ExportError):pick_video(p,None,UI(quiet=True))
    assert pick_video(p,'b.mp4',UI(quiet=True)).span.read()==b'y'

def test_never_overwrite(tmp_path):
    (tmp_path/'a.mp4').write_bytes(b'old')
    with temporary_output(tmp_path,'mp4') as t:
        t.write_bytes(b'new');p=publish(t,tmp_path,'a.mp4')
    assert p.name=='a (1).mp4' and p.read_bytes()==b'new' and (tmp_path/'a.mp4').read_bytes()==b'old'

def test_output_symlink(tmp_path):
    (tmp_path/'a.mp4').symlink_to('/nonexistent')
    with temporary_output(tmp_path,'mp4') as t:t.write_bytes(b'new');p=publish(t,tmp_path,'a.mp4')
    assert p.name=='a (1).mp4'

def test_changed_source(tmp_path):
    f=tmp_path/'source';f.write_bytes(b'abc');span=Span.whole(f);f.write_bytes(b'abcd')
    with pytest.raises(ExportError):span.read()

def test_original_opts():
    s=Source(Path('/x.mp4'),'video','x')
    assert make_options(parser().parse_args(['x']),s).format=='original'
    with pytest.raises(ExportError):make_options(parser().parse_args(['x','--format','original','--fps','30']),s)
    with pytest.raises(ExportError):make_options(parser().parse_args(['x','--fps','0']),s)

def test_control_char_name():assert '\x1b' not in safe_name('abc\x1b[31m.mp4')

def test_entry_cli_invalid(tmp_path,capsys):
    f=tmp_path/'bad.mpkg';f.write_bytes(b'bad')
    assert main([str(f),'--json'])==1
    assert json.loads(capsys.readouterr().out)['ok'] is False
