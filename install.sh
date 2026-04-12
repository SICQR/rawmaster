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

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER detected"

echo ""
echo "  Installing Python dependencies (this may take a few minutes)..."
pip3 install -r requirements.txt

chmod +x rawmaster.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RC="${HOME}/.zshrc"
[ -f "${HOME}/.bashrc" ] && RC="${HOME}/.bashrc"

if grep -q "alias rawmaster=" "$RC" 2>/dev/null; then
    sed -i.bak "s|alias rawmaster=.*|alias rawmaster='python3 ${SCRIPT_DIR}/rawmaster.py'|" "$RC"
    echo "  Updated existing rawmaster alias in $RC"
else
    echo "" >> "$RC"
    echo "# RAWMASTER - Smash Daddys Audio Tools" >> "$RC"
    echo "alias rawmaster='python3 ${SCRIPT_DIR}/rawmaster.py'" >> "$RC"
    echo "  Added rawmaster alias to $RC"
fi

echo ""
echo "Done! RAWMASTER installed."
echo ""
echo "   Restart your terminal or run:  source $RC"
echo "   Then use:  rawmaster track.mp3 --stems --midi"
echo ""
echo "   First run downloads AI models (~110MB). One time only."
echo ""
