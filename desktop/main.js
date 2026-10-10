// TeamLoop desktop app: runs the crew's server in the background and shows the UI in its own window.
// Closing the window keeps the crew working from the tray; Quit stops the server.

const { app, BrowserWindow, Menu, Tray, nativeImage, shell } = require("electron");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const TITLE = "TeamLoop"; // bots never act on a window with this title, so keep it
const ROOT = findRoot();
const PORT = Number(process.env.TEAMLOOP_PORT || readEnv("TEAMLOOP_PORT") || 8790);
const BASE = `http://127.0.0.1:${PORT}`;

let win = null;
let tray = null;
let server = null;
let quitting = false;
let restarts = 0;

// ---- where the repo and Python are ----------------------------------------------------------------
function findRoot() {
  const starts = [process.env.TEAMLOOP_HOME, process.env.PORTABLE_EXECUTABLE_DIR, path.dirname(app.getPath("exe")), __dirname];
  for (const start of starts.filter(Boolean)) {
    for (let dir = path.resolve(start); ; dir = path.dirname(dir)) {
      if (fs.existsSync(path.join(dir, "teamloop", "__main__.py"))) return dir;
      if (path.dirname(dir) === dir) break;
    }
  }
  return null;
}

function readEnv(name) {
  try {
    const line = fs.readFileSync(path.join(ROOT, ".env"), "utf8").split(/\r?\n/).find((l) => l.startsWith(`${name}=`));
    return line ? line.slice(name.length + 1).trim() : null;
  } catch {
    return null;
  }
}

function python() {
  // python.exe, not pythonw: the venv's pythonw launcher drops the log output. windowsHide keeps the console hidden.
  const venv = path.join(ROOT, ".venv", "Scripts", "python.exe");
  return fs.existsSync(venv) ? venv : "python";
}

// ---- the server, restarted with backoff if it dies ------------------------------------------------
function get(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => req.destroy());
  });
}

function call(method, url) {
  return new Promise((resolve) => {
    const req = http.request(url, { method, headers: { "content-type": "application/json" } }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => resolve(body));
    });
    req.on("error", () => resolve(""));
    req.end("{}");
  });
}

function startServer() {
  const log = fs.openSync(path.join(app.getPath("logs"), "server.log"), "a");
  server = spawn(python(), ["-m", "teamloop"], { cwd: ROOT, windowsHide: true, stdio: ["ignore", log, log] });
  const started = Date.now();
  server.on("exit", (code) => {
    server = null;
    if (quitting) return;
    if (Date.now() - started > 60_000) restarts = 0; // it ran fine for a while: start the backoff over
    const wait = Math.min(30, 2 ** restarts++) * 1000;
    console.log(`server stopped (code ${code}); restarting in ${wait / 1000}s`);
    setTimeout(startServer, wait);
  });
}

async function waitForServer() {
  for (;;) {
    if (await get(`${BASE}/api/bots`)) return;
    await new Promise((r) => setTimeout(r, 500));
  }
}

// ---- approval cards -> desktop notifications ------------------------------------------------------
function watchApprovals() {
  const req = http.get(`${BASE}/api/events`, (res) => {
    let buffer = "";
    res.setEncoding("utf8");
    res.on("data", (chunk) => {
      buffer += chunk;
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const data = part.split("\n").find((l) => l.startsWith("data:"));
        if (!data) continue;
        try {
          const event = JSON.parse(data.slice(5));
          if (event.type === "approval") notify(event);
        } catch {
          /* a keep-alive or partial line */
        }
      }
    });
    res.on("end", () => setTimeout(watchApprovals, 2000));
  });
  req.on("error", () => setTimeout(watchApprovals, 2000));
}

function notify(event) {
  // A tray balloon, not a toast: Windows drops toasts from apps without a Start menu shortcut (portable .exe).
  const who = event.bot[0].toUpperCase() + event.bot.slice(1);
  console.log(`approval card ${event.id}: ${event.title}`);
  tray?.displayBalloon({ title: `${who} asks: ${event.title}`, content: event.details || "Approve or deny in TeamLoop.", iconType: "info" });
  if (win) {
    if (!win.isVisible()) win.showInactive(); // up on screen without taking the keyboard from the app a bot may be using
    win.flashFrame(true);
  }
}

// ---- window and tray ------------------------------------------------------------------------------
function icon() {
  return nativeImage.createFromPath(path.join(__dirname, "icon.png"));
}

function show() {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function createWindow() {
  win = new BrowserWindow({
    title: TITLE,
    width: 1100,
    height: 760,
    icon: icon(),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.on("page-title-updated", (e) => e.preventDefault());
  win.on("focus", () => win.flashFrame(false));
  win.on("close", (e) => {
    if (quitting) return;
    e.preventDefault(); // the crew keeps working from the tray
    win.hide();
  });
  // Links to other sites open in the normal browser, never inside the app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith(BASE)) {
      e.preventDefault();
      if (/^https?:/.test(url)) shell.openExternal(url);
    }
  });
  win.loadURL(`data:text/html,<title>${TITLE}</title><body style="font:16px system-ui;display:grid;place-items:center;height:90vh;color:%23555">Starting the crew…</body>`);
}

async function stopAll() {
  try {
    const chats = JSON.parse(await call("GET", `${BASE}/api/chats`));
    await Promise.all(chats.map((c) => call("POST", `${BASE}/api/chats/${c.id}/stop`)));
  } catch {
    /* server not up */
  }
}

function createTray() {
  tray = new Tray(icon().resize({ width: 16, height: 16 }));
  tray.setToolTip(TITLE);
  const menu = () =>
    Menu.buildFromTemplate([
      { label: "Open TeamLoop", click: show },
      { label: "Stop all work", click: stopAll },
      { type: "separator" },
      {
        label: "Start with Windows",
        type: "checkbox",
        checked: app.getLoginItemSettings().openAtLogin,
        click: (item) => {
          app.setLoginItemSettings({ openAtLogin: item.checked });
          tray.setContextMenu(menu());
        },
      },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]);
  tray.setContextMenu(menu());
  tray.on("click", show);
  tray.on("balloon-click", show);
}

// ---- start ----------------------------------------------------------------------------------------
if (!app.requestSingleInstanceLock()) {
  app.quit(); // a second launch: the first copy shows its window instead
} else {
  app.on("second-instance", show);
  app.on("window-all-closed", (e) => e.preventDefault());
  app.on("before-quit", () => {
    quitting = true;
    // the venv's pythonw is a launcher with the real server as its child: end the whole tree
    if (server) spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { windowsHide: true });
  });

  app.whenReady().then(async () => {
    app.setAppUserModelId("TeamLoop");
    createWindow();
    createTray();
    if (!ROOT) {
      win.loadURL(`data:text/html,<title>${TITLE}</title><p style="font:16px system-ui;padding:2em">Can't find the TeamLoop folder. Put the app inside the cloned repo, or set TEAMLOOP_HOME.</p>`);
      return;
    }
    if (!(await get(`${BASE}/api/bots`))) startServer(); // reuse a server that's already running
    await waitForServer();
    await win.loadURL(BASE);
    watchApprovals();
  });
}
