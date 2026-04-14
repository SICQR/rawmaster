#!/usr/bin/env python3
"""
RAWMASTER vs Suno — Stem Comparison Tool

Compares RAWMASTER's stem output against Suno Pro's stem output
on the same input track, using SDR/SIR/SAR metrics.

Usage:
  python benchmark/suno_comparison.py \\
    --mix original_track.wav \\
    --rawmaster-dir rawmaster_output/stems/ \\
    --suno-dir suno_stems/ \\
    --ground-truth-dir ground_truth_stems/   (optional — if you have original multitracks)

If no ground truth is provided, compares the two outputs against each other
(relative comparison — which is closer to the original mix when remixed).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent.parent))

STEMS = ["vocals", "drums", "bass", "other"]


def load_stem(directory, stem_name):
    """Load a stem from a directory, trying common naming patterns."""
    patterns = [
        f"{stem_name}.wav",
        f"{stem_name}.mp3",
        f"*{stem_name}*.wav",
        f"*{stem_name}*.mp3",
        f"*(Vocals)*" if stem_name == "vocals" else f"*({stem_name.title()})*",
    ]
    d = Path(directory)
    for pattern in patterns:
        matches = list(d.glob(pattern))
        if matches:
            audio, sr = sf.read(str(matches[0]), dtype="float32")
            return audio, sr, matches[0].name
    return None, None, None


def compute_sdr(ref, est):
    """Compute SDR between reference and estimated."""
    import mir_eval
    min_len = min(len(ref), len(est))
    if ref.ndim > 1: ref = ref[:min_len].mean(axis=1)
    else: ref = ref[:min_len]
    if est.ndim > 1: est = est[:min_len].mean(axis=1)
    else: est = est[:min_len]

    try:
        sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(
            ref[np.newaxis, :], est[np.newaxis, :]
        )
        return {"sdr": float(sdr[0]), "sir": float(sir[0]), "sar": float(sar[0])}
    except:
        return {"sdr": float("nan"), "sir": float("nan"), "sar": float("nan")}


def remix_stems(stem_dir, stem_names=STEMS):
    """Remix stems back to a stereo mix by summing."""
    mix = None
    sr = None
    for stem in stem_names:
        audio, file_sr, name = load_stem(stem_dir, stem)
        if audio is not None:
            sr = file_sr
            if mix is None:
                mix = audio.copy()
            else:
                min_len = min(len(mix), len(audio))
                mix = mix[:min_len] + audio[:min_len]
    return mix, sr


def main():
    parser = argparse.ArgumentParser(description="RAWMASTER vs Suno Comparison")
    parser.add_argument("--mix", required=True, help="Original mix audio file")
    parser.add_argument("--rawmaster-dir", required=True, help="RAWMASTER stems directory")
    parser.add_argument("--suno-dir", required=True, help="Suno stems directory")
    parser.add_argument("--ground-truth-dir", help="Ground truth stems directory (optional)")
    args = parser.parse_args()

    print("RAWMASTER vs Suno — Stem Comparison")
    print("=" * 60)

    # Load original mix
    mix_audio, mix_sr = sf.read(args.mix, dtype="float32")
    print(f"\nOriginal mix: {Path(args.mix).name} ({len(mix_audio)/mix_sr:.1f}s)")

    if args.ground_truth_dir:
        # Full comparison against ground truth
        print(f"\nGround truth provided — computing absolute SDR")
        print(f"\n{'Stem':12} {'RAWMASTER SDR':>15} {'Suno SDR':>15} {'Winner':>10}")
        print("-" * 60)

        for stem in STEMS:
            gt, _, _ = load_stem(args.ground_truth_dir, stem)
            rm, _, rm_name = load_stem(args.rawmaster_dir, stem)
            suno, _, suno_name = load_stem(args.suno_dir, stem)

            if gt is None:
                print(f"{stem:12} {'no ground truth':>15}")
                continue

            rm_metrics = compute_sdr(gt, rm) if rm is not None else {"sdr": float("nan")}
            suno_metrics = compute_sdr(gt, suno) if suno is not None else {"sdr": float("nan")}

            rm_sdr = rm_metrics["sdr"]
            suno_sdr = suno_metrics["sdr"]
            winner = "RAWMASTER" if rm_sdr > suno_sdr else "Suno" if suno_sdr > rm_sdr else "Tie"
            diff = rm_sdr - suno_sdr

            print(f"{stem:12} {rm_sdr:>+12.2f} dB {suno_sdr:>+12.2f} dB {winner:>10} ({diff:+.1f})")

    else:
        # Relative comparison: which remix is closer to the original mix?
        print(f"\nNo ground truth — comparing remixed stems vs original mix")

        rm_remix, _ = remix_stems(args.rawmaster_dir)
        suno_remix, _ = remix_stems(args.suno_dir)

        if rm_remix is not None:
            rm_metrics = compute_sdr(mix_audio, rm_remix)
            print(f"\nRAWMASTER remix vs original: SDR={rm_metrics['sdr']:+.2f} dB")
        else:
            print("\nRAWMASTER: no stems found")

        if suno_remix is not None:
            suno_metrics = compute_sdr(mix_audio, suno_remix)
            print(f"Suno remix vs original:     SDR={suno_metrics['sdr']:+.2f} dB")
        else:
            print("Suno: no stems found")

        if rm_remix is not None and suno_remix is not None:
            diff = rm_metrics["sdr"] - suno_metrics["sdr"]
            winner = "RAWMASTER" if diff > 0.5 else "Suno" if diff < -0.5 else "Tie"
            print(f"\nWinner: {winner} (delta: {diff:+.1f} dB)")

    print()


if __name__ == "__main__":
    main()
