/**
 * RAWMASTER for Suno — Popup Script
 */

const COMPANION_URL = 'http://127.0.0.1:5432';

async function checkStatus() {
  const el = document.getElementById('status');
  el.textContent  = 'Checking companion…';
  el.className    = 'status checking';

  try {
    const resp = await fetch(`${COMPANION_URL}/health`, {
      signal: AbortSignal.timeout(2500),
    });
    const data = await resp.json();
    if (resp.ok && data.status === 'ok') {
      el.textContent = `✅ Companion running  (v${data.version})`;
      el.className   = 'status ok';
      document.getElementById('store-link').textContent = 'rawmaster.smashd.tools';
      document.getElementById('store-link').href        = 'https://rawmaster.smashd.tools';
    } else {
      throw new Error();
    }
  } catch {
    el.textContent = '❌ Companion not running — install it';
    el.className   = 'status err';
  }
}

// Persist settings
document.getElementById('stems').addEventListener('change', (e) => {
  chrome.storage.local.set({ stems: e.target.value });
});
document.getElementById('midi').addEventListener('change', (e) => {
  chrome.storage.local.set({ midi: e.target.value });
});

// Load saved settings
chrome.storage.local.get(['stems', 'midi'], ({ stems, midi }) => {
  if (stems) document.getElementById('stems').value = stems;
  if (midi)  document.getElementById('midi').value  = midi;
});

checkStatus();
