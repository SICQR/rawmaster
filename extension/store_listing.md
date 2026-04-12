# Chrome Web Store Listing — RAWMASTER for Suno

---

## Metadata

| Field | Value |
|-------|-------|
| **Name** | RAWMASTER for Suno |
| **Category** | Music |
| **Language** | English |
| **Visibility** | Public |

---

## Short description (132 chars max)

```
Get clean stems and a remastered WAV from any Suno track — right in your browser. Requires RAWMASTER Companion app.
```

*(116 chars)*

---

## Detailed description

```
RAWMASTER for Suno adds a single button to every track on suno.com.

Click it → your track gets processed locally on your machine → you download a ZIP with:
  → Remastered WAV (spectral gating + LUFS normalisation + hard limiter)
  → 4 clean stems: vocals, drums, bass, other (HTDemucs fine-tuned)
  → MIDI extracted from bass stem (Basic-Pitch)
  → BPM and key detection written to info.txt

100% local processing. Your music never leaves your machine. No uploads. No cloud.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REQUIRES: RAWMASTER Companion app
£24 one-time at scanme2.gumroad.com/l/rawmaster

The Companion is a small Python app that runs locally on your Mac or Windows machine. It handles the heavy lifting (AI stem separation, audio processing) and sends the ZIP back to your browser.

If the Companion isn't running, the button shows you where to download it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SETTINGS (in the extension popup):
  → Choose 4 or 6 stems
  → Toggle MIDI extraction on/off

PRIVACY:
This extension does not collect, transmit, or store any user data. All processing happens via the local Companion app running at 127.0.0.1. Nothing leaves your device.

Full privacy policy: https://rawmaster.smashd.tools/privacy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Smash Daddys Audio Tools | Strip it back. Own the stems.
https://rawmaster.smashd.tools
```

---

## Screenshots needed (1280×800 or 640×400)

| # | Scene | Notes |
|---|-------|-------|
| 1 | RAWMASTER button visible on a Suno track card | Show button injected cleanly into the Suno UI |
| 2 | Popup showing "✅ Companion running" | Open popup while companion is running |
| 3 | Processing in progress ("⏳ Processing…") | Click button, catch the in-progress state |
| 4 | ZIP contents in Finder | Show remaster.wav, stems/, midi/, info.txt |
| 5 | Popup settings panel | stems + MIDI dropdowns |

---

## Store icon

Use `icons/icon128.png` — 128×128px, dark background, red R lettermark.

---

## Privacy policy URL

```
https://rawmaster.smashd.tools/privacy
```

---

## Permissions justification (required by Chrome Web Store)

| Permission | Justification |
|-----------|---------------|
| `storage` | Saves user preferences (stem count, MIDI toggle) locally |
| `downloads` | Triggers ZIP file download after processing |
| `host_permissions: suno.com` | Injects the RAWMASTER button into suno.com |
| `host_permissions: *.suno.ai` | Reads audio URLs from Suno's CDN |
| `host_permissions: 127.0.0.1:5432` | Communicates with the local RAWMASTER Companion daemon |

---

## Checklist before submission

- [ ] All 5 screenshots captured
- [ ] Privacy policy page live at rawmaster.smashd.tools/privacy
- [ ] Tested in Chrome with extension loaded in developer mode
- [ ] Tested companion connection check (with and without daemon running)
- [ ] Tested full download flow with a real Suno track
- [ ] Version in manifest.json matches submitted version
- [ ] Icons look correct at all sizes
