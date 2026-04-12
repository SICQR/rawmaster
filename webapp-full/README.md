---
title: RAWMASTER
emoji: 🎛️
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: "5.0"
app_file: app.py
pinned: false
---

# RAWMASTER — Full Web App

**Smash Daddys Audio Tools | Strip it back. Own the stems.**

Full-featured audio processing — no time limits, all modes.

---

## Features

| Tab | What it does |
|-----|-------------|
| 🔍 **Info** | BPM detection, key + mode, duration, sample rate |
| 🥁 **Stems** | AI stem separation (4-stem or 6-stem via Demucs htdemucs_ft / htdemucs_6s) + MIDI extraction |
| 🎛 **Master** | Full mastering chain: noise gate → LUFS normalisation → hard limiter → 24-bit WAV |
| 🔇 **Denoise** | Spectral gating noise reduction (adjustable strength) |

---

## Running locally

```bash
cd webapp-full
pip install -r requirements.txt
# basic-pitch needs special install to avoid TF/CoreML conflicts:
pip install basic-pitch --no-deps
pip install mir-eval pretty-midi resampy onnxruntime

python app.py
# → http://localhost:7860
```

## Deploy to HuggingFace Spaces

1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space)
2. Set SDK = **Gradio**
3. Push this directory (with `README.md` frontmatter) to the Space repo
4. Set the `RAWMASTER_SKIP_LICENSE=1` secret in Space settings (already set in app.py via `os.environ.setdefault`)

> **Note:** First run downloads the Demucs model (~110 MB). On Spaces this is cached between runs.

## Deploy to Railway

```bash
# railway.app — set env var PORT (Railway sets this automatically)
# The app binds to 0.0.0.0:$PORT on launch
railway up
```

---

## Supported formats

MP3, WAV, FLAC, AIFF, OGG, M4A

---

*Buy the full CLI at [scanme2.gumroad.com](https://scanme2.gumroad.com) — 19 GBP*
