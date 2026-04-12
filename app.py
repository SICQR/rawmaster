#!/usr/bin/env python3
"""
RAWMASTER Ñ Gradio UI
Smash Daddys Audio Tools | Strip it back. Own the stems.
Run: python3 app.py  ->  http://localhost:7860
"""

import tempfile
import zipfile
from pathlib import Path

import gradio as gr

# Import pipeline functions from rawmaster.py (same dir)
from rawmaster import detect_info, remaster, separate_stems, extract_midi

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


def process(audio_input, do_stems, n_stems, do_midi, midi_all):
    if audio_input is None:
        yield "No file uploaded. Drop a track and try again.", None, None, None, None, ""
        return

    audio_path = Path(audio_input)
    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_"))
    status = []

    try:
        info_dir = tmp_dir / "info"
        info_dir.mkdir()
        info = detect_info(audio_path, info_dir)
        info_str = f"BPM: {info['bpm']}  |  Key: {info['key']} {info['mode']}"
        status.append(f"BPM+Key: {info_str}")
    except Exception as e:
        info_str = ""
        status.append(f"BPM/Key detection failed: {e}")

    yield "\n".join(status), None, None, None, None, info_str

    try:
        remaster_dir = tmp_dir / "remaster"
        remaster_dir.mkdir()
        remaster_path = remaster(audio_path, remaster_dir)
        status.append("Remaster complete")
    except Exception as e:
        status.append(f"Remaster failed: {e}")
        yield "\n".join(status), None, None, None, None, info_str
        return

    yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

    stems_zip_path = None
    midi_zip_path = None

    if do_stems:
        status.append(f"Separating stems ({n_stems}-stem model) - grab a coffee...")
        yield "\n".join(status), str(remaster_path), str(remaster_path), None, None, info_str

        try:
            six_stem = (str(n_stems) == "6")
            stems_dir = tmp_dir / "stems_run"
            stems_dir.mkdir()
            stem_paths = separate_stems(audio_path, stems_dir, six_stem=six_stem)
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
                midi_dir.mkdir()
                extract_midi(stem_paths, midi_dir, midi_all=midi_all)
                midi_files = list(midi_dir.glob("*.mid"))
                if midi_files:
                    status.append(f"MIDI extracted ({len(midi_files)} file(s))")
                    midi_zip_path = tmp_dir / "midi.zip"
                    with zipfile.ZipFile(midi_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in midi_files:
                            zf.write(f, f.name)
                else:
                    status.append("MIDI: no output files generated")
            except Exception as e:
                status.append(f"MIDI extraction failed: {e}")

    status.append("Done. Go make noise.")
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
        inputs=[audio_input, do_stems, n_stems, do_midi, midi_all],
        outputs=[status_box, remaster_audio, remaster_dl, stems_dl, midi_dl, info_box],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
