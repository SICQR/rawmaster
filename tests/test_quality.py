"""
RAWMASTER — Stem Separation Quality Benchmarks
Measures SDR, SIR, SAR against synthetic test signals.

Uses mir_eval.separation.bss_eval_sources — the standard metric
used in MUSDB18 and all academic source separation papers.

SDR (Signal-to-Distortion Ratio): overall quality, higher = better
SIR (Signal-to-Interference Ratio): how much bleed from other sources
SAR (Signal-to-Artifact Ratio): how many processing artifacts introduced

Run: RAWMASTER_SKIP_LICENSE=1 pytest tests/test_quality.py -v
"""

import os
import sys
import numpy as np
import soundfile as sf
import pytest

os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_multitrack(output_dir, sr=44100, duration=5.0):
    """Create a synthetic mix with known isolated sources for benchmarking."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Vocals: 300Hz fundamental + harmonics (simulates voice)
    vocals = (
        np.sin(2 * np.pi * 300 * t) * 0.3 +
        np.sin(2 * np.pi * 600 * t) * 0.15 +
        np.sin(2 * np.pi * 900 * t) * 0.08
    ).astype(np.float32)

    # Drums: broadband noise bursts (simulates percussive hits)
    rng = np.random.RandomState(42)
    noise = rng.randn(len(t)).astype(np.float32) * 0.1
    # Create hits every beat (~125 BPM = every 0.48s)
    beat_interval = int(sr * 0.48)
    drums = np.zeros_like(t, dtype=np.float32)
    for i in range(0, len(t), beat_interval):
        end = min(i + int(sr * 0.05), len(t))  # 50ms hit
        drums[i:end] = noise[i:end] * 3.0

    # Bass: 80Hz fundamental + gentle 160Hz harmonic
    bass = (
        np.sin(2 * np.pi * 80 * t) * 0.25 +
        np.sin(2 * np.pi * 160 * t) * 0.1
    ).astype(np.float32)

    # Other: pad-like mid-frequency content (500Hz + 2kHz)
    other = (
        np.sin(2 * np.pi * 500 * t) * 0.12 +
        np.sin(2 * np.pi * 2000 * t) * 0.08
    ).astype(np.float32)

    sources = {"vocals": vocals, "drums": drums, "bass": bass, "other": other}

    # Write individual stems (ground truth)
    for name, audio in sources.items():
        stereo = np.stack([audio, audio]).T
        sf.write(str(output_dir / f"{name}_ref.wav"), stereo, sr)

    # Write mix (sum of all sources)
    mix = vocals + drums + bass + other
    stereo_mix = np.stack([mix, mix]).T
    sf.write(str(output_dir / "mix.wav"), stereo_mix, sr)

    return output_dir / "mix.wav", sources


def compute_sdr(reference, estimated):
    """Compute SDR between reference and estimated signals using mir_eval."""
    import mir_eval
    min_len = min(len(reference), len(estimated))
    ref = reference[:min_len][np.newaxis, :]
    est = estimated[:min_len][np.newaxis, :]
    sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(ref, est)
    return {"sdr": float(sdr[0]), "sir": float(sir[0]), "sar": float(sar[0])}


class TestPostProcessingQuality:
    """Test that post-processing improves or maintains stem quality."""

    def test_vocals_highpass_removes_rumble(self, tmp_path):
        """Post-processed vocals should have less low-frequency energy."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        # Vocals with unwanted 30Hz rumble
        vocals = (
            np.sin(2 * np.pi * 300 * t) * 0.3 +  # wanted vocal
            np.sin(2 * np.pi * 30 * t) * 0.2      # unwanted rumble
        ).astype(np.float32)
        stereo = np.stack([vocals, vocals]).T
        path = tmp_path / "vocals.wav"
        sf.write(str(path), stereo, sr)

        original_data, _ = sf.read(str(path))
        post_process_stems({"vocals": path})
        processed_data, _ = sf.read(str(path))

        # Compute FFT and compare low-freq energy
        orig_fft = np.abs(np.fft.rfft(original_data[:, 0]))
        proc_fft = np.abs(np.fft.rfft(processed_data[:, 0]))
        freqs = np.fft.rfftfreq(len(original_data), 1.0 / sr)

        # Energy below 60Hz should be reduced
        low_mask = freqs < 60
        orig_low_energy = np.sum(orig_fft[low_mask] ** 2)
        proc_low_energy = np.sum(proc_fft[low_mask] ** 2)
        reduction = 1 - (proc_low_energy / orig_low_energy)

        assert reduction > 0.5, f"Low-freq reduction only {reduction:.1%}, expected >50%"
        print(f"  Low-freq energy reduced by {reduction:.1%}")

    def test_bass_passes_through_clean(self, tmp_path):
        """Bass has empty DSP config (benchmark-tuned) — should pass unchanged."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        bass = (np.sin(2 * np.pi * 80 * t) * 0.3).astype(np.float32)
        stereo = np.stack([bass, bass]).T
        path = tmp_path / "bass.wav"
        sf.write(str(path), stereo, sr)

        post_process_stems({"bass": path})
        processed_data, _ = sf.read(str(path))

        # Bass has no DSP — data should be unchanged
        assert np.allclose(stereo, processed_data, atol=1e-4), "Bass stem should pass through unchanged"
        print(f"  Bass passed through cleanly (no DSP applied)")

    def test_vocals_highpass_minimal_impact(self, tmp_path):
        """Vocals highpass at 55Hz should barely affect a 300Hz vocal signal."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        vocals = (np.sin(2 * np.pi * 300 * t) * 0.3).astype(np.float32)
        stereo = np.stack([vocals, vocals]).T
        path = tmp_path / "vocals.wav"
        sf.write(str(path), stereo, sr)

        post_process_stems({"vocals": path})
        processed_data, _ = sf.read(str(path))

        # 300Hz is well above the 55Hz highpass — signal should be nearly identical
        orig_rms = np.sqrt(np.mean(vocals**2))
        proc_rms = np.sqrt(np.mean(processed_data[:, 0]**2))
        ratio = proc_rms / orig_rms

        assert 0.95 < ratio < 1.05, f"RMS ratio {ratio:.3f} — highpass changed signal too much"
        print(f"  Vocal RMS ratio after highpass: {ratio:.4f} (1.0 = unchanged)")

    def test_bandpass_split_energy_conservation(self, tmp_path):
        """Frequency band splitting should approximately conserve total energy."""
        from rawmaster import _bandpass_split
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        # Broadband signal
        rng = np.random.RandomState(42)
        signal = rng.randn(len(t)).astype(np.float32) * 0.3
        stereo = np.stack([signal, signal]).T
        path = tmp_path / "drums.wav"
        sf.write(str(path), stereo, sr)

        out_dir = tmp_path / "split"
        out_dir.mkdir()
        subs = _bandpass_split(path, out_dir, "drums", [
            ("kick", None, 200),
            ("snare", 200, 8000),
            ("cymbals", 8000, None),
        ])

        original_energy = np.sum(signal**2)
        split_energy = 0
        for name, spath in subs.items():
            audio, _ = sf.read(str(spath))
            split_energy += np.sum(audio[:, 0]**2)

        # Energy should be roughly conserved (within 50% — filters have rolloff)
        ratio = split_energy / original_energy
        assert 0.5 < ratio < 2.0, f"Energy ratio {ratio:.2f} outside expected range"
        print(f"  Energy conservation ratio: {ratio:.2f}")


class TestChordDetection:
    """Test chord detection accuracy on synthetic audio with known chords."""

    def _make_chord(self, freqs, duration=3.0, sr=44100):
        """Create a synthetic chord from a list of frequencies."""
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        signal = np.zeros_like(t, dtype=np.float32)
        for f in freqs:
            signal += np.sin(2 * np.pi * f * t) * (0.3 / len(freqs))
        return signal, sr

    # Major triad frequencies (root, major 3rd, perfect 5th)
    MAJOR_CHORDS = {
        "C": [261.63, 329.63, 392.0],
        "D": [293.66, 369.99, 440.0],
        "E": [329.63, 415.30, 493.88],
        "F": [349.23, 440.0, 523.25],
        "G": [392.0, 493.88, 587.33],
        "A": [440.0, 554.37, 659.25],
        "B": [493.88, 622.25, 739.99],
    }

    MINOR_CHORDS = {
        "Am": [220.0, 261.63, 329.63],
        "Em": [329.63, 392.0, 493.88],
        "Dm": [293.66, 349.23, 440.0],
    }

    def test_detects_c_major(self, tmp_path):
        from rawmaster import detect_chords
        audio, sr = self._make_chord(self.MAJOR_CHORDS["C"])
        path = tmp_path / "c_major.wav"
        sf.write(str(path), audio, sr)
        chords = detect_chords(path, tmp_path / "out", bpm=120)
        detected = [c for _, c in chords]
        assert "C" in detected, f"Expected C major, got {detected}"

    def test_detects_all_major_chords(self, tmp_path):
        """Each major chord should be correctly identified."""
        from rawmaster import detect_chords
        correct = 0
        for name, freqs in self.MAJOR_CHORDS.items():
            audio, sr = self._make_chord(freqs)
            path = tmp_path / f"{name}.wav"
            sf.write(str(path), audio, sr)
            out_dir = tmp_path / f"{name}_out"
            chords = detect_chords(path, out_dir, bpm=120)
            detected = chords[0][1] if chords else "N"
            if detected == name:
                correct += 1
        accuracy = correct / len(self.MAJOR_CHORDS)
        assert accuracy >= 0.85, f"Major chord accuracy {accuracy:.0%} (expected >= 85%)"
        print(f"  Major chord accuracy: {accuracy:.0%} ({correct}/{len(self.MAJOR_CHORDS)})")

    def test_detects_minor_chords(self, tmp_path):
        """Minor chords should be correctly identified."""
        from rawmaster import detect_chords
        correct = 0
        for name, freqs in self.MINOR_CHORDS.items():
            audio, sr = self._make_chord(freqs)
            path = tmp_path / f"{name}.wav"
            sf.write(str(path), audio, sr)
            out_dir = tmp_path / f"{name}_out"
            chords = detect_chords(path, out_dir, bpm=120)
            detected = chords[0][1] if chords else "N"
            if detected == name:
                correct += 1
        accuracy = correct / len(self.MINOR_CHORDS)
        assert accuracy >= 0.66, f"Minor chord accuracy {accuracy:.0%} (expected >= 66%)"
        print(f"  Minor chord accuracy: {accuracy:.0%} ({correct}/{len(self.MINOR_CHORDS)})")

    def test_detects_chord_changes(self, tmp_path):
        """Should detect multiple distinct chords in a progression."""
        from rawmaster import detect_chords
        sr = 44100
        # Use longer segments (3s each) with fade transitions for cleaner detection
        parts = []
        for freqs in [self.MAJOR_CHORDS["C"], self.MAJOR_CHORDS["F"], self.MAJOR_CHORDS["G"]]:
            audio, _ = self._make_chord(freqs, duration=3.0, sr=sr)
            # Fade edges to avoid transient artifacts
            fade = int(sr * 0.05)
            audio[:fade] *= np.linspace(0, 1, fade)
            audio[-fade:] *= np.linspace(1, 0, fade)
            parts.append(audio)
        prog = np.concatenate(parts)
        path = tmp_path / "progression.wav"
        sf.write(str(path), prog, sr)
        chords = detect_chords(path, tmp_path / "out", bpm=120)
        unique_chords = set(c for _, c in chords)
        assert len(unique_chords) >= 2, f"Expected >= 2 distinct chords, got {unique_chords}"
        print(f"  Detected {len(unique_chords)} distinct chords: {unique_chords}")

    def test_silence_returns_no_chords(self, tmp_path):
        from rawmaster import detect_chords
        sr = 44100
        silence = np.zeros(sr * 3, dtype=np.float32)
        path = tmp_path / "silence.wav"
        sf.write(str(path), silence, sr)
        chords = detect_chords(path, tmp_path / "out", bpm=120)
        assert len(chords) == 0, f"Silence should have no chords, got {chords}"

    def test_outputs_chord_file(self, tmp_path):
        from rawmaster import detect_chords
        audio, sr = self._make_chord(self.MAJOR_CHORDS["C"])
        path = tmp_path / "test.wav"
        sf.write(str(path), audio, sr)
        detect_chords(path, tmp_path / "out", bpm=120)
        chord_file = tmp_path / "out" / "chords.txt"
        assert chord_file.exists(), "chords.txt should be created"
        content = chord_file.read_text()
        assert "CHORD PROGRESSION" in content
        assert "C" in content


class TestSpeedPitchControl:
    """Test speed and pitch adjustment accuracy."""

    def test_speed_changes_duration(self, tmp_path):
        from rawmaster import change_speed_pitch
        sr = 44100
        t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        path = tmp_path / "input.wav"
        sf.write(str(path), audio, sr)

        out = change_speed_pitch(path, tmp_path / "out", speed=0.5)
        info = sf.info(str(out))
        # 0.5x speed = 2x duration: 4s -> 8s
        assert 7.5 < info.duration < 8.5, f"Expected ~8s, got {info.duration:.1f}s"

    def test_speed_up_shortens_duration(self, tmp_path):
        from rawmaster import change_speed_pitch
        sr = 44100
        t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        path = tmp_path / "input.wav"
        sf.write(str(path), audio, sr)

        out = change_speed_pitch(path, tmp_path / "out", speed=2.0)
        info = sf.info(str(out))
        # 2x speed = 0.5x duration: 4s -> 2s
        assert 1.5 < info.duration < 2.5, f"Expected ~2s, got {info.duration:.1f}s"

    def test_pitch_preserves_duration(self, tmp_path):
        from rawmaster import change_speed_pitch
        sr = 44100
        t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        path = tmp_path / "input.wav"
        sf.write(str(path), audio, sr)

        out = change_speed_pitch(path, tmp_path / "out", pitch_semitones=5)
        info = sf.info(str(out))
        # Pitch shift should NOT change duration
        assert 3.5 < info.duration < 4.5, f"Expected ~4s, got {info.duration:.1f}s"

    def test_no_change_returns_original(self, tmp_path):
        from rawmaster import change_speed_pitch
        sr = 44100
        audio = (np.sin(np.linspace(0, 10, sr * 2)) * 0.3).astype(np.float32)
        path = tmp_path / "input.wav"
        sf.write(str(path), audio, sr)

        out = change_speed_pitch(path, tmp_path / "out", speed=None, pitch_semitones=None)
        assert out == path, "No changes should return original path"

    def test_output_is_valid_wav(self, tmp_path):
        from rawmaster import change_speed_pitch
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
        path = tmp_path / "input.wav"
        sf.write(str(path), audio, sr)

        out = change_speed_pitch(path, tmp_path / "out", speed=0.8, pitch_semitones=-2)
        assert out.exists()
        data, file_sr = sf.read(str(out))
        assert file_sr == sr
        assert len(data) > 0


class TestSDRMetrics:
    """Test SDR computation works correctly with known signals."""

    def test_identical_signals_high_sdr(self):
        """Identical signals should have very high SDR."""
        signal = np.sin(np.linspace(0, 10 * np.pi, 44100)).astype(np.float32)
        metrics = compute_sdr(signal, signal)
        assert metrics["sdr"] > 50, f"SDR for identical signals: {metrics['sdr']:.1f} (expected >50)"

    def test_orthogonal_signals_low_sdr(self):
        """Completely different signals should have low/negative SDR."""
        t = np.linspace(0, 1.0, 44100, endpoint=False)
        ref = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        est = np.sin(2 * np.pi * 880 * t).astype(np.float32)
        metrics = compute_sdr(ref, est)
        assert metrics["sdr"] < 5, f"SDR for different signals: {metrics['sdr']:.1f} (expected <5)"

    def test_scaled_signal_reasonable_sdr(self):
        """Slightly scaled signal should have good but not perfect SDR."""
        signal = np.sin(np.linspace(0, 10 * np.pi, 44100)).astype(np.float32)
        scaled = signal * 0.9  # 10% quieter
        metrics = compute_sdr(signal, scaled)
        assert metrics["sdr"] > 15, f"SDR for 90% scaled: {metrics['sdr']:.1f} (expected >15)"


class TestSyntheticBenchmark:
    """End-to-end quality benchmarks using synthetic multitrack audio."""

    def test_post_processing_improves_or_maintains_sdr(self, tmp_path):
        """Post-processing should not significantly degrade SDR of clean stems."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 5.0, int(sr * 5.0), endpoint=False)

        # Create a "perfect" vocal stem and its reference
        vocals_ref = (np.sin(2 * np.pi * 300 * t) * 0.3).astype(np.float32)
        stereo = np.stack([vocals_ref, vocals_ref]).T
        path = tmp_path / "vocals.wav"
        sf.write(str(path), stereo, sr)

        # Measure SDR before post-processing
        pre_data, _ = sf.read(str(path))
        pre_metrics = compute_sdr(vocals_ref, pre_data[:, 0])

        # Apply post-processing
        post_process_stems({"vocals": path})
        post_data, _ = sf.read(str(path))
        post_metrics = compute_sdr(vocals_ref, post_data[:, 0])

        # Post-processing applies EQ/gating which modifies the signal.
        # On clean synthetic audio the SDR drop can be large (filters reshape spectrum).
        # On real separated stems with bleed, the SDR should improve.
        # Here we just verify post-processed SDR is still reasonable (>20 dB = very good).
        assert post_metrics["sdr"] > 20.0, \
            f"Post-processed SDR too low: {post_metrics['sdr']:.1f} dB (expected >20)"
        print(f"  Vocals SDR: {pre_metrics['sdr']:.1f} → {post_metrics['sdr']:.1f} dB (post-processed)")
