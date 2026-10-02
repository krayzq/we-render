from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import pytest

ROOT=Path(__file__).resolve().parents[1]

def build(path):
    spec=importlib.util.spec_from_file_location("wrbuild",ROOT/"tools/build.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m.build_app(path)

def test_portable_isolated(tmp_path):
    app=build(tmp_path/"we-render.pyz")
    p=subprocess.run([sys.executable,"-I","-S",str(app),"--version"],capture_output=True,text=True)
    assert p.returncode==0 and p.stdout.strip()=="0.1.0b3"
    p=subprocess.run([sys.executable,"-I","-S",str(app),"--help"],capture_output=True,text=True)
    assert p.returncode==0 and "--wizard" in p.stdout
    with zipfile.ZipFile(app) as z:
        names=z.namelist()
        assert "we_render/native/frame_bridge.c" in names
        assert "vendor/rich/__init__.py" not in names
        assert not any(n.endswith((".ttf",".otf",".woff",".woff2")) for n in names)

def test_build_is_reproducible(tmp_path):
    a=build(tmp_path/"a.pyz").read_bytes()
    b=build(tmp_path/"b.pyz").read_bytes()
    assert a==b

def test_install_uninstall(tmp_path):
    prefix=tmp_path/"user prefix"
    cmd=["sh",str(ROOT/"install.sh"),"--prefix",str(prefix)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    launch=prefix/"bin/we-render"
    assert launch.is_file()
    p=subprocess.run([str(launch),"--version"],capture_output=True,text=True)
    assert p.returncode==0 and p.stdout.strip()=="0.1.0b3"
    (prefix/"kept.mp4").write_bytes(b"keep")
    assert subprocess.run(cmd+["--uninstall"],capture_output=True).returncode==0
    assert not launch.exists() and (prefix/"kept.mp4").read_bytes()==b"keep"

def test_installer_refuses_unowned(tmp_path):
    p=tmp_path/"bin";p.mkdir(parents=True)
    (p/"we-render").write_text("unrelated")
    result=subprocess.run(["sh",str(ROOT/"install.sh"),"--prefix",str(tmp_path)],capture_output=True)
    assert result.returncode==1 and (p/"we-render").read_text()=="unrelated"

def test_workflows_parse():
    yaml=pytest.importorskip("yaml")
    for path in (ROOT/".github/workflows").glob("*.yml"):
        data=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
        assert "on" in data and "jobs" in data and "permissions" in data

def test_wizard_terminal(tmp_path):
    pexpect=pytest.importorskip("pexpect")
    from test_core import pack
    source=tmp_path/"Demo.mpkg";source.write_bytes(pack([("wallpaper.mp4",b"demo bytes")]))
    child=pexpect.spawn(sys.executable,["-m","we_render","-o",str(tmp_path/"out")],encoding="utf-8",timeout=10,env={**os.environ,"NO_COLOR":"1"})
    child.expect("Wallpaper file, folder or Steam Workshop URL");child.sendline(str(source))
    child.expect("Use recommended settings");child.expect("Choose");child.sendline("1")
    child.expect("Saved");child.expect(pexpect.EOF);child.close()
    assert child.exitstatus==0
    assert (tmp_path/"out/Demo.mp4").read_bytes()==b"demo bytes"
