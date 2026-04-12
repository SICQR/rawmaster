# RAWMASTER - Launch Posts

---

## Twitter / X - Launch Thread

Tweet 1 (main)
---
Just shipped RAWMASTER.

Drop any Suno track -> get back:
-> Remastered WAV (LUFS normalised)
-> 4 clean stems (HTDemucs)
-> MIDI from the bass line
-> BPM + key detection

100% local. Your music never leaves your machine.

GBP19 one-time -> scanme2.gumroad.com/l/rawmaster-cli
---

Tweet 2
---
The problem: Suno gives you a mixed MP3.

You want the stems. You want the MIDI. You want it mastered.

RAWMASTER runs entirely on your Mac or PC. No cloud, no subscription, no upload limits. Just your files.
---

Tweet 3
---
If you're on Chrome and use Suno daily:

RAWMASTER for Suno is a browser extension that adds a single button to every track card.

Click it -> ZIP downloads with everything inside.

The button talks to a local daemon. Zero data leaves your machine.
---

Tweet 4
---
Try the demo first (90 second limit, no install):

-> huggingface.co/spaces/smashd/rawmaster

Full version (no limits, Chrome extension, menu bar app):
-> rawmaster.smashd.tools

Built with HTDemucs + Basic-Pitch + pyloudnorm. All open-source under the hood.
---

Tweet 5 (close)
---
3 tiers:
- CLI only (GBP19) - terminal nerds
- Desktop companion (GBP29) - Chrome extension + menu bar
- Full toolkit bundle (GBP39) - everything + future tools

One-time. No subscription. License key, works offline.

-> rawmaster.smashd.tools
---

---

## Reddit - r/SunoAI

Title:
Built a local tool that pulls stems + MIDI from any Suno track - no upload, no cloud

Body:
Hey r/SunoAI - I made something that scratched my own itch and figured others might want it.

RAWMASTER is a local audio processing tool specifically designed around the Suno workflow.

What it does:
- Pulls the audio from any Suno track
- Runs HTDemucs fine-tuned model to separate into 4 clean stems (vocals, drums, bass, other)
- Extracts MIDI from the bass stem using Basic-Pitch
- Remasters the full mix: spectral noise gate -> LUFS normalisation to -14 -> hard limiter
- Detects BPM + key
- Packages everything into a ZIP

How it works:
Chrome extension adds a button to every Suno track card. Click it, the extension sends the
audio URL to a local Flask server running on your machine. Nothing is uploaded anywhere.

Try the demo (no install, 90 second limit):
-> huggingface.co/spaces/smashd/rawmaster

Full version:
-> rawmaster.smashd.tools (GBP19-GBP39 one-time, no subscription)

---

## Reddit - r/WeAreTheMusicMakers

Title:
RAWMASTER: local stem separation + MIDI extraction for AI-generated audio (HTDemucs + Basic-Pitch)

Body:
I've been using Suno to sketch ideas but the output is always a mixed-down file.

RAWMASTER packages HTDemucs + Basic-Pitch + pyloudnorm into a single local pipeline.

The pipeline:
1. Spectral noise gating (noisereduce)
2. HTDemucs fine-tuned model - 4 or 6 stems
3. Basic-Pitch neural MIDI extraction from bass stem
4. pyloudnorm LUFS normalisation to -14, hard limiter at -0.3 dBTP
5. librosa BPM + chroma key detection
6. All outputs bundled: remaster.wav, stems/, midi/, info.txt

100% local. Chrome extension for Suno, CLI, Gradio web UI. One-time license.

Demo (90s limit): huggingface.co/spaces/smashd/rawmaster
Full version: rawmaster.smashd.tools
GitHub: github.com/SICQR/rawmaster

---

## Product Hunt - Submission Draft

Name: RAWMASTER

Tagline:
Local stem separation + MIDI extraction for AI-generated audio

Description:
RAWMASTER turns any mixed audio file into a production-ready stem pack - on your machine.

Drop in a file (or click a button on Suno): get back a remastered WAV, 4 clean stems via
HTDemucs, MIDI from the bass line via Basic-Pitch, and BPM/key detection.

100% local. Your music never leaves your machine. One-time license (GBP19-GBP39).

Includes: Python CLI, Gradio web UI, Chrome extension for Suno, macOS menu bar daemon.

Try the demo: huggingface.co/spaces/smashd/rawmaster

Topics: Audio, Music, Developer Tools, AI, Productivity

Links:
- Website: https://rawmaster.smashd.tools
- Demo: https://huggingface.co/spaces/smashd/rawmaster
- GitHub: https://github.com/SICQR/rawmaster

Maker first comment:
Hey PH! I'm Phil - I make music tools under Smash Daddys Audio Tools.

The problem: AI music generators spit out a mixed-down file. As a producer, that's useless.

RAWMASTER packages HTDemucs + Basic-Pitch + pyloudnorm into a single local pipeline.
Chrome extension adds a one-click button to every Suno track card. Everything runs on your machine.

Free demo on HuggingFace -> rawmaster.smashd.tools for the full thing.

---

## Posting Order

1. HuggingFace Spaces - must be live before anything else
2. Twitter thread - post all 5 tweets as a thread
3. r/SunoAI - during peak hours (US evening)
4. r/WeAreTheMusicMakers - 30 mins after SunoAI post
5. Product Hunt - Tuesday or Wednesday at 00:01 PST

---

## Assets needed before posting

- [ ] HuggingFace Space live at huggingface.co/spaces/smashd/rawmaster
- [ ] Landing page live at rawmaster.smashd.tools
- [ ] Screenshot of extension button in Suno UI
- [ ] Demo GIF: button click -> ZIP download (15 seconds)
- [ ] Product Hunt thumbnail: 240x240, dark bg, red RAWMASTER wordmark