# RAWMASTER — Setup Guide (Mac, Windows + Linux)

## What you're getting

Stem separation, reference mastering, MIDI extraction, BPM/key detection — all running locally on your machine. No cloud, no account, no limits.

---

## Quick Start (5 minutes)

### Step 1: Install Python

**Mac:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or 3.12 (NOT 3.14 — some AI dependencies don't support it yet)
3. Run the `.pkg` installer
4. **SSL certificates (usually automatic):** RAWMASTER now points Python at a bundled certificate file, so the AI model download should work out of the box. If you ever hit a download/SSL error, open Finder → Applications → Python 3.x → double-click **"Install Certificates.command"** and try again.

**Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or 3.12 (NOT 3.14 — some deps don't support it yet on Windows)
3. Run installer — **CHECK "Add Python to PATH"** at the bottom of the first screen
4. Click "Install Now"

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv ffmpeg -y
```

**Linux (Fedora):**
```bash
sudo dnf install python3 python3-pip ffmpeg -y
```

---

### Step 2: Open a terminal

**Windows:** Press `Win + R`, type `cmd`, press Enter
**Linux:** Open your terminal app

---

### Step 3: Navigate to the RAWMASTER folder

Unzip this package somewhere, then:

**Mac / Linux:**
```bash
cd ~/Downloads/rawmaster
```

**Windows:**
```
cd C:\Users\YourName\Downloads\rawmaster
```

---

### Step 4: Create a virtual environment and install

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install basic-pitch --no-deps
pip install mir-eval pretty-midi resampy
```

**Windows:**
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install basic-pitch --no-deps
pip install mir-eval pretty-midi resampy
```

First run downloads AI models (~110MB). This happens once.

---

### Step 5: Set up for free use

**Mac / Linux:**
```bash
export RAWMASTER_SKIP_LICENSE=1
```

**Windows:**
```
set RAWMASTER_SKIP_LICENSE=1
```

To make this permanent:
- **Mac:** Add `export RAWMASTER_SKIP_LICENSE=1` to your `~/.zshrc`, then `source ~/.zshrc`
- **Linux:** Add `export RAWMASTER_SKIP_LICENSE=1` to your `~/.bashrc`, then `source ~/.bashrc`
- **Windows:** Search "Environment Variables" in Start, add `RAWMASTER_SKIP_LICENSE` with value `1` to User Variables

---

### Step 6: Run it

**Always activate the venv first:**

Mac / Linux: `source .venv/bin/activate`
Windows: `.venv\Scripts\activate`

Then:

```bash
# Remaster only
python rawmaster.py track.mp3

# Remaster + 4 stems
python rawmaster.py track.mp3 --stems

# Remaster + stems + MIDI from bass
python rawmaster.py track.mp3 --stems --midi

# Reference mastering (match your track to a pro mix)
python rawmaster.py track.mp3 --ref pro_mix.wav

# Reference mastering + stems + MIDI
python rawmaster.py track.mp3 --ref pro_mix.wav --stems --midi

# 6-stem mode (adds guitar + piano)
python rawmaster.py track.mp3 --stems 6

# Process a whole folder
python rawmaster.py ./my_tracks/ --stems

# BPM + key only (fast, no processing)
python rawmaster.py track.mp3 --info
```

---

### Step 7 (optional): Desktop UI

If you prefer drag-and-drop instead of the command line:

```bash
python app.py
```

Then open http://localhost:7860 in your browser. Drop your track, click the button.

---

## Output

Everything lands in a `rawmaster_output/` folder next to your input file:

```
rawmaster_output/
  trackname/
    trackname_RAWMASTER.wav    <- remastered 24-bit WAV
    info.txt                   <- BPM + key
    stems/
      vocals.wav
      drums.wav
      bass.wav
      other.wav
    midi/
      bass.mid
```

---

## What is reference mastering?

Use `--ref` with any professionally mastered track. RAWMASTER will match your track's EQ curve, loudness, and dynamics to the reference. Think of it as "make my track sound like this one."

Example: you have a rough mix and a Kendrick track you love the sound of:
```
python rawmaster.py my_rough_mix.wav --ref kendrick_reference.wav
```

Your mix comes out with matched frequency balance and loudness. It won't copy the music — just the sonic character.

---

## Supported formats

Input: MP3, WAV, FLAC, AIFF, OGG, M4A
Output: Always 24-bit WAV at 44.1kHz

---

## Troubleshooting

**Stem separation fails with a network / SSL error (Mac)**
This is the most common Mac issue. Python from python.org doesn't trust macOS system certificates by default, so the AI model download fails.

Fix: open Finder → Applications → Python 3.x → double-click **"Install Certificates.command"**. Then try again.

If that doesn't work, run this inside the venv:
```bash
pip install certifi
/Applications/Python\ 3.12/Install\ Certificates.command
```
(Replace 3.12 with whatever version you installed.)

**Stem separation fails with "Python 3.14" in the error**
You're running the app with the wrong Python — Python 3.14 is too new for some AI libraries. Make sure you've installed Python 3.11 or 3.12 from python.org and are running inside the venv:
```bash
source .venv/bin/activate
python app.py
```
The `(.venv)` prefix in your terminal prompt confirms the venv is active.

**"python is not recognized"**
Python isn't in your PATH. Reinstall and check "Add to PATH" (Windows) or use `python3` instead of `python` (Mac/Linux).

**"No module named X"**
You forgot to activate the venv. Run `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\activate` (Windows) first.

**Stems are slow**
Normal on CPU — expect 5-15 minutes per track. If you have an NVIDIA GPU, install PyTorch with CUDA for much faster processing:
```
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```
Mac users with Apple Silicon (M1/M2/M3/M4) already get hardware acceleration automatically via MPS — no extra steps needed.

**MIDI sounds wrong**
Basic-Pitch works best on clean bass lines. The bass stem is the most reliable source.

**"externally-managed-environment" error**
You need to use the virtual environment. Follow Step 4 above.

---

Enjoy. Go make noise.
