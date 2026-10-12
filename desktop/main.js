// TeamLoop desktop app: runs the crew's server in the background and shows the UI in its own window.
// Closing the window keeps the crew working from the tray; Quit stops the server.

const { app, BrowserWindow, Menu, Tray, globalShortcut, nativeImage, shell } = require("electron");
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
let restartTimer = null;

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

// Ctrl+Alt+Q from any app: stop every chat, so no bot keeps the mouse, the keyboard or a card going.
function registerStopAll() {
  const ok = globalShortcut.register("Control+Alt+Q", async () => {
    const body = await call("POST", `${BASE}/api/stop-all`);
    let stopped = 0;
    try { stopped = JSON.parse(body).stopped.length; } catch { /* server not answering */ }
    console.log(`Ctrl+Alt+Q: stop-all answered ${body || "nothing"}`);
    tray?.displayBalloon({
      title: "Stopped",
      content: body ? (stopped ? `Stopped ${stopped} chat${stopped === 1 ? "" : "s"}. Nothing else will move.` : "Nothing was running.")
                    : "TeamLoop isn't answering; close it from the tray to be sure.",
      iconType: body ? "info" : "warning",
    });
  });
  if (!ok) console.log("Ctrl+Alt+Q is taken by another app; Stop in each chat still works");
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
    restartTimer = setTimeout(() => {
      restartTimer = null;
      startServer();
    }, wait);
  });
}

// A server this app didn't start (one already running when it opened) has no exit event to watch,
// so check its health; after 3 misses in a row, start our own.
function watchHealth() {
  let misses = 0;
  setInterval(async () => {
    if (quitting || server || restartTimer) return (misses = 0);
    misses = (await get(`${BASE}/api/bots`)) ? 0 : misses + 1;
    if (misses >= 3) {
      misses = 0;
      console.log("the server stopped answering; starting our own");
      startServer();
    }
  }, 5000);
}

// Wait for the server; after 45 s show what's wrong and where the log is, keep trying, and go on as soon as it answers.
const SLOW_START_MS = 45_000;

async function waitForServer() {
  const started = Date.now();
  let shown = false;
  for (;;) {
    if (await get(`${BASE}/api/bots`)) return;
    if (!shown && Date.now() - started > SLOW_START_MS && win && !win.isDestroyed()) {
      shown = true;
      win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(slowStartPage())}`);
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

function slowStartPage() {
  const log = path.join(app.getPath("logs"), "server.log").replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return `<!doctype html><title>${TITLE}</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;
background:#090c18;color:#eceffa;font:16px system-ui;text-align:center;padding:24px"><div style="max-width:560px">
<div style="font-size:44px">🛠️</div><h2>TeamLoop's server hasn't started yet</h2>
<p style="color:#8e97bb">It's been more than 45 seconds. TeamLoop keeps trying and opens here by itself as soon as it
answers.</p><p style="color:#8e97bb">If it doesn't, the reason is in the server log:<br>
<code style="color:#eceffa;user-select:all">${log}</code></p></div>`;
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

// The logo comes with the UI: after every load of the app (start-up, and the reload an Update does) the window,
// taskbar button and tray take the icon the server has now, so a new logo shows without reinstalling.
function refreshIcon() {
  http.get(`${BASE}/app-icon.png?t=${Date.now()}`, (res) => {
    if (res.statusCode !== 200) return res.resume();
    const chunks = [];
    res.on("data", (c) => chunks.push(c));
    res.on("end", () => {
      const img = nativeImage.createFromBuffer(Buffer.concat(chunks));
      if (img.isEmpty()) return;
      win?.setIcon(img);
      tray?.setImage(img.resize({ width: 16, height: 16 }));
    });
  }).on("error", () => { /* keep the icon we have */ });
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
    minWidth: 900,  // below this the chat list and the chat stop fitting side by side
    minHeight: 640,
    icon: icon(),
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.on("page-title-updated", (e) => e.preventDefault());
  win.webContents.on("did-finish-load", () => {
    if (win.webContents.getURL().startsWith(BASE)) refreshIcon();
  });
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
    globalShortcut.unregisterAll();
    // the venv's pythonw is a launcher with the real server as its child: end the whole tree
    if (server) spawnSync("taskkill", ["/pid", String(server.pid), "/T", "/F"], { windowsHide: true });
  });

  app.whenReady().then(async () => {
    app.setAppUserModelId("TeamLoop");
    createWindow();
    createTray();
    registerStopAll();
    if (!ROOT) {
      win.loadURL(`data:text/html,<title>${TITLE}</title><p style="font:16px system-ui;padding:2em">Can't find the TeamLoop folder. Put the app inside the cloned repo, or set TEAMLOOP_HOME.</p>`);
      return;
    }
    if (!(await get(`${BASE}/api/bots`))) startServer(); // reuse a server that's already running
    await waitForServer();
    await win.loadURL(BASE);
    watchApprovals();
    watchHealth();
  });
}
