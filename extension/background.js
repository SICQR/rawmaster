/**
 * RAWMASTER for Suno — Service Worker (background.js)
 *
 * Responsibilities:
 * - Handle messages from content.js and popup.js
 * - Open Gumroad store page when companion is not found
 * - Keep extension alive during long processing jobs
 */

const STORE_URL = 'https://scanme2.gumroad.com/l/rawmaster';

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === 'install') {
    // Open a welcome tab on first install
    chrome.tabs.create({ url: 'https://rawmaster.smashd.tools' });
  }
  console.log('[RAWMASTER] Extension installed/updated');
});

// Message handler
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'openStore') {
    chrome.tabs.create({ url: STORE_URL });
    sendResponse({ ok: true });
  }
  return true; // Keep channel open for async responses
});
