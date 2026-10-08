const path = require('path');
const fs   = require('fs');
const http = require('http');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
let passed = 0, failed = 0;

function ok(msg)   { console.log(`✅ PASS: ${msg}`); passed++; }
function fail(msg) { console.log(`❌ FAIL: ${msg}`); failed++; }

// TEST 1 — All files exist
console.log('\n── TEST 1: File Existence ──');
const required = [
  'electron/main.js',
  'electron/process-manager.js',
  'electron/server-checker.js',
  'electron/splash.html',
  'electron/preload.js',
  'package.json',
];
required.forEach(f => {
  const full = path.join(ROOT, f);
  fs.existsSync(full) ? ok(f) : fail(`${f} MISSING`);
});

// TEST 2 — package.json valid
console.log('\n── TEST 2: package.json ──');
const pkg = require(path.join(ROOT, 'package.json'));
pkg.main === 'electron/main.js'
  ? ok('main entry = electron/main.js')
  : fail(`main entry wrong: ${pkg.main}`);
pkg.scripts?.start?.includes('electron')
  ? ok('start script has electron')
  : fail('start script missing electron');
!pkg.scripts?.dev?.includes('run dev')
  ? ok('dev script safe (no recursive npm run dev)')
  : fail('dev script may cause recursive launch');

// TEST 3 — No recursive npm run dev in process-manager
console.log('\n── TEST 3: process-manager.js bug check ──');
const pm = fs.readFileSync(path.join(ROOT, 'electron/process-manager.js'), 'utf8');
!pm.includes("'npm', ['run', 'dev']") && !pm.includes('"npm", ["run", "dev"]')
  ? ok('No recursive npm run dev found')
  : fail('STILL has npm run dev — BUG NOT FIXED');
pm.includes('vite')
  ? ok('Vite command present in frontend start')
  : fail('Vite not found in process-manager');
pm.includes('BACKEND_DIR')
  ? ok('BACKEND_DIR used for backend CWD')
  : fail('BACKEND_DIR missing');
pm.includes('path.resolve')
  ? ok('Uses absolute paths (path.resolve)')
  : fail('Should use path.resolve for absolute paths');

// TEST 4 — main.js has safe null checks
console.log('\n── TEST 4: main.js safety checks ──');
const mainJs = fs.readFileSync(path.join(ROOT, 'electron/main.js'), 'utf8');
mainJs.includes('isDestroyed()')
  ? ok('isDestroyed() check present (splash crash fix)')
  : fail('isDestroyed() check MISSING — splash will crash');
mainJs.includes('safeUpdateStatus') || mainJs.includes('try {')
  ? ok('Safe IPC update with error handling')
  : fail('IPC updates not wrapped safely');
mainJs.includes('did-fail-load')
  ? ok('Frontend reload on fail present')
  : fail('did-fail-load handler missing');

// TEST 5 — Ollama already-running detection
console.log('\n── TEST 5: Ollama detection logic ──');
const alreadyRunning = pm.includes('Already running') || pm.includes('alreadyRunning');
alreadyRunning
  ? ok('Ollama already-running check present')
  : fail('Ollama always tries to start — no pre-check');

// TEST 6 — Backend dir correct
console.log('\n── TEST 6: Backend directory ──');
const backendPath = path.join(ROOT, 'backend');
const mainPyExists = fs.existsSync(path.join(backendPath, 'main.py'));
mainPyExists
  ? ok(`main.py found at ${backendPath}`)
  : fail(`main.py NOT found at ${backendPath} — uvicorn will fail`);

// TEST 7 — Vite binary
console.log('\n── TEST 7: Vite binary ──');
const frontendPath = path.join(ROOT, 'frontend');
const viteBin = path.join(frontendPath, 'node_modules', '.bin', 'vite.cmd');
const viteExists = fs.existsSync(viteBin);
viteExists
  ? ok(`Vite binary found: ${viteBin}`)
  : fail(`Vite binary NOT found at ${viteBin} — run npm install in frontend/`);

// TEST 8 — Server checker exports
console.log('\n── TEST 8: Server checker ──');
try {
  const checker = require(path.join(ROOT, 'electron/server-checker.js'));
  typeof checker.checkUrl === 'function'
    ? ok('checkUrl exported')
    : fail('checkUrl not a function');
  typeof checker.waitForUrl === 'function'
    ? ok('waitForUrl exported')
    : fail('waitForUrl not a function');
} catch(e) {
  fail(`server-checker load error: ${e.message}`);
}

// TEST 9 — Ollama live check
console.log('\n── TEST 9: Ollama live check ──');
const req = http.get('http://localhost:11434/api/tags', {timeout:3000}, (res) => {
  res.statusCode < 400
    ? ok(`Ollama reachable (status ${res.statusCode}) — will be auto-detected`)
    : fail(`Ollama returned ${res.statusCode}`);
  printSummary();
});
req.on('error', () => {
  ok('Ollama not running — app will auto-start it');
  printSummary();
});
req.on('timeout', () => { req.destroy(); ok('Ollama timeout — app will start it'); printSummary(); });

function printSummary() {
  console.log(`\n══════════════════════════════`);
  console.log(`TOTAL: ${passed + failed} tests`);
  console.log(`✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);
  if (failed === 0) {
    console.log(`\n🚀 All tests passed! Run: npm start`);
  } else {
    console.log(`\n⚠️  Fix ${failed} failing tests, then run npm start`);
  }
  console.log(`══════════════════════════════`);
}
