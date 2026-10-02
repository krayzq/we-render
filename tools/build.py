#!/usr/bin/env python3
"""Build the standalone zipapp and release archives using only the standard library."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from we_render import __version__

FIXED=(2026,10,2,0,0,0)

def add(z,name,data,executable=False):
    item=zipfile.ZipInfo(str(name).replace("\\","/"),FIXED)
    item.compress_type=zipfile.ZIP_DEFLATED
    item.external_attr=(0o100755 if executable else 0o100644)<<16
    z.writestr(item,data)

def files_under(base):
    if not base.exists():return []
    return sorted(
        p for p in base.rglob("*")
        if p.is_file()
        and not any(x in p.parts for x in ("__pycache__",".pytest_cache",".git","dist"))
        and p.suffix not in (".pyc",".pyo")
    )

def build_app(destination):
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(b"#!/usr/bin/env python3\n")
    with zipfile.ZipFile(destination,"a") as z:
        add(z,"__main__.py",b"from we_render.cli import main\nraise SystemExit(main())\n")
        for p in files_under(ROOT/"we_render"):
            add(z,p.relative_to(ROOT),p.read_bytes())
        add(z,"LICENSE",(ROOT/"LICENSE").read_bytes())
    destination.chmod(0o755)
    return destination

def build(out=None):
    out=Path(out or ROOT/"dist")
    out.mkdir(parents=True,exist_ok=True)

    app=build_app(out/"we-render.pyz")

    source=out/f"we-render-{__version__}-source.zip"
    content=[]
    for name in ("we_render","tests","tools",".github"):
        content += files_under(ROOT/name)
    content += [ROOT/"docs/cover.png"]
    for name in (
        "README.md","LICENSE","THIRD_PARTY.md","CHANGELOG.md","pyproject.toml",
        ".gitignore","install.sh"
    ):
        p=ROOT/name
        if p.is_file():content.append(p)

    with zipfile.ZipFile(source,"w") as z:
        for p in sorted(content):
            add(z,Path("we-render")/p.relative_to(ROOT),p.read_bytes(),p.name.endswith(".sh"))

    portable=out/f"we-render-{__version__}-linux.zip"
    with zipfile.ZipFile(portable,"w") as z:
        add(z,"we-render/we-render.pyz",app.read_bytes(),True)
        for name in ("install.sh","README.md","LICENSE","THIRD_PARTY.md"):
            add(z,"we-render/"+name,(ROOT/name).read_bytes(),name.endswith(".sh"))
        add(z,"we-render/docs/cover.png",(ROOT/"docs/cover.png").read_bytes())

    sums=[app,source,portable]
    (out/"SHA256SUMS").write_text(
        "".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.name+"\n" for p in sums)
    )
    print(json.dumps({"version":__version__,"artifacts":[str(p) for p in sums]},indent=2))
    return app

if __name__=="__main__":
    build()
