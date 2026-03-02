from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def find_repo_root() -> Path:
    candidates: list[Path] = []
    cwd = Path.cwd().resolve()
    candidates.append(cwd)

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir, exe_dir.parent, exe_dir.parent.parent])
    else:
        script_dir = Path(__file__).resolve().parent
        candidates.extend([script_dir.parent, script_dir.parent.parent])

    for candidate in candidates:
        if (candidate / "app").exists() and (candidate / "web").exists():
            return candidate
    raise RuntimeError("Cannot locate project root (expected app/ and web/).")


def resolve_python() -> list[str]:
    python_bin = shutil.which("python")
    if python_bin:
        return [python_bin]
    py_launcher = shutil.which("py")
    if py_launcher:
        return [py_launcher, "-3"]
    raise RuntimeError("Python not found in PATH.")


def resolve_npm() -> str:
    npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
    if npm_bin:
        return npm_bin
    fallback = Path(r"C:\Program Files\nodejs\npm.cmd")
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("npm not found. Install Node.js LTS first.")


def ensure_web_env(root: Path) -> None:
    target = root / "web" / ".env.local"
    if target.exists():
        return
    source = root / "web" / ".env.local.example"
    if source.exists():
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_db(root: Path, python_cmd: list[str]) -> None:
    cmd = python_cmd + [
        "-c",
        (
            "import app.db.models; "
            "from app.db.base import Base; "
            "from app.db.session import engine; "
            "Base.metadata.create_all(bind=engine); "
            "print('db ready')"
        ),
    ]
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", "sqlite:///./app.db")
    env.setdefault("REDIS_URL", "redis://localhost:6379/0")
    subprocess.run(cmd, cwd=root, env=env, check=True)


def launch_backend(root: Path, python_cmd: list[str]) -> None:
    cmd = python_cmd + ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", "sqlite:///./app.db")
    env.setdefault("REDIS_URL", "redis://localhost:6379/0")
    subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def launch_frontend(root: Path, npm_cmd: str) -> None:
    env = os.environ.copy()
    node_dir = str(Path(npm_cmd).resolve().parent)
    env["Path"] = f"{node_dir};{env.get('Path', '')}"
    subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=root / "web",
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pokemon RP one-click launcher")
    parser.add_argument("--check", action="store_true", help="Check dependencies only")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser")
    parser.add_argument("--open-browser", action="store_true", help="Force open browser")
    return parser.parse_args()


def should_open_browser(args: argparse.Namespace) -> bool:
    if args.no_browser:
        return False
    if args.open_browser:
        return True
    env_value = os.getenv("RP_OPEN_BROWSER", "0").strip().lower()
    return env_value not in {"0", "false", "no", "off"}


def main() -> int:
    args = parse_args()
    root = find_repo_root()
    python_cmd = resolve_python()
    npm_cmd = resolve_npm()

    print(f"[ok] project root: {root}")
    print(f"[ok] python: {' '.join(python_cmd)}")
    print(f"[ok] npm: {npm_cmd}")

    ensure_web_env(root)
    if args.check:
        print("[ok] dependency check finished.")
        return 0

    ensure_db(root, python_cmd)
    launch_backend(root, python_cmd)
    launch_frontend(root, npm_cmd)
    print("[ok] backend and frontend started.")

    if should_open_browser(args):
        time.sleep(5)
        webbrowser.open("http://localhost:3000")
        print("[ok] browser opened: http://localhost:3000")
    else:
        print("[ok] browser auto-open is disabled (use --open-browser to enable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
