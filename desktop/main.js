const { app, BrowserWindow, dialog } = require("electron");
const { execSync, spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

let runtime = null;
let backendProc = null;
let frontendProc = null;
let fileEnvCache = null;
let mainWindow = null;

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
}

function resolveRuntime() {
  if (!app.isPackaged) {
    const repoRoot = path.resolve(__dirname, "..");
    return {
      mode: "dev",
      repoRoot,
      logsDir: path.join(repoRoot, "logs"),
      webRuntimeDir: path.join(repoRoot, "web"),
      backendExe: null,
      dbPath: path.join(repoRoot, "app.db"),
    };
  }

  const resourcesRoot = process.resourcesPath;
  const userData = app.getPath("userData");
  return {
    mode: "packaged",
    repoRoot: resourcesRoot,
    logsDir: path.join(userData, "logs"),
    webRuntimeDir: path.join(resourcesRoot, "web-runtime"),
    backendExe: path.join(resourcesRoot, "backend", "PokemonRP-Backend.exe"),
    dbPath: path.join(userData, "app.db"),
  };
}

function ensureLogsDir() {
  const logsDir = runtime ? runtime.logsDir : path.resolve(__dirname, "..", "logs");
  if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
  }
}

function fileStream(name) {
  ensureLogsDir();
  return fs.createWriteStream(path.join(runtime.logsDir, name), { flags: "a", encoding: "utf8" });
}

function now() {
  return new Date().toISOString();
}

function log(msg) {
  ensureLogsDir();
  const line = `${now()} ${msg}\n`;
  fs.appendFileSync(path.join(runtime.logsDir, "desktop-electron.log"), line, { encoding: "utf8" });
}

function pythonCmd() {
  if (process.env.PYTHON_PATH && process.env.PYTHON_PATH.trim()) {
    return process.env.PYTHON_PATH.trim();
  }
  return process.platform === "win32" ? "python" : "python3";
}

function parseDotEnv(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const out = {};
  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

function loadRuntimeEnv() {
  if (fileEnvCache) return fileEnvCache;
  if (runtime.mode === "packaged") {
    const envPath = path.join(path.dirname(process.execPath), ".env");
    fileEnvCache = parseDotEnv(envPath);
    return fileEnvCache;
  }
  fileEnvCache = parseDotEnv(path.join(runtime.repoRoot, ".env"));
  return fileEnvCache;
}

function defaultEnv() {
  const env = { ...process.env, ...loadRuntimeEnv() };
  const sqlitePath = runtime.dbPath.replace(/\\/g, "/");
  env.DATABASE_URL = env.DATABASE_URL || `sqlite:///${sqlitePath}`;
  env.REDIS_URL = env.REDIS_URL || "redis://localhost:6379/0";
  return env;
}

function runEnsureDb() {
  const code =
    "import app.db.models; from app.db.base import Base; from app.db.session import engine; Base.metadata.create_all(bind=engine); print('db ready')";
  const ret = spawnSync(pythonCmd(), ["-c", code], {
    cwd: runtime.repoRoot,
    env: defaultEnv(),
    encoding: "utf8",
  });
  if (ret.status !== 0) {
    throw new Error(`ensure db failed: ${ret.stderr || ret.stdout || ret.status}`);
  }
}

function spawnBackend() {
  const out = fileStream("backend.electron.stdout.log");
  const err = fileStream("backend.electron.stderr.log");

  let proc;
  if (runtime.mode === "packaged") {
    if (!fs.existsSync(runtime.backendExe)) {
      throw new Error(`backend exe not found: ${runtime.backendExe}`);
    }
    proc = spawn(runtime.backendExe, [], {
      cwd: path.dirname(runtime.backendExe),
      env: defaultEnv(),
      stdio: ["ignore", "pipe", "pipe"],
    });
  } else {
    proc = spawn(
      pythonCmd(),
      ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
      {
        cwd: runtime.repoRoot,
        env: defaultEnv(),
        stdio: ["ignore", "pipe", "pipe"],
      }
    );
  }

  proc.stdout.pipe(out);
  proc.stderr.pipe(err);
  proc.on("exit", (code) => log(`backend exited code=${code}`));
  log(`backend started pid=${proc.pid} mode=${runtime.mode}`);
  return proc;
}

function spawnFrontend() {
  const out = fileStream("frontend.electron.stdout.log");
  const err = fileStream("frontend.electron.stderr.log");

  let command;
  let args;
  let cwd;
  let env;

  if (runtime.mode === "packaged") {
    const standaloneServer = path.join(runtime.webRuntimeDir, "server.js");
    const nextCli = path.join(runtime.webRuntimeDir, "node_modules", "next", "dist", "bin", "next");

    if (fs.existsSync(standaloneServer)) {
      command = process.execPath;
      args = [standaloneServer];
      cwd = runtime.webRuntimeDir;
      env = {
        ...process.env,
        ELECTRON_RUN_AS_NODE: "1",
        NODE_ENV: "production",
        PORT: "3000",
        HOSTNAME: "127.0.0.1",
        NEXT_TELEMETRY_DISABLED: "1",
      };
    } else if (fs.existsSync(nextCli)) {
      command = process.execPath;
      args = [nextCli, "start", "-p", "3000", "-H", "127.0.0.1"];
      cwd = runtime.webRuntimeDir;
      env = {
        ...process.env,
        ELECTRON_RUN_AS_NODE: "1",
        NODE_ENV: "production",
      };
    } else {
      throw new Error(`frontend runtime not found: ${standaloneServer}`);
    }
  } else {
    command = process.platform === "win32" ? "cmd.exe" : "npm";
    args =
      process.platform === "win32"
        ? ["/d", "/s", "/c", "npm run dev -- --hostname 127.0.0.1 --port 3000"]
        : ["run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"];
    cwd = runtime.webRuntimeDir;
    env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE;
  }

  const proc = spawn(command, args, {
    cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  proc.stdout.pipe(out);
  proc.stderr.pipe(err);
  proc.on("exit", (code) => log(`frontend exited code=${code}`));
  log(`frontend started pid=${proc.pid} mode=${runtime.mode}`);
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
      const timer = setTimeout(() => controller.abort(), 2500);
      const resp = await fetch(url, { signal: controller.signal, cache: "no-store" });
      clearTimeout(timer);
      if (resp.status >= 200 && resp.status < 500) return;
    } catch (_err) {
      // retry
    }
    await sleep(600);
  }
  throw new Error(`wait timeout: ${url}`);
}

async function isHttpReady(url) {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    const resp = await fetch(url, { signal: controller.signal, cache: "no-store" });
    clearTimeout(timer);
    return resp.status >= 200 && resp.status < 500;
  } catch (_err) {
    return false;
  }
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

function getListeningPids(port) {
  try {
    if (process.platform !== "win32") return [];
    const raw = execSync(`netstat -ano | findstr :${port}`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    const pids = new Set();
    for (const line of raw.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.includes("LISTENING")) continue;
      const parts = trimmed.split(/\s+/);
      if (parts.length < 5) continue;
      const local = parts[1] || "";
      const pid = Number(parts[parts.length - 1]);
      if (!local.endsWith(`:${port}`) && !local.endsWith(`]:${port}`)) continue;
      if (Number.isFinite(pid) && pid > 0 && pid !== process.pid) {
        pids.add(pid);
      }
    }
    return Array.from(pids.values());
  } catch (_err) {
    return [];
  }
}

function killPortListeners(port, reason) {
  const pids = getListeningPids(port);
  for (const pid of pids) {
    try {
      if (process.platform === "win32") {
        spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        process.kill(pid, "SIGTERM");
      }
      log(`killed pid=${pid} port=${port} reason=${reason}`);
    } catch (_err) {
      // ignore
    }
  }
  return pids.length;
}

function cleanNextDevCache() {
  if (runtime.mode !== "dev") return;
  const nextDir = path.join(runtime.webRuntimeDir, ".next");
  if (!fs.existsSync(nextDir)) return;
  try {
    fs.rmSync(nextDir, { recursive: true, force: true });
    log(`cleared next cache dir=${nextDir}`);
  } catch (err) {
    log(`clear next cache failed: ${err instanceof Error ? err.message : String(err)}`);
  }
}

async function ensureServices() {
  const backendReady = await isHttpReady("http://127.0.0.1:8000/healthz");
  if (!backendReady) {
    const killed = killPortListeners(8000, "backend_unhealthy");
    if (killed > 0) {
      await sleep(800);
    }
  }
  if (runtime.mode === "dev" && !backendReady) {
    runEnsureDb();
  }

  if (!backendReady) {
    backendProc = spawnBackend();
  } else {
    log("backend already ready on :8000, reuse existing instance");
  }
  await waitHttp("http://127.0.0.1:8000/healthz", 120_000);

  const frontendBaseReady = await isHttpReady("http://127.0.0.1:3000/");
  const frontendAdventureReady = frontendBaseReady
    ? await isHttpReady("http://127.0.0.1:3000/adventure")
    : false;
  const frontendReady = frontendBaseReady && frontendAdventureReady;
  if (!frontendReady) {
    const killed = killPortListeners(3000, "frontend_unhealthy");
    if (killed > 0) {
      await sleep(1000);
    }
    cleanNextDevCache();
    frontendProc = spawnFrontend();
  } else {
    log("frontend already ready on :3000, reuse existing instance");
  }
  await waitHttp("http://127.0.0.1:3000/", 180_000);
  await waitHttp("http://127.0.0.1:3000/adventure", 120_000);
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

  win.loadURL("http://127.0.0.1:3000/adventure");
  mainWindow = win;
  win.on("closed", () => {
    if (mainWindow === win) {
      mainWindow = null;
    }
  });
}

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  killTree(frontendProc);
  killTree(backendProc);
});

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(async () => {
  try {
    runtime = resolveRuntime();
    ensureLogsDir();
    log(`runtime mode=${runtime.mode}`);
    await ensureServices();
    createMainWindow();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (runtime) {
      log(`startup failed: ${msg}`);
    }
    dialog.showErrorBox("Pokemon RP Desktop 启动失败", msg);
    killTree(frontendProc);
    killTree(backendProc);
    app.quit();
  }
});
