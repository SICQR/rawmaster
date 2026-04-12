# RAWMASTER — Gumroad Product Copy
Ready to paste into Gumroad product creation form.

---

## PRODUCT 1 — RAWMASTER CLI

| Field | Value |
|-------|-------|
| **Name** | RAWMASTER — Stem Separation & Remaster Tool (CLI) |
| **Price** | £19.00 GBP |
| **URL slug** | `rawmaster-cli` |
| **Final URL** | https://scanme2.gumroad.com/l/rawmaster-cli |
| **License keys** | ✅ ENABLE |
| **Call to action** | Download RAWMASTER |

**Summary line (shown in search/preview):**
> The stem upgrade Suno charges $22/month for — yours forever.

**Description (paste into body):**

---

RAWMASTER is a command-line tool that turns any audio file into clean stems, a remastered WAV, MIDI, BPM and key detection — all running locally on your machine.

**What you get:**
→ 4-stem separation via HTDemucs v4 (vocals / drums / bass / other)
→ Remaster pipeline: spectral gating + LUFS normalisation + hard limiter
→ MIDI extraction from bass stem (polyphonic, via Basic-Pitch)
→ BPM + musical key detection on every track
→ Batch mode: process a whole folder in one command
→ 100% local — no uploads, no cloud, no ongoing costs

**Works on:** macOS (M1/M2/M3/M4 + Intel) + Windows
**Requires:** Python 3.10+ (install script handles the rest)

**Commands:**
```
rawmaster track.mp3                  → remaster only
rawmaster track.mp3 --stems          → remaster + 4 stems
rawmaster track.mp3 --stems --midi   → + MIDI from bass
rawmaster ./folder/ --stems          → batch mode
```

**License:** One-time payment. One machine. No expiry.

---

**Delivery:** ZIP file containing:
- `rawmaster.py`
- `install.sh`
- `install.bat`
- `requirements.txt`
- `README.md`

Or direct them to the GitHub repo: https://github.com/SICQR/rawmaster

---

## PRODUCT 2 — RAWMASTER DESKTOP

| Field | Value |
|-------|-------|
| **Name** | RAWMASTER — Desktop App (Drag & Drop UI) |
| **Price** | £29.00 GBP |
| **URL slug** | `rawmaster` |
| **Final URL** | https://scanme2.gumroad.com/l/rawmaster |
| **License keys** | ✅ ENABLE |
| **Call to action** | Download RAWMASTER Desktop |

**Summary line:**
> Drag. Drop. Done. The full RAWMASTER pipeline with a visual interface.

**Description (paste into body):**

---

RAWMASTER Desktop is the drag-and-drop version of RAWMASTER — same powerful pipeline, no terminal required.

Open the app in your browser, drop your track, click the button. You get back a remastered WAV, 4 clean stems, MIDI, and BPM + key info. All local, all private, all yours.

**What you get:**
→ Everything in the CLI version
→ Drag-and-drop browser UI (runs at localhost:7860)
→ In-browser audio playback of remastered track
→ One-click download of stems ZIP and MIDI ZIP
→ Visual progress indicator as each stage completes

**Works on:** macOS + Windows + Linux
**Requires:** Python 3.10+ (install script handles the rest)

**License:** One-time payment. One machine. No expiry.

---

**Delivery:** ZIP file containing all CLI files + `app.py` + updated `install.sh`

---

## PRODUCT 3 — SMASH DADDYS TOOLKIT (BUNDLE)

| Field | Value |
|-------|-------|
| **Name** | Smash Daddys Toolkit — GRANULE + RAWMASTER |
| **Price** | £39.00 GBP |
| **URL slug** | `rawmaster-bundle` |
| **Final URL** | https://scanme2.gumroad.com/l/rawmaster-bundle |
| **License keys** | ✅ ENABLE |
| **Call to action** | Get the Toolkit |

**Summary line:**
> Both Smash Daddys tools. One price.

**Description (paste into body):**

---

The Smash Daddys Toolkit contains both audio tools:

**GRANULE** — Granular reverb browser plugin (£15 value)
Experimental granular reverb effect. Runs in any browser. No installation.

**RAWMASTER Desktop** — Stem separation + remaster tool (£29 value)
HTDemucs stems, spectral gating remaster, MIDI extraction, BPM + key detection.

Total value: £44. Bundle price: £39.

**License:** One-time payment. One machine per tool. No expiry.

---

**Delivery:** ZIP containing both products' files.

---

## POST-PURCHASE STEPS

1. Create all 3 products on Gumroad
2. Enable license keys on each
3. Copy the `product_id` from each product's Settings > Integrations page
4. Update `rawmaster.py` line 35: `GUMROAD_PRODUCT_ID = "your_real_product_id"`
5. Commit + push to GitHub
6. Test the full license validation flow with a test purchase

## GUMROAD API NOTE

For products created after Jan 2023, Gumroad's license verification API uses `product_id` (NOT `product_permalink`). The `product_id` is a short alphanumeric string found in the product's Settings > Integrations panel.

The verification endpoint used in rawmaster.py:
```
POST https://api.gumroad.com/v2/licenses/verify
  product_id: <your_product_id>
  license_key: <customer_key>
  increment_uses_count: false
```
