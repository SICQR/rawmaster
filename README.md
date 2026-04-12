# RAWMASTER
**Smash Daddys Audio Tools | Strip it back. Own the stems.**

Stem separation, remaster, MIDI extraction, and BPM/key detection � all local, no cloud, no API calls.

```
???????  ?????? ???    ???????   ???? ?????? ????????????????????????????????
???????????????????    ???????? ??????????????????????????????????????????????
??????????????????? ?? ??????????????????????????????   ???   ??????  ????????
?????????????????????????????????????????????????????   ???   ??????  ????????
???  ??????  ???????????????? ??? ??????  ???????????   ???   ???????????  ???
???  ??????  ??? ???????? ???     ??????  ???????????   ???   ???????????  ???
```

---

## Install
bash install.sh

## Python 3.14 / macOS note
If you see "externally-managed-environment" — the install script handles this automatically via venv. Do not use --break-system-packages.

## Developer mode
Add RAWMASTER_SKIP_LICENSE=1 to your shell env to skip license checks:
echo 'export RAWMASTER_SKIP_LICENSE=1' >> ~/.zshrc && source ~/.zshrc

---

> **macOS / Python 3.14 install**
> If you get an `externally-managed-environment` error, run:
> ```bash
> bash install.sh   # handles venv + basic-pitch workaround automatically
> ```
> If you built this yourself, add `RAWMASTER_SKIP_LICENSE=1` to your shell env
> (or just run `bash install.sh` -- it detects the git repo and does this for you).


## What it does

| Output | Details |
|--------|---------|
| `{track}_RAWMASTER.wav` | Spectral gating + LUFS normalisation + hard limiter, 24-bit WAV |
| `stems/vocals.wav` | HTDemucs fine-tuned model |
| `stems/drums.wav` | HTDemucs fine-tuned model |
| `stems/bass.wav` | HTDemucs fine-tuned model |
| `stems/other.wav` | HTDemucs fine-tuned model |
| `midi/bass.mid` | Basic-Pitch neural MIDI transcription |
| `info.txt` | BPM and musical key |

Everything runs on your machine. No subscription. No internet required after first run.

---

## Requirements

- Python 3.9+
- macOS, Linux, or Windows
- ~1GB disk for AI models (downloaded once)
- GPU optional � CPU works fine (stems take longer)

---

## Install

### macOS / Linux

```bash
git clone https://github.com/SICQR/rawmaster.git
cd rawmaster
bash install.sh
```

Restart your terminal, then:

```bash
rawmaster track.mp3 --stems --midi
```

### Windows

```batch
git clone https://github.com/SICQR/rawmaster.git
cd rawmaster
install.bat
```

Then run:

```batch
python rawmaster.py track.mp3 --stems --midi
```

---

## Developer mode

If you cloned this repo yourself, `install.sh` detects the `.git` directory and writes the launcher with `RAWMASTER_SKIP_LICENSE=1` baked in — no Gumroad key needed.

To bypass the license check without re-running the installer, set the env var before running:

```bash
export RAWMASTER_SKIP_LICENSE=1
rawmaster track.mp3 --stems
```

Any non-empty value works — `1`, `true`, `yes`, etc. The launcher at `/usr/local/bin/rawmaster` inherits the variable from your shell automatically.

---

## Usage

```bash
rawmaster track.mp3                    # remaster only
rawmaster track.mp3 --stems           # remaster + 4 stems
rawmaster track.mp3 --stems --midi    # stems + MIDI (bass only)
rawmaster track.mp3 --stems --midi-all # stems + MIDI (bass + vocals)
rawmaster track.mp3 --stems 6         # 6-stem mode (adds guitar + piano)
rawmaster ./folder/ --stems           # batch mode
rawmaster track.mp3 --info            # BPM + key only
rawmaster --version
```

Supported formats: MP3, WAV, FLAC, AIFF, OGG, M4A

---

## Output structure

```
rawmaster_output/
??? {trackname}/
    ??? {trackname}_RAWMASTER.wav
    ??? info.txt
    ??? stems/
    ?   ??? vocals.wav
    ?   ??? drums.wav
    ?   ??? bass.wav
    ?   ??? other.wav
    ??? midi/
        ??? bass.mid
```

Output folder created at the same level as the input file.

---

## Remaster pipeline

1. Load audio, resample to 44100 Hz, convert to float32
2. Spectral gating via `noisereduce` � kills shimmer and hiss without destroying transients (`prop_decrease=0.6`)
3. LUFS normalisation to -14.0 (streaming standard) via `pyloudnorm`
4. Hard limiter at -0.3 dBFS
5. Write 24-bit WAV

---

## Models

| Task | Model |
|------|-------|
| Stem separation | HTDemucs fine-tuned (`htdemucs_ft`) |
| MIDI extraction | Basic-Pitch (Spotify/GitHub) |
| Noise reduction | noisereduce (spectral gating) |

Downloaded automatically on first use (~110MB total).

---

## License

One-time purchase. **[scanme2.gumroad.com](https://scanme2.gumroad.com)** � �19

You'll receive a license key in your Gumroad receipt. Enter it on first run. Re-validated every 30 days (cached offline).

---

## Troubleshooting

**Stems are slow** � CPU mode is normal. Expect 5�15 min per track. GPU speeds this up significantly.

**MIDI sounds wrong** � Basic-Pitch works best on clean isolated bass or melodic lines. Bass stem is the most reliable.

**`rawmaster: command not found`** � Run `source ~/.zshrc` after install, or restart your terminal.

**License validation fails offline** � If you've validated before, cached license works for 30 days.

---

*Smash Daddys Audio Tools*
