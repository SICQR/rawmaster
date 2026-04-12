#!/usr/bin/env python3
"""
RAWMASTER Full — Gradio Web App
Smash Daddys Audio Tools | Strip it back. Own the stems.

Full-featured: no time limits, all processing modes.
Deployable to HuggingFace Spaces or Railway.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import gradio as gr
import librosa
import numpy as np
import noisereduce as nr
import pyloudnorm as pyln
import soundfile as sf

# ── Skip license in web context (set via environment or inline) ─────────────
os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")

# ─────────────────────────────────────────────
#  THEME / CSS
# ─────────────────────────────────────────────

GOLD = "#C8962C"
DARK_BG = "#080808"
PANEL_BG = "#111111"
BORDER = "#2a2a2a"
TEXT = "#f0ece4"
MUTED = "#8a8480"

css = f"""
/* ── Global reset ── */
body, .gradio-container {{
    background: {DARK_BG} !important;
    color: {TEXT} !important;
    font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
}}

/* ── RAWMASTER header ── */
.rawmaster-header {{
    text-align: center;
    padding: 2rem 0 1rem;
    border-bottom: 1px solid {GOLD};
    margin-bottom: 1.5rem;
}}
.rawmaster-logo {{
    font-size: 2rem;
    font-weight: 900;
    letter-spacing: 0.15em;
    color: {GOLD} !important;
    font-family: monospace;
}}
.rawmaster-sub {{
    color: {MUTED} !important;
    font-size: 0.85rem;
    letter-spacing: 0.08em;
    margin-top: 0.25rem;
}}

/* ── Panels ── */
.gr-box, .gr-panel, .block, .svelte-1ed2p3z {{
    background: {PANEL_BG} !important;
    border-color: {BORDER} !important;
}}

/* ── Labels & text ── */
h1, h2, h3, h4 {{
    color: {TEXT} !important;
    font-family: monospace !important;
    letter-spacing: 0.06em;
}}
label, .gr-block-label, p, span {{
    color: {MUTED} !important;
    font-family: monospace !important;
}}

/* ── Primary button (gold) ── */
.gr-button-primary, button[variant="primary"], .primary {{
    background: {GOLD} !important;
    border: none !important;
    color: #000 !important;
    font-weight: 900 !important;
    letter-spacing: 0.08em !important;
    font-family: monospace !important;
}}
.gr-button-primary:hover, button[variant="primary"]:hover {{
    background: #e0aa30 !important;
    transform: translateY(-1px);
}}

/* ── Secondary buttons ── */
.gr-button-secondary, button[variant="secondary"] {{
    background: transparent !important;
    border: 1px solid {GOLD} !important;
    color: {GOLD} !important;
    font-family: monospace !important;
}}

/* ── Tabs ── */
.tab-nav button {{
    background: transparent !important;
    color: {MUTED} !important;
    border: none !important;
    font-family: monospace !important;
    font-size: 0.9rem;
    letter-spacing: 0.05em;
}}
.tab-nav button.selected {{
    color: {GOLD} !important;
    border-bottom: 2px solid {GOLD} !important;
}}

/* ── Info card ── */
.info-card {{
    background: #161616 !important;
    border: 1px solid {BORDER};
    border-left: 3px solid {GOLD};
    padding: 1rem 1.25rem;
    border-radius: 4px;
    font-family: monospace;
    font-size: 1.05rem;
    line-height: 1.8;
}}

/* ── Stem cards ── */
.stem-row {{
    border-top: 1px solid {BORDER};
    padding: 0.5rem 0;
}}

/* ── Status box ── */
.status-box textarea {{
    background: #060606 !important;
    color: #7ec87e !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.8rem;
    border-color: {BORDER} !important;
}}

/* ── Audio player ── */
.audio-player {{
    background: #161616 !important;
    border: 1px solid {BORDER} !important;
}}

footer {{ display: none !important; }}
"""


# ─────────────────────────────────────────────
#  CORE PROCESSING FUNCTIONS
#  (adapted from rawmaster.py — no license, no CLI)
# ─────────────────────────────────────────────

def detect_info(audio_path: Path) -> dict:
    """BPM + key + duration + sample rate detection."""
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

    # Key via chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    key = key_names[int(chroma_mean.argmax())]

    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    idx = key_names.index(key)
    maj_corr = np.corrcoef(np.roll(major_profile, -idx), chroma_mean)[0, 1]
    min_corr = np.corrcoef(np.roll(minor_profile, -idx), chroma_mean)[0, 1]
    mode = "major" if maj_corr > min_corr else "minor"

    # Duration & sample rate
    duration_sec = librosa.get_duration(y=y, sr=sr)
    mins = int(duration_sec // 60)
    secs = int(duration_sec % 60)

    return {
        "bpm": round(bpm, 2),
        "key": key,
        "mode": mode,
        "duration": f"{mins}:{secs:02d}",
        "sample_rate": sr,
        "duration_sec": duration_sec,
    }


def apply_denoise(audio_path: Path, out_dir: Path, prop_decrease: float = 0.6) -> Path:
    """Spectral gating noise reduction only."""
    audio, sr = librosa.load(str(audio_path), sr=44100, mono=False, dtype=np.float32)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)

    denoised = np.stack([
        nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=prop_decrease)
        for ch in audio
    ])

    out_path = out_dir / (audio_path.stem + "_denoised.wav")
    sf.write(str(out_path), denoised.T, sr, subtype="PCM_24")
    return out_path


def apply_master(audio_path: Path, out_dir: Path, target_lufs: float = -14.0) -> Path:
    """
    Full mastering chain:
      1. Spectral noise gate
      2. LUFS normalisation (streaming standard)
      3. Hard limiter at -0.3 dBFS
    Output: 24-bit WAV @ 44100 Hz
    """
    audio, sr = librosa.load(str(audio_path), sr=44100, mono=False, dtype=np.float32)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)

    # 1. Noise gate
    denoised = np.stack([
        nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=0.6)
        for ch in audio
    ])

    # 2. LUFS normalise
    meter = pyln.Meter(sr)
    audio_T = denoised.T
    loudness = meter.integrated_loudness(audio_T)
    if np.isfinite(loudness):
        normalised = pyln.normalize.loudness(audio_T, loudness, target_lufs).T
    else:
        normalised = denoised

    # 3. Hard limiter
    peak = 10 ** (-0.3 / 20)
    limited = np.clip(normalised, -peak, peak)

    out_path = out_dir / (audio_path.stem + "_RAWMASTER.wav")
    sf.write(str(out_path), limited.T, sr, subtype="PCM_24")
    return out_path


def separate_stems(audio_path: Path, out_dir: Path, six_stem: bool = False) -> dict:
    """
    Run demucs stem separation.
    Returns dict of {stem_name: Path}
    """
    model = "htdemucs_6s" if six_stem else "htdemucs_ft"
    tmp = out_dir / "_demucs_tmp"
    stems_out = out_dir / "stems"
    stems_out.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--shifts", os.environ.get("RAWMASTER_TEST_SHIFTS", "2"),
        "--overlap", "0.25",
        "--float32",
        "--clip-mode", "rescale",
        "-o", str(tmp),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True, capture_output=False)

    demucs_track_dir = tmp / model / audio_path.stem
    stem_paths = {}
    for stem_file in sorted(demucs_track_dir.glob("*.wav")):
        dest = stems_out / stem_file.name
        shutil.move(str(stem_file), str(dest))
        stem_paths[stem_file.stem] = dest

    shutil.rmtree(str(tmp), ignore_errors=True)
    return stem_paths


def extract_midi(stem_paths: dict, out_dir: Path, midi_all: bool = False) -> list:
    """MIDI extraction from bass (and optionally vocals) stem."""
    try:
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
    except ImportError:
        raise ImportError("basic-pitch is not installed. See requirements.txt.")

    out_dir.mkdir(exist_ok=True)
    targets = ["bass"]
    if midi_all and "vocals" in stem_paths:
        targets.append("vocals")

    midi_files = []
    for stem_name in targets:
        if stem_name not in stem_paths:
            continue
        stem_path = stem_paths[stem_name]
        _, midi_data, _ = predict(str(stem_path), ICASSP_2022_MODEL_PATH)
        out_mid = out_dir / (stem_path.stem + ".mid")
        midi_data.write(str(out_mid))
        midi_files.append(out_mid)
    return midi_files


# ─────────────────────────────────────────────
#  GRADIO HANDLER FUNCTIONS
# ─────────────────────────────────────────────

def _tmp_dir():
    return Path(tempfile.mkdtemp(prefix="rawmaster_"))


def run_info(audio_input):
    """Tab 1: BPM + Key + file metadata."""
    if audio_input is None:
        return "⚠ No file uploaded.", None

    audio_path = Path(audio_input)
    try:
        info = detect_info(audio_path)
        result = (
            f"🎵  BPM:          {info['bpm']}\n"
            f"🎼  Key:          {info['key']} {info['mode']}\n"
            f"⏱  Duration:     {info['duration']}\n"
            f"📐  Sample Rate:  {info['sample_rate']} Hz"
        )
        return result, str(audio_path)
    except Exception as e:
        return f"❌ Error: {e}", None


def run_stems(audio_input, n_stems, do_midi, midi_all, progress=gr.Progress()):
    """Tab 2: Stem separation + optional MIDI extraction."""
    if audio_input is None:
        return (
            "⚠ No file uploaded.",
            None, None, None, None, None, None,  # 6 stems + extra
            None, None,  # zip, midi zip
        )

    audio_path = Path(audio_input)
    tmp = _tmp_dir()

    try:
        progress(0, desc="Starting stem separation…")
        six_stem = (str(n_stems) == "6")
        stem_paths = separate_stems(audio_path, tmp, six_stem=six_stem)
        progress(0.8, desc="Stems separated")

        # Build per-stem outputs (up to 6 slots)
        stem_order = ["vocals", "drums", "bass", "other", "guitar", "piano"]
        stem_files = []
        for s in stem_order:
            p = stem_paths.get(s)
            stem_files.append(str(p) if p else None)
        # Pad to exactly 6
        while len(stem_files) < 6:
            stem_files.append(None)

        # Build stems ZIP
        stems_zip = tmp / "stems.zip"
        with zipfile.ZipFile(stems_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for sp in stem_paths.values():
                zf.write(sp, sp.name)

        midi_zip = None
        if do_midi:
            progress(0.85, desc="Extracting MIDI…")
            try:
                midi_dir = tmp / "midi"
                midi_files = extract_midi(stem_paths, midi_dir, midi_all=midi_all)
                if midi_files:
                    midi_zip = tmp / "midi.zip"
                    with zipfile.ZipFile(midi_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in midi_files:
                            zf.write(f, f.name)
            except Exception as midi_err:
                pass  # MIDI is optional — don't fail the whole run

        progress(1.0, desc="Done")
        status = f"✅ {len(stem_paths)} stems separated"
        if do_midi and midi_zip:
            status += f"  |  MIDI extracted"

        return (
            status,
            stem_files[0],  # vocals
            stem_files[1],  # drums
            stem_files[2],  # bass
            stem_files[3],  # other
            stem_files[4],  # guitar (6-stem only)
            stem_files[5],  # piano (6-stem only)
            str(stems_zip),
            str(midi_zip) if midi_zip else None,
        )

    except Exception as e:
        return (
            f"❌ Error: {e}",
            None, None, None, None, None, None,
            None, None,
        )


def run_master(audio_input, target_lufs, progress=gr.Progress()):
    """Tab 3: Full mastering chain."""
    if audio_input is None:
        return "⚠ No file uploaded.", None, None

    audio_path = Path(audio_input)
    tmp = _tmp_dir()

    try:
        progress(0.1, desc="Applying noise reduction…")
        out_path = apply_master(audio_path, tmp, target_lufs=float(target_lufs))
        progress(1.0, desc="Mastering complete")
        return "✅ Mastering complete — 24-bit WAV @ 44.1kHz", str(out_path), str(out_path)
    except Exception as e:
        return f"❌ Error: {e}", None, None


def run_denoise(audio_input, prop_decrease, progress=gr.Progress()):
    """Tab 4: Noise reduction only."""
    if audio_input is None:
        return "⚠ No file uploaded.", None, None

    audio_path = Path(audio_input)
    tmp = _tmp_dir()

    try:
        progress(0.2, desc="Running spectral gating…")
        out_path = apply_denoise(audio_path, tmp, prop_decrease=float(prop_decrease))
        progress(1.0, desc="Done")
        return "✅ Noise reduction applied", str(out_path), str(out_path)
    except Exception as e:
        return f"❌ Error: {e}", None, None


# ─────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────

def _audio_upload(label="Drop your track here"):
    return gr.Audio(
        label=label,
        type="filepath",
        sources=["upload"],
        elem_classes=["audio-player"],
    )


def _status(lines=4):
    return gr.Textbox(
        label="Status",
        lines=lines,
        interactive=False,
        elem_classes=["status-box"],
    )


# ─────────────────────────────────────────────
#  BUILD UI
# ─────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="yellow",
        secondary_hue="gray",
        neutral_hue="gray",
        font=gr.themes.GoogleFont("JetBrains Mono"),
    ),
    css=css,
    title="RAWMASTER",
) as demo:

    # ── Header ──────────────────────────────────
    gr.HTML("""
    <div class="rawmaster-header">
        <div class="rawmaster-logo">⬛ RAWMASTER</div>
        <div class="rawmaster-sub">SMASH DADDYS AUDIO TOOLS &nbsp;|&nbsp; STRIP IT BACK. OWN THE STEMS.</div>
    </div>
    """)

    # ── Tabs ─────────────────────────────────────
    with gr.Tabs():

        # ══════════════════════════════════════════
        #  TAB 1 — AUDIO INFO
        # ══════════════════════════════════════════
        with gr.Tab("🔍 Info"):
            gr.Markdown("### Detect BPM, Key, Duration & Sample Rate")
            with gr.Row():
                with gr.Column(scale=1):
                    info_upload = _audio_upload("Upload audio file")
                    info_btn = gr.Button("ANALYZE", variant="primary", size="lg")

                with gr.Column(scale=1):
                    info_status = gr.Textbox(
                        label="Analysis Results",
                        lines=6,
                        interactive=False,
                        elem_classes=["status-box"],
                        placeholder="BPM, Key, Duration and Sample Rate will appear here…",
                    )
                    info_playback = gr.Audio(
                        label="Preview",
                        type="filepath",
                        interactive=False,
                        visible=True,
                    )

            info_btn.click(
                fn=run_info,
                inputs=[info_upload],
                outputs=[info_status, info_playback],
            )

        # ══════════════════════════════════════════
        #  TAB 2 — STEM SEPARATION
        # ══════════════════════════════════════════
        with gr.Tab("🥁 Stems"):
            gr.Markdown("### AI Stem Separation via Demucs htdemucs_ft / htdemucs_6s")
            gr.Markdown(
                "_First run downloads the Demucs model (~110 MB). Separation takes 30–120s depending on track length._"
            )

            with gr.Row():
                with gr.Column(scale=1):
                    stems_upload = _audio_upload("Upload audio file")

                    with gr.Row():
                        n_stems = gr.Radio(
                            choices=["4", "6"],
                            value="4",
                            label="Stem count",
                            info="4: vocals / drums / bass / other   |   6: + guitar + piano",
                        )
                    with gr.Row():
                        do_midi = gr.Checkbox(label="Extract MIDI from bass stem", value=False)
                        midi_all = gr.Checkbox(
                            label="Also extract MIDI from vocals",
                            value=False,
                            visible=False,
                        )

                    stems_btn = gr.Button("SEPARATE STEMS", variant="primary", size="lg")

                with gr.Column(scale=1):
                    stems_status = _status(3)

                    gr.Markdown("#### Individual Stems")
                    vocals_out = gr.Audio(label="🎤 Vocals", type="filepath", interactive=False)
                    drums_out  = gr.Audio(label="🥁 Drums",  type="filepath", interactive=False)
                    bass_out   = gr.Audio(label="🎸 Bass",   type="filepath", interactive=False)
                    other_out  = gr.Audio(label="🎹 Other",  type="filepath", interactive=False)

                    with gr.Row(visible=False) as six_stem_row:
                        guitar_out = gr.Audio(label="🎸 Guitar", type="filepath", interactive=False)
                        piano_out  = gr.Audio(label="🎹 Piano",  type="filepath", interactive=False)

                    gr.Markdown("#### Download All")
                    stems_zip_dl = gr.File(label="All stems (ZIP)")
                    midi_zip_dl  = gr.File(label="MIDI files (ZIP)", visible=False)

            # Show 6-stem extras when 6 selected
            n_stems.change(
                fn=lambda v: gr.update(visible=(v == "6")),
                inputs=n_stems,
                outputs=six_stem_row,
            )
            # Show midi_all when do_midi checked
            do_midi.change(
                fn=lambda v: [gr.update(visible=v), gr.update(visible=v)],
                inputs=do_midi,
                outputs=[midi_all, midi_zip_dl],
            )

            stems_btn.click(
                fn=run_stems,
                inputs=[stems_upload, n_stems, do_midi, midi_all],
                outputs=[
                    stems_status,
                    vocals_out, drums_out, bass_out, other_out,
                    guitar_out, piano_out,
                    stems_zip_dl, midi_zip_dl,
                ],
            )

        # ══════════════════════════════════════════
        #  TAB 3 — MASTER
        # ══════════════════════════════════════════
        with gr.Tab("🎛 Master"):
            gr.Markdown("### Full Mastering Chain")
            gr.Markdown(
                "Applies spectral noise gate → LUFS normalization → hard limiter. "
                "Outputs 24-bit WAV @ 44.1 kHz."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    master_upload = _audio_upload("Upload audio file")

                    target_lufs = gr.Slider(
                        minimum=-23,
                        maximum=-9,
                        value=-14,
                        step=0.5,
                        label="Target LUFS",
                        info="-14 = streaming standard  |  -9 = loud/club  |  -23 = broadcast",
                    )

                    master_btn = gr.Button("MASTER IT", variant="primary", size="lg")

                with gr.Column(scale=1):
                    master_status = _status(3)
                    master_playback = gr.Audio(
                        label="Mastered preview",
                        type="filepath",
                        interactive=False,
                    )
                    master_dl = gr.File(label="Download mastered WAV")

            master_btn.click(
                fn=run_master,
                inputs=[master_upload, target_lufs],
                outputs=[master_status, master_playback, master_dl],
            )

        # ══════════════════════════════════════════
        #  TAB 4 — DENOISE
        # ══════════════════════════════════════════
        with gr.Tab("🔇 Denoise"):
            gr.Markdown("### Spectral Gating Noise Reduction")
            gr.Markdown(
                "Uses `noisereduce` (stationary=False) to remove background hiss, "
                "room noise, and low-level interference — without affecting the signal."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    denoise_upload = _audio_upload("Upload audio file")

                    prop_decrease = gr.Slider(
                        minimum=0.1,
                        maximum=1.0,
                        value=0.6,
                        step=0.05,
                        label="Reduction strength",
                        info="0.1 = subtle  |  0.6 = balanced  |  1.0 = aggressive",
                    )

                    denoise_btn = gr.Button("DENOISE", variant="primary", size="lg")

                with gr.Column(scale=1):
                    denoise_status = _status(3)
                    denoise_playback = gr.Audio(
                        label="Denoised preview",
                        type="filepath",
                        interactive=False,
                    )
                    denoise_dl = gr.File(label="Download denoised WAV")

            denoise_btn.click(
                fn=run_denoise,
                inputs=[denoise_upload, prop_decrease],
                outputs=[denoise_status, denoise_playback, denoise_dl],
            )

    # ── Footer ──────────────────────────────────
    gr.HTML(f"""
    <div style="
        text-align: center;
        padding: 1.5rem 0 0.5rem;
        border-top: 1px solid {BORDER};
        margin-top: 2rem;
        color: {MUTED};
        font-family: monospace;
        font-size: 0.78rem;
        letter-spacing: 0.06em;
    ">
        RAWMASTER v1.0 &nbsp;·&nbsp; Smash Daddys Audio Tools
        &nbsp;·&nbsp; <a href="https://scanme2.gumroad.com" style="color:{GOLD}; text-decoration:none;">scanme2.gumroad.com</a>
    </div>
    """)


# ─────────────────────────────────────────────
#  LAUNCH
# ─────────────────────────────────────────────

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        show_error=True,
    )
