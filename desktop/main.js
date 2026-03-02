const { app, BrowserWindow, dialog } = require("electron");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const webDir = path.join(repoRoot, "web");
const logsDir = path.join(repoRoot, "logs");

let backendProc = null;
let frontendProc = null;

function ensureLogsDir() {
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
  }
}

function fileStream(name) {
  ensureLogsDir();
  return fs.createWriteStream(path.join(logsDir, name), { flags: "a", encoding: "utf8" });
}

function now() {
  return new Date().toISOString();
}

function log(msg) {
  ensureLogsDir();
  const line = `${now()} ${msg}\n`;
  fs.appendFileSync(path.join(logsDir, "desktop-electron.log"), line, { encoding: "utf8" });
}

function npmCmd() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function pythonCmd() {
  if (process.env.PYTHON_PATH && process.env.PYTHON_PATH.trim()) {
    return process.env.PYTHON_PATH.trim();
  }
  return process.platform === "win32" ? "python" : "python3";
}

function runEnsureDb() {
  const code =
    "import app.db.models; from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine); print('db ready')";
  const env = { ...process.env };
  env.DATABASE_URL = env.DATABASE_URL || "sqlite:///./app.db";
  env.REDIS_URL = env.REDIS_URL || "redis://localhost:6379/0";
  const ret = spawnSync(pythonCmd(), ["-c", code], {
    cwd: repoRoot,
    env,
    encoding: "utf8",
  });
  if (ret.status !== 0) {
    throw new Error(`ensure db failed: ${ret.stderr || ret.stdout || ret.status}`);
  }
}

function spawnBackend() {
  const env = { ...process.env };
  env.DATABASE_URL = env.DATABASE_URL || "sqlite:///./app.db";
  env.REDIS_URL = env.REDIS_URL || "redis://localhost:6379/0";
  const out = fileStream("backend.electron.stdout.log");
  const err = fileStream("backend.electron.stderr.log");
  const proc = spawn(
    pythonCmd(),
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    { cwd: repoRoot, env, stdio: ["ignore", "pipe", "pipe"] }
  );
  proc.stdout.pipe(out);
  proc.stderr.pipe(err);
  log(`backend started pid=${proc.pid}`);
  return proc;
}

function spawnFrontend() {
  const env = { ...process.env };
  const out = fileStream("frontend.electron.stdout.log");
  const err = fileStream("frontend.electron.stderr.log");
  const command = process.platform === "win32" ? "cmd.exe" : npmCmd();
  const args =
    process.platform === "win32" ? ["/d", "/s", "/c", "npm run dev"] : ["run", "dev"];
  const proc = spawn(command, args, {
    cwd: webDir,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  proc.stdout.pipe(out);
  proc.stderr.pipe(err);
  log(`frontend started pid=${proc.pid}`);
  return proc;
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitHttp(url, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), 2500);
      const resp = await fetch(url, { signal: controller.signal, cache: "no-store" });
      clearTimeout(t);
      if (resp.status >= 200 && resp.status < 500) return;
    } catch (_err) {
      // retry
    }
    await sleep(600);
  }
  throw new Error(`wait timeout: ${url}`);
}

function killTree(proc) {
  if (!proc || proc.killed) return;
  try {
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      proc.kill("SIGTERM");
    }
    log(`stopped pid=${proc.pid}`);
  } catch (_err) {
    // ignore
  }
}

async function ensureServices() {
  runEnsureDb();
  backendProc = spawnBackend();
  frontendProc = spawnFrontend();
  await waitHttp("http://127.0.0.1:8000/healthz", 90_000);
  await waitHttp("http://127.0.0.1:3000/login", 120_000);
  log("backend/frontend ready");
}

function createMainWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 920,
    minWidth: 1100,
    minHeight: 760,
    autoHideMenuBar: true,
    title: "Pokemon RP Desktop",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadURL("http://127.0.0.1:3000/login");
}

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  killTree(frontendProc);
  killTree(backendProc);
});

app.whenReady().then(async () => {
  try {
    await ensureServices();
    createMainWindow();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    log(`startup failed: ${msg}`);
    dialog.showErrorBox("Pokemon RP Desktop 启动失败", msg);
    killTree(frontendProc);
    killTree(backendProc);
    app.quit();
  }
});
