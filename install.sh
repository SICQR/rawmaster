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

# Create venv if it doesn't exist
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

# Activate venv
source "$SCRIPT_DIR/.venv/bin/activate"

echo "  Installing Python dependencies (this may take a few minutes)..."
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt"

chmod +x "$SCRIPT_DIR/rawmaster.py"

# Write /usr/local/bin/rawmaster
echo "  Writing launcher to /usr/local/bin/rawmaster..."
RAWMASTER_LAUNCHER=$(cat <<LAUNCH
#!/bin/bash
source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/rawmaster.py" "\$@"
LAUNCH
)
echo "$RAWMASTER_LAUNCHER" | sudo tee /usr/local/bin/rawmaster > /dev/null
sudo chmod +x /usr/local/bin/rawmaster

# Write /usr/local/bin/rawmaster-ui
echo "  Writing launcher to /usr/local/bin/rawmaster-ui..."
RAWMASTER_UI_LAUNCHER=$(cat <<LAUNCH
#!/bin/bash
source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/app.py" "\$@"
LAUNCH
)
echo "$RAWMASTER_UI_LAUNCHER" | sudo tee /usr/local/bin/rawmaster-ui > /dev/null
sudo chmod +x /usr/local/bin/rawmaster-ui

echo ""
echo "  Testing installation..."
rawmaster --help

echo ""
echo "Done! RAWMASTER installed."
echo ""
echo "   CLI:  rawmaster track.mp3 --stems --midi"
echo "   UI:   rawmaster-ui  (opens at http://localhost:7860)"
echo ""
echo "   First run downloads AI models (~110MB). One time only."
echo ""
