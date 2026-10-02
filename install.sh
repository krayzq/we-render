#!/bin/sh
set -eu

PREFIX="$HOME/.local"
UNINSTALL=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix)
            [ "$#" -ge 2 ] || { echo "Missing value for --prefix" >&2; exit 2; }
            PREFIX=$2
            shift 2
            ;;
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        -h|--help)
            echo "Usage: ./install.sh [--prefix PATH] [--uninstall]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
    esac
done

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APPDIR="$PREFIX/share/we-render"
APP="$APPDIR/we-render.pyz"
LAUNCHER="$PREFIX/bin/we-render"
MARKER="# we-render-install-v2"

if [ "$UNINSTALL" -eq 1 ]; then
    if [ -f "$LAUNCHER" ]; then
        grep -qxF "$MARKER" "$LAUNCHER" || {
            echo "Refusing to remove an unrecognized $LAUNCHER" >&2
            exit 1
        }
        rm -f -- "$LAUNCHER"
    fi
    rm -f -- "$APP"
    rmdir "$APPDIR" 2>/dev/null || true
    echo "WE Render uninstalled. Exports and Steam files were kept."
    exit 0
fi

python3 -c 'import sys; raise SystemExit(sys.version_info < (3,10))' || {
    echo "Python 3.10 or newer is required." >&2
    exit 1
}

SOURCE="$ROOT/we-render.pyz"
if [ ! -f "$SOURCE" ]; then
    if [ -f "$ROOT/tools/build.py" ]; then
        python3 "$ROOT/tools/build.py" >/dev/null
        SOURCE="$ROOT/dist/we-render.pyz"
    fi
fi
[ -f "$SOURCE" ] || {
    echo "we-render.pyz was not found. Download the Linux release ZIP." >&2
    exit 1
}

if [ -e "$LAUNCHER" ] && ! grep -qxF "$MARKER" "$LAUNCHER" 2>/dev/null; then
    echo "Refusing to replace an existing unrecognized $LAUNCHER" >&2
    exit 1
fi

mkdir -p -- "$APPDIR" "$PREFIX/bin"
install -m 755 -- "$SOURCE" "$APP"

TMP="$LAUNCHER.tmp.$$"
trap 'rm -f -- "$TMP"' EXIT HUP INT TERM
cat >"$TMP" <<EOF
#!/bin/sh
$MARKER
exec python3 "$APP" "\$@"
EOF
chmod 755 "$TMP"
mv -f -- "$TMP" "$LAUNCHER"
trap - EXIT HUP INT TERM

echo "Installed: $LAUNCHER"
echo "Run: $LAUNCHER --doctor"
