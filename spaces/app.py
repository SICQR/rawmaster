#!/usr/bin/env python3
"""
RAWMASTER -- HuggingFace Spaces Demo
Smash Daddys Audio Tools | Strip it back. Own the stems.
Demo: 90-second limit, no license validation.
Full version at scanme2.gumroad.com -- 19 GBP
"""

import subprocess
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path

import gradio as gr
import librosa
import numpy as np
import noisereduce as nr
import pyloudnorm as pyln
import soundfile as sf

DEMO_LIMIT_SEC = 90
WATERMARK = "Full version (no limits, best quality, reference mastering) at scanme2.gumroad.com -- from 19 GBP"

# Chord detection templates
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_CHORD_TEMPLATES = {}
for _i, _note in enumerate(_NOTE_NAMES):
    _maj = np.zeros(12)
    _maj[_i] = 1
    _maj[(_i + 4) % 12] = 1
    _maj[(_i + 7) % 12] = 1
    _CHORD_TEMPLATES[_note] = _maj
    _mi = np.zeros(12)
    _mi[_i] = 1
    _mi[(_i + 3) % 12] = 1
    _mi[(_i + 7) % 12] = 1
    _CHORD_TEMPLATES[f"{_note}m"] = _mi

css = """
body, .gradio-container { background: #080808 !important; color: #f0ece4 !important; }
.gr-button-primary { background: #e63012 !important; border: none !important; color: #fff !important; font-weight: bold; }
.gr-button-primary:hover { background: #ff3d1a !important; }
h1, h2, h3 { font-family: monospace !important; color: #f0ece4 !important; letter-spacing: 0.1em; }
p, label, .gr-block-label { color: #b0aaa4 !important; font-family: monospace !important; }
.gr-box, .gr-panel, .block { background: #161616 !important; border-color: #2a2a2a !important; }
footer { display: none !important; }
"""


def _remaster(audio_path, output_dir):
    audio, sr = librosa.load(str(audio_path), sr=44100, mono=False, dtype=np.float32)
    if audio.ndim == 1:
        audio = np.expand_dims(audio, axis=0)
    denoised = np.stack([
        nr.reduce_noise(y=ch, sr=sr, stationary=False, prop_decrease=0.6)
        for ch in audio
    ])
    meter = pyln.Meter(sr)
    audio_for_lufs = denoised.T
    loudness = meter.integrated_loudness(audio_for_lufs)
    if np.isfinite(loudness):
        gain = pyln.normalize.loudness(audio_for_lufs, loudness, -14.0)
        normalised = gain.T
    else:
        normalised = denoised
    peak = 10 ** (-0.3 / 20)
    limited = np.clip(normalised, -peak, peak)
    out_path = output_dir / (audio_path.stem + "_RAWMASTER.wav")
    sf.write(str(out_path), limited.T, sr, subtype="PCM_24")
    return out_path


def _detect_info(audio_path):
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    key = keys[int(chroma_mean.argmax())]
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    idx = keys.index(key)
    maj = np.corrcoef(np.roll(major_profile, -idx), chroma_mean)[0, 1]
    min_ = np.corrcoef(np.roll(minor_profile, -idx), chroma_mean)[0, 1]
    mode = "major" if maj > min_ else "minor"
    return {"bpm": round(bpm, 2), "key": key, "mode": mode}


def _separate_stems(audio_path, output_dir, six_stem=False):
    model = "htdemucs_6s" if six_stem else "htdemucs_ft"
    stems_out = output_dir / "stems"
    stems_out.mkdir(exist_ok=True)
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model, "--shifts", "2",
        "--overlap", "0.25", "--float32",
        "--clip-mode", "rescale",
        "-o", str(output_dir / "_demucs_tmp"),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True)
    demucs_track_dir = output_dir / "_demucs_tmp" / model / audio_path.stem
    stem_paths = {}
    for stem_file in demucs_track_dir.glob("*.wav"):
        dest = stems_out / stem_file.name
        shutil.move(str(stem_file), str(dest))
        stem_paths[stem_file.stem] = dest
    shutil.rmtree(str(output_dir / "_demucs_tmp"), ignore_errors=True)
    return stem_paths


def _extract_midi(stem_paths, output_dir, midi_all=False):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    output_dir.mkdir(exist_ok=True)
    targets = ["bass"]
    if midi_all and "vocals" in stem_paths:
        targets.append("vocals")
    for stem_name in targets:
        if stem_name not in stem_paths:
            continue
        stem_path = stem_paths[stem_name]
        _, midi_data, _ = predict(str(stem_path), ICASSP_2022_MODEL_PATH)
        midi_data.write(str(output_dir / (stem_path.stem + ".mid")))


def _detect_chords(audio_path, bpm=120.0):
    """Detect chord progression — returns list of (time, chord_name)."""
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    hop_length = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=bpm)[1]
    if len(beat_frames) < 2:
        beat_frames = np.arange(0, chroma.shape[1], int(sr / hop_length * 0.5))
    chords = []
    prev = None
    for i in range(len(beat_frames) - 1):
        seg = chroma[:, beat_frames[i]:beat_frames[i + 1]].mean(axis=1)
        norm = np.linalg.norm(seg)
        if norm < 0.01:
            continue
        seg /= norm
        best_chord, best_score = "N", 0.3
        for name, tmpl in _CHORD_TEMPLATES.items():
            score = np.dot(seg, tmpl / np.linalg.norm(tmpl))
            if score > best_score:
                best_score = score
                best_chord = name
        if best_chord != prev:
            t = round(librosa.frames_to_time(beat_frames[i], sr=sr, hop_length=hop_length), 2)
            chords.append((t, best_chord))
            prev = best_chord
    return chords


def _change_speed_pitch(audio_path, output_dir, speed=None, pitch=None):
    """Apply speed/pitch changes. Returns path to modified file."""
    if (speed is None or speed == 1.0) and (pitch is None or pitch == 0):
        return audio_path
    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    if speed and speed != 1.0:
        if y.ndim == 1:
            y = librosa.effects.time_stretch(y, rate=speed)
        else:
            y = np.stack([librosa.effects.time_stretch(ch, rate=speed) for ch in y])
    if pitch and pitch != 0:
        if y.ndim == 1:
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch)
        else:
            y = np.stack([librosa.effects.pitch_shift(ch, sr=sr, n_steps=pitch) for ch in y])
    out_path = output_dir / (audio_path.stem + "_adjusted.wav")
    sf.write(str(out_path), y.T if y.ndim > 1 else y, sr, subtype="PCM_24")
    return out_path


def _crop_to_limit(audio_path, tmp_dir, limit_sec):
    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    n_samples = y.shape[0] if y.ndim == 1 else y.shape[1]
    limit_samples = limit_sec * sr
    if n_samples <= limit_samples:
        return audio_path
    y_cropped = y[:limit_samples] if y.ndim == 1 else y[:, :limit_samples]
    cropped_path = tmp_dir / (audio_path.stem + "_cropped" + audio_path.suffix)
    sf.write(str(cropped_path), y_cropped.T if y.ndim > 1 else y_cropped, sr)
    return cropped_path


def process(audio_input, reference_input, do_stems, n_stems, do_midi, midi_all, do_chords, speed_val, pitch_val):
    if audio_input is None:
        yield "No file uploaded.", None, None, None, None, ""
        return

    audio_path = Path(audio_input)
    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_demo_"))
    status = [WATERMARK, ""]

    if reference_input:
        status.append("🎯 Reference mastering is a paid feature → scanme2.gumroad.com")
        status.append("   Using standard remaster for this demo.\n")

    duration = librosa.get_duration(path=str(audio_path))
    if duration > DEMO_LIMIT_SEC:
        status.append(f"Cropping to {DEMO_LIMIT_SEC}s (demo limit) -- full version has no limit")
        audio_path = _crop_to_limit(audio_path, tmp_dir, DEMO_LIMIT_SEC)
    yield "\n".join(status), None, None, None, None, ""

    try:
        info = _detect_info(audio_path)
        info_str = f"BPM: {info['bpm']}  |  Key: {info['key']} {info['mode']}"
        status.append(f"BPM+Key: {info_str}")
    except Exception as e:
        info_str = ""
        info = {}
        status.append(f"BPM/Key failed: {e}")
    yield "\n".join(status), None, None, None, None, info_str

    # Chord detection
    if do_chords:
        try:
            chords = _detect_chords(audio_path, bpm=info.get("bpm", 120))
            chord_names = [c for _, c in chords[:6]]
            if chord_names:
                info_str += f"  |  Chords: {' -> '.join(chord_names)}"
                status.append(f"Chords: {' -> '.join(chord_names)}")
        except Exception as e:
            status.append(f"Chord detection failed: {e}")
        yield "\n".join(status), None, None, None, None, info_str

    try:
        remaster_dir = tmp_dir / "remaster"
        remaster_dir.mkdir()
        remaster_path = _remaster(audio_path, remaster_dir)
        status.append("Remaster complete (demo uses fast quality -- full version has best/ensemble)")
    except Exception as e:
        status.append(f"Remaster failed: {e}")
        yield "\n".join(status), None, None, None, None, info_str
        return

    # Speed/pitch adjustment
    spd = float(speed_val) if speed_val and float(speed_val) != 1.0 else None
    pit = float(pitch_val) if pitch_val and float(pitch_val) != 0 else None
    if spd or pit:
        try:
            _change_speed_pitch(remaster_path, remaster_dir, speed=spd, pitch=pit)
            label = []
            if spd:
                label.append(f"{spd}x")
            if pit:
                label.append(f"{pit:+.0f}st")
            status.append(f"Speed/pitch adjusted ({', '.join(label)})")
        except Exception as e:
            status.append(f"Speed/pitch failed: {e}")

    yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

    stems_zip_path = None
    midi_zip_path = None

    if do_stems:
        status.append(f"Separating stems ({n_stems}-stem) -- this takes ~30s...")
        yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

        try:
            six_stem = (str(n_stems) == "6")
            stems_dir = tmp_dir / "stems_run"
            stems_dir.mkdir()
            stem_paths = _separate_stems(audio_path, stems_dir, six_stem=six_stem)
            status.append(f"Stems separated ({len(stem_paths)} tracks)")
            stems_zip_path = tmp_dir / "stems.zip"
            with zipfile.ZipFile(stems_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for stem_name, stem_file in stem_paths.items():
                    zf.write(stem_file, stem_file.name)
        except Exception as e:
            status.append(f"Stem separation failed: {e}")
            yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str
            return

        yield "\n".join(status), str(remaster_path), str(remaster_path), str(stems_zip_path), None, info_str

        if do_midi:
            try:
                midi_dir = tmp_dir / "midi"
                _extract_midi(stem_paths, midi_dir, midi_all=midi_all)
                midi_files = list(midi_dir.glob("*.mid"))
                if midi_files:
                    status.append(f"MIDI extracted ({len(midi_files)} file(s))")
                    midi_zip_path = tmp_dir / "midi.zip"
                    with zipfile.ZipFile(midi_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in midi_files:
                            zf.write(f, f.name)
            except Exception as e:
                status.append(f"MIDI failed: {e}")

    status.append("")
    status.append("Done. Go make noise.")
    status.append(WATERMARK)
    yield (
        "\n".join(status),
        str(remaster_path),
        str(remaster_path),
        str(stems_zip_path) if stems_zip_path else None,
        str(midi_zip_path) if midi_zip_path else None,
        info_str,
    )


with gr.Blocks(theme=gr.themes.Base(), css=css, title="RAWMASTER Demo") as demo:

    gr.Markdown(f"""
# RAWMASTER
**Smash Daddys Audio Tools -- Strip it back. Own the stems.**

> Demo mode -- tracks cropped to {DEMO_LIMIT_SEC}s. **[Full version: scanme2.gumroad.com](https://scanme2.gumroad.com)** -- 19 GBP, no limits.
""")

    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                label=f"Drop your track here (max {DEMO_LIMIT_SEC}s in demo)",
                type="filepath",
                sources=["upload"],
            )
            reference_input = gr.Audio(
                label="Reference track (paid feature — preview only in demo)",
                type="filepath",
                sources=["upload"],
            )
            do_stems = gr.Checkbox(label="Separate stems", value=True)
            n_stems = gr.Radio(["4", "6"], label="Number of stems", value="4", visible=True)
            do_midi = gr.Checkbox(label="Extract MIDI (bass stem)", value=True, visible=True)
            midi_all = gr.Checkbox(label="Also extract MIDI from vocals", value=False, visible=False)
            do_chords = gr.Checkbox(label="Detect chord progression", value=True)
            with gr.Row():
                speed_val = gr.Number(label="Speed", value=1.0, minimum=0.25, maximum=4.0, step=0.05,
                                      info="1.0 = normal, 0.5 = half speed")
                pitch_val = gr.Number(label="Pitch (semitones)", value=0, minimum=-12, maximum=12, step=1,
                                      info="0 = normal, +2 = up, -3 = down")
            run_btn = gr.Button("RAWMASTER IT", variant="primary", size="lg")

        with gr.Column(scale=1):
            status_box = gr.Textbox(label="Status", lines=10, interactive=False)
            remaster_audio = gr.Audio(label="Remastered track", type="filepath", interactive=False)
            remaster_dl = gr.File(label="Download remastered WAV")
            stems_dl = gr.File(label="Download stems (ZIP)")
            midi_dl = gr.File(label="Download MIDI (ZIP)")
            info_box = gr.Textbox(label="BPM + Key + Chords", interactive=False)

    do_stems.change(
        fn=lambda v: [gr.update(visible=v), gr.update(visible=v)],
        inputs=do_stems, outputs=[n_stems, do_midi],
    )
    do_midi.change(fn=lambda v: gr.update(visible=v), inputs=do_midi, outputs=midi_all)

    run_btn.click(
        fn=process,
        inputs=[audio_input, reference_input, do_stems, n_stems, do_midi, midi_all, do_chords, speed_val, pitch_val],
        outputs=[status_box, remaster_audio, remaster_dl, stems_dl, midi_dl, info_box],
    )

if __name__ == "__main__":
    demo.launch()
