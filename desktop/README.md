# TeamLoop desktop app

Runs the crew's server in the background (no console window) and shows the app in its own window.
Closing the window keeps the crew working from the tray (Open, Stop all work, Start with Windows,
Quit). Quit stops the server. If the server crashes, it restarts by itself. Only one copy runs.
Approval cards show a tray notification and flash the window.

From a fresh clone (after the Python setup in the main README, and `npm run build` in `ui/`):

```
cd desktop
npm install
npm start                # run it
npm run dist             # build desktop/dist/TeamLoop.exe (portable, unsigned)
```

The app finds the repo by looking upward from where it runs, so keep `TeamLoop.exe` inside the
cloned folder (e.g. `desktop/dist/`), or set `TEAMLOOP_HOME` to the repo path. The server log is
in `%APPDATA%\TeamLoop\logs\server.log`.

No Electron? Double-click `start_teamloop.vbs` in the repo root (server hidden, opens the browser)
or `start_teamloop.bat` (server in a console window).
