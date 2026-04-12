#!/usr/bin/env python3
"""
RAWMASTER — Smash Daddys Audio Tools
Strip it back. Own the stems.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf
import noisereduce as nr
import pyloudnorm as pyln
import requests

__version__ = "1.0.0"

BANNER = r"""
██████╗  █████╗ ██╗    ██╗███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗
██╔══██╗██╔══██╗██║    ██║████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗
██████╔╝███████║██║ █╗ ██║██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝
██╔══██╗██╔══██║██║███╗██║██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗
██║  ██║██║  ██║╚███╔███╔╝██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
           Smash Daddys Audio Tools  |  Strip it back. Own the stems.
"""

SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".ogg", ".m4a"}

GUMROAD_PRODUCT_ID = "kxiip"  # RAWMASTER CLI product ID


# ─────────────────────────────────────────────
#  LICENSE
# ─────────────────────────────────────────────

def validate_license(key: str) -> bool:
    resp = requests.post(
        "https://api.gumroad.com/v2/licenses/verify",
        data={
            "product_id": GUMROAD_PRODUCT_ID,
            "license_key": key,
            "increment_uses_count": "false",
        },
        timeout=10,
    )
    data = resp.json()
    return data.get("success", False) and not data.get("purchase", {}).get("refunded", False)


def check_license():
    # CI / dev bypass — set RAWMASTER_SKIP_LICENSE=1 to skip entirely
    if os.environ.get("RAWMASTER_SKIP_LICENSE") == "1":
        return

    license_dir = Path(os.environ.get("RAWMASTER_LICENSE_DIR", str(Path.home() / ".rawmaster")))
    license_file = license_dir / "license"

    if license_file.exists():
        mtime = license_file.stat().st_mtime
        if (time.time() - mtime) < 30 * 86400:
            return  # valid, skip re-check

    print("\n🔑 Enter your RAWMASTER license key (from your Gumroad receipt):")
    key = input("  Key: ").strip()

    try:
        if validate_license(key):
            license_dir.mkdir(exist_ok=True)
            license_file.write_text(key)
            print("  ✅ License validated\n")
        else:
            print("  ❌ Invalid license key. Buy at scanme2.gumroad.com")
            sys.exit(1)
    except Exception:
        if license_file.exists():
            print("  ⚠️  Offline — using cached license\n")
        else:
            print("  ❌ Cannot validate license — check your internet connection")
            sys.exit(1)


# ─────────────────────────────────────────────
#  MODEL DOWNLOAD WARNING
# ─────────────────────────────────────────────

def warn_if_first_run():
    """Warn once if Demucs models haven't been downloaded yet."""
    checkpoint_dir = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    model_files = list(checkpoint_dir.glob("htdemucs*")) if checkpoint_dir.exists() else []
    if not model_files:
        print("  📥 Downloading AI models on first run (~110MB). This happens once only...")


# ─────────────────────────────────────────────
#  STEP 1 — REMASTER
# ─────────────────────────────────────────────

def remaster(audio_path: Path, output_dir: Path) -> Path:
    print(f"  🎛  Remastering {audio_path.name}…")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load & resample to 44100 Hz, float32
    audio, sr = librosa.load(str(audio_path), sr=44100, mono=False, dtype=np.float32)

    # Ensure 2D: (channels, samples)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)

    # Spectral gating (noisereduce) per channel
    denoised = np.stack([
        nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=0.6)
        for ch in audio
    ])

    # LUFS normalise to -14.0 (streaming standard)
    meter = pyln.Meter(sr)
    # pyloudnorm expects (samples, channels) — transpose
    audio_for_lufs = denoised.T
    loudness = meter.integrated_loudness(audio_for_lufs)
    target_lufs = -14.0
    if np.isfinite(loudness):
        gain = pyln.normalize.loudness(audio_for_lufs, loudness, target_lufs)
        normalised = gain.T  # back to (channels, samples)
    else:
        normalised = denoised

    # Hard limiter at -0.3 dBFS
    peak = 10 ** (-0.3 / 20)
    limited = np.clip(normalised, -peak, peak)

    # Write 24-bit WAV (soundfile expects (samples, channels))
    out_name = audio_path.stem + "_RAWMASTER.wav"
    out_path = output_dir / out_name
    sf.write(str(out_path), limited.T, sr, subtype="PCM_24")
    print(f"  ✅ Remaster saved → {out_path.name}")
    return out_path


# ─────────────────────────────────────────────
#  STEP 2 — STEM SEPARATION
# ─────────────────────────────────────────────

def separate_stems(audio_path: Path, output_dir: Path, six_stem: bool = False) -> dict:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    print("  🥁 Separating stems (htdemucs_ft)…")
    warn_if_first_run()

    model = "htdemucs_6s" if six_stem else "htdemucs_ft"
    stems_out = output_dir / "stems"
    stems_out.mkdir(exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--shifts", os.environ.get("RAWMASTER_TEST_SHIFTS", "2"),
        "--overlap", "0.25",
        "--float32",
        "--clip-mode", "rescale",
        "-o", str(output_dir / "_demucs_tmp"),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)

    # Demucs output: _demucs_tmp/{model}/{trackname}/{stem}.wav
    track_name = audio_path.stem
    demucs_track_dir = output_dir / "_demucs_tmp" / model / track_name

    stem_paths = {}
    for stem_file in demucs_track_dir.glob("*.wav"):
        dest = stems_out / stem_file.name
        shutil.move(str(stem_file), str(dest))
        stem_paths[stem_file.stem] = dest
        print(f"  ✅ Stem saved → stems/{stem_file.name}")

    # Clean up Demucs temp dir
    shutil.rmtree(str(output_dir / "_demucs_tmp"), ignore_errors=True)

    return stem_paths


# ─────────────────────────────────────────────
#  STEP 3 — MIDI EXTRACTION
# ─────────────────────────────────────────────

def extract_midi(stem_paths: dict, output_dir: Path, midi_all: bool = False):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    midi_out = output_dir / "midi"
    midi_out.mkdir(exist_ok=True)

    targets = ["bass"]
    if midi_all and "vocals" in stem_paths:
        targets.append("vocals")
    # Never extract from "other" — too noisy

    for stem_name in targets:
        if stem_name not in stem_paths:
            print(f"  ⚠️  Stem '{stem_name}' not found, skipping MIDI extraction")
            continue

        stem_path = stem_paths[stem_name]
        print(f"  🎹 Extracting MIDI from {stem_name}…")
        warn_if_first_run()

        from pathlib import Path as _BPPath
        _onnx = str(_BPPath(ICASSP_2022_MODEL_PATH).parent / 'nmp.onnx')
        model_output, midi_data, note_activations = predict(
            str(stem_path),
            _onnx,
        )
        out_mid = midi_out / (stem_path.stem + ".mid")
        midi_data.write(str(out_mid))
        print(f"  ✅ MIDI saved → midi/{out_mid.name}")


# ─────────────────────────────────────────────
#  STEP 4 — BPM + KEY
# ─────────────────────────────────────────────

def detect_info(audio_path: Path, output_dir: Path) -> dict:
    print("  🔍 Detecting BPM and key…")
    output_dir.mkdir(parents=True, exist_ok=True)
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

    # Key via chroma correlation
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    key = keys[int(chroma_mean.argmax())]

    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    idx = keys.index(key)
    maj_corr = np.corrcoef(np.roll(major_profile, -idx), chroma_mean)[0, 1]
    min_corr = np.corrcoef(np.roll(minor_profile, -idx), chroma_mean)[0, 1]
    mode = "major" if maj_corr > min_corr else "minor"

    info = {"bpm": round(bpm, 2), "key": key, "mode": mode}
    info_txt = output_dir / "info.txt"
    info_txt.write_text(
        f"BPM:  {info['bpm']}\n"
        f"Key:  {info['key']} {info['mode']}\n"
    )
    print(f"  ✅ BPM: {info['bpm']}  Key: {info['key']} {info['mode']}")
    return info


# ─────────────────────────────────────────────
#  PROCESS SINGLE FILE
# ─────────────────────────────────────────────

def process_file(
    audio_path: Path,
    do_stems: bool = False,
    do_midi: bool = False,
    do_midi_all: bool = False,
    do_info: bool = False,
    six_stem: bool = False,
):
    if not audio_path.exists():
        print(f"  ❌ File not found: {audio_path}")
        return

    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        print(f"  ⚠️  Skipping unsupported format: {audio_path.name}")
        return

    # Output dir at same level as input
    output_root = audio_path.parent / "rawmaster_output" / audio_path.stem
    output_root.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*60}")
    print(f"  📁 Output → {output_root}")

    if do_info and not do_stems and not do_midi and not do_midi_all:
        detect_info(audio_path, output_root)
        return

    # Always remaster (unless info-only)
    remaster(audio_path, output_root)

    # BPM + key always written alongside remaster
    detect_info(audio_path, output_root)

    stem_paths = {}
    if do_stems or do_midi or do_midi_all:
        stem_paths = separate_stems(audio_path, output_root, six_stem=six_stem)

    if do_midi or do_midi_all:
        extract_midi(stem_paths, output_root, midi_all=do_midi_all)

    print(f"\n  🎉 Done → {output_root}\n")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        prog="rawmaster",
        description="Smash Daddys Audio Tools — stem separation, remaster, MIDI, BPM/key",
    )
    parser.add_argument("input", nargs="?", help="Audio file or folder path")
    parser.add_argument("--stems", nargs="?", const=4, type=int,
                        metavar="N", help="Separate stems (4 or 6)")
    parser.add_argument("--midi", action="store_true",
                        help="Extract MIDI from bass stem")
    parser.add_argument("--midi-all", action="store_true",
                        help="Extract MIDI from bass + vocals stems")
    parser.add_argument("--info", action="store_true",
                        help="BPM + key detection only")
    parser.add_argument("--version", action="version", version=f"RAWMASTER {__version__}")

    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(0)

    # License check
    check_license()

    input_path = Path(args.input)
    six_stem = (args.stems == 6) if args.stems is not None else False
    do_stems = args.stems is not None
    do_midi = args.midi
    do_midi_all = args.midi_all
    do_info = args.info

    # Batch mode (folder)
    if input_path.is_dir():
        audio_files = [
            f for f in sorted(input_path.iterdir())
            if f.suffix.lower() in SUPPORTED_FORMATS
        ]
        if not audio_files:
            print(f"  ❌ No supported audio files found in {input_path}")
            sys.exit(1)
        print(f"  📂 Batch mode: {len(audio_files)} file(s) found in {input_path.name}/\n")
        for f in audio_files:
            process_file(f, do_stems, do_midi, do_midi_all, do_info, six_stem)
    else:
        process_file(input_path, do_stems, do_midi, do_midi_all, do_info, six_stem)


if __name__ == "__main__":
    main()
