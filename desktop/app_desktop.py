#!/usr/bin/env python3
"""
RAWMASTER Desktop — Custom web UI powered by Stitch designs.
Serves at http://localhost:7860

Run: python desktop/app_desktop.py
"""

import json
import os
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, url_for
from flask_cors import CORS

# Add parent dir for rawmaster imports
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")

from rawmaster import (
    detect_info, detect_chords, remaster, remaster_with_reference,
    separate_stems, extract_midi, change_speed_pitch,
    convert_output_format, SUPPORTED_FORMATS,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# In-memory job tracking
jobs = {}


@app.route("/")
def index():
    return render_template("app.html")


@app.route("/library")
def library():
    return render_template("desktop_app_library.html")


@app.route("/export")
def export_wizard():
    return render_template("export_wizard.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Upload an audio file and start processing."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Save to temp
    tmp_dir = Path(tempfile.mkdtemp(prefix="rawmaster_desktop_"))
    audio_path = tmp_dir / file.filename
    file.save(str(audio_path))

    job_id = str(int(time.time() * 1000))
    jobs[job_id] = {
        "status": "uploaded",
        "audio_path": str(audio_path),
        "tmp_dir": str(tmp_dir),
        "filename": file.filename,
        "progress": 0,
        "steps": [],
        "results": {},
    }

    return jsonify({"job_id": job_id, "filename": file.filename})


@app.route("/api/process", methods=["POST"])
def process():
    """Start processing a job. Runs in background thread."""
    data = request.json or {}
    job_id = data.get("job_id")
    if not job_id or job_id not in jobs:
        return jsonify({"error": "Invalid job_id"}), 400

    job = jobs[job_id]
    config = {
        "stems": data.get("stems", 4),
        "quality": data.get("quality", "best"),
        "midi": data.get("midi", True),
        "chords": data.get("chords", True),
        "speed": data.get("speed"),
        "pitch": data.get("pitch"),
        "reference": data.get("reference"),
        "format": data.get("format", "wav24"),
        "bpm_filename": data.get("bpm_filename", False),
    }

    def run_pipeline():
        try:
            audio_path = Path(job["audio_path"])
            tmp_dir = Path(job["tmp_dir"])
            output_dir = tmp_dir / "output"
            output_dir.mkdir(exist_ok=True)

            # Step 1: BPM + Key
            job["status"] = "detecting"
            job["steps"].append({"name": "BPM + Key", "status": "running"})
            job["progress"] = 10
            info = detect_info(audio_path, output_dir)
            job["results"]["info"] = info
            job["steps"][-1]["status"] = "done"

            # Step 2: Chords
            if config["chords"]:
                job["steps"].append({"name": "Chords", "status": "running"})
                job["progress"] = 20
                chords = detect_chords(audio_path, output_dir, bpm=info.get("bpm", 120))
                job["results"]["chords"] = [(float(t), c) for t, c in chords[:12]]
                job["steps"][-1]["status"] = "done"

            # Step 3: Remaster
            job["status"] = "mastering"
            job["steps"].append({"name": "Remaster", "status": "running"})
            job["progress"] = 30
            remaster_dir = output_dir / "remaster"
            remaster_dir.mkdir(exist_ok=True)
            remaster_path = remaster(audio_path, remaster_dir)
            job["results"]["remaster"] = str(remaster_path)
            job["steps"][-1]["status"] = "done"

            # Step 4: Speed/Pitch
            if config.get("speed") or config.get("pitch"):
                job["steps"].append({"name": "Speed/Pitch", "status": "running"})
                job["progress"] = 40
                sp = config.get("speed")
                pt = config.get("pitch")
                change_speed_pitch(remaster_path, remaster_dir,
                                   speed=float(sp) if sp else None,
                                   pitch_semitones=float(pt) if pt else None)
                job["steps"][-1]["status"] = "done"

            # Step 5: Stems
            stems_str = str(config["stems"])
            if stems_str and stems_str != "0":
                job["status"] = "separating"
                job["steps"].append({"name": "Stem Separation", "status": "running"})
                job["progress"] = 50

                max_stems = (stems_str.lower() == "max")
                six_stem = (stems_str == "6") or max_stems
                stem_paths = separate_stems(
                    audio_path, output_dir,
                    six_stem=six_stem,
                    quality=config["quality"],
                    max_stems=max_stems,
                )
                job["results"]["stems"] = {k: str(v) for k, v in stem_paths.items()}
                job["steps"][-1]["status"] = "done"
                job["progress"] = 85

                # Step 6: MIDI
                if config["midi"]:
                    job["steps"].append({"name": "MIDI", "status": "running"})
                    job["progress"] = 90
                    extract_midi(stem_paths, output_dir, midi_all=False)
                    midi_dir = output_dir / "midi"
                    if midi_dir.exists():
                        job["results"]["midi"] = [str(f) for f in midi_dir.glob("*.mid")]
                    job["steps"][-1]["status"] = "done"

            # Step 7: Format conversion
            if config["format"] != "wav24" or config["bpm_filename"]:
                job["steps"].append({"name": "Export", "status": "running"})
                convert_output_format(output_dir, fmt=config["format"],
                                      bpm_filename=config["bpm_filename"], info=info)
                job["steps"][-1]["status"] = "done"

            job["status"] = "done"
            job["progress"] = 100

        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)
            import traceback
            traceback.print_exc()

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    return jsonify({"status": "processing", "job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    """Poll job status."""
    if job_id not in jobs:
        return jsonify({"error": "Unknown job"}), 404
    job = jobs[job_id]
    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "steps": job["steps"],
        "results": job.get("results", {}),
        "error": job.get("error"),
        "filename": job.get("filename"),
    })


@app.route("/api/download/<job_id>/<asset>")
def download(job_id, asset):
    """Download a processed asset."""
    if job_id not in jobs:
        return jsonify({"error": "Unknown job"}), 404

    job = jobs[job_id]
    tmp_dir = Path(job["tmp_dir"])
    output_dir = tmp_dir / "output"

    if asset == "remaster":
        path = job["results"].get("remaster")
        if path and Path(path).exists():
            return send_file(path, as_attachment=True)

    elif asset == "stems":
        stems_dir = output_dir / "stems"
        if stems_dir.exists():
            zip_path = tmp_dir / "stems.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in stems_dir.glob("*.wav"):
                    zf.write(f, f.name)
                for f in stems_dir.glob("*.aiff"):
                    zf.write(f, f.name)
            return send_file(str(zip_path), as_attachment=True,
                             download_name="stems.zip")

    elif asset == "midi":
        midi_dir = output_dir / "midi"
        if midi_dir.exists():
            zip_path = tmp_dir / "midi.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in midi_dir.glob("*.mid"):
                    zf.write(f, f.name)
            return send_file(str(zip_path), as_attachment=True,
                             download_name="midi.zip")

    return jsonify({"error": "Asset not found"}), 404


@app.route("/api/library")
def library_data():
    """Scan rawmaster_output directories for processed tracks."""
    # Look in common locations
    search_dirs = [
        Path.home() / "rawmaster_output",
        Path.cwd() / "rawmaster_output",
    ]

    tracks = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for track_dir in sorted(search_dir.iterdir()):
            if not track_dir.is_dir():
                continue
            track = {
                "name": track_dir.name,
                "path": str(track_dir),
                "has_stems": (track_dir / "stems").exists(),
                "has_midi": (track_dir / "midi").exists(),
                "has_remaster": any(track_dir.glob("*_RAWMASTER.*")),
            }
            # Read info.txt if available
            info_file = track_dir / "info.txt"
            if info_file.exists():
                for line in info_file.read_text().splitlines():
                    if line.startswith("BPM:"):
                        track["bpm"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Key:"):
                        track["key"] = line.split(":", 1)[1].strip()
            # Read chords if available
            chord_file = track_dir / "chords.txt"
            track["has_chords"] = chord_file.exists()

            tracks.append(track)

    return jsonify({"tracks": tracks})


if __name__ == "__main__":
    print("\n  RAWMASTER Desktop")
    print("  http://localhost:7860\n")
    app.run(host="0.0.0.0", port=7860, debug=False)
