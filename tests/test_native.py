"""Real GLX pixel path on an ABI fixture, NOT an actual Wallpaper Engine scene."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import pytest
from we_render.renderer import render,build_bridge
from we_render.source import Source
from we_render.options import Options
from we_render.errors import ExportError

HERE=Path(__file__).parent/'native'
pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY') or not shutil.which('cc') or not shutil.which('ffmpeg'),reason='X11, compiler and FFmpeg required')

@pytest.fixture(scope='module')
def fixture_engine(tmp_path_factory):
    root=tmp_path_factory.mktemp('native');lib=root/'libfixture.so';app=root/'renderer'
    subprocess.run(['cc','-shared','-fPIC',str(HERE/'glfw_fixture.c'),'-o',str(lib),'-lX11','-l:libGL.so.1'],check=True,capture_output=True)
    subprocess.run(['cc',str(HERE/'render_fixture.c'),'-o',str(app),'-L'+str(root),'-lfixture','-Wl,-rpath,'+str(root)],check=True,capture_output=True)
    return app

def run(tmp_path,app,opts,size=(160,90)):
    assets=tmp_path/'assets';assets.mkdir(exist_ok=True);(assets/'shaders').mkdir(exist_ok=True)
    s=Source(tmp_path,'scene','Synthetic ABI fixture',tmp_path,*size)
    return render(s,tmp_path/'out',assets,opts,str(app),lambda *x:None)

@pytest.mark.parametrize('fmt',['mp4','png','jpg','gif'])
def test_gl_frames(tmp_path,fixture_engine,fmt):
    opts=Options(format=fmt,resolution='original',duration=.5,fps=20,warmup=.2,at=.25)
    result=run(tmp_path,fixture_engine,opts)
    log=Path(result['log']).read_text()
    assert 'mapped=0' in log
    assert result['media']['width']==160
    if fmt=='mp4':assert result['media']['frames']==10 and result['media']['fps']==20

def test_pixel_orientation(tmp_path,fixture_engine):
    result=run(tmp_path,fixture_engine,Options(format='png',resolution='original',at=0))
    p=subprocess.run(['ffmpeg','-v','error','-i',result['path'],'-f','rawvideo','-pix_fmt','rgb24','-frames:v','1','pipe:1'],capture_output=True,check=True)
    data=p.stdout
    top=data[(10*160+10)*3:(10*160+10)*3+3];bottom=data[(80*160+10)*3:(80*160+10)*3+3]
    assert top[0]>240 and top[2]<10 and bottom[2]>240 and bottom[0]<10

def test_actual_4k_sixty(tmp_path,fixture_engine):
    result=run(tmp_path,fixture_engine,Options(duration=.1,warmup=0),(3840,2160))
    assert result['media']['width']==3840 and result['media']['height']==2160 and result['media']['fps']==60 and result['media']['frames']==6

def test_mismatch_rejected(tmp_path,fixture_engine,monkeypatch):
    monkeypatch.setenv('WE_TEST_MISMATCH','1')
    with pytest.raises(ExportError):run(tmp_path,fixture_engine,Options(duration=.1,warmup=0))
    assert not list((tmp_path/'out').glob('*.mp4'))

def test_native_cancel(tmp_path,fixture_engine):
    def cancel(current,total,stage):
        if current>1:raise KeyboardInterrupt()
    assets=tmp_path/'assets';assets.mkdir()
    s=Source(tmp_path,'scene','cancel',tmp_path,160,90)
    with pytest.raises(KeyboardInterrupt):render(s,tmp_path/'out',assets,Options(duration=120,warmup=0),str(fixture_engine),cancel)
    assert not list((tmp_path/'out').glob('*.mp4'))
