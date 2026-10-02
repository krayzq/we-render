from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import pytest
from we_render.media import convert,probe
from we_render.options import Options
from we_render.cli import main
from test_core import pack

pytestmark=pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg required')

@pytest.fixture
def movie(tmp_path):
    path=tmp_path/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=24','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    return path

def test_original_movie(movie,tmp_path,capsys):
    assert main([str(movie),'-o',str(tmp_path/'out'),'--json'])==0
    out=json.loads(capsys.readouterr().out)
    assert Path(out['path']).read_bytes()==movie.read_bytes()
    assert probe(Path(out['path']))['fps']==24

def test_original_mpkg(movie,tmp_path,capsys):
    f=tmp_path/'Knight.mpkg';f.write_bytes(pack([('project.json',b'{"type":"Scene","title":"Demo"}'),('wallpaper.mp4',movie.read_bytes())]))
    assert main([str(f),'-o',str(tmp_path/'out'),'--json'])==0
    out=json.loads(capsys.readouterr().out)
    assert Path(out['path']).name=='Demo.mp4'
    assert Path(out['path']).read_bytes()==movie.read_bytes()

@pytest.mark.parametrize('fmt',['mp4','gif','png','jpg'])
def test_conversion(movie,tmp_path,fmt):
    opts=Options(format=fmt,resolution='original',duration=.2,fps=25,at=.2)
    result=convert(movie,tmp_path/'out','test',opts,lambda *x:None)
    assert Path(result['path']).stat().st_size>0
    assert result['media']['width']==160 and result['media']['height']==90
    if fmt=='mp4':assert result['media']['frames']==5 and result['media']['fps']==25

def test_real_hevc(movie,tmp_path):
    result=convert(movie,tmp_path/'out','hevc',Options(codec='hevc',resolution='original',duration=.1),lambda *x:None)
    assert result['media']['codec']=='hevc'

def test_cancel_cleans(movie,tmp_path):
    def stop(*a):raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):convert(movie,tmp_path/'out','cancel',Options(duration=50),stop)
    assert not list((tmp_path/'out').glob('*.mp4'))
