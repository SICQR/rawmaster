#!/usr/bin/env python3
"""
RAWMASTER Ñ Gradio UI
Smash Daddys Audio Tools | Strip it back. Own the stems.
Run: python3 app.py  ->  http://localhost:7860
"""

import tempfile
import time
import zipfile
from pathlib import Path

import gradio as gr

# Import pipeline functions from rawmaster.py (same dir)
from rawmaster import detect_info, remaster, remaster_with_reference, separate_stems, extract_midi, SUPPORTED_FORMATS


def _elapsed(t0):
    """Format elapsed time since t0."""
    s = time.time() - t0
    if s < 60:
        return f"{s:.0f}s"
    return f"{int(s // 60)}m {int(s % 60)}s"

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


def process(audio_input, reference_input, do_stems, n_stems, do_midi, midi_all):
    if audio_input is None:
        yield "Drop a track above and click RAWMASTER IT.", None, None, None, None, ""
        return

    audio_path = Path(audio_input)

    # Input validation
    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        yield f"Unsupported format: {audio_path.suffix}\nSupported: MP3, WAV, FLAC, AIFF, OGG, M4A", None, None, None, None, ""
        return

    file_mb = audio_path.stat().st_size / (1024 * 1024)

    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_"))
    t0 = time.time()
    total_steps = 2 + (1 if do_stems else 0) + (1 if do_midi and do_stems else 0)
    step = 0
    status = []
    outputs = []  # track what was produced

    if file_mb > 500:
        status.append(f"Large file ({file_mb:.0f}MB) — stem separation may take a while.\n")

    # Step 1: BPM + Key
    step += 1
    status.append(f"[{step}/{total_steps}] Detecting BPM + key...")
    yield "\n".join(status), None, None, None, None, ""

    try:
        info_dir = tmp_dir / "info"
        info_dir.mkdir()
        info = detect_info(audio_path, info_dir)
        info_str = f"BPM: {info['bpm']}  |  Key: {info['key']} {info['mode']}"
        status[-1] = f"[{step}/{total_steps}] BPM + Key detected ({_elapsed(t0)})"
    except Exception as e:
        info_str = ""
        status[-1] = f"[{step}/{total_steps}] BPM/Key failed: {e}"

    yield "\n".join(status), None, None, None, None, info_str

    # Step 2: Remaster
    step += 1
    t_step = time.time()
    if reference_input:
        status.append(f"[{step}/{total_steps}] Reference mastering — matching to {Path(reference_input).name}...")
    else:
        status.append(f"[{step}/{total_steps}] Remastering...")
    yield "\n".join(status), None, None, None, None, info_str

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
        yield "\n".join(status), None, None, None, None, info_str
        return

    yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

    stems_zip_path = None
    midi_zip_path = None

    if do_stems:
        step += 1
        t_step = time.time()
        status.append(f"[{step}/{total_steps}] Separating stems ({n_stems}-stem) — typically 5-15 min on CPU...")
        yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

        try:
            six_stem = (str(n_stems) == "6")
            stems_dir = tmp_dir / "stems_run"
            stems_dir.mkdir()
            stem_paths = separate_stems(audio_path, stems_dir, six_stem=six_stem)
            status[-1] = f"[{step}/{total_steps}] Stems separated — {len(stem_paths)} tracks ({_elapsed(t_step)})"
            outputs.append(f"{len(stem_paths)} stems")

            stems_zip_path = tmp_dir / "stems.zip"
            with zipfile.ZipFile(stems_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for stem_name, stem_file in stem_paths.items():
                    zf.write(stem_file, stem_file.name)

        except Exception as e:
            status[-1] = f"[{step}/{total_steps}] Stem separation failed: {e}"
            yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str
            return

        yield "\n".join(status), str(remaster_path), str(remaster_path), str(stems_zip_path), None, info_str

        if do_midi:
            step += 1
            t_step = time.time()
            status.append(f"[{step}/{total_steps}] Extracting MIDI...")
            yield "\n".join(status), str(remaster_path), str(remaster_path), str(stems_zip_path), None, info_str

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
    yield (
        "\n".join(status),
        str(remaster_path),
        str(remaster_path),
        str(stems_zip_path) if stems_zip_path else None,
        str(midi_zip_path) if midi_zip_path else None,
        info_str,
    )


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
            status_box = gr.Textbox(
                label="Status",
                lines=8,
                interactive=False,
                placeholder="Upload a track and click RAWMASTER IT...",
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
        fn=lambda v: [gr.update(visible=v), gr.update(visible=v)],
        inputs=do_stems,
        outputs=[n_stems, do_midi],
    )
    do_midi.change(
        fn=lambda v: gr.update(visible=v),
        inputs=do_midi,
        outputs=midi_all,
    )

    run_btn.click(
        fn=process,
        inputs=[audio_input, reference_input, do_stems, n_stems, do_midi, midi_all],
        outputs=[status_box, remaster_audio, remaster_dl, stems_dl, midi_dl, info_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
