const http = require('http');
const https = require('https');
const dns = require('dns');

if (dns && typeof dns.setDefaultResultOrder === 'function') {
  dns.setDefaultResultOrder('ipv4first');
}

// Check if a URL returns 200
function checkUrl(url, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode >= 200 && res.statusCode < 500);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

// Wait until URL is up, checking every intervalMs
// Returns true when up, false if maxWaitMs exceeded
async function waitForUrl(url, maxWaitMs = 60000, intervalMs = 1500) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const ok = await checkUrl(url);
    if (ok) return true;
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return false;
}

module.exports = { checkUrl, waitForUrl };
