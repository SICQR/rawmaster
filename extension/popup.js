/**
 * RAWMASTER for Suno — Popup Script
 */

const COMPANION_URL = 'http://127.0.0.1:5432';

async function checkStatus() {
  const el = document.getElementById('status');
  const textEl = document.getElementById('status-text');
  textEl.textContent = 'Checking companion…';
  el.className = 'status checking';
  el.innerHTML = '<span class="dot-spin"></span> <span id="status-text">Checking companion…</span>';

  try {
    const resp = await fetch(`${COMPANION_URL}/health`, {
      signal: AbortSignal.timeout(2500),
    });
    const data = await resp.json();
    if (resp.ok && data.status === 'ok') {
      el.innerHTML = `<span class="dot dot-green"></span> <span id="status-text">Companion running (v${data.version})</span>`;
      el.className = 'status ok';
      document.getElementById('store-link').textContent = 'rawmaster.smashd.tools';
      document.getElementById('store-link').href = 'https://rawmaster.smashd.tools';
    } else {
      throw new Error();
    }
  } catch {
    el.innerHTML = '<span class="dot dot-red"></span> <span id="status-text">Companion not running</span>';
    el.className = 'status err';
  }
}

// Persist settings
document.getElementById('stems').addEventListener('change', (e) => {
  chrome.storage.local.set({ stems: e.target.value });
});
document.getElementById('midi').addEventListener('change', (e) => {
  chrome.storage.local.set({ midi: e.target.value });
});
document.getElementById('reference').addEventListener('change', (e) => {
  chrome.storage.local.set({ reference: e.target.value });
  document.getElementById('ref-url-row').style.display = e.target.value === 'on' ? 'flex' : 'none';
});

// Reference URL validation
const refUrlInput = document.getElementById('ref-url');
refUrlInput.addEventListener('input', (e) => {
  const val = e.target.value.trim();
  chrome.storage.local.set({ reference_url: val });
  if (!val) {
    e.target.className = '';
    return;
  }
  const isValid = /^https?:\/\/.+\.(mp3|wav|flac|aiff|ogg|m4a)(\?.*)?$/i.test(val);
  e.target.className = isValid ? 'ref-url-valid' : 'ref-url-invalid';
});

// Load saved settings
chrome.storage.local.get(['stems', 'midi', 'reference', 'reference_url'], ({ stems, midi, reference, reference_url }) => {
  if (stems) document.getElementById('stems').value = stems;
  if (midi) document.getElementById('midi').value = midi;
  if (reference) {
    document.getElementById('reference').value = reference;
    document.getElementById('ref-url-row').style.display = reference === 'on' ? 'flex' : 'none';
  }
  if (reference_url) {
    refUrlInput.value = reference_url;
    const isValid = /^https?:\/\/.+\.(mp3|wav|flac|aiff|ogg|m4a)(\?.*)?$/i.test(reference_url);
    refUrlInput.className = isValid ? 'ref-url-valid' : 'ref-url-invalid';
  }
});

checkStatus();
