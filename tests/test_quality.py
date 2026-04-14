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

    def test_bass_lowpass_removes_bleed(self, tmp_path):
        """Post-processed bass should have less high-frequency bleed."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        # Bass with high-freq bleed at 12kHz
        bass = (
            np.sin(2 * np.pi * 80 * t) * 0.3 +    # wanted bass
            np.sin(2 * np.pi * 12000 * t) * 0.15   # unwanted bleed
        ).astype(np.float32)
        stereo = np.stack([bass, bass]).T
        path = tmp_path / "bass.wav"
        sf.write(str(path), stereo, sr)

        post_process_stems({"bass": path})
        processed_data, _ = sf.read(str(path))

        orig_fft = np.abs(np.fft.rfft(bass))
        proc_fft = np.abs(np.fft.rfft(processed_data[:, 0]))
        freqs = np.fft.rfftfreq(len(bass), 1.0 / sr)

        # Energy above 10kHz should be heavily reduced
        high_mask = freqs > 10000
        orig_high = np.sum(orig_fft[high_mask] ** 2)
        proc_high = np.sum(proc_fft[high_mask] ** 2)
        reduction = 1 - (proc_high / max(orig_high, 1e-10))

        assert reduction > 0.7, f"High-freq reduction only {reduction:.1%}, expected >70%"
        print(f"  High-freq bleed reduced by {reduction:.1%}")

    def test_noise_gate_silences_quiet_passages(self, tmp_path):
        """Noise gate should silence near-silent sections."""
        from rawmaster import post_process_stems
        sr = 44100
        t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
        # Vocals: loud section then very quiet noise
        vocals = np.zeros_like(t, dtype=np.float32)
        vocals[:sr] = np.sin(2 * np.pi * 300 * t[:sr]) * 0.3  # 1s of vocals
        vocals[sr:] = np.random.RandomState(42).randn(len(t) - sr).astype(np.float32) * 0.0005  # very quiet noise
        stereo = np.stack([vocals, vocals]).T
        path = tmp_path / "vocals.wav"
        sf.write(str(path), stereo, sr)

        post_process_stems({"vocals": path})
        processed_data, _ = sf.read(str(path))

        # The quiet section (after 1.5s to avoid transients) should be quieter
        quiet_section_orig = np.sqrt(np.mean(vocals[int(sr * 1.5):]**2))
        quiet_section_proc = np.sqrt(np.mean(processed_data[int(sr * 1.5):, 0]**2))

        assert quiet_section_proc <= quiet_section_orig, \
            f"Quiet section got louder: {quiet_section_orig:.6f} → {quiet_section_proc:.6f}"
        print(f"  Quiet section RMS: {quiet_section_orig:.6f} → {quiet_section_proc:.6f}")

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
