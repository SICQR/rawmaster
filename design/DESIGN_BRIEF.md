# RAWMASTER — Design Brief for UI/UX Redesign

## What This Document Is

A complete description of RAWMASTER — what it does, who it's for, how it works, and what every screen needs to contain. Use this to design a modern, polished UI that can be implemented in code afterward.

---

## 1. PRODUCT OVERVIEW

**RAWMASTER** is a desktop audio processing tool for music producers. It takes any audio file and outputs stems, a remastered mix, MIDI, chord progressions, and BPM/key data — all processed locally on the user's machine.

**Tagline:** "Strip it back. Own the stems."

**One-line description:** Local stem separation, reference mastering, chord detection, MIDI extraction, and speed/pitch control — all in one tool for a one-time price.

**Target users:**
- Music producers who use AI generators (Suno, Udio) and need stems from their mixes
- DJs who want stems + BPM/key for remixing
- Musicians who want to learn songs (chord detection, speed control)
- Bedroom producers who can't afford monthly subscriptions

**Competitors:** Moises ($9.99/mo), LANDR ($6-39/mo), iZotope RX ($400)

**Pricing:** £19 CLI, £29 Desktop (the UI being designed), £39 Bundle

---

## 2. BRAND IDENTITY

**Brand name:** RAWMASTER by Smash Daddys Audio Tools
**Sub-brand:** Smash Daddys / Raw Convict Records

**Colors:**
- Primary background: `#080808` (near black)
- Card/panel background: `#111111`
- Hover/active: `#1a1a1a`
- Borders: `#2a2a2a`
- Accent (primary CTA, highlights): `#e63012` (red)
- Accent hover: `#ff3d1a`
- Text primary: `#f0ece4` (warm off-white)
- Text muted: `#888880`
- Success green: `#2ecc40`
- Warning amber: `#C8962C`

**Typography:**
- Headings: Space Mono (monospace, bold, wide tracking)
- Body text: Inter (clean sans-serif)
- Code/data values: monospace

**Tone:** Technical but accessible. Professional audio tool, not a toy. Dark, minimal, no clutter. Inspired by DAW interfaces and terminal aesthetics.

---

## 3. THE DESKTOP APP (Main Design Task)

The desktop app runs in a browser at `localhost:7860`. It's a single-page application with a two-column layout.

### 3A. LEFT COLUMN — Controls (Input)

**1. Audio Upload Zone**
- Large drag-and-drop area
- Accepts: MP3, WAV, FLAC, AIFF, OGG, M4A
- Shows waveform thumbnail after upload
- Shows filename, duration, file size
- "X" button to clear and start over

**2. Reference Track Upload (Optional)**
- Smaller drag-and-drop area below the main one
- Label: "Reference track (optional)"
- Help text below: "Upload a pro master as reference. Your track's EQ, loudness, and dynamics will be matched to it."
- When filled, shows the reference filename

**3. Stem Controls**
- Checkbox: "Separate stems" (default: on)
- When on, reveals:
  - Radio group: "4 stems" | "6 stems" | "max (12)"
    - 4 = vocals, drums, bass, other
    - 6 = adds guitar, piano
    - max = 12 sub-stems: lead vocals, backing vocals, kick, snare/hats, cymbals, bass, guitar, piano, sub synths, mid synths, high FX
  - Radio group: "Quality" — fast | good | best
    - fast: ~5 min, single model
    - good: ~15 min, single model, more shifts
    - best: ~30 min, 3-model ensemble (BS-Roformer + 2x Demucs)

**4. MIDI Controls**
- Checkbox: "Extract MIDI" (default: on, only visible when stems enabled)
- When on, reveals sub-checkbox: "Also from vocals" (default: off)

**5. Analysis Controls**
- Checkbox: "Detect chord progression" (default: on)

**6. Speed/Pitch Controls**
- Two number inputs side by side in a row:
  - Speed: default 1.0, range 0.25-4.0, step 0.05
    - Help text: "1.0 = normal, 0.5 = half speed, 2.0 = double"
  - Pitch (semitones): default 0, range -12 to +12, step 1
    - Help text: "0 = normal, +2 = up, -3 = down"

**7. Action Button**
- Full-width red button: "RAWMASTER IT"
- Bold, monospace text, prominent

### 3B. RIGHT COLUMN — Output (Results)

**1. Status Panel**
- Shows processing progress as colored HTML
- Step numbers: `[1/6] BPM + Key detected (9s)`
- Each step is color-coded:
  - In progress: amber/orange text
  - Completed: default text
  - Failed: red text
  - Final "DONE" line: green, bold
- During stem separation:
  - Red progress bar (0-100%) filling left to right
  - Per-stem checklist with icons:
    - 🎤 vocals ✓ (green when done)
    - 🥁 drums ... (gray when pending)
    - 🎸 bass ✓
    - etc.
  - Live elapsed timer updating every 5 seconds

**2. Remastered Track Player**
- Audio waveform with play/pause controls
- Shows after remaster completes
- Playable in-browser

**3. Download Buttons**
- "Download remastered WAV" — shows filename + file size (e.g., "track_RAWMASTER.wav  75.4 MB ↓")
- "Download stems (ZIP)" — appears after stems complete
- "Download MIDI (ZIP)" — appears after MIDI extraction

**4. Info Bar**
- Shows: "BPM: 125.0  |  Key: F# minor  |  Chords: C → F → G → Am"
- Updated in real-time as each analysis step completes

---

## 4. PROCESSING PIPELINE (What happens when user clicks "RAWMASTER IT")

In order, with status updates at each step:

1. **BPM + Key Detection** (~5s)
   - Uses librosa beat tracking + chroma correlation
   - Output: BPM value, key name, major/minor mode

2. **Chord Detection** (~5s, if enabled)
   - Beat-synchronous chroma analysis
   - Matches against 36 chord templates (major, minor, dom7)
   - Output: timestamped chord progression → chords.txt

3. **Remaster** (~10s)
   - Standard: spectral gating → LUFS -14.0 normalization → hard limiter -0.3 dBFS
   - With reference: matchering library matches EQ, loudness, dynamics to reference
   - Output: 24-bit WAV at 44.1kHz

4. **Speed/Pitch** (~5s, if changed from defaults)
   - Time-stretch via librosa
   - Pitch-shift preserving duration
   - Output: separate WAV with speed/pitch in filename

5. **Stem Separation** (5-30 min depending on quality)
   - Best quality: BS-Roformer for vocals (12.9 dB SDR) + Demucs ensemble
   - Max mode: 6-stem → cascade into 12 sub-stems
   - Post-processing: gentle highpass filters per stem type
   - Output: individual WAV files per stem

6. **MIDI Extraction** (~10s)
   - Basic-Pitch neural model on bass (and optionally vocals)
   - Output: .mid files

---

## 5. OUTPUT FILE STRUCTURE

```
rawmaster_output/
  {trackname}/
    {trackname}_RAWMASTER.wav        ← remastered 24-bit WAV
    {trackname}_0.8x_+2st.wav       ← speed/pitch adjusted (if enabled)
    info.txt                          ← BPM + key
    chords.txt                        ← chord progression with timestamps
    stems/
      vocals.wav                      ← or lead_vocals.wav in max mode
      drums.wav                       ← or kick.wav, snare_hats.wav, cymbals.wav
      bass.wav
      other.wav                       ← or sub_synths.wav, mid_synths.wav, high_fx.wav
      guitar.wav                      ← 6-stem and max mode
      piano.wav                       ← 6-stem and max mode
    midi/
      bass.mid
      vocals.mid                      ← if "also from vocals" enabled
```

---

## 6. LANDING PAGE (rawmaster.smashd.tools)

Single-page marketing site. Sections in order:

### Navigation (fixed top)
- Logo: "RAW**MASTER**" (MASTER in red)
- Links: Features | Pipeline | Pricing | FAQ | GitHub
- CTA button: "Get RAWMASTER" (red, links to #pricing)
- Mobile: hamburger menu that opens vertical overlay

### Hero
- Label: "SMASH DADDYS AUDIO TOOLS" (red, small caps)
- Title: "RAW\nMASTER" (huge, bold, monospace)
- Subtitle: "Strip it back. Own the stems."
- Value prop: "The stem upgrade Suno charges $22/month for — yours forever."
- Tech stack line: "HTDemucs · BS-Roformer · Basic-Pitch · matchering · All local"
- Two buttons:
  - Primary (red): "Get RAWMASTER — from £19" → #pricing
  - Secondary (outline): "Try free demo (90s limit)" → HuggingFace
- Below buttons: "One-time payment. No subscription. No cloud. No account."
- Terminal mockup showing a real CLI session with colored output

### Features Grid (9 cards)
1. 🥁 4-STEM SEPARATION — HTDemucs vocals/drums/bass/other
2. 🎛 REMASTER PIPELINE — Spectral gating + LUFS + limiter
3. 🎯 REFERENCE MASTERING — [NEW badge] Match EQ/loudness to a reference
4. 🎹 MIDI EXTRACTION — Bass + vocals to polyphonic MIDI
5. 🔍 BPM + KEY + CHORDS — Beat tracking, key, timestamped chord chart
6. ⏩ SPEED + PITCH CONTROL — Time-stretch and pitch-shift
7. 📂 BATCH MODE — Process whole folders
8. 🔒 100% LOCAL — No uploads, no cloud, no subscription
9. (optional: 12-STEM MAX MODE — lead/backing vocals, kick, snare, cymbals, synths, FX)

### Pipeline (vertical steps)
01. Load + Resample (44.1kHz, float32)
02. Spectral Gating (noisereduce)
03. LUFS Normalisation (pyloudnorm, -14.0)
04. Hard Limiter (-0.3 dBFS)
04b. Reference Mastering (optional, matchering)
05. Chord Detection (librosa chroma + templates)
06. Speed/Pitch (librosa time_stretch + pitch_shift)
07. Stem Separation (BS-Roformer + Demucs ensemble)
08. MIDI Extraction (Basic-Pitch)

### Output Structure
Tree visualization showing the file output structure

### CLI Reference (command grid)
- BASIC: `rawmaster track.mp3`
- STEMS: `rawmaster track.mp3 --stems`
- STEMS + MIDI: `rawmaster track.mp3 --stems --midi`
- 6-STEM: `rawmaster track.mp3 --stems 6`
- MAX (12-STEM): `rawmaster track.mp3 --stems max`
- REFERENCE: `rawmaster track.mp3 --ref pro_mix.wav`
- CHORDS: `rawmaster track.mp3 --chords`
- SPEED/PITCH: `rawmaster track.mp3 --speed 0.8 --pitch +2`
- BATCH: `rawmaster ./folder/ --stems`
- INFO ONLY: `rawmaster track.mp3 --info`

### No Cloud Section
"Your music stays on your machine."
Pills: No cloud processing | No subscription | No internet after setup | macOS + Windows + Linux | CPU + GPU

### FAQ (6 accordion items)
1. How long does processing take?
2. What are the system requirements?
3. What does reference mastering do?
4. Can I use outputs commercially?
5. What audio formats are supported?
6. What's the refund policy?

### Pricing (3 cards)
- CLI: £19 — terminal power users
- DESKTOP [MOST POPULAR]: £29 — drag-and-drop UI
- TOOLKIT: £39 — RAWMASTER + GRANULE reverb plugin

### Comparison Table
| Feature | CLI | DESKTOP | TOOLKIT |
Stem separation, remaster, reference mastering, MIDI, chords, speed/pitch, batch, GUI, GRANULE

### Footer
- Logo + site nav (Features, Pipeline, Pricing, FAQ)
- External links (GitHub, Demo, Gumroad)
- Legal links (Terms, Privacy, Attributions)
- Copyright: © 2026 Smash Daddys / Raw Convict Records

---

## 7. CHROME EXTENSION POPUP (280px wide)

Small settings panel for the browser extension:

- Header: ⚡ RAWMASTER / for Suno
- Status indicator: green dot + "Companion running (v1.0.0)" or red dot + "Companion not running"
- Settings:
  - Stems: dropdown (4 stems / 6 stems) with ? tooltip
  - MIDI: dropdown (Yes / No) with ? tooltip
  - Reference master: dropdown (Off / On) with ? tooltip
  - When reference is On: URL text input for reference track URL
- Footer: version + link to rawmaster.smashd.tools

---

## 8. WEB APP (rawmaster.smashd.tools/app or separate subdomain)

Lightweight browser-based BPM + key detection only (no stems, no mastering — those require the paid desktop version).

- Header: "RAWMASTER web" badge
- Drag-and-drop audio upload
- Waveform visualization
- Results: BPM, Key, Duration, Sample Rate in stat cards
- Copy button to copy results
- Upsell CTA: "Need stems, MIDI, or reference mastering? Get Full RAWMASTER — from £19"
- Footer: "Powered by RAWMASTER · Web Audio API · 100% client-side"

---

## 9. USER LIBRARY / HISTORY

Users process many tracks over time. They need to find, replay, and re-download their outputs without reprocessing. The library is a second major view in the desktop app.

### Library View (Tab or sidebar toggle alongside the main processing view)

**Layout:** Grid or list of previously processed tracks, sorted by most recent.

**Per-track card shows:**
- Track name (filename)
- Date processed
- Thumbnail waveform
- Tags showing what was done: "4 stems" | "MIDI" | "Reference mastered" | "Chords"
- BPM + Key badges
- Quick actions: Play remaster | Open folder | Re-process

**Filtering/sorting:**
- Sort by: date, name, BPM, key
- Filter by: has stems, has MIDI, has chords, key (for DJ use — find all tracks in Am)
- Search by filename

**Import tracks:**
- Drag-and-drop files or folders into the library to import
- "Import folder" button to scan a music folder (recursively finds all audio files)
- Imports from DJ software: Rekordbox XML, Serato crates, iTunes/Music.app library
- Each imported track shows as "unprocessed" until user runs it through RAWMASTER
- Bulk select + "Process all" for batch operations
- Import from cloud: paste a Suno/Udio URL to download and add to library

**How it works technically:**
- Scan the `rawmaster_output/` directory (or a user-configured output directory)
- Each subdirectory = one processed track
- Read `info.txt` for BPM/key, `chords.txt` for chord data
- Check for existence of `stems/`, `midi/` to show tags
- Imported but unprocessed tracks stored in a `rawmaster_library/` directory
- Lightweight JSON index file for fast browsing (rebuilt from filesystem on startup)
- No database needed — filesystem is the source of truth

**Quick play:**
- Click any track to play the remastered WAV in-browser
- Click any stem to solo it
- Side-by-side comparison: original vs remastered

**Stem mixer (advanced, future feature):**
- For tracks with stems: show a simple mixer with volume sliders per stem
- Mute/solo each stem
- Export the custom mix as a new WAV
- This is the "Moises practice mode" equivalent

**DJ Integration:**
- Export library as CSV: track name, BPM, key, chords, file path
- Compatible with Rekordbox, Serato, Traktor import
- Filter by key for harmonic mixing

---

## 10. DESIGN PRINCIPLES

1. **Dark-first.** This is an audio tool. Dark backgrounds, subtle borders, nothing bright except the red accent.
2. **Information density.** Producers want data — BPM, key, chords, progress percentage, file sizes. Show it all, but hierarchically.
3. **Terminal aesthetic.** Monospace for headings and data values. The CLI heritage should be visible in the UI.
4. **No clutter.** Every element earns its space. Hide secondary controls until relevant (MIDI options hidden until stems are enabled).
5. **Progress is king.** The longest operation (stem separation) can take 30 minutes. The UI must constantly show it's alive — timer, progress bar, per-stem checklist.
6. **Trust signals.** One-time pricing, local processing, open-source models. These are competitive advantages — make them visually prominent.

---

## 10. KEY SCREENS TO DESIGN

In priority order:

1. **Desktop app main screen** — the two-column layout described in Section 3
2. **Desktop app during processing** — progress bar, stem checklist, timer all visible
3. **Desktop app after completion** — all outputs ready, download buttons active
4. **Landing page hero + features** — the first impression
5. **Landing page pricing section** — conversion-critical
6. **Landing page mobile view** — hamburger menu, stacked layout
7. **Chrome extension popup** — small but polished

---

## 11. TECHNICAL NOTES FOR IMPLEMENTATION

- The desktop app is built with Gradio (Python). Gradio supports custom CSS and HTML components.
- The landing page is pure HTML + CSS (no framework). Inline styles, Google Fonts (Space Mono + Inter).
- The web app is Next.js + Tailwind CSS + React.
- The Chrome extension popup is vanilla HTML + CSS + JS (280px wide, dark theme).
- All pages share the same color palette and typography.
