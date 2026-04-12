"""
RAWMASTER Companion Daemon
Runs as a local HTTP server at 127.0.0.1:5432
Receives audio processing requests from the Chrome extension
"""

import sys
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Import core pipeline from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from rawmaster import (
    detect_info,
    remaster,
    separate_stems,
    extract_midi,
    check_license,
)

app = Flask(__name__)
CORS(app, origins=["chrome-extension://*"])  # Only allow requests from Chrome extensions

PORT = 5432


@app.route("/health", methods=["GET"])
def health():
    """Extension polls this to check if daemon is running."""
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/process", methods=["POST"])
def process():
    """
    Accepts:  JSON { "audio_url": "https://...", "stems": 4, "midi": true }
    Returns:  ZIP file — remaster.wav + stems/ + midi/ + info.txt
    """
    import requests as req

    data = request.json or {}
    audio_url = data.get("audio_url")
    n_stems = int(data.get("stems", 4))
    do_midi = bool(data.get("midi", True))

    if not audio_url:
        return jsonify({"error": "No audio_url provided"}), 400

    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_companion_"))

    try:
        # ── Download audio from Suno CDN ───────────────────────────────
        resp = req.get(audio_url, stream=True, timeout=30,
                       headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        audio_path = tmp_dir / "input.mp3"
        with open(audio_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        # ── Remaster ───────────────────────────────────────────────────
        remaster_dir = tmp_dir / "remaster"
        remaster_dir.mkdir()
        remaster_path = remaster(audio_path, remaster_dir)
        # remaster() returns path to the _RAWMASTER.wav inside remaster_dir

        # ── BPM + Key ──────────────────────────────────────────────────
        info_dir = tmp_dir / "info"
        info_dir.mkdir()
        info = detect_info(audio_path, info_dir)

        # ── Stem Separation ────────────────────────────────────────────
        stem_paths = {}
        if n_stems > 0:
            six_stem = (n_stems == 6)
            stems_run_dir = tmp_dir / "stems_run"
            stems_run_dir.mkdir()
            stem_paths = separate_stems(audio_path, stems_run_dir, six_stem=six_stem)
            # stem_paths is a dict {stem_name: Path}

        # ── MIDI Extraction ────────────────────────────────────────────
        midi_dir = tmp_dir / "midi"
        if do_midi and stem_paths:
            midi_dir.mkdir()
            extract_midi(stem_paths, midi_dir, midi_all=False)
            # extract_midi takes full stem dict, extracts bass (and optionally vocals)

        # ── Bundle into ZIP ────────────────────────────────────────────
        zip_path = tmp_dir / "rawmaster_output.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Remastered WAV
            zf.write(remaster_path, "remaster.wav")

            # Stems
            for stem_name, stem_file in stem_paths.items():
                zf.write(stem_file, f"stems/{stem_file.name}")

            # MIDI
            if midi_dir.exists():
                for f in midi_dir.glob("*.mid"):
                    zf.write(f, f"midi/{f.name}")

            # Info
            info_txt = tmp_dir / "info.txt"
            info_txt.write_text(
                f"BPM:  {info['bpm']}\n"
                f"Key:  {info['key']} {info['mode']}\n"
            )
            zf.write(info_txt, "info.txt")

        return send_file(
            str(zip_path),
            mimetype="application/zip",
            as_attachment=True,
            download_name="rawmaster_output.zip",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def run_server():
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    check_license()  # Validate Gumroad license before starting
    print(f"RAWMASTER Companion running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    run_server()
