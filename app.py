#!/usr/bin/env python3
"""
RAWMASTER Ñ Gradio UI
Smash Daddys Audio Tools | Strip it back. Own the stems.
Run: python3 app.py  ->  http://localhost:7860
"""

import re
import tempfile
import time
import zipfile
from pathlib import Path

import gradio as gr

# Import pipeline functions from rawmaster.py (same dir)
from rawmaster import detect_info, remaster, remaster_with_reference, separate_stems, extract_midi, SUPPORTED_FORMATS, QUALITY_PRESETS

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


def process(audio_input, reference_input, do_stems, n_stems, quality_setting, do_midi, midi_all):
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
    total_steps = 2 + (1 if do_stems else 0) + (1 if do_midi and do_stems else 0)
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
        status[-1] = f"[{step}/{total_steps}] BPM/Key failed: {e}"

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

    stems_zip_path = None
    midi_zip_path = None
    stem_status = None

    if do_stems:
        step += 1
        t_step = time.time()
        six_stem = (str(n_stems) == "6")
        expected_stems = ["vocals", "drums", "bass", "other"]
        if six_stem:
            expected_stems += ["guitar", "piano"]

        status.append(f"[{step}/{total_steps}] Separating stems ({n_stems}-stem)...")
        stem_status = [(s, False) for s in expected_stems]
        yield _yld(status, progress=0, stem_list=stem_status, remaster=remaster_path, info=info_str)

        try:
            stems_dir = tmp_dir / "stems_run"
            stems_dir.mkdir()

            import subprocess as sp
            import sys as _sys
            import os as _os
            model = "htdemucs_6s" if six_stem else "htdemucs_ft"
            q = quality_setting if quality_setting in ("fast", "good", "best") else "best"
            shifts, overlap = QUALITY_PRESETS[q]
            shifts = int(_os.environ.get("RAWMASTER_TEST_SHIFTS", str(shifts)))
            demucs_cmd = [
                _sys.executable, "-m", "demucs",
                "-n", model,
                "--shifts", str(shifts),
                "--overlap", str(overlap),
                "--float32",
                "--clip-mode", "rescale",
                "-o", str(stems_dir / "_demucs_tmp"),
                str(audio_path),
            ]

            # Write stderr to temp file so we can read Demucs progress
            stderr_path = tmp_dir / "demucs_stderr.txt"
            stderr_file = open(stderr_path, "w")
            proc = sp.Popen(demucs_cmd, stdout=sp.PIPE, stderr=stderr_file)

            # Poll every 4 seconds — parse percentage from Demucs tqdm output
            last_pct = 0
            while proc.poll() is None:
                time.sleep(4)
                elapsed = _elapsed(t_step)

                # Read stderr for tqdm progress (e.g. "45%|████")
                try:
                    stderr_file.flush()
                    raw = open(stderr_path).read()
                    pct_matches = re.findall(r'(\d+)%\|', raw)
                    if pct_matches:
                        last_pct = int(pct_matches[-1])
                except Exception:
                    pass

                status[-1] = f"[{step}/{total_steps}] Separating stems ({n_stems}-stem) — {elapsed} elapsed"
                yield _yld(status, progress=last_pct, stem_list=stem_status,
                           remaster=remaster_path, info=info_str)

            stderr_file.close()

            if proc.returncode != 0:
                raw = open(stderr_path).read()
                raise RuntimeError(f"Demucs failed: {raw[:200]}")

            # Move stems and show each one appearing
            import shutil
            track_name = audio_path.stem
            demucs_track_dir = stems_dir / "_demucs_tmp" / model / track_name
            stems_out = stems_dir / "stems"
            stems_out.mkdir(parents=True, exist_ok=True)
            stem_paths = {}
            found_stems = set()
            for stem_file in sorted(demucs_track_dir.glob("*.wav")):
                dest = stems_out / stem_file.name
                shutil.move(str(stem_file), str(dest))
                stem_paths[stem_file.stem] = dest
                found_stems.add(stem_file.stem)
                # Update stem checklist
                stem_status = [(s, s in found_stems) for s in expected_stems]
                status[-1] = f"[{step}/{total_steps}] Extracting stems..."
                yield _yld(status, progress=100, stem_list=stem_status,
                           remaster=remaster_path, info=info_str)

            shutil.rmtree(str(stems_dir / "_demucs_tmp"), ignore_errors=True)

            stem_status = [(s, True) for s in expected_stems]
            status[-1] = f"[{step}/{total_steps}] Stems separated — {len(stem_paths)} tracks ({_elapsed(t_step)})"
            outputs.append(f"{len(stem_paths)} stems")

            stems_zip_path = tmp_dir / "stems.zip"
            with zipfile.ZipFile(stems_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for stem_name, stem_file in stem_paths.items():
                    zf.write(stem_file, stem_file.name)

        except Exception as e:
            status[-1] = f"[{step}/{total_steps}] Stem separation failed: {e}"
            yield _yld(status, remaster=remaster_path, info=info_str)
            return

        yield _yld(status, progress=100, stem_list=stem_status,
                    remaster=remaster_path, stems_zip=stems_zip_path, info=info_str)

        if do_midi:
            step += 1
            t_step = time.time()
            status.append(f"[{step}/{total_steps}] Extracting MIDI...")
            yield _yld(status, progress=100, stem_list=stem_status,
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
                "*Upload a pro master as reference. Your track's EQ, loudness, and dynamics will be matched to it — like LANDR, but local.*",
                elem_classes=["ref-help"],
            )
            do_stems = gr.Checkbox(label="Separate stems", value=True)
            n_stems = gr.Radio(
                ["4", "6"],
                label="Number of stems",
                value="4",
                visible=True,
                info="4 = vocals/drums/bass/other  |  6 = adds guitar + piano",
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
                label="BPM + Key",
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
        inputs=[audio_input, reference_input, do_stems, n_stems, quality, do_midi, midi_all],
        outputs=[status_box, remaster_audio, remaster_dl, stems_dl, midi_dl, info_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
