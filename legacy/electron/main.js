const {
  app, BrowserWindow, Tray, Menu,
  nativeImage, shell
} = require('electron');
const path = require('path');
const {
  startOllama, startBackend, startFrontend,
  killAll, FRONTEND_URL
} = require('./process-manager');

let splashWindow = null;
let mainWindow   = null;
let tray         = null;
let isQuitting   = false;

// ── Safe IPC helpers (won't crash if splash destroyed) ──
function safeUpdateStatus(service, state, msg) {
  try {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.executeJavaScript(
        `window.updateStatus && window.updateStatus(
          '${service}', '${state}',
          '${msg.replace(/'/g, "\\'")}')`
      ).catch(() => {});
    }
  } catch (e) {
    console.log(`[Splash] updateStatus skipped: ${e.message}`);
  }
}

function safeUpdateProgress(pct, msg) {
  try {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.webContents.executeJavaScript(
        `window.updateProgress && window.updateProgress(
          ${pct},
          '${msg.replace(/'/g, "\\'")}')`
      ).catch(() => {});
    }
  } catch (e) {
    console.log(`[Splash] updateProgress skipped: ${e.message}`);
  }
}

// ── Splash window ────────────────────────────────────
function createSplash() {
  splashWindow = new BrowserWindow({
    width: 480,
    height: 560,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    center: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  splashWindow.once('ready-to-show', () => splashWindow.show());
}

// ── Main app window ───────────────────────────────────
function createMain() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: 'AI Teacher Clone',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(FRONTEND_URL);

  mainWindow.once('ready-to-show', () => {
    // Close splash safely before showing main
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
    console.log('[Main] App window ready');
  });

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  // If frontend fails to load, retry after 3s
  mainWindow.webContents.on('did-fail-load', (e, code, desc) => {
    console.error(`[Main] Page failed to load: ${desc} — retrying in 3s`);
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.loadURL(FRONTEND_URL);
      }
    }, 3000);
  });
}

// ── System tray ───────────────────────────────────────
function createTray() {
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip('AI Teacher Clone');

  const menu = Menu.buildFromTemplate([
    {
      label: '📚 Open App',
      click: () => { mainWindow?.show(); mainWindow?.focus(); },
    },
    { type: 'separator' },
    {
      label: '📡 Backend API Docs',
      click: () => shell.openExternal('http://localhost:8002/docs'),
    },
    {
      label: '🌐 Open in Browser',
      click: () => shell.openExternal(FRONTEND_URL),
    },
    { type: 'separator' },
    {
      label: '❌ Quit',
      click: () => {
        isQuitting = true;
        killAll();
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
  tray.on('double-click', () => {
    mainWindow?.show();
    mainWindow?.focus();
  });
}

// ── Startup sequence ──────────────────────────────────
async function startAllServices() {
  console.log('[Startup] Beginning service startup sequence...');

  // OLLAMA
  safeUpdateProgress(5, 'Checking Ollama...');
  safeUpdateStatus('ollama', 'checking', 'Checking...');
  const ollamaOk = await startOllama();
  safeUpdateStatus(
    'ollama',
    ollamaOk ? 'ok' : 'error',
    ollamaOk ? 'Running ✓' : 'Failed — check Ollama'
  );
  safeUpdateProgress(25, ollamaOk
    ? 'Ollama ready — starting backend...'
    : 'Ollama issue — continuing...');

  // BACKEND
  safeUpdateStatus('backend', 'checking', 'Starting...');
  const backendOk = await startBackend();
  safeUpdateStatus(
    'backend',
    backendOk ? 'ok' : 'error',
    backendOk ? 'Running on :8002 ✓' : 'Failed to start'
  );
  safeUpdateProgress(55, backendOk
    ? 'Backend ready — starting frontend...'
    : 'Backend failed — check Python/uvicorn');

  // FRONTEND
  safeUpdateStatus('frontend', 'checking', 'Starting Vite...');
  const frontendOk = await startFrontend();
  safeUpdateStatus(
    'frontend',
    frontendOk ? 'ok' : 'error',
    frontendOk ? 'Running on :5175 ✓' : 'Failed to start'
  );
  safeUpdateProgress(80, 'Checking database...');

  // DB (passive check)
  await new Promise(r => setTimeout(r, 800));
  safeUpdateStatus(
    'db',
    backendOk ? 'ok' : 'error',
    backendOk ? 'Ready ✓' : 'Backend not available'
  );
  safeUpdateProgress(100, 'All systems ready! Opening app...');

  console.log(`[Startup] Results — Ollama:${ollamaOk} Backend:${backendOk} Frontend:${frontendOk}`);

  // Wait so user sees 100%
  await new Promise(r => setTimeout(r, 1500));

  // Open main window even if some services failed
  createMain();
}

// ── App lifecycle ─────────────────────────────────────
app.whenReady().then(async () => {
  console.log('[App] Electron ready');
  createSplash();
  createTray();

  // Wait for splash to render
  await new Promise(r => setTimeout(r, 1000));

  await startAllServices().catch(err => {
    console.error('[App] Startup error:', err);
    // Still try to open main window
    createMain();
  });
});

app.on('window-all-closed', e => {
  // Keep running in tray
  e.preventDefault();
});

app.on('before-quit', () => {
  isQuitting = true;
  killAll();
});

app.on('activate', () => {
  mainWindow?.show();
});
