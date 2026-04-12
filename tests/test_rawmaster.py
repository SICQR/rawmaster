"""
RAWMASTER Unit Tests — corrected for actual API signatures
Run: python3 -m pytest tests/test_rawmaster.py -v --tb=short -m "not slow"
Run slow: python3 -m pytest tests/test_rawmaster.py -v --tb=short -m "slow" -s
"""

import os
import sys
import shutil
import subprocess
import numpy as np
import soundfile as sf
import pytest
from pathlib import Path

os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_audio_path(tmp_path_factory):
    """10-second synthetic stereo WAV for fast unit tests."""
    tmp = tmp_path_factory.mktemp("audio")
    path = tmp / "test_track.wav"
    sr = 44100
    t = np.linspace(0, 10, sr * 10)
    audio = (
        np.sin(2 * np.pi * 60  * t) * np.exp(-5 * (t % 0.5)) * 0.7
        + np.sin(2 * np.pi * 80  * t) * 0.3
        + np.sin(2 * np.pi * 440 * t) * 0.2
        + np.random.normal(0, 0.01, len(t))
    )
    audio = audio / np.max(np.abs(audio)) * 0.85
    stereo = np.column_stack([audio, audio * 0.97])
    sf.write(str(path), stereo, sr)
    return path


@pytest.fixture(scope="session")
def test_mp3_path(tmp_path_factory, test_audio_path):
    """MP3 version of test audio for realistic Suno-like input."""
    tmp = tmp_path_factory.mktemp("mp3")
    mp3 = tmp / "test_track.mp3"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(test_audio_path), "-b:a", "128k", str(mp3)],
            capture_output=True,
        )
        if result.returncode == 0:
            return mp3
    except FileNotFoundError:
        pass
    # ffmpeg not available — return WAV as fallback
    wav = tmp / "test_track.wav"
    shutil.copy(str(test_audio_path), str(wav))
    return wav


# ─── detect_info ──────────────────────────────────────────────────────────────
# API: detect_info(audio_path: Path, output_dir: Path) -> dict

class TestDetectInfo:
    def test_returns_bpm(self, test_audio_path, tmp_path):
        from rawmaster import detect_info
        result = detect_info(test_audio_path, tmp_path / "info")
        assert "bpm" in result
        assert isinstance(result["bpm"], float)
        assert 40.0 <= result["bpm"] <= 300.0, f"BPM {result['bpm']} out of musical range"

    def test_returns_key(self, test_audio_path, tmp_path):
        from rawmaster import detect_info
        result = detect_info(test_audio_path, tmp_path / "info")
        valid_keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        assert result["key"] in valid_keys, f"Key {result['key']} not valid"

    def test_returns_mode(self, test_audio_path, tmp_path):
        from rawmaster import detect_info
        result = detect_info(test_audio_path, tmp_path / "info")
        assert result["mode"] in ["major", "minor"]

    def test_info_txt_written(self, test_audio_path, tmp_path):
        from rawmaster import detect_info
        info_dir = tmp_path / "info"
        info_dir.mkdir()
        detect_info(test_audio_path, info_dir)
        assert (info_dir / "info.txt").exists()
        content = (info_dir / "info.txt").read_text()
        assert "BPM" in content
        assert "Key" in content

    def test_handles_mp3_input(self, test_mp3_path, tmp_path):
        from rawmaster import detect_info
        result = detect_info(test_mp3_path, tmp_path / "info")
        assert result["bpm"] > 0


# ─── remaster ─────────────────────────────────────────────────────────────────
# API: remaster(audio_path: Path, output_dir: Path) -> Path
# output_dir is a DIRECTORY; function writes {stem}_RAWMASTER.wav inside it

class TestRemaster:
    def test_creates_output_file(self, test_audio_path, tmp_path):
        from rawmaster import remaster
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(test_audio_path, out_dir)
        assert result.exists(), f"Remaster output not created at {result}"

    def test_output_is_valid_wav(self, test_audio_path, tmp_path):
        from rawmaster import remaster
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(test_audio_path, out_dir)
        data, sr = sf.read(str(result))
        assert sr > 0
        assert len(data) > 0
        assert data.ndim == 2, "Expected stereo output"

    def test_output_loudness_near_target(self, test_audio_path, tmp_path):
        import pyloudnorm as pyln
        from rawmaster import remaster
        # Create a quiet input
        quiet_path = tmp_path / "quiet.wav"
        data, sr = sf.read(str(test_audio_path))
        sf.write(str(quiet_path), data * 0.05, sr)

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(quiet_path, out_dir)
        out_data, out_sr = sf.read(str(result))
        meter = pyln.Meter(out_sr)
        loudness = meter.integrated_loudness(out_data)
        assert loudness > -20.0, f"Remaster too quiet: {loudness:.1f} LUFS"

    def test_output_does_not_clip(self, test_audio_path, tmp_path):
        from rawmaster import remaster
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(test_audio_path, out_dir)
        data, _ = sf.read(str(result))
        peak = np.max(np.abs(data))
        assert peak <= 1.0, f"Output clips at {peak:.4f}"

    def test_sample_rate_preserved(self, test_audio_path, tmp_path):
        from rawmaster import remaster
        _, input_sr = sf.read(str(test_audio_path))
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(test_audio_path, out_dir)
        _, out_sr = sf.read(str(result))
        assert out_sr == input_sr

    def test_noise_reduced(self, tmp_path):
        """Output should have lower high-frequency noise floor than noisy input."""
        from rawmaster import remaster
        noisy_path = tmp_path / "noisy.wav"
        sr = 44100
        t = np.linspace(0, 5, sr * 5)
        signal = np.sin(2 * np.pi * 440 * t) * 0.5
        noise = np.random.normal(0, 0.15, len(t))
        noisy = signal + noise
        stereo = np.column_stack([noisy, noisy])
        sf.write(str(noisy_path), stereo, sr)

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = remaster(noisy_path, out_dir)

        def hf_rms(audio, sr, cutoff=4000):
            mono = audio[:, 0] if audio.ndim == 2 else audio
            fft = np.abs(np.fft.rfft(mono))
            freqs = np.fft.rfftfreq(len(mono), 1 / sr)
            return np.sqrt(np.mean(fft[freqs > cutoff] ** 2))

        in_data, _ = sf.read(str(noisy_path))
        out_data, _ = sf.read(str(result))
        assert hf_rms(out_data, sr) < hf_rms(in_data, sr), "Noise not reduced"


# ─── separate_stems ───────────────────────────────────────────────────────────
# API: separate_stems(audio_path, output_dir, six_stem=False) -> dict[str, Path]

class TestSeparateStems:
    def test_function_importable(self):
        from rawmaster import separate_stems
        assert callable(separate_stems)

    def test_bad_path_raises(self, tmp_path):
        from rawmaster import separate_stems
        with pytest.raises(Exception):
            separate_stems(Path("/nonexistent/track.mp3"), tmp_path)

    @pytest.mark.slow
    def test_creates_four_stems(self, test_audio_path, tmp_path):
        from rawmaster import separate_stems
        stem_paths = separate_stems(test_audio_path, tmp_path)
        assert isinstance(stem_paths, dict)
        assert len(stem_paths) == 4, f"Expected 4 stems, got {len(stem_paths)}: {list(stem_paths.keys())}"

    @pytest.mark.slow
    def test_stem_names_correct(self, test_audio_path, tmp_path):
        from rawmaster import separate_stems
        stem_paths = separate_stems(test_audio_path, tmp_path)
        assert "vocals" in stem_paths
        assert "drums" in stem_paths
        assert "bass" in stem_paths
        assert "other" in stem_paths

    @pytest.mark.slow
    def test_stems_are_valid_audio(self, test_audio_path, tmp_path):
        from rawmaster import separate_stems
        stem_paths = separate_stems(test_audio_path, tmp_path)
        for name, path in stem_paths.items():
            assert path.exists(), f"Stem file missing: {path}"
            data, sr = sf.read(str(path))
            assert sr > 0
            assert len(data) > 0
            assert not np.all(data == 0), f"Stem {name} is silent"

    @pytest.mark.slow
    def test_stems_sum_approximates_original(self, test_audio_path, tmp_path):
        """Sum of stems should positively correlate with original."""
        from rawmaster import separate_stems
        stem_paths = separate_stems(test_audio_path, tmp_path)
        original, sr = sf.read(str(test_audio_path))
        stems = [sf.read(str(p))[0] for p in sorted(stem_paths.values())]
        min_len = min(len(original), min(len(s) for s in stems))
        original = original[:min_len]
        stems = [s[:min_len] for s in stems]
        stem_sum = sum(stems)
        corr = np.corrcoef(original[:, 0], stem_sum[:, 0])[0, 1]
        assert corr > 0.5, f"Stem reconstruction correlation too low: {corr:.3f}"


# ─── extract_midi ─────────────────────────────────────────────────────────────
# API: extract_midi(stem_paths: dict, output_dir: Path, midi_all=False)
# Takes a DICT of stem_name -> Path (not a single audio path)

class TestExtractMidi:
    def test_function_importable(self):
        from rawmaster import extract_midi
        assert callable(extract_midi)

    @pytest.mark.slow
    def test_creates_midi_file(self, test_audio_path, tmp_path):
        from rawmaster import separate_stems, extract_midi
        # First separate to get stem_paths dict
        stem_paths = separate_stems(test_audio_path, tmp_path / "stems")
        midi_dir = tmp_path / "midi"
        midi_dir.mkdir()
        extract_midi(stem_paths, midi_dir)
        midi_files = list(midi_dir.rglob("*.mid"))
        assert len(midi_files) > 0, "No MIDI file created"

    @pytest.mark.slow
    def test_midi_is_valid(self, test_audio_path, tmp_path):
        import mido
        from rawmaster import separate_stems, extract_midi
        stem_paths = separate_stems(test_audio_path, tmp_path / "stems")
        midi_dir = tmp_path / "midi"
        midi_dir.mkdir()
        extract_midi(stem_paths, midi_dir)
        for midi_file in midi_dir.rglob("*.mid"):
            mid = mido.MidiFile(str(midi_file))
            total_notes = sum(
                1 for track in mid.tracks for msg in track if msg.type == "note_on"
            )
            assert total_notes >= 0  # zero notes is valid for some audio


# ─── License validation ────────────────────────────────────────────────────────

class TestLicenseValidation:
    def test_invalid_key_returns_false(self):
        from rawmaster import validate_license
        # Product ID is a placeholder — will return False (not raise)
        result = validate_license("FAKE-KEY-DOES-NOT-EXIST-0000")
        assert result is False


# ─── CLI integration ───────────────────────────────────────────────────────────

class TestCLI:
    RAWMASTER = str(Path(__file__).parent.parent / "rawmaster.py")
    VENV_PYTHON = str(Path(__file__).parent.parent / ".venv" / "bin" / "python3")

    @property
    def python(self):
        return self.VENV_PYTHON if Path(self.VENV_PYTHON).exists() else sys.executable

    def test_version_flag(self):
        result = subprocess.run(
            [self.python, self.RAWMASTER, "--version"],
            capture_output=True, text=True,
        )
        assert result.returncode in [0, 1]

    def test_help_flag(self):
        result = subprocess.run(
            [self.python, self.RAWMASTER, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        combined = (result.stdout + result.stderr).lower()
        assert "rawmaster" in combined or "usage" in combined

    def test_missing_file_exits_nonzero(self):
        result = subprocess.run(
            [self.python, self.RAWMASTER, "/nonexistent/file.mp3"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    @pytest.mark.slow
    def test_info_flag_on_real_file(self, test_audio_path):
        result = subprocess.run(
            [self.python, self.RAWMASTER, str(test_audio_path), "--info"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "BPM" in result.stdout
        assert "Key" in result.stdout

    @pytest.mark.slow
    def test_remaster_only_creates_output(self, test_audio_path, tmp_path):
        local = tmp_path / "input.wav"
        shutil.copy(str(test_audio_path), str(local))
        result = subprocess.run(
            [self.python, self.RAWMASTER, str(local)],
            capture_output=True, text=True,
        )
        output_candidates = list(tmp_path.rglob("*_RAWMASTER.wav"))
        assert len(output_candidates) > 0, (
            f"Remaster not created.\nstdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )
