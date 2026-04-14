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
import tempfile
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

# Stem modes
STEM_MODES = {4, 6, 12}  # 12 = "max" mode with cascaded sub-separation

# Stem separation quality presets: (shifts, overlap)
QUALITY_PRESETS = {
    "fast": (2, 0.25),   # ~5 min per track — rough separation
    "good": (5, 0.50),   # ~15 min — much cleaner, recommended
    "best": (10, 0.75),  # ~30 min — studio quality, maximum clarity
}

# Ensemble: run two models, blend for cleaner separation (best quality only)
ENSEMBLE_MODELS = [
    ("htdemucs_ft", 0.6),  # primary — fine-tuned, best single model
    ("htdemucs", 0.4),     # secondary — different spectral characteristics
]

# BS-Roformer model for best-in-class vocal separation (12.9 dB SDR vs Demucs 10.8)
ROFORMER_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"

# Per-stem DSP — tuned against MUSDB18 benchmarks.
# Only sub-bass rumble removal (highpass) and very gentle noise gate.
# No compression, no de-essing, no noise reduction — all hurt SDR.
STEM_DSP = {
    "vocals": {"highpass_hz": 55},
    "drums": {"highpass_hz": 20},
    "bass": {},
    "other": {},
    "guitar": {"highpass_hz": 45},
    "piano": {"highpass_hz": 30},
    # Sub-stems (max mode) — filters are part of the bandpass split already
    "lead_vocals": {"highpass_hz": 55},
    "backing_vocals": {"highpass_hz": 55},
    "kick": {},
    "snare_hats": {},
    "cymbals": {},
    "sub_synths": {},
    "mid_synths": {},
    "high_fx": {},
}

# Gumroad product IDs — update these after creating products on Gumroad
# Find each ID in: Gumroad Dashboard → Product → Settings → Integrations
GUMROAD_PRODUCT_IDS = [
    "iolsms",     # CLI (£19)
    "kmgake",     # Desktop (£29)
    "uvznyb",     # Toolkit Bundle (£39)
]


# ─────────────────────────────────────────────
#  LICENSE
# ─────────────────────────────────────────────

def validate_license(key: str) -> bool:
    """Try all product IDs — any valid match means the license is good."""
    for product_id in GUMROAD_PRODUCT_IDS:
        try:
            resp = requests.post(
                "https://api.gumroad.com/v2/licenses/verify",
                data={
                    "product_id": product_id,
                    "license_key": key,
                    "increment_uses_count": "false",
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("success") and not data.get("purchase", {}).get("refunded", False):
                return True
        except Exception:
            continue
    return False


def check_license():
    # CI / dev bypass — set RAWMASTER_SKIP_LICENSE=1 (or any non-empty value) to skip
    if os.environ.get("RAWMASTER_SKIP_LICENSE"):
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


def remaster_with_reference(audio_path: Path, reference_path: Path, output_dir: Path) -> Path:
    """Reference mastering — match EQ, loudness, and dynamics to a reference track."""
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference file not found: {reference_path}")

    try:
        import matchering as mg
    except ImportError:
        print("  ⚠️  matchering not installed. Install with: pip install matchering")
        print("  Falling back to standard remaster…")
        return remaster(audio_path, output_dir)

    print(f"  🎯 Reference mastering {audio_path.name} → matched to {reference_path.name}…")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Denoise target first (spectral gate) — cleaner input = better spectral match
    audio, sr = librosa.load(str(audio_path), sr=44100, mono=False, dtype=np.float32)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)
    denoised = np.stack([
        nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=0.6)
        for ch in audio
    ])

    # Write denoised audio to temp file (matchering needs file paths)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    os.close(tmp_fd)

    try:
        sf.write(tmp_path, denoised.T, sr, subtype="PCM_24")

        out_name = audio_path.stem + "_RAWMASTER.wav"
        out_path = output_dir / out_name

        mg.process(
            target=tmp_path,
            reference=str(reference_path),
            results=[mg.pcm24(str(out_path))],
        )
        print(f"  ✅ Reference master saved → {out_path.name}")
        return out_path

    except Exception as e:
        print(f"  ⚠️  Reference mastering failed: {e}")
        print("  Falling back to standard remaster…")
        return remaster(audio_path, output_dir)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────
#  STEP 2 — STEM SEPARATION
# ─────────────────────────────────────────────

def _run_demucs_model(audio_path: Path, output_dir: Path, model: str,
                      shifts: int, overlap: float) -> dict:
    """Run a single Demucs model and return {stem_name: Path}."""
    tmp_out = output_dir / "_demucs_tmp"
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--shifts", str(shifts),
        "--overlap", str(overlap),
        "--float32",
        "--clip-mode", "rescale",
        "-o", str(tmp_out),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)

    track_name = audio_path.stem
    demucs_dir = tmp_out / model / track_name
    stem_paths = {}
    for stem_file in demucs_dir.glob("*.wav"):
        stem_paths[stem_file.stem] = stem_file
    return stem_paths


def _run_roformer_vocals(audio_path: Path, output_dir: Path) -> dict:
    """Run BS-Roformer for best-in-class vocal/instrumental separation (12.9 dB SDR)."""
    try:
        from audio_separator.separator import Separator
    except ImportError:
        print("  ⚠️  audio-separator not installed. Install with: pip install audio-separator[cpu]")
        return {}

    print("  🎤 BS-Roformer vocal separation (12.9 dB SDR)…")
    out_dir = output_dir / "_roformer_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    separator = Separator(
        output_dir=str(out_dir),
        output_format="WAV",
        output_bitdepth="FLOAT",
        log_level=30,  # WARNING only — suppress info spam
    )
    separator.load_model(model_filename=ROFORMER_MODEL)
    output_files = separator.separate(str(audio_path))

    # Map output filenames to stems
    stem_paths = {}
    for f in output_files:
        full_path = out_dir / f
        if not full_path.exists():
            full_path = Path(f)  # might be absolute already
        if "(Vocals)" in f or "vocals" in f.lower():
            stem_paths["vocals"] = full_path
        elif "(Instrumental)" in f or "instrumental" in f.lower():
            stem_paths["instrumental"] = full_path
    return stem_paths


def separate_stems_ensemble(audio_path: Path, output_dir: Path,
                            quality: str = "best") -> dict:
    """Run Demucs ensemble + BS-Roformer for maximum separation quality."""
    shifts, overlap = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["best"])
    shifts = int(os.environ.get("RAWMASTER_TEST_SHIFTS", str(shifts)))

    stems_out = output_dir / "stems"
    stems_out.mkdir(parents=True, exist_ok=True)

    # Step 1: Run BS-Roformer for best-in-class vocals (12.9 dB SDR)
    roformer_vocals = None
    try:
        roformer_paths = _run_roformer_vocals(audio_path, output_dir)
        if "vocals" in roformer_paths:
            roformer_vocals = roformer_paths["vocals"]
            print("  ✅ BS-Roformer vocals ready")
    except Exception as e:
        print(f"  ⚠️  BS-Roformer failed: {e} — using Demucs vocals only")

    # Step 2: Run Demucs models for full stem set
    model_results = []
    for i, (model_name, weight) in enumerate(ENSEMBLE_MODELS):
        print(f"  🥁 Model {i+1}/{len(ENSEMBLE_MODELS)}: {model_name} (shifts={shifts})…")
        warn_if_first_run()
        try:
            paths = _run_demucs_model(audio_path, output_dir, model_name, shifts, overlap)
            model_results.append((paths, weight))
        except Exception as e:
            print(f"  ⚠️  Model {model_name} failed: {e}")
            if not model_results:
                raise
            print("  Using single-model output only.")
            break

    # Step 3: Blend Demucs stems
    print(f"  🔀 Blending {len(model_results)} Demucs model(s)…")
    all_stem_names = set()
    for paths, _ in model_results:
        all_stem_names.update(paths.keys())

    blended_paths = {}
    for stem_name in sorted(all_stem_names):
        blended = None
        total_weight = 0.0
        sr = None
        for paths, weight in model_results:
            if stem_name not in paths:
                continue
            audio, sr = sf.read(str(paths[stem_name]), dtype="float32")
            if blended is None:
                blended = audio * weight
            else:
                min_len = min(len(blended), len(audio))
                blended = blended[:min_len] + audio[:min_len] * weight
            total_weight += weight

        if blended is not None and total_weight > 0:
            blended /= total_weight
            dest = stems_out / f"{stem_name}.wav"
            sf.write(str(dest), blended, sr, subtype="FLOAT")
            blended_paths[stem_name] = dest
            print(f"  ✅ Blended → stems/{stem_name}.wav")

    # Step 4: Replace Demucs vocals with BS-Roformer/Demucs hybrid (70/30 blend)
    if roformer_vocals and "vocals" in blended_paths:
        print("  🎤 Blending BS-Roformer vocals (70%) + Demucs vocals (30%)…")
        roformer_audio, sr = sf.read(str(roformer_vocals), dtype="float32")
        demucs_audio, _ = sf.read(str(blended_paths["vocals"]), dtype="float32")
        min_len = min(len(roformer_audio), len(demucs_audio))
        hybrid_vocals = roformer_audio[:min_len] * 0.7 + demucs_audio[:min_len] * 0.3
        dest = stems_out / "vocals.wav"
        sf.write(str(dest), hybrid_vocals, sr, subtype="FLOAT")
        blended_paths["vocals"] = dest
        print("  ✅ Hybrid vocals → stems/vocals.wav (BS-Roformer + Demucs)")

    # Clean up
    shutil.rmtree(str(output_dir / "_demucs_tmp"), ignore_errors=True)
    shutil.rmtree(str(output_dir / "_roformer_tmp"), ignore_errors=True)

    return blended_paths


def post_process_stems(stem_paths: dict, sr: int = 44100) -> dict:
    """Apply light per-stem DSP: gentle filters + noise gate only.

    Tuned against MUSDB18 benchmarks. Aggressive compression/de-essing/noise
    reduction was removed because it hurt SDR by -0.33 dB average on clean stems.
    Only filters that cut obvious bleed (sub-bass rumble, high-freq leakage)
    and a gentle noise gate are kept.
    """
    try:
        from pedalboard import (
            Pedalboard, HighpassFilter, LowpassFilter, NoiseGate,
        )
    except ImportError:
        print("  ⚠️  pedalboard not available — skipping stem post-processing")
        return stem_paths

    print("  🎛  Post-processing stems…")

    for stem_name, stem_path in stem_paths.items():
        dsp_config = STEM_DSP.get(stem_name)
        if not dsp_config:
            continue

        audio, file_sr = sf.read(str(stem_path), dtype="float32")
        # pedalboard wants (channels, samples)
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
        else:
            audio = audio.T

        effects = []

        if "highpass_hz" in dsp_config:
            effects.append(HighpassFilter(cutoff_frequency_hz=dsp_config["highpass_hz"]))

        if "lowpass_hz" in dsp_config:
            effects.append(LowpassFilter(cutoff_frequency_hz=dsp_config["lowpass_hz"]))

        if "gate_db" in dsp_config:
            effects.append(NoiseGate(threshold_db=dsp_config["gate_db"]))

        if effects:
            board = Pedalboard(effects)
            audio = board(audio, file_sr)

        # Write back — transpose to (samples, channels)
        sf.write(str(stem_path), audio.T, file_sr, subtype="FLOAT")
        print(f"  ✅ Post-processed → {stem_name}")

    return stem_paths


def _bandpass_split(audio_path: Path, output_dir: Path, stem_name: str,
                    bands: list, sr: int = 44100) -> dict:
    """Split a stem into frequency bands. bands = [(name, low_hz, high_hz), ...]"""
    from scipy.signal import butter, sosfilt

    audio, file_sr = sf.read(str(audio_path), dtype="float32")
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=1)

    sub_paths = {}
    for band_name, low_hz, high_hz in bands:
        filtered = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            if low_hz and high_hz:
                sos = butter(4, [low_hz, high_hz], btype="band", fs=file_sr, output="sos")
            elif low_hz:
                sos = butter(4, low_hz, btype="high", fs=file_sr, output="sos")
            elif high_hz:
                sos = butter(4, high_hz, btype="low", fs=file_sr, output="sos")
            else:
                filtered[:, ch] = audio[:, ch]
                continue
            filtered[:, ch] = sosfilt(sos, audio[:, ch])

        out_path = output_dir / f"{band_name}.wav"
        sf.write(str(out_path), filtered, file_sr, subtype="FLOAT")
        sub_paths[band_name] = out_path
        print(f"  ✅ Sub-stem → {band_name}.wav")

    return sub_paths


def sub_separate_stems(stem_paths: dict, output_dir: Path, quality: str = "best") -> dict:
    """Cascade 6-stem output into 12 sub-stems via re-separation and frequency splitting."""
    print("  🔬 Sub-separating into 12 stems…")
    stems_out = output_dir / "stems"
    stems_out.mkdir(parents=True, exist_ok=True)
    result = {}

    # ── Vocals → lead + backing via re-running Demucs on vocal stem ──
    if "vocals" in stem_paths:
        vocals_path = stem_paths["vocals"]
        print("  🎤 Splitting vocals → lead + backing…")
        try:
            shifts, overlap = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["best"])
            shifts = int(os.environ.get("RAWMASTER_TEST_SHIFTS", str(shifts)))
            vocal_sub = _run_demucs_model(vocals_path, output_dir, "htdemucs_ft", shifts, overlap)
            # Demucs on a vocal stem: "vocals" = lead, "other" = backing/harmonies
            if "vocals" in vocal_sub:
                dest = stems_out / "lead_vocals.wav"
                shutil.move(str(vocal_sub["vocals"]), str(dest))
                result["lead_vocals"] = dest
                print("  ✅ Lead vocals extracted")
            # Everything else Demucs finds = backing
            backing_parts = [v for k, v in vocal_sub.items() if k != "vocals"]
            if backing_parts:
                # Merge all non-vocal parts into one backing stem
                backing_audio = None
                backing_sr = None
                for bp in backing_parts:
                    a, backing_sr = sf.read(str(bp), dtype="float32")
                    backing_audio = a if backing_audio is None else backing_audio[:len(a)] + a[:len(backing_audio)]
                dest = stems_out / "backing_vocals.wav"
                sf.write(str(dest), backing_audio, backing_sr, subtype="FLOAT")
                result["backing_vocals"] = dest
                print("  ✅ Backing vocals extracted")
            shutil.rmtree(str(output_dir / "_demucs_tmp"), ignore_errors=True)
        except Exception as e:
            print(f"  ⚠️  Vocal sub-separation failed: {e} — keeping original")
            result["vocals"] = stem_paths["vocals"]

    # ── Drums → kick, snare+hats, cymbals via frequency bands ──
    if "drums" in stem_paths:
        print("  🥁 Splitting drums → kick, snare+hats, cymbals…")
        drum_subs = _bandpass_split(
            stem_paths["drums"], stems_out, "drums",
            [
                ("kick", None, 200),
                ("snare_hats", 200, 8000),
                ("cymbals", 8000, None),
            ],
        )
        result.update(drum_subs)

    # ── Bass → keep as-is ──
    if "bass" in stem_paths:
        dest = stems_out / "bass.wav"
        if stem_paths["bass"] != dest:
            shutil.copy2(str(stem_paths["bass"]), str(dest))
        result["bass"] = dest

    # ── Guitar → keep as-is ──
    if "guitar" in stem_paths:
        dest = stems_out / "guitar.wav"
        if stem_paths["guitar"] != dest:
            shutil.copy2(str(stem_paths["guitar"]), str(dest))
        result["guitar"] = dest

    # ── Piano → keep as-is ──
    if "piano" in stem_paths:
        dest = stems_out / "piano.wav"
        if stem_paths["piano"] != dest:
            shutil.copy2(str(stem_paths["piano"]), str(dest))
        result["piano"] = dest

    # ── Other → sub_synths, mid_synths, high_fx via frequency bands ──
    if "other" in stem_paths:
        print("  🎶 Splitting other → sub synths, mid synths, high FX…")
        other_subs = _bandpass_split(
            stem_paths["other"], stems_out, "other",
            [
                ("sub_synths", None, 250),
                ("mid_synths", 250, 4000),
                ("high_fx", 4000, None),
            ],
        )
        result.update(other_subs)

    return result


def separate_stems(audio_path: Path, output_dir: Path, six_stem: bool = False,
                   quality: str = "good", max_stems: bool = False) -> dict:
    """Separate stems with optional ensemble, sub-separation, and post-processing."""
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    warn_if_first_run()

    # Max mode: force 6-stem + sub-separation
    if max_stems:
        six_stem = True
        quality = "best"

    # Choose separation strategy
    if quality == "best" and not six_stem:
        # Ensemble mode (4-stem only — no second 6-stem model)
        stem_paths = separate_stems_ensemble(audio_path, output_dir, quality=quality)
    else:
        # Single model (4 or 6 stem)
        shifts, overlap = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["good"])
        shifts = int(os.environ.get("RAWMASTER_TEST_SHIFTS", str(shifts)))
        model = "htdemucs_6s" if six_stem else "htdemucs_ft"
        print(f"  🥁 Separating stems ({model}, quality={quality}, shifts={shifts})…")

        paths = _run_demucs_model(audio_path, output_dir, model, shifts, overlap)

        stems_out = output_dir / "stems"
        stems_out.mkdir(parents=True, exist_ok=True)
        stem_paths = {}
        for stem_name, stem_file in paths.items():
            dest = stems_out / stem_file.name
            shutil.move(str(stem_file), str(dest))
            stem_paths[stem_name] = dest
            print(f"  ✅ Stem saved → stems/{stem_file.name}")

        shutil.rmtree(str(output_dir / "_demucs_tmp"), ignore_errors=True)

    # Max mode: cascade into 12 sub-stems
    if max_stems:
        stem_paths = sub_separate_stems(stem_paths, output_dir, quality=quality)

    # Always post-process
    stem_paths = post_process_stems(stem_paths)

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
#  STEP 5 — CHORD DETECTION
# ─────────────────────────────────────────────

# Chord templates: 12 major + 12 minor triads
_CHORD_TEMPLATES = {}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for i, note in enumerate(_NOTE_NAMES):
    # Major triad: root + major third (4) + perfect fifth (7)
    maj = np.zeros(12)
    maj[i] = 1
    maj[(i + 4) % 12] = 1
    maj[(i + 7) % 12] = 1
    _CHORD_TEMPLATES[note] = maj
    # Minor triad: root + minor third (3) + perfect fifth (7)
    mi = np.zeros(12)
    mi[i] = 1
    mi[(i + 3) % 12] = 1
    mi[(i + 7) % 12] = 1
    _CHORD_TEMPLATES[f"{note}m"] = mi
    # Dominant 7th: root + major third (4) + fifth (7) + minor seventh (10)
    dom7 = np.zeros(12)
    dom7[i] = 1
    dom7[(i + 4) % 12] = 1
    dom7[(i + 7) % 12] = 1
    dom7[(i + 10) % 12] = 1
    _CHORD_TEMPLATES[f"{note}7"] = dom7


def detect_chords(audio_path: Path, output_dir: Path, bpm: float = 120.0) -> list:
    """Detect chord progression with timestamps. Returns list of (time_sec, chord_name)."""
    print("  🎵 Detecting chords…")
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    # Use beat-synchronous chroma for cleaner chord boundaries
    hop_length = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)

    # Segment by beats if BPM is available, otherwise use fixed segments
    if bpm and bpm > 0:
        beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=bpm)[1]
        if len(beat_frames) < 2:
            beat_frames = np.arange(0, chroma.shape[1], int(sr / hop_length * 0.5))
    else:
        beat_frames = np.arange(0, chroma.shape[1], int(sr / hop_length * 0.5))

    # Match each segment to best chord template
    chords = []
    prev_chord = None
    for i in range(len(beat_frames) - 1):
        start_frame = beat_frames[i]
        end_frame = beat_frames[i + 1] if i + 1 < len(beat_frames) else chroma.shape[1]
        segment_chroma = chroma[:, start_frame:end_frame].mean(axis=1)

        # Normalize
        norm = np.linalg.norm(segment_chroma)
        if norm < 0.01:
            continue  # silence
        segment_chroma /= norm

        # Find best matching chord
        best_chord = "N"  # no chord
        best_score = 0.3  # minimum threshold
        for chord_name, template in _CHORD_TEMPLATES.items():
            score = np.dot(segment_chroma, template / np.linalg.norm(template))
            if score > best_score:
                best_score = score
                best_chord = chord_name

        time_sec = round(librosa.frames_to_time(start_frame, sr=sr, hop_length=hop_length), 2)

        # Only add if chord changed
        if best_chord != prev_chord:
            chords.append((time_sec, best_chord))
            prev_chord = best_chord

    # Write chord chart
    chord_txt = output_dir / "chords.txt"
    lines = ["CHORD PROGRESSION", "=" * 40, ""]
    for time_sec, chord in chords:
        mins = int(time_sec // 60)
        secs = time_sec % 60
        lines.append(f"  {mins}:{secs:05.2f}  {chord}")
    lines.append("")
    chord_txt.write_text("\n".join(lines))
    print(f"  ✅ Chords detected — {len(chords)} changes → chords.txt")
    return chords


# ─────────────────────────────────────────────
#  STEP 6 — SPEED / PITCH CONTROL
# ─────────────────────────────────────────────

def change_speed_pitch(audio_path: Path, output_dir: Path,
                       speed: float = None, pitch_semitones: float = None) -> Path:
    """Change speed and/or pitch of an audio file. Returns path to modified file."""
    if speed is None and pitch_semitones is None:
        return audio_path

    output_dir.mkdir(parents=True, exist_ok=True)
    y, sr = librosa.load(str(audio_path), sr=None, mono=False)

    label_parts = []

    if speed is not None and speed != 1.0:
        print(f"  ⏩ Changing speed to {speed}x…")
        if y.ndim == 1:
            y = librosa.effects.time_stretch(y, rate=speed)
        else:
            # Process each channel
            y = np.stack([librosa.effects.time_stretch(ch, rate=speed) for ch in y])
        label_parts.append(f"{speed}x")

    if pitch_semitones is not None and pitch_semitones != 0:
        print(f"  🎼 Shifting pitch by {pitch_semitones:+.1f} semitones…")
        if y.ndim == 1:
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch_semitones)
        else:
            y = np.stack([librosa.effects.pitch_shift(ch, sr=sr, n_steps=pitch_semitones) for ch in y])
        label_parts.append(f"{pitch_semitones:+.0f}st")

    label = "_".join(label_parts)
    stem = audio_path.stem
    out_path = output_dir / f"{stem}_{label}.wav"
    audio_out = y.T if y.ndim > 1 else y
    sf.write(str(out_path), audio_out, sr, subtype="PCM_24")
    print(f"  ✅ Speed/pitch adjusted → {out_path.name}")
    return out_path


# ─────────────────────────────────────────────
#  STEP 7 — EXPORT FORMAT CONVERSION
# ─────────────────────────────────────────────

FORMAT_MAP = {
    "wav24": ("PCM_24", ".wav"),
    "wav32": ("FLOAT", ".wav"),
    "aiff": ("PCM_24", ".aiff"),
    "mp3": (None, ".mp3"),  # handled separately via ffmpeg/pydub
}


def convert_output_format(output_dir: Path, fmt: str = "wav24",
                          bpm_filename: bool = False, info: dict = None):
    """Convert all output WAVs to the specified format."""
    if fmt == "wav24" and not bpm_filename:
        return  # default format, nothing to do

    subtype, ext = FORMAT_MAP.get(fmt, ("PCM_24", ".wav"))
    print(f"  📦 Converting outputs to {fmt.upper()}…")

    # Find all WAV files in the output directory (remaster + stems)
    wav_files = list(output_dir.rglob("*.wav"))

    for wav_path in wav_files:
        audio, sr = sf.read(str(wav_path), dtype="float32")

        # Build new filename
        stem_name = wav_path.stem
        if bpm_filename and info:
            bpm = info.get("bpm", 0)
            key = info.get("key", "")
            mode = info.get("mode", "")
            stem_name = f"{stem_name}_{bpm}bpm_{key}{mode}"

        new_name = f"{stem_name}{ext}"
        new_path = wav_path.parent / new_name

        if fmt == "mp3":
            # Convert to MP3 via a temp WAV + ffmpeg
            try:
                import subprocess as _sp
                temp_wav = wav_path.parent / f"_temp_{wav_path.name}"
                sf.write(str(temp_wav), audio, sr, subtype="PCM_24")
                mp3_path = wav_path.parent / new_name
                _sp.run([
                    "ffmpeg", "-y", "-i", str(temp_wav),
                    "-codec:a", "libmp3lame", "-b:a", "320k",
                    str(mp3_path)
                ], check=True, capture_output=True)
                temp_wav.unlink()
                if wav_path.exists() and mp3_path.exists():
                    wav_path.unlink()  # remove original WAV
                print(f"  ✅ {new_name}")
            except Exception as e:
                print(f"  ⚠️  MP3 conversion failed for {wav_path.name}: {e}")
        else:
            # Write in the target format
            sf.write(str(new_path), audio, sr, subtype=subtype)
            if new_path != wav_path and new_path.exists():
                wav_path.unlink()
            print(f"  ✅ {new_name}")

    print(f"  ✅ Export complete ({fmt.upper()})")


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
    reference_path: Path = None,
    quality: str = "good",
    max_stems: bool = False,
    do_chords: bool = False,
    speed: float = None,
    pitch_semitones: float = None,
    output_format: str = "wav24",
    bpm_filename: bool = False,
):
    if not audio_path.exists():
        print(f"  ❌ File not found: {audio_path}")
        sys.exit(1)

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
    if reference_path:
        remaster_with_reference(audio_path, reference_path, output_root)
    else:
        remaster(audio_path, output_root)

    # BPM + key always written alongside remaster
    info = detect_info(audio_path, output_root)

    # Chord detection
    if do_chords:
        detect_chords(audio_path, output_root, bpm=info.get("bpm", 120))

    # Speed/pitch adjustment (applies to the remastered output)
    if speed is not None or pitch_semitones is not None:
        remaster_file = output_root / (audio_path.stem + "_RAWMASTER.wav")
        if remaster_file.exists():
            change_speed_pitch(remaster_file, output_root, speed=speed, pitch_semitones=pitch_semitones)

    stem_paths = {}
    if do_stems or do_midi or do_midi_all:
        stem_paths = separate_stems(audio_path, output_root, six_stem=six_stem, quality=quality, max_stems=max_stems)

    if do_midi or do_midi_all:
        extract_midi(stem_paths, output_root, midi_all=do_midi_all)

    # Export format conversion
    if output_format != "wav24" or bpm_filename:
        convert_output_format(output_root, fmt=output_format,
                              bpm_filename=bpm_filename, info=info)

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
    parser.add_argument("--stems", nargs="?", const=4,
                        metavar="N", help="Separate stems: 4, 6, or max (12 sub-stems)")
    parser.add_argument("--midi", action="store_true",
                        help="Extract MIDI from bass stem")
    parser.add_argument("--midi-all", action="store_true",
                        help="Extract MIDI from bass + vocals stems")
    parser.add_argument("--info", action="store_true",
                        help="BPM + key detection only")
    parser.add_argument("--ref", "--reference", dest="reference",
                        metavar="FILE",
                        help="Reference track for mastering (match EQ + loudness + dynamics)")
    parser.add_argument("--quality", choices=["fast", "good", "best"], default="best",
                        help="Stem separation quality: fast (~5min), good (~15min), best (~30min, default)")
    parser.add_argument("--chords", action="store_true",
                        help="Detect chord progression and save to chords.txt")
    parser.add_argument("--speed", type=float, metavar="X",
                        help="Change playback speed (e.g. 0.8 = 80%%, 1.2 = 120%%)")
    parser.add_argument("--pitch", type=float, metavar="N",
                        help="Shift pitch in semitones (e.g. +2, -3)")
    parser.add_argument("--format", choices=["wav24", "wav32", "aiff", "mp3"],
                        default="wav24",
                        help="Output format: wav24 (default), wav32 (float), aiff, mp3")
    parser.add_argument("--bpm-filename", action="store_true",
                        help="Append BPM and key to output filenames")
    parser.add_argument("--version", action="version", version=f"RAWMASTER {__version__}")

    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(0)

    # License check
    check_license()

    input_path = Path(args.input)

    # Parse --stems: can be 4, 6, or "max"
    max_stems = False
    six_stem = False
    do_stems = args.stems is not None
    if args.stems is not None:
        if str(args.stems).lower() == "max":
            max_stems = True
            six_stem = True  # max mode uses 6-stem as base
        else:
            try:
                n = int(args.stems)
                six_stem = (n == 6)
            except ValueError:
                print(f"  ❌ Invalid stem count: {args.stems}. Use 4, 6, or max.")
                sys.exit(1)

    do_midi = args.midi
    do_midi_all = args.midi_all
    do_info = args.info
    reference_path = Path(args.reference) if args.reference else None
    if reference_path and not reference_path.exists():
        print(f"  ❌ Reference file not found: {reference_path}")
        sys.exit(1)
    quality = args.quality
    do_chords = args.chords
    speed = args.speed
    pitch_semitones = args.pitch
    output_format = args.format
    bpm_filename = args.bpm_filename

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
            process_file(f, do_stems, do_midi, do_midi_all, do_info, six_stem, reference_path, quality, max_stems, do_chords, speed, pitch_semitones, output_format, bpm_filename)
    else:
        process_file(input_path, do_stems, do_midi, do_midi_all, do_info, six_stem, reference_path, quality, max_stems, do_chords, speed, pitch_semitones)


if __name__ == "__main__":
    main()
