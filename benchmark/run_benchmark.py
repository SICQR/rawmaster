#!/usr/bin/env python3
"""
RAWMASTER — MUSDB18 Separation Quality Benchmark

Compares RAWMASTER's stem separation against ground truth stems from MUSDB18.
Measures SDR, SIR, SAR per stem across the test set.

Tests three configurations:
  1. Demucs htdemucs_ft only (baseline)
  2. Demucs ensemble (htdemucs_ft + htdemucs blend)
  3. RAWMASTER full pipeline (ensemble + BS-Roformer + post-processing)

Usage:
  RAWMASTER_SKIP_LICENSE=1 python benchmark/run_benchmark.py [--tracks N] [--fast]
"""

import os
import sys
import json
import time
import shutil
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
import musdb
import mir_eval

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("RAWMASTER_SKIP_LICENSE", "1")

STEMS = ["vocals", "drums", "bass", "other"]
RESULTS_DIR = Path(__file__).parent / "results"


def compute_metrics(reference, estimated, sr=44100):
    """Compute SDR, SIR, SAR between reference and estimated."""
    min_len = min(len(reference), len(estimated))
    if min_len < sr:  # need at least 1 second
        return {"sdr": float("nan"), "sir": float("nan"), "sar": float("nan")}

    ref = reference[:min_len]
    est = estimated[:min_len]

    # mono if needed
    if ref.ndim > 1:
        ref = ref.mean(axis=1)
    if est.ndim > 1:
        est = est.mean(axis=1)

    try:
        sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(
            ref[np.newaxis, :], est[np.newaxis, :]
        )
        return {"sdr": float(sdr[0]), "sir": float(sir[0]), "sar": float(sar[0])}
    except Exception as e:
        return {"sdr": float("nan"), "sir": float("nan"), "sar": float("nan")}


def separate_with_demucs_only(mix_path, output_dir, model="htdemucs_ft", shifts=2):
    """Baseline: single Demucs model, no post-processing."""
    from rawmaster import _run_demucs_model
    paths = _run_demucs_model(mix_path, output_dir, model, shifts=shifts, overlap=0.25)
    return {name: path for name, path in paths.items() if name in STEMS}


def separate_with_rawmaster(mix_path, output_dir, quality="fast"):
    """Full RAWMASTER pipeline: ensemble + Roformer + post-processing."""
    from rawmaster import separate_stems
    paths = separate_stems(mix_path, output_dir, six_stem=False, quality=quality)
    return {name: path for name, path in paths.items() if name in STEMS}


def benchmark_track(track, output_base, configs, fast=False):
    """Benchmark one MUSDB18 track across all configurations."""
    print(f"\n{'='*60}")
    print(f"  Track: {track.name}")
    print(f"  Duration: {track.audio.shape[0]/track.rate:.1f}s")
    print(f"{'='*60}")

    # Write mix to WAV
    track_dir = output_base / track.name.replace(" ", "_")
    track_dir.mkdir(parents=True, exist_ok=True)
    mix_path = track_dir / "mix.wav"
    sf.write(str(mix_path), track.audio, track.rate)

    # Write ground truth stems
    gt_dir = track_dir / "ground_truth"
    gt_dir.mkdir(exist_ok=True)
    ground_truth = {}
    for stem in STEMS:
        gt_audio = track.targets[stem].audio
        gt_path = gt_dir / f"{stem}.wav"
        sf.write(str(gt_path), gt_audio, track.rate)
        ground_truth[stem] = gt_audio

    results = {"track": track.name, "duration": track.audio.shape[0] / track.rate}

    for config_name, config_fn in configs.items():
        print(f"\n  --- {config_name} ---")
        config_dir = track_dir / config_name.replace(" ", "_")
        config_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        try:
            stem_paths = config_fn(mix_path, config_dir)
            elapsed = time.time() - t0
            print(f"  Separated in {elapsed:.1f}s")

            config_results = {"time": elapsed, "stems": {}}
            for stem in STEMS:
                if stem in stem_paths:
                    est_audio, _ = sf.read(str(stem_paths[stem]), dtype="float32")
                    metrics = compute_metrics(ground_truth[stem], est_audio, track.rate)
                    config_results["stems"][stem] = metrics
                    print(f"    {stem:8} SDR={metrics['sdr']:+.2f}  SIR={metrics['sir']:+.2f}  SAR={metrics['sar']:+.2f}")
                else:
                    print(f"    {stem:8} MISSING")
                    config_results["stems"][stem] = {"sdr": float("nan"), "sir": float("nan"), "sar": float("nan")}

            results[config_name] = config_results

        except Exception as e:
            print(f"  FAILED: {e}")
            results[config_name] = {"error": str(e)}

        # Cleanup temp dirs
        for d in config_dir.glob("_demucs_tmp"):
            shutil.rmtree(str(d), ignore_errors=True)
        for d in config_dir.glob("_roformer_tmp"):
            shutil.rmtree(str(d), ignore_errors=True)

    return results


def print_summary(all_results):
    """Print average SDR across all tracks per configuration."""
    print(f"\n\n{'='*70}")
    print(f"  BENCHMARK SUMMARY — {len(all_results)} tracks")
    print(f"{'='*70}\n")

    configs = set()
    for r in all_results:
        configs.update(k for k in r.keys() if k not in ("track", "duration"))

    for config in sorted(configs):
        sdr_values = {stem: [] for stem in STEMS}
        sir_values = {stem: [] for stem in STEMS}
        times = []

        for r in all_results:
            if config in r and "stems" in r[config]:
                for stem in STEMS:
                    if stem in r[config]["stems"]:
                        sdr = r[config]["stems"][stem]["sdr"]
                        sir = r[config]["stems"][stem]["sir"]
                        if np.isfinite(sdr):
                            sdr_values[stem].append(sdr)
                        if np.isfinite(sir):
                            sir_values[stem].append(sir)
                times.append(r[config].get("time", 0))

        print(f"  {config}")
        print(f"  {'─'*50}")
        avg_sdr_all = []
        for stem in STEMS:
            if sdr_values[stem]:
                avg_sdr = np.mean(sdr_values[stem])
                avg_sir = np.mean(sir_values[stem])
                avg_sdr_all.append(avg_sdr)
                print(f"    {stem:8}  SDR={avg_sdr:+.2f} dB  SIR={avg_sir:+.2f} dB  (n={len(sdr_values[stem])})")
        if avg_sdr_all:
            print(f"    {'AVERAGE':8}  SDR={np.mean(avg_sdr_all):+.2f} dB")
        if times:
            print(f"    Avg time: {np.mean(times):.1f}s per track")
        print()


def main():
    parser = argparse.ArgumentParser(description="RAWMASTER MUSDB18 Benchmark")
    parser.add_argument("--tracks", type=int, default=5, help="Number of tracks to benchmark (default: 5)")
    parser.add_argument("--fast", action="store_true", help="Use fast quality (shifts=2) for RAWMASTER configs too")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Use RAWMASTER_TEST_SHIFTS=1 for faster benchmarking on sample data
    if args.fast:
        os.environ["RAWMASTER_TEST_SHIFTS"] = "1"

    print("RAWMASTER MUSDB18 Benchmark")
    print(f"Tracks: {args.tracks}")
    print(f"Fast mode: {args.fast}")
    print()

    db = musdb.DB(subsets="test")
    tracks = db.tracks[:args.tracks]

    output_base = RESULTS_DIR / f"run_{int(time.time())}"
    output_base.mkdir(parents=True, exist_ok=True)

    configs = {
        "1_demucs_only": lambda m, o: separate_with_demucs_only(m, o, "htdemucs_ft", shifts=2),
        "2_rawmaster_full": lambda m, o: separate_with_rawmaster(m, o, quality="fast" if args.fast else "best"),
    }

    all_results = []
    for track in tracks:
        result = benchmark_track(track, output_base, configs, fast=args.fast)
        all_results.append(result)

    # Save raw results
    results_file = output_base / "results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nRaw results saved to: {results_file}")

    print_summary(all_results)


if __name__ == "__main__":
    main()
