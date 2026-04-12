#!/bin/bash
set -e

echo ""
echo "RAWMASTER -- Smash Daddys Audio Tools"
echo "Strip it back. Own the stems."
echo ""
echo "Installing RAWMASTER..."
echo ""

if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is required. Install from https://python.org"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))")
echo "  Python $PY_VER detected"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Create venv ────────────────────────────────────────────────────────────────
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

PIP="$SCRIPT_DIR/.venv/bin/pip"

echo "  Upgrading pip..."
"$PIP" install --upgrade pip --quiet

echo "  Installing core dependencies..."
"$PIP" install -r "$SCRIPT_DIR/requirements.txt" --quiet

# ── basic-pitch: must be installed with --no-deps on Python 3.14 / Apple Silicon
echo "  Installing basic-pitch (no-deps workaround for Python 3.14)..."
"$PIP" install basic-pitch --no-deps --quiet
"$PIP" install mir-eval pretty-midi resampy onnxruntime --quiet

chmod +x "$SCRIPT_DIR/rawmaster.py"

# ── Detect developer / self-build mode ────────────────────────────────────────
DEV_MODE=0
if [ -d "$SCRIPT_DIR/.git" ]; then
    DEV_MODE=1
    echo "  Git repo detected — enabling developer mode (license bypass)."
fi

# ── Write /usr/local/bin/rawmaster ────────────────────────────────────────────
echo "  Writing launcher to /usr/local/bin/rawmaster..."

if [ "$DEV_MODE" -eq 1 ]; then
    SKIP_LINE='export RAWMASTER_SKIP_LICENSE=1'
else
    SKIP_LINE='export RAWMASTER_SKIP_LICENSE="${RAWMASTER_SKIP_LICENSE}"'
fi

sudo tee /usr/local/bin/rawmaster > /dev/null << LAUNCHEREOF
#!/bin/bash
$SKIP_LINE
source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/rawmaster.py" "\$@"
LAUNCHEREOF
sudo chmod +x /usr/local/bin/rawmaster

# ── Write /usr/local/bin/rawmaster-ui ─────────────────────────────────────────
echo "  Writing launcher to /usr/local/bin/rawmaster-ui..."

sudo tee /usr/local/bin/rawmaster-ui > /dev/null << LAUNCHEREOF
#!/bin/bash
$SKIP_LINE
source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/app.py" "\$@"
LAUNCHEREOF
sudo chmod +x /usr/local/bin/rawmaster-ui

# ── Smoke test ─────────────────────────────────────────────────────────────────
echo ""
echo "  Testing installation..."
/usr/local/bin/rawmaster --help

echo ""
echo "Done! RAWMASTER installed."
echo ""
if [ "$DEV_MODE" -eq 1 ]; then
    echo "   Developer mode: license check bypassed automatically."
else
    echo "   If you built this yourself, add RAWMASTER_SKIP_LICENSE=1 to your shell env."
fi
echo ""
echo "   CLI:  rawmaster track.mp3 --stems --midi"
echo "   UI:   rawmaster-ui  (opens at http://localhost:7860)"
echo ""
echo "   First run downloads AI models (~110MB). One time only."
echo ""
