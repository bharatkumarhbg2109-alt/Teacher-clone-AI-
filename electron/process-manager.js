const { spawn } = require('child_process');
const path = require('path');
const { checkUrl, waitForUrl } = require('./server-checker');

// Absolute paths — no relative path issues
const ROOT         = path.resolve(__dirname, '..');
const BACKEND_DIR  = path.resolve(ROOT, 'backend');
const FRONTEND_DIR = path.resolve(ROOT, 'frontend');

const OLLAMA_URL   = 'http://localhost:11434/api/tags';
const BACKEND_URL  = 'http://localhost:8002/';
const FRONTEND_URL = 'http://localhost:5175/';

const processes = [];

// ── Free port if already in use ───────────────────────
function killPort(port) {
  if (process.platform === 'win32') {
    try {
      const { execSync } = require('child_process');
      const out = execSync(`netstat -ano | findstr :${port}`, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      });
      const lines = out.trim().split('\n');
      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0' && pid !== String(process.pid)) {
          console.log(`[Port] Freeing port ${port} (terminating stale PID ${pid})`);
          try {
            execSync(`taskkill /pid ${pid} /f /t`, { stdio: 'ignore' });
          } catch (_) {}
        }
      }
    } catch (_) {}
  }
}

// ── Spawn helper ──────────────────────────────────────
function spawnProc(cmd, args, cwd, label, extraEnv = {}) {
  console.log(`[${label}] CMD: ${cmd} ${args.join(' ')}`);
  console.log(`[${label}] CWD: ${cwd}`);

  const env = {
    ...process.env,
    ...extraEnv,
    // Ensure Python finds modules in backend dir
    PYTHONPATH: BACKEND_DIR,
  };

  const proc = spawn(cmd, args, {
    cwd,
    shell: true,
    windowsHide: true,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  proc.stdout.on('data', d =>
    console.log(`[${label}] ${d.toString().trim()}`));
  proc.stderr.on('data', d =>
    console.error(`[${label}] ERR: ${d.toString().trim()}`));
  proc.on('close', code =>
    console.log(`[${label}] exited code=${code}`));
  proc.on('error', err =>
    console.error(`[${label}] spawn error: ${err.message}`));

  processes.push({ proc, label });
  return proc;
}

// ── Ollama ────────────────────────────────────────────
async function startOllama() {
  console.log('[Ollama] Checking if already running...');
  const alreadyRunning = await checkUrl(OLLAMA_URL);
  if (alreadyRunning) {
    console.log('[Ollama] Already running — skipping start');
    return true;
  }
  console.log('[Ollama] Not running — starting now...');
  spawnProc('ollama', ['serve'], ROOT, 'Ollama');
  const ok = await waitForUrl(OLLAMA_URL, 30000, 1500);
  console.log(`[Ollama] Start result: ${ok}`);
  return ok;
}

// ── FastAPI Backend ───────────────────────────────────
async function startBackend() {
  console.log(`[Backend] Starting from: ${BACKEND_DIR}`);
  killPort(8002);

  // Find python executable
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

  spawnProc(
    pythonCmd,
    [
      '-m', 'uvicorn',
      'main:app',
      '--host', '0.0.0.0',
      '--port', '8002',
      '--reload',
    ],
    BACKEND_DIR,   // ← CWD is backend/ so main.py is found
    'Backend',
    {
      // Add backend dir to Python path explicitly
      PYTHONPATH: BACKEND_DIR,
    }
  );

  const ok = await waitForUrl(BACKEND_URL, 60000, 2000);
  console.log(`[Backend] Start result: ${ok}`);
  return ok;
}

// ── Frontend (Vite) ───────────────────────────────────
async function startFrontend() {
  console.log(`[Frontend] Starting Vite from: ${FRONTEND_DIR}`);
  killPort(5175);

  // BUG FIX: Do NOT use "npm run dev" — it picks up ROOT package.json
  // Instead: directly invoke vite executable
  const viteCmd   = process.platform === 'win32'
    ? path.join(FRONTEND_DIR, 'node_modules', '.bin', 'vite.cmd')
    : path.join(FRONTEND_DIR, 'node_modules', '.bin', 'vite');

  const fallback  = 'npx';
  const fallbackArgs = ['vite', '--host', '0.0.0.0', '--port', '5175'];

  // Try direct vite binary first
  const fs = require('fs');
  if (fs.existsSync(viteCmd)) {
    console.log('[Frontend] Using direct vite binary');
    const execPath = path.isAbsolute(viteCmd)
      ? path.relative(FRONTEND_DIR, viteCmd)
      : viteCmd;
    spawnProc(execPath, ['--host', '0.0.0.0', '--port', '5175'],
              FRONTEND_DIR, 'Frontend');
  } else {
    console.log('[Frontend] Vite binary not found, using npx vite');
    spawnProc(fallback, fallbackArgs, FRONTEND_DIR, 'Frontend');
  }

  const ok = await waitForUrl(FRONTEND_URL, 60000, 2000);
  console.log(`[Frontend] Start result: ${ok}`);
  return ok;
}

// ── Kill all on exit ──────────────────────────────────
function killAll() {
  console.log(`[ProcessManager] Killing ${processes.length} processes...`);
  for (const { proc, label } of processes) {
    try {
      if (!proc.killed && proc.pid) {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', String(proc.pid), '/f', '/t'],
                { shell: true, windowsHide: true });
        } else {
          proc.kill('SIGTERM');
        }
        console.log(`[${label}] Kill signal sent (pid ${proc.pid})`);
      }
    } catch (e) {
      console.error(`[${label}] Kill error: ${e.message}`);
    }
  }
  killPort(8002);
  killPort(5175);
}

module.exports = {
  startOllama,
  startBackend,
  startFrontend,
  killAll,
  FRONTEND_URL,
  BACKEND_URL,
};
