#!/usr/bin/env python3
"""
RAWMASTER Ñ Gradio UI
Smash Daddys Audio Tools | Strip it back. Own the stems.
Run: python3 app.py  ->  http://localhost:7860
"""

import os
import re
import tempfile
import time
import zipfile
from pathlib import Path

import gradio as gr

# Import pipeline functions from rawmaster.py (same dir)
from rawmaster import (
    detect_info, remaster, remaster_with_reference, separate_stems, extract_midi,
    post_process_stems, _run_demucs_model,
    SUPPORTED_FORMATS, QUALITY_PRESETS, ENSEMBLE_MODELS,
)

# ── Status rendering ───────────────────────────────────────────────────────────

STEM_ICONS = {
    "vocals": "🎤", "drums": "🥁", "bass": "🎸", "other": "🎶",
    "guitar": "🎵", "piano": "🎹",
}


def _elapsed(t0):
    """Format elapsed time since t0."""
    s = time.time() - t0
    if s < 60:
        return f"{s:.0f}s"
    return f"{int(s // 60)}m {int(s % 60)}s"


def _progress_bar(pct):
    """Render an HTML progress bar."""
    pct = max(0, min(100, int(pct)))
    return (
        f'<div style="background:#1e1e1e;border-radius:4px;height:18px;margin:6px 0;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#e63012,#ff5533);height:100%;width:{pct}%;'
        f'border-radius:4px;transition:width 0.5s ease;display:flex;align-items:center;'
        f'justify-content:center;font-size:10px;color:#fff;font-family:monospace;font-weight:700">'
        f'{pct}%</div></div>'
    )


def _render_status(lines, progress=None, stem_list=None):
    """Build HTML status box from lines, optional progress bar, optional stem list."""
    html = '<div style="font-family:monospace;font-size:13px;line-height:1.8;color:#f0ece4">'
    for line in lines:
        if line.startswith("DONE"):
            html += f'<div style="color:#2ecc40;font-weight:700;margin-top:8px">{line}</div>'
        elif "failed" in line.lower() or "error" in line.lower():
            html += f'<div style="color:#e63012">{line}</div>'
        elif "still working" in line or "elapsed" in line:
            html += f'<div style="color:#C8962C">{line}</div>'
        else:
            html += f'<div>{line}</div>'
    if progress is not None:
        html += _progress_bar(progress)
    if stem_list:
        html += '<div style="margin-top:6px;font-size:12px;color:#888">'
        for stem_name, done in stem_list:
            icon = STEM_ICONS.get(stem_name, "🎶")
            if done:
                html += f'<span style="color:#2ecc40;margin-right:12px">{icon} {stem_name} ✓</span>'
            else:
                html += f'<span style="color:#444;margin-right:12px">{icon} {stem_name} ...</span>'
        html += '</div>'
    html += '</div>'
    return html


css = """
body, .gradio-container { background: #080808 !important; color: #f0ece4 !important; }
.gr-button-primary { background: #e63012 !important; border: none !important; color: #fff !important; font-weight: bold; letter-spacing: 0.05em; }
.gr-button-primary:hover { background: #ff3d1a !important; }
h1, h2, h3 { font-family: monospace !important; color: #f0ece4 !important; letter-spacing: 0.1em; }
p, label, .gr-block-label { color: #b0aaa4 !important; font-family: monospace !important; }
.gr-box, .gr-panel, .block { background: #161616 !important; border-color: #2a2a2a !important; }
.gr-input, .gr-textarea, textarea, input[type=text] { background: #1e1e1e !important; color: #f0ece4 !important; border-color: #2a2a2a !important; font-family: monospace !important; }
.gr-radio label, .gr-checkbox label { color: #b0aaa4 !important; font-family: monospace !important; }
footer { display: none !important; }
"""


def _yld(status, progress=None, stem_list=None, remaster=None, stems_zip=None, midi_zip=None, info=""):
    """Helper to yield a consistent tuple with rendered HTML status."""
    return (
        _render_status(status, progress=progress, stem_list=stem_list),
        str(remaster) if remaster else None,
        str(remaster) if remaster else None,
        str(stems_zip) if stems_zip else None,
        str(midi_zip) if midi_zip else None,
        info,
    )


def process(audio_input, reference_input, do_stems, n_stems, quality_setting, do_midi, midi_all, do_chords, speed_val, pitch_val):
    if audio_input is None:
        yield _yld(["Drop a track above and click RAWMASTER IT."])
        return

    audio_path = Path(audio_input)

    # Input validation
    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        yield _yld([f"Unsupported format: {audio_path.suffix}", "Supported: MP3, WAV, FLAC, AIFF, OGG, M4A"])
        return

    file_mb = audio_path.stat().st_size / (1024 * 1024)

    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_"))
    t0 = time.time()
    has_speed_pitch = (speed_val and float(speed_val) != 1.0) or (pitch_val and float(pitch_val) != 0)
    total_steps = (
        2
        + (1 if do_chords else 0)
        + (1 if has_speed_pitch else 0)
        + (1 if do_stems else 0)
        + (1 if do_midi and do_stems else 0)
    )
    step = 0
    status = []
    outputs = []

    if file_mb > 500:
        status.append(f"Large file ({file_mb:.0f}MB) — stem separation may take a while.")

    # Step 1: BPM + Key
    step += 1
    status.append(f"[{step}/{total_steps}] Detecting BPM + key...")
    yield _yld(status)

    try:
        info_dir = tmp_dir / "info"
        info_dir.mkdir()
        info = detect_info(audio_path, info_dir)
        info_str = f"BPM: {info['bpm']}  |  Key: {info['key']} {info['mode']}"
        status[-1] = f"[{step}/{total_steps}] BPM + Key detected ({_elapsed(t0)})"
    except Exception as e:
        info_str = ""
        info = {}
        status[-1] = f"[{step}/{total_steps}] BPM/Key failed: {e}"

    yield _yld(status, info=info_str)

    # Chord detection (if enabled)
    if do_chords:
        step += 1
        t_step = time.time()
        status.append(f"[{step}/{total_steps}] Detecting chords...")
        yield _yld(status, info=info_str)
        try:
            from rawmaster import detect_chords
            chords = detect_chords(audio_path, tmp_dir / "chords", bpm=info.get("bpm", 120))
            chord_names = [c for _, c in chords[:8]]
            info_str += f"  |  Chords: {' → '.join(chord_names)}"
            status[-1] = f"[{step}/{total_steps}] Chords detected — {len(chords)} changes ({_elapsed(t_step)})"
        except Exception as e:
            status[-1] = f"[{step}/{total_steps}] Chord detection failed: {e}"
        yield _yld(status, info=info_str)

    # Step 2: Remaster
    step += 1
    t_step = time.time()
    if reference_input:
        status.append(f"[{step}/{total_steps}] Reference mastering — matching to {Path(reference_input).name}...")
    else:
        status.append(f"[{step}/{total_steps}] Remastering...")
    yield _yld(status, info=info_str)

    try:
        remaster_dir = tmp_dir / "remaster"
        remaster_dir.mkdir()
        if reference_input:
            ref_path = Path(reference_input)
            remaster_path = remaster_with_reference(audio_path, ref_path, remaster_dir)
            status[-1] = f"[{step}/{total_steps}] Reference master complete ({_elapsed(t_step)})"
            outputs.append("remaster (reference-matched)")
        else:
            remaster_path = remaster(audio_path, remaster_dir)
            status[-1] = f"[{step}/{total_steps}] Remaster complete ({_elapsed(t_step)})"
            outputs.append("remaster")
    except Exception as e:
        status[-1] = f"[{step}/{total_steps}] Remaster failed: {e}"
        yield _yld(status, info=info_str)
        return

    yield _yld(status, remaster=remaster_path, info=info_str)

    # Speed/pitch adjustment
    if has_speed_pitch:
        step += 1
        t_step = time.time()
        spd = float(speed_val) if speed_val else None
        pit = float(pitch_val) if pitch_val else None
        label = []
        if spd and spd != 1.0:
            label.append(f"{spd}x speed")
        if pit and pit != 0:
            label.append(f"{pit:+.0f} semitones")
        status.append(f"[{step}/{total_steps}] Adjusting {' + '.join(label)}...")
        yield _yld(status, remaster=remaster_path, info=info_str)
        try:
            from rawmaster import change_speed_pitch
            change_speed_pitch(remaster_path, tmp_dir / "remaster", speed=spd, pitch_semitones=pit)
            status[-1] = f"[{step}/{total_steps}] Speed/pitch adjusted ({_elapsed(t_step)})"
            outputs.append(" + ".join(label))
        except Exception as e:
            status[-1] = f"[{step}/{total_steps}] Speed/pitch failed: {e}"
        yield _yld(status, remaster=remaster_path, info=info_str)

    stems_zip_path = None
    midi_zip_path = None
    stem_status = None

    if do_stems:
        step += 1
        t_step = time.time()
        is_max = (str(n_stems).lower() == "max")
        six_stem = (str(n_stems) == "6") or is_max
        if is_max:
            expected_stems = [
                "lead_vocals", "backing_vocals", "kick", "snare_hats", "cymbals",
                "bass", "guitar", "piano", "sub_synths", "mid_synths", "high_fx",
            ]
        elif six_stem:
            expected_stems = ["vocals", "drums", "bass", "other", "guitar", "piano"]
        else:
            expected_stems = ["vocals", "drums", "bass", "other"]

        q = quality_setting if quality_setting in ("fast", "good", "best") else "best"
        use_ensemble = (q == "best" and not six_stem and not is_max)
        shifts, overlap = QUALITY_PRESETS[q]
        shifts = int(os.environ.get("RAWMASTER_TEST_SHIFTS", str(shifts)))

        models_to_run = ENSEMBLE_MODELS if use_ensemble else [("htdemucs_6s" if six_stem else "htdemucs_ft", 1.0)]
        mode_label = "ensemble" if use_ensemble else n_stems + "-stem"

        status.append(f"[{step}/{total_steps}] Separating stems ({mode_label}, shifts={shifts})...")
        stem_status = [(s, False) for s in expected_stems]
        yield _yld(status, progress=0, stem_list=stem_status, remaster=remaster_path, info=info_str)

        try:
            stems_dir = tmp_dir / "stems_run"
            stems_dir.mkdir()
            import subprocess as sp
            import sys as _sys
            import shutil

            all_model_paths = []

            # Run each model with progress heartbeat
            for model_idx, (model_name, weight) in enumerate(models_to_run):
                model_label = f"model {model_idx+1}/{len(models_to_run)} ({model_name})" if use_ensemble else model_name

                stderr_path = tmp_dir / f"demucs_stderr_{model_idx}.txt"
                stderr_file = open(stderr_path, "w")

                demucs_cmd = [
                    _sys.executable, "-m", "demucs",
                    "-n", model_name,
                    "--shifts", str(shifts),
                    "--overlap", str(overlap),
                    "--float32",
                    "--clip-mode", "rescale",
                    "-o", str(stems_dir / "_demucs_tmp"),
                    str(audio_path),
                ]
                proc = sp.Popen(demucs_cmd, stdout=sp.PIPE, stderr=stderr_file)

                last_pct = 0
                while proc.poll() is None:
                    time.sleep(4)
                    elapsed = _elapsed(t_step)
                    try:
                        stderr_file.flush()
                        raw = open(stderr_path).read()
                        pct_matches = re.findall(r'(\d+)%\|', raw)
                        if pct_matches:
                            last_pct = int(pct_matches[-1])
                    except Exception:
                        pass

                    # Scale progress: model 1 = 0-45%, model 2 = 45-90%, post = 90-100%
                    if use_ensemble:
                        base_pct = model_idx * 45
                        scaled_pct = base_pct + int(last_pct * 0.45)
                    else:
                        scaled_pct = int(last_pct * 0.9)

                    status[-1] = f"[{step}/{total_steps}] {model_label} — {elapsed} elapsed"
                    yield _yld(status, progress=scaled_pct, stem_list=stem_status,
                               remaster=remaster_path, info=info_str)

                stderr_file.close()

                if proc.returncode != 0:
                    raw = open(stderr_path).read()
                    raise RuntimeError(f"Demucs {model_name} failed: {raw[:200]}")

                # Collect stem paths for this model
                track_name = audio_path.stem
                demucs_dir = stems_dir / "_demucs_tmp" / model_name / track_name
                model_stems = {}
                for sf_path in demucs_dir.glob("*.wav"):
                    model_stems[sf_path.stem] = sf_path
                all_model_paths.append((model_stems, weight))

            # Blend or move stems
            stems_out = stems_dir / "stems"
            stems_out.mkdir(parents=True, exist_ok=True)
            stem_paths = {}
            found_stems = set()

            if use_ensemble and len(all_model_paths) > 1:
                status[-1] = f"[{step}/{total_steps}] Blending {len(all_model_paths)} models..."
                yield _yld(status, progress=90, stem_list=stem_status, remaster=remaster_path, info=info_str)

                import soundfile as _sf
                all_stem_names = set()
                for paths, _ in all_model_paths:
                    all_stem_names.update(paths.keys())

                for stem_name in sorted(all_stem_names):
                    blended = None
                    total_w = 0.0
                    file_sr = None
                    for paths, w in all_model_paths:
                        if stem_name not in paths:
                            continue
                        audio_data, file_sr = _sf.read(str(paths[stem_name]), dtype="float32")
                        if blended is None:
                            blended = audio_data * w
                        else:
                            min_len = min(len(blended), len(audio_data))
                            blended = blended[:min_len] + audio_data[:min_len] * w
                        total_w += w
                    if blended is not None and total_w > 0:
                        blended /= total_w
                        dest = stems_out / f"{stem_name}.wav"
                        _sf.write(str(dest), blended, file_sr, subtype="FLOAT")
                        stem_paths[stem_name] = dest
                        found_stems.add(stem_name)
                        stem_status = [(s, s in found_stems) for s in expected_stems]
                        yield _yld(status, progress=92, stem_list=stem_status,
                                   remaster=remaster_path, info=info_str)
            else:
                # Single model — just move stems
                model_stems = all_model_paths[0][0]
                for stem_name, sf_path in sorted(model_stems.items()):
                    dest = stems_out / sf_path.name
                    shutil.move(str(sf_path), str(dest))
                    stem_paths[stem_name] = dest
                    found_stems.add(stem_name)
                    stem_status = [(s, s in found_stems) for s in expected_stems]
                    yield _yld(status, progress=92, stem_list=stem_status,
                               remaster=remaster_path, info=info_str)

            shutil.rmtree(str(stems_dir / "_demucs_tmp"), ignore_errors=True)

            # Max mode: cascade into 12 sub-stems
            if is_max:
                from rawmaster import sub_separate_stems
                status[-1] = f"[{step}/{total_steps}] Sub-separating into 12 stems (vocals, drums, other)..."
                yield _yld(status, progress=93, stem_list=stem_status, remaster=remaster_path, info=info_str)
                stem_paths = sub_separate_stems(stem_paths, stems_dir, quality=q)
                found_stems = set(stem_paths.keys())
                stem_status = [(s, s in found_stems) for s in expected_stems]
                yield _yld(status, progress=96, stem_list=stem_status, remaster=remaster_path, info=info_str)

            # Post-process stems
            status[-1] = f"[{step}/{total_steps}] Post-processing stems (EQ, gating, compression)..."
            yield _yld(status, progress=97, stem_list=stem_status, remaster=remaster_path, info=info_str)
            stem_paths = post_process_stems(stem_paths)

            stem_status = [(s, True) for s in expected_stems]
            status[-1] = f"[{step}/{total_steps}] Stems separated + post-processed — {len(stem_paths)} tracks ({_elapsed(t_step)})"
            outputs.append(f"{len(stem_paths)} stems")

            stems_zip_path = tmp_dir / "stems.zip"
            with zipfile.ZipFile(stems_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for stem_name, stem_file in stem_paths.items():
                    zf.write(stem_file, stem_file.name)

        except Exception as e:
            status[-1] = f"[{step}/{total_steps}] Stem separation failed: {e}"
            yield _yld(status, remaster=remaster_path, info=info_str)
            return

        yield _yld(
            status, progress=100, stem_list=stem_status,
            remaster=remaster_path, stems_zip=stems_zip_path, info=info_str)

        if do_midi:
            step += 1
            t_step = time.time()
            status.append(f"[{step}/{total_steps}] Extracting MIDI...")
            yield _yld(
                status, progress=100, stem_list=stem_status,
                remaster=remaster_path, stems_zip=stems_zip_path, info=info_str)

            try:
                midi_dir = tmp_dir / "midi"
                midi_dir.mkdir()
                extract_midi(stem_paths, midi_dir, midi_all=midi_all)
                midi_files = list(midi_dir.glob("*.mid"))
                if midi_files:
                    status[-1] = f"[{step}/{total_steps}] MIDI extracted — {len(midi_files)} file(s) ({_elapsed(t_step)})"
                    outputs.append(f"{len(midi_files)} MIDI")
                    midi_zip_path = tmp_dir / "midi.zip"
                    with zipfile.ZipFile(midi_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in midi_files:
                            zf.write(f, f.name)
                else:
                    status[-1] = f"[{step}/{total_steps}] MIDI: no output generated"
            except Exception as e:
                status[-1] = f"[{step}/{total_steps}] MIDI failed: {e}"

    # Completion summary
    status.append("")
    status.append(f"DONE — {' + '.join(outputs)} ready ({_elapsed(t0)} total)")
    yield _yld(status, progress=100, stem_list=stem_status if do_stems else None,
               remaster=remaster_path, stems_zip=stems_zip_path, midi_zip=midi_zip_path, info=info_str)


with gr.Blocks(theme=gr.themes.Base(), css=css, title="RAWMASTER") as demo:

    gr.Markdown("""
# RAWMASTER
**Smash Daddys Audio Tools Ñ Strip it back. Own the stems.**
""")

    with gr.Row():
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                label="Drop your track here",
                type="filepath",
                sources=["upload"],
            )
            reference_input = gr.Audio(
                label="Reference track (optional)",
                type="filepath",
                sources=["upload"],
            )
            gr.Markdown(
                "*Upload a pro master as reference. Your track's EQ, loudness, and dynamics will be matched to it. Pro-grade mastering, 100% local.*",
                elem_classes=["ref-help"],
            )
            do_stems = gr.Checkbox(label="Separate stems", value=True)
            n_stems = gr.Radio(
                ["4", "6", "max"],
                label="Number of stems",
                value="max",
                visible=True,
                info="4 = core  |  6 = + guitar/piano  |  max = 12 sub-stems (lead/backing vocals, kick, snare, cymbals, bass, guitar, piano, synths, FX)",
            )
            quality = gr.Radio(
                ["fast", "good", "best"],
                label="Stem quality",
                value="best",
                visible=True,
                info="fast ~5min | good ~15min | best ~30min (recommended)",
            )
            do_midi = gr.Checkbox(
                label="Extract MIDI (bass stem)",
                value=True,
                visible=True,
            )
            midi_all = gr.Checkbox(
                label="Also extract MIDI from vocals",
                value=False,
                visible=False,
            )
            gr.Markdown("---")
            do_chords = gr.Checkbox(label="Detect chord progression", value=True)
            with gr.Row():
                speed_val = gr.Number(
                    label="Speed",
                    value=1.0,
                    minimum=0.25,
                    maximum=4.0,
                    step=0.05,
                    info="1.0 = normal, 0.5 = half speed, 2.0 = double",
                )
                pitch_val = gr.Number(
                    label="Pitch (semitones)",
                    value=0,
                    minimum=-12,
                    maximum=12,
                    step=1,
                    info="0 = normal, +2 = up 2 semitones, -3 = down 3",
                )
            run_btn = gr.Button("RAWMASTER IT", variant="primary", size="lg")

        with gr.Column(scale=1):
            status_box = gr.HTML(
                value='<div style="font-family:monospace;font-size:13px;color:#555;padding:16px">Upload a track and click RAWMASTER IT...</div>',
            )
            remaster_audio = gr.Audio(
                label="Remastered track",
                type="filepath",
                interactive=False,
            )
            remaster_dl = gr.File(label="Download remastered WAV")
            stems_dl = gr.File(label="Download stems (ZIP)")
            midi_dl = gr.File(label="Download MIDI (ZIP)")
            info_box = gr.Textbox(
                label="BPM + Key + Chords",
                interactive=False,
                placeholder="-",
            )

    do_stems.change(
        fn=lambda v: [gr.update(visible=v), gr.update(visible=v), gr.update(visible=v)],
        inputs=do_stems,
        outputs=[n_stems, quality, do_midi],
    )
    do_midi.change(
        fn=lambda v: gr.update(visible=v),
        inputs=do_midi,
        outputs=midi_all,
    )

    run_btn.click(
        fn=process,
        inputs=[audio_input, reference_input, do_stems, n_stems, quality, do_midi, midi_all, do_chords, speed_val, pitch_val],
        outputs=[status_box, remaster_audio, remaster_dl, stems_dl, midi_dl, info_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
