#!/bin/bash
set -e

echo ""
echo "⚡ RAWMASTER Companion — Install"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 required. Install from https://python.org"
    exit 1
fi

# Install dependencies
echo "  Installing dependencies..."
pip3 install flask flask-cors rumps

# Verify rawmaster.py exists in parent directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAWMASTER_PY="${SCRIPT_DIR}/../rawmaster.py"

if [ ! -f "$RAWMASTER_PY" ]; then
    echo "❌ rawmaster.py not found at $RAWMASTER_PY"
    echo "   Make sure you're running this from the companion/ folder inside the rawmaster repo."
    exit 1
fi

echo "  rawmaster.py found ✓"

# Create LaunchAgent for auto-start on login
PLIST="$HOME/Library/LaunchAgents/com.smashd.rawmaster-companion.plist"

cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.smashd.rawmaster-companion</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>${SCRIPT_DIR}/menubar.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/.rawmaster/companion.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.rawmaster/companion.err</string>
</dict>
</plist>
PLIST_EOF

mkdir -p "$HOME/.rawmaster"

# Load the agent
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "✅ RAWMASTER Companion installed and started."
echo ""
echo "   ⚡ Look for the lightning bolt in your menu bar."
echo "   Companion will start automatically on login."
echo "   Logs: ~/.rawmaster/companion.log"
echo ""
echo "   To uninstall: launchctl unload $PLIST && rm $PLIST"
echo ""
