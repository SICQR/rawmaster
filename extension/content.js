/**
 * RAWMASTER for Suno — Content Script
 * Injects "⬇ RAWMASTER" button into Suno track cards
 *
 * Suno's DOM changes frequently. This uses MutationObserver to handle
 * dynamically loaded content and tries multiple selectors in priority order.
 *
 * Audio URL resolution order:
 *  1. <audio> element src on the card
 *  2. data-audio-url / data-clip-id attributes
 *  3. CDN URL constructed from clip/song ID (cdn1.suno.ai/{id}.mp3)
 *  4. Network intercept cache (set by background.js)
 */

const COMPANION_URL = 'http://127.0.0.1:5432';
const BUTTON_CLASS   = 'rawmaster-btn';
const INJECTED_ATTR  = 'data-rawmaster-injected';

// Candidate selectors for Suno track cards (update if Suno changes DOM)
const CARD_SELECTORS = [
  '[data-testid="song-row"]',
  '[data-testid="clip-card"]',
  '[class*="song-row"]',
  '[class*="song-card"]',
  '[class*="SongCard"]',
  '[class*="clip-item"]',
  '[class*="ClipItem"]',
  '[class*="track-item"]',
  '[class*="TrackCard"]',
  'article[class*="song"]',
];

// Candidate selectors for the action toolbar inside a card
const TOOLBAR_SELECTORS = [
  '[class*="action-buttons"]',
  '[class*="ActionButtons"]',
  '[class*="song-actions"]',
  '[class*="SongActions"]',
  '[class*="controls"]',
  '[class*="Controls"]',
  '[class*="button-group"]',
  '[class*="ButtonGroup"]',
  '[data-testid="song-actions"]',
];

// ── Companion health check ─────────────────────────────────────────────────

let companionAlive = false;

async function pingCompanion() {
  try {
    const resp = await fetch(`${COMPANION_URL}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    companionAlive = resp.ok;
  } catch {
    companionAlive = false;
  }
}

// Poll every 15s so button state stays accurate
pingCompanion();
setInterval(pingCompanion, 15_000);


// ── Audio URL resolution ───────────────────────────────────────────────────

function findAudioUrl(card) {
  // 1. Explicit <audio> element
  const audioEl = card.querySelector('audio[src]');
  if (audioEl?.src?.startsWith('http')) return audioEl.src;

  // 2. data attributes on the card itself
  const attrs = [
    'data-audio-url', 'data-audio-src',
    'data-clip-audio', 'data-song-audio',
  ];
  for (const attr of attrs) {
    const val = card.getAttribute(attr);
    if (val?.startsWith('http')) return val;
  }

  // 3. Suno CDN URL built from clip/song ID
  const idAttrs = [
    'data-clip-id', 'data-song-id', 'data-id',
    'data-track-id', 'id',
  ];
  for (const attr of idAttrs) {
    const id = card.getAttribute(attr);
    // Suno clip IDs look like UUIDs: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    if (id && /^[0-9a-f-]{32,}$/i.test(id)) {
      return `https://cdn1.suno.ai/${id}.mp3`;
    }
  }

  // 4. Look inside the card for any suno CDN links
  for (const a of card.querySelectorAll('a[href], source[src]')) {
    const url = a.href || a.src;
    if (url && (url.includes('suno.ai') || url.includes('.mp3'))) return url;
  }

  // 5. Try to extract a clip ID from the card's React fibre data
  // (Suno stores clip data in __reactFiber / __reactProps)
  try {
    const fiberKey = Object.keys(card).find(k => k.startsWith('__reactFiber'));
    if (fiberKey) {
      const fiberStr = JSON.stringify(card[fiberKey]?.return?.memoizedProps || {});
      const match = fiberStr.match(/"audio_url":"(https:[^"]+)"/);
      if (match) return match[1];
      const idMatch = fiberStr.match(/"id":"([0-9a-f-]{32,})"/i);
      if (idMatch) return `https://cdn1.suno.ai/${idMatch[1]}.mp3`;
    }
  } catch {}

  return null;
}

// Get a human-readable track name for the download filename
function getTrackName(card) {
  const titleEl = card.querySelector(
    '[class*="title"], [class*="Title"], [data-testid="song-name"], h3, h4'
  );
  if (titleEl?.textContent?.trim()) {
    return titleEl.textContent.trim().replace(/[^a-zA-Z0-9 _-]/g, '').trim().slice(0, 60);
  }
  return 'rawmaster_output';
}


// ── Button injection ───────────────────────────────────────────────────────

function createButton() {
  const btn = document.createElement('button');
  btn.className  = BUTTON_CLASS;
  btn.textContent = '⬇ RAWMASTER';
  btn.title = 'Process with RAWMASTER (stems + remaster + MIDI)';
  btn.style.cssText = `
    background: #e63012;
    color: white;
    border: none;
    padding: 4px 10px;
    font-size: 11px;
    font-family: monospace;
    letter-spacing: 0.08em;
    font-weight: bold;
    cursor: pointer;
    border-radius: 3px;
    margin-left: 8px;
    white-space: nowrap;
    vertical-align: middle;
    transition: background 0.15s;
    flex-shrink: 0;
  `;
  btn.addEventListener('mouseenter', () => { btn.style.background = '#ff3d1a'; });
  btn.addEventListener('mouseleave', () => { btn.style.background = btn._errorState ? '#666' : '#e63012'; });
  return btn;
}

async function handleClick(e, card, btn) {
  e.stopPropagation();
  e.preventDefault();

  // Re-check companion on click
  await pingCompanion();

  if (!companionAlive) {
    btn._errorState = true;
    btn.textContent = '❌ Get Companion →';
    btn.style.background = '#555';
    setTimeout(() => {
      chrome.runtime.sendMessage({ action: 'openStore' });
      btn.textContent   = '⬇ RAWMASTER';
      btn.style.background = '#e63012';
      btn._errorState   = false;
      btn.disabled      = false;
    }, 1200);
    return;
  }

  const audioUrl = findAudioUrl(card);
  if (!audioUrl) {
    btn.textContent = '❌ No audio URL';
    setTimeout(() => { btn.textContent = '⬇ RAWMASTER'; btn.disabled = false; }, 2500);
    return;
  }

  btn.textContent = '⏳ Processing…';
  btn.disabled    = true;

  // Read settings from storage
  const { stems = '4', midi = 'true', reference = 'off', reference_url = '' } =
    await chrome.storage.local.get(['stems', 'midi', 'reference', 'reference_url']);

  const payload = {
    audio_url: audioUrl,
    stems:     parseInt(stems, 10),
    midi:      midi === 'true',
  };
  if (reference === 'on' && reference_url) {
    payload.reference_url = reference_url;
    btn.textContent = '🎯 Ref mastering…';
  }

  try {
    const resp = await fetch(`${COMPANION_URL}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${resp.status}`);
    }

    const blob     = await resp.blob();
    const url      = URL.createObjectURL(blob);
    const filename = `${getTrackName(card)}_rawmaster.zip`;
    const a        = document.createElement('a');
    a.href         = url;
    a.download     = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    btn.textContent = '✅ Done!';
    setTimeout(() => { btn.textContent = '⬇ RAWMASTER'; btn.disabled = false; }, 3000);

  } catch (err) {
    console.error('[RAWMASTER]', err);
    btn.textContent = `❌ ${err.message.slice(0, 28)}`;
    btn.disabled    = false;
    setTimeout(() => { btn.textContent = '⬇ RAWMASTER'; }, 4000);
  }
}

function injectButton(card) {
  if (card.getAttribute(INJECTED_ATTR)) return;
  card.setAttribute(INJECTED_ATTR, '1');

  const btn = createButton();
  btn.addEventListener('click', (e) => handleClick(e, card, btn));

  // Try to find the action toolbar
  for (const sel of TOOLBAR_SELECTORS) {
    const toolbar = card.querySelector(sel);
    if (toolbar) {
      toolbar.appendChild(btn);
      return;
    }
  }

  // Fallback: append to card itself
  card.style.position = 'relative';
  card.appendChild(btn);
}

function scanAndInject(root = document) {
  for (const sel of CARD_SELECTORS) {
    root.querySelectorAll(sel).forEach(injectButton);
  }
}


// ── MutationObserver ───────────────────────────────────────────────────────

const observer = new MutationObserver((mutations) => {
  for (const mutation of mutations) {
    for (const node of mutation.addedNodes) {
      if (!(node instanceof Element)) continue;
      // Check if the added node itself is a card
      for (const sel of CARD_SELECTORS) {
        if (node.matches(sel)) injectButton(node);
      }
      // Check descendants
      scanAndInject(node);
    }
  }
});

observer.observe(document.body, { childList: true, subtree: true });

// Initial scan
scanAndInject();
