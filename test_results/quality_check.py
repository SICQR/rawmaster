#!/usr/bin/env python3
"""
RAWMASTER Quality Gate
Run: python3 test_results/quality_check.py
Exit 0 = all checks pass. Exit 1 = fail (do not ship).
"""

import sys
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT_ROOT = ROOT / "rawmaster_output"
if not OUTPUT_ROOT.exists():
    candidates = sorted(ROOT.rglob("rawmaster_output"))
    if candidates:
        OUTPUT_ROOT = candidates[0]

PASS = True
issues = []
passing = []


def check(condition, pass_msg, fail_msg):
    global PASS
    if condition:
        passing.append(f"✅  {pass_msg}")
    else:
        issues.append(f"❌  {fail_msg}")
        PASS = False


# ── 1. Remaster file ──────────────────────────────────────────────────────

remasters = list(OUTPUT_ROOT.rglob("*_RAWMASTER.wav"))
check(len(remasters) > 0, "Remaster file found", "No *_RAWMASTER.wav found")

if remasters:
    data, sr = sf.read(str(remasters[0]))
    if data.ndim == 1:
        data = data[:, np.newaxis]

    meter = pyln.Meter(sr)
    try:
        lufs = meter.integrated_loudness(data)
        check(lufs is not None and np.isfinite(lufs),
              f"LUFS measurable: {lufs:.1f}", "LUFS measurement failed")
        check(-20.0 < lufs < -8.0,
              f"Remaster loudness OK: {lufs:.1f} LUFS",
              f"Remaster loudness out of range: {lufs:.1f} LUFS (expected -20 to -8)")
    except Exception as e:
        issues.append(f"❌  LUFS measurement error: {e}")
        PASS = False

    peak = float(np.max(np.abs(data)))
    check(peak <= 1.0,
          f"No clipping (peak {peak:.4f})",
          f"Remaster clips! peak={peak:.4f}")

    check(sr >= 44100,
          f"Sample rate OK: {sr}Hz",
          f"Sample rate too low: {sr}Hz")

    check(data.shape[1] == 2,
          "Stereo output confirmed",
          f"Not stereo: shape={data.shape}")

# ── 2. Stems ─────────────────────────────────────────────────────────────

stems = list(OUTPUT_ROOT.rglob("stems/*.wav"))
check(len(stems) >= 4,
      f"{len(stems)} stems created",
      f"Expected 4+ stems, found {len(stems)}")

for stem in stems:
    data, sr = sf.read(str(stem))
    rms = float(np.sqrt(np.mean(np.array(data, dtype=float) ** 2)))
    # warn only — some stems legitimately have low energy
    if rms < 0.0001:
        issues.append(f"⚠️   {stem.name} may be silent (RMS={rms:.6f})")
    else:
        passing.append(f"✅  {stem.name} has signal (RMS={rms:.4f})")

# ── 3. MIDI ───────────────────────────────────────────────────────────────

midis = list(OUTPUT_ROOT.rglob("midi/*.mid"))
if not midis:
    issues.append("⚠️   No MIDI files found (non-fatal — bass may be silent in test audio)")
else:
    passing.append(f"✅  {len(midis)} MIDI file(s) created")
    try:
        import mido
        for midi_file in midis:
            mid = mido.MidiFile(str(midi_file))
            notes = sum(1 for t in mid.tracks for m in t if m.type == "note_on")
            passing.append(f"✅  {midi_file.name}: {notes} note events, {mid.length:.1f}s")
    except ImportError:
        passing.append("   (mido not installed — skipping MIDI note count)")

# ── 4. info.txt ───────────────────────────────────────────────────────────

infos = list(OUTPUT_ROOT.rglob("info.txt"))
check(len(infos) > 0, "info.txt present", "No info.txt found")

if infos:
    content = infos[0].read_text()
    check("BPM" in content and "Key" in content,
          f"info.txt valid: {content.strip()!r}",
          f"info.txt malformed: {content!r}")

# ── Report ────────────────────────────────────────────────────────────────

print()
print("=" * 56)
print("  RAWMASTER Quality Gate")
print("=" * 56)
for msg in passing:
    print(f"  {msg}")
if issues:
    print()
    for msg in issues:
        print(f"  {msg}")
print()
print("=" * 56)

if PASS:
    print("  ✅  ALL CHECKS PASSED — READY FOR MARKET")
    print("=" * 56)
    sys.exit(0)
else:
    fatal = [i for i in issues if i.startswith("❌")]
    warnings = [i for i in issues if i.startswith("⚠️")]
    print(f"  {'❌' if fatal else '⚠️ '}  {len(fatal)} FAILURE(S), {len(warnings)} WARNING(S)")
    print("=" * 56)
    sys.exit(1 if fatal else 0)
