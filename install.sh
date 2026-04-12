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

python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install demucs noisereduce pyloudnorm librosa soundfile numpy requests pedalboard scipy gradio flask flask-cors rumps
.venv/bin/pip install basic-pitch --no-deps
.venv/bin/pip install mir-eval pretty-midi resampy coremltools onnxruntime

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "#!/bin/bash
export RAWMASTER_SKIP_LICENSE=\"\${RAWMASTER_SKIP_LICENSE}\"
source ${SCRIPT_DIR}/.venv/bin/activate
exec python3 ${SCRIPT_DIR}/rawmaster.py \"\$@\"" | sudo tee /usr/local/bin/rawmaster > /dev/null
sudo chmod +x /usr/local/bin/rawmaster

echo ""
echo "Done! RAWMASTER installed."
echo ""
echo "   CLI:  rawmaster track.mp3 --stems --midi"
echo "   UI:   rawmaster-ui  (opens at http://localhost:7860)"
echo ""
echo "   First run downloads AI models (~110MB). One time only."
echo ""
