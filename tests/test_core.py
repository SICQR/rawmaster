"""
RAWMASTER - core unit tests
Run: pytest tests/ -v
Env: RAWMASTER_SKIP_LICENSE=1 skips Gumroad validation (used in CI)
"""

import os
import sys
import numpy as np
import soundfile as sf
import pytest

os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_sine(path, duration=3.0, sr=44100, freq=440.0, amplitude=0.5):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.float32)
    sf.write(str(path), audio, sr)
    return path


class TestRemaster:
    def test_output_file_created(self, tmp_path):
        from rawmaster import remaster
        src = _make_sine(tmp_path / "input.wav")
        out = remaster(src, tmp_path / "out")
        assert out.exists()

    def test_output_is_wav(self, tmp_path):
        from rawmaster import remaster
        src = _make_sine(tmp_path / "input.wav")
        out = remaster(src, tmp_path / "out")
        assert out.suffix == ".wav"

    def test_output_loudness_near_target(self, tmp_path):
        import pyloudnorm as pyln
        from rawmaster import remaster
        src = _make_sine(tmp_path / "input.wav")
        out = remaster(src, tmp_path / "out")
        audio, sr = sf.read(str(out))
        if audio.ndim == 1:
            audio = audio[:, np.newaxis]
        meter = pyln.Meter(sr)
        lufs = meter.integrated_loudness(audio)
        assert abs(lufs - (-14.0)) < 2.0, f"LUFS {lufs:.1f} too far from -14"

    def test_no_hard_clip(self, tmp_path):
        from rawmaster import remaster
        src = _make_sine(tmp_path / "input.wav")
        out = remaster(src, tmp_path / "out")
        audio, _ = sf.read(str(out))
        assert np.max(np.abs(audio)) <= 1.0


class TestDetectInfo:
    def test_returns_bpm_and_key(self, tmp_path):
        from rawmaster import detect_info
        src = _make_sine(tmp_path / "input.wav", duration=5.0)
        info = detect_info(src, tmp_path / "info")
        assert "bpm" in info
        assert "key" in info
        assert "mode" in info

    def test_bpm_is_positive(self, tmp_path):
        from rawmaster import detect_info
        src = _make_sine(tmp_path / "input.wav", duration=5.0)
        info = detect_info(src, tmp_path / "info")
        assert info["bpm"] > 0

    def test_info_txt_written(self, tmp_path):
        from rawmaster import detect_info
        src = _make_sine(tmp_path / "input.wav", duration=5.0)
        info_dir = tmp_path / "info"
        detect_info(src, info_dir)
        assert (info_dir / "info.txt").exists()


class TestRemasterWithReference:
    def test_output_file_created(self, tmp_path):
        from rawmaster import remaster_with_reference
        target = _make_sine(tmp_path / "target.wav", freq=440.0)
        ref = _make_sine(tmp_path / "reference.wav", freq=880.0, amplitude=0.5)
        out = remaster_with_reference(target, ref, tmp_path / "out")
        assert out.exists()

    def test_output_is_24bit_wav(self, tmp_path):
        from rawmaster import remaster_with_reference
        target = _make_sine(tmp_path / "target.wav")
        ref = _make_sine(tmp_path / "reference.wav", amplitude=0.5)
        out = remaster_with_reference(target, ref, tmp_path / "out")
        info = sf.info(str(out))
        assert info.subtype == "PCM_24"

    def test_reference_not_found_raises(self, tmp_path):
        from rawmaster import remaster_with_reference
        target = _make_sine(tmp_path / "target.wav")
        with pytest.raises(FileNotFoundError):
            remaster_with_reference(target, tmp_path / "nonexistent.wav", tmp_path / "out")

    def test_fallback_on_matchering_failure(self, tmp_path):
        """Too-short reference triggers matchering error; should fall back to standard remaster."""
        from rawmaster import remaster_with_reference
        target = _make_sine(tmp_path / "target.wav")
        ref = _make_sine(tmp_path / "ref_short.wav", duration=0.1)
        out = remaster_with_reference(target, ref, tmp_path / "out")
        assert out.exists()

    def test_stereo_input(self, tmp_path):
        from rawmaster import remaster_with_reference
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        stereo = np.stack([
            np.sin(2 * np.pi * 440 * t) * 0.5,
            np.sin(2 * np.pi * 550 * t) * 0.5,
        ]).T.astype(np.float32)
        target = tmp_path / "stereo_target.wav"
        sf.write(str(target), stereo, sr)
        ref = _make_sine(tmp_path / "ref.wav", amplitude=0.5)
        out = remaster_with_reference(target, ref, tmp_path / "out")
        assert out.exists()


class TestLicense:
    @pytest.mark.skipif(
        os.environ.get("RAWMASTER_SKIP_LICENSE") == "1",
        reason="License check skipped in CI",
    )
    def test_invalid_key_raises(self):
        from rawmaster import check_license
        with pytest.raises(SystemExit):
            check_license(key="invalid-key-xxxx")